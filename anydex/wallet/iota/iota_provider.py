import abc
from datetime import datetime

from iota import AsyncIota, ProposedTransaction

from anydex.wallet.provider import Provider


class IotaProvider(Provider, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def initialize_api(self, node, seed):
        """
        Initialize an API instance
        :param node: node to which API should connect
        :param seed: seed to use for all further API calls
        :return: initialized API
        """

    @abc.abstractmethod
    def submit_transaction(self, tx: ProposedTransaction):
        """
        Submit a proposed transaction to the network
        :param tx: the proposed transaction to submit to the network
        :return: the bundle containing the transaction
        """

    @abc.abstractmethod
    def get_balance(self, address):
        """
        Get the balance of the given address
        :param address: address whose balance is being retrieved
        :return: the balance
        """

    @abc.abstractmethod
    def get_seed_balance(self):
        """
        Get the balance of the given seed
        :return: the balance
        """

    @abc.abstractmethod
    def get_seed_transactions(self):
        """
        Retrieve all the transactions associated with the given seed
        :return: a list of all fetched transactions
        """

    @abc.abstractmethod
    def get_all_bundles(self):
        """
        Retrieve all the bundles associated with the seed
        :return: a list of all fetched bundles
        """

    @abc.abstractmethod
    def generate_address(self, index):
        """
        Get the newly generated address
        :param index: index from which start fetching a non-spent address
        :return: the new unspent address
        """

    @abc.abstractmethod
    def is_spent(self, address):
        """
        Check whether an address is spent
        :param address: address to check whether spent
        :return: boolean
        """

    @abc.abstractmethod
    def get_confirmations(self, tx_hash):
        """
        Check whether transactions are confirmed
        :param tx_hash: transaction to check whether confirmed
        :return: boolean
        """


class PyOTAIotaProvider(IotaProvider):
    """
    PyOTA provider for interaction with an IOTA ledger.
    """

    def __init__(self, testnet=True, node=None, seed=None):
        super().__init__()
        self.testnet = testnet
        self.async_api = self.initialize_api(node, seed)
        self.account_data = None
        self.last_update = None
        self.update_interval = 5

    def initialize_api(self, node, seed):
        if node is None:
            if self.testnet:
                node = 'https://nodes.comnet.thetangle.org:443'
            else:
                node = 'https://nodes.thetangle.org:443'

        async_api = AsyncIota(adapter=node, seed=seed, devnet=self.testnet)
        return async_api

    async def update_account_data(self):

        diff = datetime.now() - self.last_update if self.last_update else None

        if diff is None or diff.total_seconds() > float(self.update_interval):
            self.account_data = await self.async_api.get_account_data()
            self.last_update = datetime.now()

    async def submit_transaction(self, tx: ProposedTransaction):
        response = await self.async_api.send_transfer(transfers=[tx],
                                                      min_weight_magnitude=10)
        return response['bundle']

    async def get_balance(self, address):
        response = await self.async_api.get_balances(addresses=[address])
        return response['balances'][0]

    async def get_seed_balance(self):
        await self.update_account_data()
        return self.account_data['balance']

    async def get_transactions(self, address):
        """
        Retrieve all the transactions associated with the given address
        :param address: address whose transactions are being retrieved
        :return: a list of all fetched transactions
        """
        transactions = await self.async_api.find_transaction_objects(addresses=[address])
        return transactions

    async def get_seed_transactions(self):
        # fetch transactions from wallet_addresses from account_data
        await self.update_account_data()
        wallet_addresses = self.account_data['addresses']
        transactions = await self.async_api.find_transaction_objects(addresses=wallet_addresses)
        return transactions['transactions']

    async def get_all_bundles(self):
        await self.update_account_data()
        return self.account_data['bundles']

    async def generate_address(self, index):
        new_addresses = await self.async_api.get_new_addresses(index=index, count=1, security_level=2)
        return new_addresses['addresses'][0]

    async def is_spent(self, address):
        response = await self.async_api.were_addresses_spent_from([address])
        return response['states'][0]

    async def get_confirmations(self, tx_hash):
        response = await self.async_api.get_inclusion_states([tx_hash], None)
        return response['states'][0]
