import os
import time
from abc import ABCMeta

from ipv8.util import fail, succeed
from sqlalchemy import func, or_
from web3 import Web3

from anydex.wallet.ethereum.eth_database import initialize_db, Key, Transaction
from anydex.wallet.ethereum.eth_provider import AutoEthereumProvider, AutoTestnetEthereumProvider
from anydex.wallet.wallet import Wallet, InsufficientFunds


class AbstractEthereumWallet(Wallet, metaclass=ABCMeta):
    """
    This class is responsible for handling the Ethereum wallet.
    """

    def __init__(self, db_path: str, testnet: bool, chain_id: int, provider):
        super(AbstractEthereumWallet, self).__init__()

        self.network = 'ethereum_testnet' if testnet else 'ethereum'
        self.wallet_name = f'tribler_{self.network}'
        self.testnet = testnet
        self.unlocked = True

        self.chain_id = chain_id
        self.min_confirmations = 0
        self.account = None
        self._session = initialize_db(os.path.join(db_path, 'eth.db'))

        if provider:
            self.provider = provider
        else:  # the testnet we are currently using is ropsten
            self.provider = AutoTestnetEthereumProvider() if testnet else AutoEthereumProvider()

        existing_wallet = self._session.query(Key).filter(Key.name == self.wallet_name).first()
        if existing_wallet:
            self.account = Web3().eth.account.from_key(existing_wallet.private_key)
            self.created = True

    def create_wallet(self):
        """
        If no account exists yet, create a new one.
        """
        if self.account:
            return fail(RuntimeError(f'Ethereum wallet with name {self.wallet_name} already exists'))

        self._logger.info('Creating Ethereum wallet with name %s', self.wallet_name)
        if not self.account:
            self.account = Web3().eth.account.create()
            self.created = True
            self._session.add(Key(name=self.wallet_name, private_key=self.account.key, address=self.account.address))
            self._session.commit()

        return succeed(None)

    def get_balance(self):
        if not self.account:
            return succeed({
                'available': 0,
                'pending': 0,
                'currency': self.get_identifier(),
                'precision': self.precision()
            })

        self._update_database(self.get_transactions())
        pending_outgoing = self.get_outgoing_amount()

        return succeed({
            'available': self.provider.get_balance(self.get_address().result()) - pending_outgoing,
            'pending': self.get_incoming_amount(),
            'currency': self.get_identifier(),
            'precision': self.precision()
        })

    def get_outgoing_amount(self):
        """
        Get the current amount of ethereum that we are sending, but is still unconfirmed.
        :return: pending outgoing amount
        """
        outgoing = self._session.query(func.sum(Transaction.value)).filter(Transaction.is_pending.is_(True)).filter(
            func.lower(Transaction.from_) == self.account.address.lower()).first()[0]
        return outgoing if outgoing else 0

    def get_incoming_amount(self):
        """
        Get the current amount of ethereum that is being sent to us, but is still unconfirmed.
        :return: pending incoming amount
        """
        incoming = self._session.query(func.sum(Transaction.value)).filter(Transaction.is_pending.is_(True)).filter(
            func.lower(Transaction.to) == self.account.address.lower()).first()[0]
        return incoming if incoming else 0

    async def transfer(self, amount, address) -> str:
        """
        Transfer Ethereum to another wallet.
        If the amount exceeds the available balance, an `InsufficientFunds` exception is raised.

        :param amount: the transfer amount
        :param address: the receiver address
        :return: transfer hash
        """
        balance = await self.get_balance()

        if balance['available'] < int(amount):
            raise InsufficientFunds('Insufficient funds')

        self._logger.info('Creating Ethereum payment with amount %f to address %s', amount, address)

        transaction = {
            'from': self.get_address().result(),
            'to': address,
            'value': int(amount),
            'nonce': self.get_transaction_count(),
            'gasPrice': self.provider.get_gas_price(),
            'chainId': self.chain_id
        }

        transaction['gas'] = self.provider.estimate_gas(transaction)
        # submit to blockchain
        signed = self.account.sign_transaction(transaction)
        self.provider.submit_transaction(signed['rawTransaction'].hex())

        # add transaction to database
        self._session.add(
            Transaction(
                from_=transaction['from'],
                to=transaction['to'],
                value=transaction['value'],
                gas=transaction['gas'],
                nonce=transaction['nonce'],
                gas_price=transaction['gasPrice'],
                hash=signed['hash'].hex(),
                is_pending=True
            )
        )
        self._session.commit()
        return signed['hash'].hex()

    def get_address(self):
        if not self.account:
            return succeed('')
        return succeed(self.account.address)

    def get_transactions(self):
        """
        Retrieve list of transactions from provider.

        :return: list of transactions
        """
        if not self.account:
            return succeed([])

        transactions = self.provider.get_transactions(self.get_address().result())

        self._update_database(transactions)
        # in the future we might use the provider to only retrieve transactions past a certain date/block

        transactions_db = self._session.query(Transaction).filter(
            or_(func.lower(Transaction.from_) == self.get_address().result().lower(),
                func.lower(Transaction.to) == self.get_address().result().lower()
                )).all()

        transactions_to_return = []
        latest_block_height = self.provider.get_latest_blocknr()
        for tx in transactions_db:
            confirmations = latest_block_height - tx.block_number + 1 if tx.block_number else 0
            transactions_to_return.append({
                'id': tx.hash,
                'outgoing': tx.from_.lower() == self.get_address().result().lower(),
                'from': tx.from_,
                'to': tx.to,
                'amount': tx.value,
                'fee_amount': tx.gas * tx.gas_price,
                'currency': self.get_identifier(),
                'timestamp': time.mktime(tx.date_time.timetuple()),
                'description': f'Confirmations: {confirmations}'
            })

        return succeed(transactions_to_return)

    def _update_database(self, transactions):
        """
        Update transactions in the database.
        Pending transactions that have been confirmed will be updated to have a block number and will no longer be
        pending.
        Other transactions that are not in the database will be added.

        :param transactions: list of transactions retrieved by self.provider
        """
        pending_transactions = self._session.query(Transaction).filter(Transaction.is_pending.is_(True)).all()
        confirmed_transactions = self._session.query(Transaction).filter(Transaction.is_pending.is_(False)).all()
        self._logger.debug('Updating ethereum database')
        for transaction in transactions:
            if transaction in pending_transactions:
                # update transaction set is_pending = false where hash = ''
                self._session.query(Transaction).filter(Transaction.hash == transaction.hash).update({
                    Transaction.is_pending: False,
                    Transaction.block_number: transaction.block_number
                })
            elif transaction not in confirmed_transactions:
                self._session.add(transaction)
        self._session.commit()

    def get_transaction_count(self):
        """
        Get the amount of transactions sent by this wallet
        """
        row = self._session.query(Transaction.nonce).filter(Transaction.from_ == self.get_address().result()).order_by(
            Transaction.nonce.desc()).first()
        if row:
            return row[0] + 1  # nonce + 1
        return 0

    def min_unit(self):
        return 1

    def precision(self):
        return 18


class EthereumWallet(AbstractEthereumWallet):
    def __init__(self, db_path, provider=None):
        super(EthereumWallet, self).__init__(db_path, False, 1, provider)

    def get_identifier(self):
        return 'ETH'

    def get_name(self):
        return 'ethereum'


class EthereumTestnetWallet(AbstractEthereumWallet):
    def __init__(self, db_path, provider=None):
        super(EthereumTestnetWallet, self).__init__(db_path, True, 3, provider)

    def get_identifier(self):
        return 'TETH'

    def get_name(self):
        return 'testnet ethereum'
