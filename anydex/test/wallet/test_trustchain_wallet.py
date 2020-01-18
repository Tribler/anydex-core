from binascii import hexlify

from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from anydex.test.util import timeout
from anydex.wallet.tc_wallet import TrustchainWallet
from anydex.wallet.wallet import InsufficientFunds


class TestTrustchainWallet(TestBase):

    def setUp(self):
        super(TestTrustchainWallet, self).setUp()
        self.initialize(TrustChainCommunity, 2)
        self.tc_wallet = TrustchainWallet(self.nodes[0].overlay)
        self.tc_wallet.MONITOR_DELAY = 0.01
        self.tc_wallet.check_negative_balance = True

    async def tearDown(self):
        await self.tc_wallet.shutdown_task_manager()
        await super(TestTrustchainWallet, self).tearDown()

    def create_node(self):
        return MockIPv8(u"curve25519", TrustChainCommunity, working_directory=u":memory:")

    def test_get_mc_wallet_name(self):
        """
        Test the identifier of the Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.get_name(), 'Tokens (MB)')

    def test_get_mc_wallet_id(self):
        """
        Test the identifier of a Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.get_identifier(), 'MB')

    @timeout(2)
    async def test_get_balance(self):
        """
        Test the balance retrieval of a Trustchain wallet
        """
        await self.introduce_nodes()

        balance = await self.tc_wallet.get_balance()
        self.assertEqual(balance['available'], 0)

        his_pubkey = list(self.nodes[0].network.verified_peers)[0].public_key.key_to_bin()
        tx = {
            b'up': 20 * 1024 * 1024,
            b'down': 5 * 1024 * 1024,
            b'total_up': 20 * 1024 * 1024,
            b'total_down': 5 * 1024 * 1024
        }
        self.nodes[0].overlay.sign_block(list(self.nodes[0].network.verified_peers)[0], public_key=his_pubkey,
                                         block_type=b'tribler_bandwidth', transaction=tx)

        await self.deliver_messages()

        balance = await self.tc_wallet.get_balance()
        self.assertEqual(balance['available'], 15)

    def test_create_wallet(self):
        """
        Test whether creating a Trustchain wallet raises an error
        """
        self.assertRaises(RuntimeError, self.tc_wallet.create_wallet)

    async def test_transfer_invalid(self):
        """
        Test the transfer method of a Trustchain wallet
        """
        with self.assertRaises(InsufficientFunds):
            await self.tc_wallet.transfer(200, None)

    async def test_monitor_transaction(self):
        """
        Test the monitoring of a transaction in a Trustchain wallet
        """
        his_pubkey = self.nodes[0].overlay.my_peer.public_key.key_to_bin()

        tx_future = self.tc_wallet.monitor_transaction('%s.1' % hexlify(his_pubkey).decode('utf-8'))

        # Now create the transaction
        transaction = {
            b'up': 20 * 1024 * 1024,
            b'down': 5 * 1024 * 1024,
            b'total_up': 20 * 1024 * 1024,
            b'total_down': 5 * 1024 * 1024
        }
        await self.nodes[1].overlay.sign_block(list(self.nodes[1].network.verified_peers)[0], public_key=his_pubkey,
                                         block_type=b'tribler_bandwidth', transaction=transaction)

        await tx_future

    @timeout(2)
    async def test_monitor_tx_existing(self):
        """
        Test monitoring a transaction that already exists
        """
        transaction = {
            b'up': 20 * 1024 * 1024,
            b'down': 5 * 1024 * 1024,
            b'total_up': 20 * 1024 * 1024,
            b'total_down': 5 * 1024 * 1024
        }
        his_pubkey = self.nodes[0].overlay.my_peer.public_key.key_to_bin()
        await self.nodes[1].overlay.sign_block(list(self.nodes[1].network.verified_peers)[0], public_key=his_pubkey,
                                               block_type=b'tribler_bandwidth', transaction=transaction)
        await self.tc_wallet.monitor_transaction('%s.1' % hexlify(his_pubkey).decode('utf-8'))

    def test_address(self):
        """
        Test the address of a Trustchain wallet
        """
        self.assertTrue(self.tc_wallet.get_address())

    async def test_get_transaction(self):
        """
        Test the retrieval of transactions of a Trustchain wallet
        """
        transactions = await self.tc_wallet.get_transactions()
        self.assertIsInstance(transactions, list)

    def test_min_unit(self):
        """
        Test the minimum unit of a Trustchain wallet
        """
        self.assertEqual(self.tc_wallet.min_unit(), 1)

    async def test_get_statistics(self):
        """
        Test fetching statistics from a Trustchain wallet
        """
        self.tc_wallet.check_negative_balance = False
        res = self.tc_wallet.get_statistics()
        self.assertEqual(res["total_blocks"], 0)
        await self.tc_wallet.transfer(5, self.nodes[1].overlay.my_peer)
        res = self.tc_wallet.get_statistics()
        self.assertEqual(0, res["total_up"])
        self.assertEqual(5 * 1024 * 1024, res["total_down"])
