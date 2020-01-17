from ipv8.util import fail, succeed

from sqlalchemy.orm import session as db_session

from anydex.test.restapi.base import TestRestApiBase
from anydex.test.util import timeout


class TestWalletsEndpoint(TestRestApiBase):

    def setUp(self):
        super(TestWalletsEndpoint, self).setUp()

        from anydex.wallet.btc_wallet import BitcoinWallet, BitcoinTestnetWallet
        wallet_path = self.temporary_directory()
        btc_wallet = BitcoinWallet(wallet_path)
        btc_testnet_wallet = BitcoinTestnetWallet(wallet_path)

        self.nodes[0].overlay.wallets[btc_wallet.get_identifier()] = btc_wallet
        self.nodes[0].overlay.wallets[btc_testnet_wallet.get_identifier()] = btc_testnet_wallet

    async def tearDown(self):
        # Close all bitcoinlib Wallet DB sessions if exists
        db_session.close_all_sessions()

        await super(TestWalletsEndpoint, self).tearDown()

    @timeout(20)
    async def test_get_wallets(self):
        """
        Testing whether the API returns wallets when we query for them
        """
        self.should_check_equality = False
        json_response = await self.do_request('wallets', expected_code=200)
        self.assertIn('wallets', json_response)
        self.assertGreaterEqual(len(json_response['wallets']), 4)

    @timeout(20)
    async def test_create_wallet_exists(self):
        """
        Testing whether creating a wallet that already exists throws an error
        """
        self.should_check_equality = False
        await self.do_request('wallets/DUM1', expected_code=400, request_type='PUT')

    @timeout(20)
    async def test_create_wallet_btc(self):
        """
        Test creating a BTC wallet
        """
        self.nodes[0].overlay.wallets['BTC'].create_wallet = lambda: succeed(None)
        self.should_check_equality = False
        await self.do_request('wallets/BTC', expected_code=200, request_type='PUT')

    @timeout(20)
    async def test_create_wallet(self):
        """
        Testing whether we can create a wallet
        """
        self.nodes[0].overlay.wallets['DUM1'].created = False
        self.should_check_equality = False
        await self.do_request('wallets/DUM1', expected_code=200, request_type='PUT')

    @timeout(20)
    async def test_create_wallet_btc_error(self):
        """
        Testing whether an error during the creation of a BTC wallet is correctly handled
        """
        self.should_check_equality = False

        await self.do_request('wallets/BTC', expected_code=200, request_type='PUT')
        self.nodes[0].overlay.wallets['BTC'].created = False
        await self.do_request('wallets/BTC', expected_code=500, request_type='PUT')

    @timeout(20)
    async def test_get_wallet_balance(self):
        """
        Testing whether we can retrieve the balance of a wallet
        """
        self.should_check_equality = False
        json_response = await self.do_request('wallets/DUM1/balance', expected_code=200)
        self.assertIn('balance', json_response)
        self.assertGreater(json_response['balance']['available'], 0)

    @timeout(20)
    async def test_get_wallet_transaction(self):
        """
        Testing whether we can receive the transactions of a wallet
        """
        self.should_check_equality = False
        json_response = await self.do_request('wallets/DUM1/transactions', expected_code=200)
        self.assertIn('transactions', json_response)

    @timeout(20)
    async def test_transfer_no_btc(self):
        """
        Test transferring assets from a non-BTC wallet
        """
        self.should_check_equality = False
        await self.do_request('wallets/DUM1/transfer', expected_code=400, request_type='POST')

    @timeout(20)
    async def test_transfer_not_created(self):
        """
        Test transferring assets from a non-created BTC wallet
        """
        self.should_check_equality = False
        await self.do_request('wallets/BTC/transfer', expected_code=400, request_type='POST')

    @timeout(20)
    async def test_transfer_bad_params(self):
        """
        Test transferring assets when providing wrong parameters
        """
        self.nodes[0].overlay.wallets['BTC'].created = True
        self.should_check_equality = False
        await self.do_request('wallets/BTC/transfer', expected_code=400, request_type='POST')

    @timeout(20)
    async def test_transfer_error(self):
        """
        Test whether we receive the right response when we try a transfer that errors
        """
        self.nodes[0].overlay.wallets['BTC'].transfer = lambda *_: fail(RuntimeError("error"))
        self.nodes[0].overlay.wallets['BTC'].created = True
        self.should_check_equality = False
        post_data = {'amount': 3, 'destination': 'abc'}
        await self.do_request('wallets/BTC/transfer', expected_code=500, request_type='POST', post_data=post_data)

    @timeout(20)
    async def test_transfer(self):
        """
        Test transferring assets
        """
        self.nodes[0].overlay.wallets['BTC'].created = True
        self.nodes[0].overlay.wallets['BTC'].transfer = lambda *_: succeed('abcd')
        self.should_check_equality = False
        post_data = {'amount': 3, 'destination': 'abc'}
        await self.do_request('wallets/BTC/transfer', expected_code=200, request_type='POST', post_data=post_data)
