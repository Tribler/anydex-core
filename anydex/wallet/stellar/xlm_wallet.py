import abc
import os
import time
from asyncio import Future
from decimal import Decimal

from ipv8.util import fail, succeed
from stellar_sdk import Keypair, TransactionBuilder, Account, Network

from anydex.wallet.cryptocurrency import Cryptocurrency
from anydex.wallet.stellar.xlm_db import Transaction, StellarDb
from anydex.wallet.stellar.xlm_provider import StellarProvider
from anydex.wallet.wallet import Wallet, InsufficientFunds


class AbstractStellarWallet(Wallet, metaclass=abc.ABCMeta):
    """
    Wallet that provides support for the native Stellar token; lumen.
    """

    def __init__(self, db_path, testnet=False, provider: StellarProvider = None):

        super().__init__()
        self.testnet = testnet
        self.provider = provider
        self.network = 'testnet' if self.testnet else Cryptocurrency.STELLAR.value
        self.unlocked = True
        self.stellar_db = StellarDb(os.path.join(db_path, 'stellar.db'))
        self.wallet_name = 'stellar_tribler_testnet' if self.testnet else 'stellar_tribler'
        self.created_on_network = False  # Stellar accounts need to be explicitly created

        secret = self.stellar_db.get_wallet_secret(self.wallet_name)
        if secret:
            self.keypair = Keypair.from_secret(secret)
            self.created = True
            sequence_nr = 0
            if self.provider.check_account_created(self.get_address()):
                self.created_on_network = True
                sequence_nr = self.get_sequence_number()
            self.account = Account(self.get_address(), sequence_nr)

    @abc.abstractmethod
    def get_identifier(self):
        return

    @abc.abstractmethod
    def get_name(self):
        return

    def create_wallet(self):
        if self.created:
            return fail(RuntimeError(f'Stellar wallet with name {self.wallet_name} already exists'))

        self._logger.info('Creating Stellar wallet with name %s', self.wallet_name)
        keypair = Keypair.random()
        self.keypair = keypair
        self.created = True
        self.account = Account(self.get_address(), 0)
        self.created_on_network = False
        self.stellar_db.add_secret(self.wallet_name, keypair.secret, keypair.public_key)

        return succeed(None)

    def check_and_update_created_on_network(self):
        """
        Check if the account has been created on the stellar network and update it accordingly.
        """
        if self.created_on_network:
            return
        if self.provider.check_account_created(self.get_address()):
            self.created_on_network = True

    def get_balance(self):
        self.check_and_update_created_on_network()
        if not self.created_on_network:
            return succeed({
                'available': 0,
                'pending': 0,
                'currency': self.get_identifier(),
                'precision': self.precision()
            })
        xlm_balance = int(float(self.provider.get_balance(
            address=self.get_address())) * self.stroop_in_lumen())  # balance is not in smallest denomination
        pending_outgoing = self.stellar_db.get_outgoing_amount(self.get_address())
        balance = {
            'available': xlm_balance - pending_outgoing,
            'pending': 0,  # transactions are confirmed every 5 secs, so is this worth doing?
            'currency': self.get_identifier(),
            'precision': self.precision()
        }
        return succeed(balance)

    def get_sequence_number(self):
        """
        Use either the database or the api to find the sequence number.
        If using the database fails we then use the provider.

        :return: sequence number of this wallet.
        """
        sequence_nr_db = self.stellar_db.get_sequence_number(self.get_address())
        return sequence_nr_db if sequence_nr_db else self.provider.get_account_sequence(
            self.get_address())

    async def transfer(self, amount, address, memo_id: int = None, asset='XLM'):
        """
        Transfer stellar lumens to the specified address.
        In the future sending other assets might also be possible.

        Normally a payment operation is used, but if the account is not created
        then an account create operation will be done.

        if you wish to send all of your balance then a merge account operation is used.

        :param amount: amount of lumens to send, in stroop (0.0000001 XLM)
        :param address: address to sent lumens to. Should be a normal encoded public key.
        :param memo_id: memo id for sending lumens to exchanges.
        :param asset: asset type. only XLM is currently supported.
        :return: Transaction hash
        """
        balance = await self.get_balance()
        fee = self.provider.get_base_fee()  # fee for one operation
        if balance['available'] - 1 < int(amount) + fee:  # stellar accounts need to hold a minimum of 1 XLM
            raise InsufficientFunds('Insufficient funds')

        self._logger.info('Creating Stellar Lumens payment with amount %s to address %s', amount, address)
        network = Network.PUBLIC_NETWORK_PASSPHRASE if not self.testnet else Network.TESTNET_NETWORK_PASSPHRASE
        tx_builder = TransactionBuilder(
            source_account=self.account,
            base_fee=self.provider.get_base_fee(),
            network_passphrase=network,
        )
        amount_in_xlm = Decimal(amount / self.stroop_in_lumen())  # amount in xlm instead of stroop (0.0000001 xlm)
        if self.provider.check_account_created(address):
            tx_builder.append_payment_op(address, amount_in_xlm, asset)
        else:
            tx_builder.append_create_account_op(address, amount_in_xlm)
        if memo_id:
            tx_builder.add_id_memo(memo_id)
        tx = tx_builder.build()
        tx.sign(self.keypair)
        xdr_tx_envelope = tx.to_xdr()

        tx_hash = self.provider.submit_transaction(xdr_tx_envelope)
        tx_db = Transaction(hash=tx_hash,
                            source_account=self.get_address(),
                            operation_count=len(tx.transaction.operations),
                            sequence_number=tx.transaction.sequence,
                            succeeded=False,
                            transaction_envelope=xdr_tx_envelope,
                            is_pending=True,
                            fee=tx.transaction.fee,
                            )
        self.stellar_db.insert_transaction(tx_db)
        return tx_hash

    def get_address(self):
        if not self.created:
            return ''
        return self.keypair.public_key

    def get_transactions(self):
        """
        Transactions in stellar is different from etheruem or bitcoin.
        A payment in stellar is the same as a transactions in ethereum or bitcoin.
        Even though this method is called get_transactions (for compat with the wallet api) it returns the `payments`
        related to this wallet.
        :return: list of payments related to the wallet.
        """
        self.check_and_update_created_on_network()
        if not self.created_on_network:
            return succeed([])

        transactions = self.provider.get_transactions(self.get_address())

        self.stellar_db.update_db(transactions)

        # list of tuples with payment and transaction

        latest_ledger_height = self.provider.get_ledger_height()
        payments_to_return = []
        payments = self.stellar_db.get_payments_and_transactions(self.get_address())
        for payment in payments:
            confirmations = latest_ledger_height - payment[1].ledger_nr + 1 if payment[1].ledger_nr else 0
            payments_to_return.append({
                'id': payment[1].hash,  # use tx hash for now
                'outgoing': payment[0].from_ == self.get_address(),
                'from': payment[0].from_,
                'to': payment[0].to,
                'amount': payment[0].amount,
                'fee_amount': payment[1].fee,
                'currency': self.get_identifier(),
                'timestamp': time.mktime(payment[1].date_time.timetuple()),
                'description': f'confirmations: {confirmations}'
            })

        return succeed(payments_to_return)

    def min_unit(self):
        return self.stroop_in_lumen()  # if the minimum unit is too low we get float precision problems

    def precision(self):
        return 7

    def monitor_transaction(self, txid):
        monitor_future = Future()

        async def monitor():
            transactions = await self.get_transactions()
            for transaction in transactions:
                if transaction['id'] == txid:
                    self._logger.debug("Found transaction with id %s", txid)
                    monitor_future.set_result(None)
                    monitor_task.cancel()

        self._logger.debug("Start polling for transaction %s", txid)
        monitor_task = self.register_task(f"{self.network}_poll_{txid}", monitor, interval=5)

        return monitor_future

    def stroop_in_lumen(self):
        """
        Get the amount of stroop in one lumen
        """
        return 1e7

    def merge_account(self, address):
        """
        Delete the wallet and send all funds to the specified address
        :param address: address to send funds to
        :return: tx hash
        """
        self.check_and_update_created_on_network()
        if not self.created_on_network:
            return fail(RuntimeError('Cannot do account merge operation: account is not created on network'))
        self._logger.info('Deleting wallet and sending all funds to address %s', address)
        network = Network.PUBLIC_NETWORK_PASSPHRASE if not self.testnet else Network.TESTNET_NETWORK_PASSPHRASE
        tx = TransactionBuilder(
            source_account=self.account,
            base_fee=self.provider.get_base_fee(),
            network_passphrase=network,
        ).append_account_merge_op(address).build()

        tx.sign(self.keypair)
        xdr_tx_envelope = tx.to_xdr()

        tx_hash = self.provider.submit_transaction(xdr_tx_envelope)
        self.created_on_network = False
        return succeed(tx_hash)


class StellarWallet(AbstractStellarWallet):

    def __init__(self, db_path, provider: StellarProvider = None):
        super().__init__(db_path, False, provider)

    def get_name(self):
        return Cryptocurrency.STELLAR.value

    def get_identifier(self):
        return 'XLM'


class StellarTestnetWallet(AbstractStellarWallet):
    def __init__(self, db_path, provider: StellarProvider = None):
        super().__init__(db_path, True, provider)

    def get_name(self):
        return f'testnet {Cryptocurrency.STELLAR.value}'

    def get_identifier(self):
        return 'TXLM'
