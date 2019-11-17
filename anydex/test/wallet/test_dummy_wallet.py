from asyncio import Future

from anydex.test.base import AbstractServer
from anydex.test.util import timeout
from anydex.wallet.dummy_wallet import BaseDummyWallet, DummyWallet1, DummyWallet2
from anydex.wallet.wallet import InsufficientFunds


class TestDummyWallet(AbstractServer):

    async def setUp(self):
        super(TestDummyWallet, self).setUp()
        self.dummy_wallet = BaseDummyWallet()

    async def tearDown(self):
        await self.dummy_wallet.shutdown_task_manager()
        await super(TestDummyWallet, self).tearDown()

    def test_wallet_id(self):
        """
        Test the identifier of a dummy wallet
        """
        self.assertEqual(self.dummy_wallet.get_identifier(), 'DUM')
        self.assertEqual(DummyWallet1().get_identifier(), 'DUM1')
        self.assertEqual(DummyWallet2().get_identifier(), 'DUM2')

    def test_wallet_name(self):
        """
        Test the name of a dummy wallet
        """
        self.assertEqual(self.dummy_wallet.get_name(), 'Dummy')
        self.assertEqual(DummyWallet1().get_name(), 'Dummy 1')
        self.assertEqual(DummyWallet2().get_name(), 'Dummy 2')

    @timeout(10)
    def test_create_wallet(self):
        """
        Test the creation of a dummy wallet
        """
        return self.dummy_wallet.create_wallet()

    @timeout(10)
    async def test_get_balance(self):
        """
        Test fetching the balance of a dummy wallet
        """
        balance = await self.dummy_wallet.get_balance()
        self.assertIsInstance(balance, dict)

    @timeout(10)
    async def test_transfer(self):
        """
        Test the transfer of money from a dummy wallet
        """
        await self.dummy_wallet.transfer(self.dummy_wallet.balance - 1, None)
        transactions = await self.dummy_wallet.get_transactions()
        self.assertEqual(len(transactions), 1)

    @timeout(10)
    async def test_transfer_invalid(self):
        """
        Test whether transferring a too large amount of money from a dummy wallet raises an error
        """
        with self.assertRaises(InsufficientFunds):
            await self.dummy_wallet.transfer(self.dummy_wallet.balance + 1, None)

    @timeout(10)
    def test_monitor(self):
        """
        Test the monitor loop of a transaction wallet
        """
        self.dummy_wallet.MONITOR_DELAY = 1
        return self.dummy_wallet.monitor_transaction("3.0")

    @timeout(10)
    def test_monitor_instant(self):
        """
        Test an instant the monitor loop of a transaction wallet
        """
        self.dummy_wallet.MONITOR_DELAY = 0
        return self.dummy_wallet.monitor_transaction("3.0")

    def test_address(self):
        """
        Test the address of a dummy wallet
        """
        self.assertIsInstance(self.dummy_wallet.get_address(), str)

    @timeout(10)
    async def test_get_transaction(self):
        """
        Test the retrieval of transactions of a dummy wallet
        """
        transactions = await self.dummy_wallet.get_transactions()
        self.assertIsInstance(transactions, list)

    def test_min_unit(self):
        """
        Test the minimum unit of a dummy wallet
        """
        self.assertEqual(self.dummy_wallet.min_unit(), 1)

    def test_generate_txid(self):
        """
        Test the generation of a random transaction id
        """
        self.assertTrue(self.dummy_wallet.generate_txid(10))
        self.assertEqual(len(self.dummy_wallet.generate_txid(20)), 20)
