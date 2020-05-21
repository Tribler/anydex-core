import datetime

from ipv8.util import succeed

from sqlalchemy.orm import session as db_session

from anydex.test.base import AbstractServer
from anydex.test.util import timeout, MockObject
from anydex.wallet.abstract_bitcoinlib_wallet import BitcoinlibWallet
from anydex.wallet.bitcoinlib_wallet import BitcoinTestnetWallet, BitcoinWallet, LitecoinWallet, \
    LitecoinTestnetWallet, DashTestnetWallet, DashWallet


def get_info(wallet: BitcoinlibWallet):
    return {
        BitcoinTestnetWallet: ['Bitcoin Test Network 3', 'testnet', 'TBTC'],
        LitecoinTestnetWallet: ['Litecoin Test Network', 'litecoin_testnet', 'XLT'],
        DashTestnetWallet: ['Dash Testnet Network', 'dash_testnet', 'tDASH'],
        BitcoinWallet: ['Bitcoin', 'bitcoin', 'BTC'],
        LitecoinWallet: ['Litecoin Network', 'litecoin', 'LTC'],
        DashWallet: ['Dash Network', 'dash', 'DASH']
    }[wallet.__class__]


def get_params(wallet: BitcoinlibWallet):
    return {
        BitcoinTestnetWallet: [
            '02000000014bca66ebc0e3ab0c5c3aec6d0b3895b968497397752977dfd4a2f0bc67db6810000000006b4830450221' +
            '00fc93a034db310fbfead113283da95e980ac7d867c7aa4e6ef0aba80ef321639e02202bc7bd7b821413d814d9f7d6' +
            'fc76ff46b9cd3493173ef8d5fac40bce77a7016d01210309702ce2d5258eacc958e5a925b14de912a23c6478b8e2fb' +
            '82af43d2021214f3feffffff029c4e7020000000001976a914d0115029aa5b2d2db7afb54a6c773ad536d0916c88ac' +
            '90f4f700000000001976a914f0eabff37e597b930647a3ec5e9df2e0fed0ae9888ac108b1500',
            'n3Uogo82Tyy76ZNuxmFfhJiFqAUbJ5BPho', 16250000],
        LitecoinTestnetWallet: [
            '01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff0403b96715ff' +
            'ffffff02506b04950000000016001467e66503f183a5e7cb4e179217d09463d180d7880000000000000000266a24aa' +
            '21a9ed38217b1b23eff4cf102287c6a9e54533148d4ef0765992132f799de26a03658200000000',
            'tltc1qvlnx2ql3swj70j6wz7fp05y5v0gcp4ugz7zten', 2500094800],
        DashTestnetWallet: [
            '020000000163090d6e9c93897c212cd24566ed54900e0eb258c6fe13e7c1e670bdb27a75c0010000006a4730440220' +
            '1634a753eb3004f9aee520911011904312da846535404dad9ed89ebcfbef79e902201d11a41569e472e0dd5afbab18' +
            '580c950d34b851364777a4d5049c333513d01c012102b673d690baa81a3e88ce40f85fa4c16027d4dfa019aa7eeaa1' +
            '4768e56ae985a1ffffffff014b0daf03000000001976a9140624ea2a0176642a1a9d16154364297143dc21e788ac00' +
            '000000',
            'yLsw8ESinrp5sSHZ9JEbzYME6EcNwBy4HE', 61803851],
        BitcoinWallet: [
            '02000000014bca66ebc0e3ab0c5c3aec6d0b3895b968497397752977dfd4a2f0bc67db6810000000006b4830450221' +
            '00fc93a034db310fbfead113283da95e980ac7d867c7aa4e6ef0aba80ef321639e02202bc7bd7b821413d814d9f7d6' +
            'fc76ff46b9cd3493173ef8d5fac40bce77a7016d01210309702ce2d5258eacc958e5a925b14de912a23c6478b8e2fb' +
            '82af43d2021214f3feffffff029c4e7020000000001976a914d0115029aa5b2d2db7afb54a6c773ad536d0916c88ac' +
            '90f4f700000000001976a914f0eabff37e597b930647a3ec5e9df2e0fed0ae9888ac108b1500',
            '1NxrPk33exXrKSuJFCHHsPVvyAstSg4S7s', 16250000],
        LitecoinWallet: [
            '020000000001047b95e486a4c85541db0743d85022849f05bbb57f3e7dc4ea981a2c5a9622a9f70000000017160014' +
            '66f5596df480f9b8aeb5460293a9782780abc6f2feffffff8e66a70a3a2dbaadc9952db44c34bf01f4dc7156243d42' +
            '696b5eff0fb91ef9370000000017160014afbb70f52f3ee8238278478a9844914735afbc86feffffff1b1036b4810b' +
            'd144985c774fd52c413437dbcfc3f9e82652e3833f121bbc35e9010000001716001401ba33a4bc8c1a89886282a559' +
            '1ae30d85cbc469feffffffa485a616781bdd79e223b2351b2aca2801e8a56539a1b1f011cb593e2845bcb600000000' +
            '17160014d46f44356f6a07412f40312b7cdddd5efcf45fc5feffffff03e8b5dc070000000017a914327928c42e1d41' +
            'c0a47ad9f109bbbcdcab29bc288700372f08000000001976a9143dde321d764f12366ea779eea7f644604e6822d588' +
            'ac208c37030000000017a914ab81c277a3a8c4835f4508e2dfec4cf4e8ae68ab8702473044022026103da513151a49' +
            '0a47b7faaeb6c0560c2c8fd962d206c4b4d7a89884c9480e02205cdf572d09175cab95ffaeb8c59bbd1ab1fd632ba4' +
            '5d07dbdeec1a93b367d877012102084797fc56939e64e1aef1eac9d1b6356a32f4696cc6389c14adb5551007cf6202' +
            '46304302201e182404e10460c2539eb691b19cdd7fa7ea66dd527c0adb9d3b32ff13b53de9021f71247ec10632c88c' +
            '16ed0ad687e1eb8796d60a06a322417aa5c5464d9edcba0121029e065c10c4ccd434d6f95a3030196ac4cd8c45d8db' +
            'cb0c3686cc8fee4bfdb3e50247304402205f773cbbe7aea6dee3548fd1fac34b6c0d85fbd2946467e69b547ac3f605' +
            '94420220015078d0fa241fc1355b977bb5781fcebce1e7edca6ea3b9277c71d3f7e0e601012103166aff7643ff4768' +
            '26b33add5e315ec0fc3fb17a99db8a19c57374e79afb2fa802473044022043b05f6fa3e4f1a81c147195ac468cdfef' +
            'a54ef04d2c0f986c75bfa4831983e902207fcb4051468710a17c273f0587a06dd435959c28f06027b73a426368b74d' +
            'afa501210381a710e414fcdebb096bd9f0a60d3f47f75339906520bbeae7a0e6bafaa7b73dcd201c00',
            'MPY1E6E3NALnzX3H3kKEftLpDSEWsdpu2g', 53972000],
        DashWallet: [
            '0200000001e2497d3c50e9d01287fe0c26f98bed6f29386a494ae7ce4b96523e9d9b7f46ad0b0000006b4830450221' +
            '00b57918729e2dadada334ae8b4bad232baae56f451b340247c965351740fed04a022056ba6fb0dfe2b3e892fe2ce5' +
            'b773064e3e6448a398c12a813ddc233e8c5321170121025637a83cde416c534086a8c30cf364def2601d6275df44c9' +
            '4249ed750cf5b10dfeffffff07aa530000000000001976a9145f1d5c344a7839187b1b90897fc36c59c429b63b88ac' +
            'a1860100000000001976a9140602fe0aa62b3687eaf23d09536a5ad15a90813888aca1860100000000001976a9141a' +
            '8d918ab028a1e676b6469f02a4208954edc48388aca1860100000000001976a914580a888e9f78d75a48374300325e' +
            '7ffb267e11fc88aca1860100000000001976a9146019b9bd9884aca97e5def7ebdc3e1653782b07888aca186010000' +
            '0000001976a9146896dcf3df5ff673864349b33410112cf7becb8e88aca1860100000000001976a914f04d17fb16a9' +
            '291d792ba35443d6835f0c2f769088ac306c1300',
            'XxbSMrZBhsRxNfB45pHBohhdaVxsMM8dy3', 100001],
    }[wallet.__class__]


class TestWallet(AbstractServer):
    """
    Tests the functionality of bitcoinlib wallets.
    """
    WALLET_UNDER_TEST = BitcoinWallet

    def setUp(self):
        super(TestWallet, self).setUp()
        self.wallet = self.WALLET_UNDER_TEST(self.session_base_dir)

        info = get_info(wallet=self.wallet)
        self.network_name = info[0]
        self.network = info[1]
        self.network_currency = info[2]
        self.min_unit = 100000
        self.precision = 8
        self.testnet = 'testnet' in self.network

        params = get_params(wallet=self.wallet)
        self.raw_tx = params[0]
        self.address = params[1]
        self.amount = params[2]

    async def tearDown(self):
        # Close all bitcoinlib Wallet DB sessions
        db_session.close_all_sessions()
        await super(TestWallet, self).tearDown()

    def new_wallet(self):
        return self.WALLET_UNDER_TEST(self.session_base_dir)

    def test_wallet_name(self):
        """
        Test the name of a wallet
        """
        self.assertEqual(self.wallet.get_name(), self.network_name)

    def test_wallet_identifier(self):
        """
        Test the identifier of a wallet
        """
        self.assertEqual(self.wallet.get_identifier(), self.network_currency)

    def test_wallet_address(self):
        """
        Test the address of a wallet
        """
        self.assertEqual(self.wallet.get_address(), '')

    def test_wallet_unit(self):
        """
        Test the minimum unit of a wallet
        """
        self.assertEqual(self.wallet.min_unit(), self.min_unit)

    async def test_balance_no_wallet(self):
        """
        Test the retrieval of the balance of a wallet that is not created yet
        """
        balance = await self.wallet.get_balance()
        self.assertEqual(balance,
                         {'available': 0, 'pending': 0, 'currency': self.network_currency,
                          'precision': self.precision})

    def test_get_testnet(self):
        """
        Tests whether the wallet is testnet or concrete
        """
        self.assertEqual(self.testnet, self.wallet.is_testnet())

    @timeout(10)
    async def test_wallet_creation(self):
        """
        Test the creating, opening, transactions and balance query of a wallet
        """
        wallet = self.new_wallet()

        await wallet.create_wallet()
        self.assertIsNotNone(wallet.wallet)
        self.assertTrue(wallet.get_address())

        _ = BitcoinTestnetWallet(self.session_base_dir)
        self.assertRaises(Exception, BitcoinTestnetWallet, self.session_base_dir, testnet=True)

        wallet.wallet.utxos_update = lambda **_: None  # We don't want to do an actual HTTP request here
        wallet.wallet.balance = lambda **_: 3
        balance = await wallet.get_balance()

        self.assertDictEqual(balance, {'available': 3, 'pending': 0,
                                       'currency': self.network_currency, 'precision': self.precision})
        wallet.wallet.transactions_update = lambda **_: None  # We don't want to do an actual HTTP request here
        transactions = await wallet.get_transactions()
        self.assertFalse(transactions)

        wallet.get_transactions = lambda: succeed([{"id": "abc"}])
        await wallet.monitor_transaction("abc")

    @timeout(10)
    async def test_correct_transfer(self):
        """
        Test that the transfer method of a wallet works
        """
        wallet = self.new_wallet()
        await wallet.create_wallet()
        wallet.get_balance = lambda: succeed({'available': 100000, 'pending': 0,
                                              'currency': self.network_currency, 'precision': self.precision})
        mock_tx = MockObject()
        mock_tx.hash = 'a' * 20
        wallet.wallet.send_to = lambda *_: mock_tx
        await wallet.transfer(3000, '2N8hwP1WmJrFF5QWABn38y63uYLhnJYJYTF')

    @timeout(10)
    async def test_create_error(self):
        """
        Test whether an error during wallet creation is handled
        """
        wallet = self.new_wallet()
        await wallet.create_wallet()  # This should work
        with self.assertRaises(Exception):
            await wallet.create_wallet()

    @timeout(10)
    async def test_transfer_no_funds(self):
        """
        Test that the transfer method of a wallet raises an error when we don't have enough funds
        """
        wallet = self.new_wallet()
        await wallet.create_wallet()
        wallet.wallet.utxos_update = lambda **_: None  # We don't want to do an actual HTTP request here
        with self.assertRaises(Exception):
            await wallet.transfer(3000, '2N8hwP1WmJrFF5QWABn38y63uYLhnJYJYTF')

    @timeout(10)
    async def test_get_transactions(self):
        """
        Test whether transactions in bitcoinlib are correctly returned
        """
        wallet = self.new_wallet()
        mock_wallet = MockObject()
        mock_wallet.transactions_update = lambda **_: None
        mock_wallet._session = MockObject()

        mock_all = MockObject()
        mock_all.all = lambda *_: [(self.raw_tx, 3, datetime.datetime(2012, 9, 16, 0, 0), 12345)]
        mock_filter = MockObject()
        mock_filter.filter = lambda *_: mock_all
        mock_wallet._session.query = lambda *_: mock_filter
        wallet.wallet = mock_wallet
        wallet.wallet.wallet_id = 3

        mock_key = MockObject()
        mock_key.address = self.address
        wallet.wallet.keys = lambda **_: [mock_key]
        wallet.created = True

        transactions = await wallet.get_transactions()
        self.assertTrue(transactions)
        self.assertEqual(transactions[0]["fee_amount"], 12345)
        self.assertEqual(transactions[0]["amount"], self.amount)


class TestDashWallet(TestWallet):
    """
    Test concrete Dash wallet implementation.
    """
    WALLET_UNDER_TEST = DashWallet
    # TODO: input/output common address bug


class TestLitecoinWallet(TestWallet):
    """
    Test concrete Litecoin wallet implementation.
    """
    WALLET_UNDER_TEST = LitecoinWallet


class TestBitcoinTestnetWallet(TestWallet):
    """
    Test testnet Bitcoin wallet implementation.
    """
    WALLET_UNDER_TEST = BitcoinTestnetWallet


class TestLitecoinTestnetWallet(TestLitecoinWallet):
    """
    Test testnet Litecoin wallet implementation.
    """
    WALLET_UNDER_TEST = LitecoinTestnetWallet


class TestDashTestnetWallet(TestDashWallet):
    """
    Test testnet Dash wallet implementation.
    """
    WALLET_UNDER_TEST = DashTestnetWallet
