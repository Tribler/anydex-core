import os
import time
from abc import ABCMeta
from asyncio import Future

from ipv8.util import fail, succeed
from web3 import Web3

from anydex.wallet.ethereum.eth_database import Transaction, EthereumDb
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
        self.database = EthereumDb(os.path.join(db_path, 'eth.db'))

        if provider:
            self.provider = provider
        else:  # the testnet we are currently using is ropsten
            self.provider = AutoTestnetEthereumProvider() if testnet else AutoEthereumProvider()

        existing_key = self.database.get_wallet_private_key(self.wallet_name)
        if existing_key:
            self.account = Web3().eth.account.from_key(existing_key)
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
            self.database.add_key(self.wallet_name, self.account.key, self.account.address)

        return succeed(None)

    def get_balance(self):
        if not self.account:
            return succeed({
                'available': 0,
                'pending': 0,
                'currency': self.get_identifier(),
                'precision': self.precision()
            })

        self.get_transactions()
        pending_outgoing = self.database.get_outgoing_amount(self.get_address().result(), self.get_identifier())

        return succeed({
            'available': self.provider.get_balance(self.get_address().result()) - pending_outgoing,
            'pending': self.database.get_incoming_amount(self.get_address().result(), self.get_identifier()),
            'currency': self.get_identifier(),
            'precision': self.precision()
        })

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
            'to': Web3.toChecksumAddress(address),  # addresses should be checksumaddresses to work
            'value': int(amount),
            'nonce': self.database.get_transaction_count(self.get_address().result()),
            'gasPrice': self.provider.get_gas_price(),
            'chainId': self.chain_id
        }

        transaction['gas'] = self.provider.estimate_gas()
        # submit to blockchain
        signed = self.account.sign_transaction(transaction)
        self.provider.submit_transaction(signed['rawTransaction'].hex())

        # add transaction to database
        self.database.add(
            Transaction(
                from_=transaction['from'],
                to=transaction['to'],
                value=transaction['value'],
                gas=transaction['gas'],
                nonce=transaction['nonce'],
                gas_price=transaction['gasPrice'],
                hash=signed['hash'].hex(),
                is_pending=True,
                token_identifier=self.get_identifier()
            )
        )
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

        self.database.update_database(transactions, self.get_identifier())
        # in the future we might use the provider to only retrieve transactions past a certain date/block

        transactions_db = self.database.get_transactions(self.get_address().result(), self.get_identifier())

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

    def min_unit(self):
        # TODO determine minimal transfer unit
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
