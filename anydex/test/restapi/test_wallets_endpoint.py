from ipv8.util import fail, succeed

from sqlalchemy.orm import session as db_session

from anydex.test.restapi.base import MarketRESTTestBase
from anydex.test.util import timeout


class TestWalletsEndpoint(MarketRESTTestBase):

    async def setUp(self):
        await super(TestWalletsEndpoint, self).setUp()

        from anydex.wallet.btc_wallet import BitcoinWallet, BitcoinTestnetWallet
        wallet_path = self.temporary_directory()
        btc_wallet = BitcoinWallet(wallet_path)
        btc_testnet_wallet = BitcoinTestnetWallet(wallet_path)

        self.market_community.wallets[btc_wallet.get_identifier()] = btc_wallet
        self.market_community.wallets[btc_testnet_wallet.get_identifier()] = btc_testnet_wallet

    async def tearDown(self):
        # Close all bitcoinlib Wallet DB sessions if exists
        db_session.close_all_sessions()

        await super(TestWalletsEndpoint, self).tearDown()

    @timeout(20)
    async def test_get_wallets(self):
        """
        Testing whether the API returns wallets when we query for them
        """
        json_response = await self.make_request(self.nodes[0], 'wallets', 'GET')
        self.assertIn('wallets', json_response)
        self.assertGreaterEqual(len(json_response['wallets']), 4)

    @timeout(20)
    async def test_create_wallet_exists(self):
        """
        Testing whether creating a wallet that already exists throws an error
        """
        await self.make_request(self.nodes[0], 'wallets/DUM1', 'PUT', expected_status=400)

    @timeout(20)
    async def test_create_wallet_btc(self):
        """
        Test creating a BTC wallet
        """
        self.market_community.wallets['BTC'].create_wallet = lambda: succeed(None)
        await self.make_request(self.nodes[0], 'wallets/BTC', 'PUT')

    @timeout(20)
    async def test_create_wallet(self):
        """
        Testing whether we can create a wallet
        """
        self.market_community.wallets['DUM1'].created = False
        await self.make_request(self.nodes[0], 'wallets/DUM1', 'PUT')

    @timeout(20)
    async def test_create_wallet_btc_error(self):
        """
        Testing whether an error during the creation of a BTC wallet is correctly handled
        """
        await self.make_request(self.nodes[0], 'wallets/BTC', 'PUT')
        self.market_community.wallets['BTC'].created = False
        await self.make_request(self.nodes[0], 'wallets/BTC', 'PUT', expected_status=500)

    @timeout(20)
    async def test_get_wallet_balance(self):
        """
        Testing whether we can retrieve the balance of a wallet
        """
        json_response = await self.make_request(self.nodes[0], 'wallets/DUM1/balance', 'GET')
        self.assertIn('balance', json_response)
        self.assertGreater(json_response['balance']['available'], 0)

    @timeout(20)
    async def test_get_wallet_transaction(self):
        """
        Testing whether we can receive the transactions of a wallet
        """
        json_response = await self.make_request(self.nodes[0], 'wallets/DUM1/transactions', 'GET')
        self.assertIn('transactions', json_response)

    @timeout(20)
    async def test_transfer_no_btc(self):
        """
        Test transferring assets from a non-BTC wallet
        """
        await self.make_request(self.nodes[0], 'wallets/DUM1/transfer', 'POST', expected_status=400, json={})

    @timeout(20)
    async def test_transfer_not_created(self):
        """
        Test transferring assets from a non-created BTC wallet
        """
        await self.make_request(self.nodes[0], 'wallets/BTC/transfer', 'POST', expected_status=400, json={})

    @timeout(20)
    async def test_transfer_bad_params(self):
        """
        Test transferring assets when providing wrong parameters
        """
        self.market_community.wallets['BTC'].created = True
        await self.make_request(self.nodes[0], 'wallets/BTC/transfer', 'POST', expected_status=400, json={})

    @timeout(20)
    async def test_transfer_error(self):
        """
        Test whether we receive the right response when we try a transfer that errors
        """
        self.market_community.wallets['BTC'].transfer = lambda *_: fail(RuntimeError("error"))
        self.market_community.wallets['BTC'].created = True
        post_data = {'amount': 3, 'destination': 'abc'}
        await self.make_request(self.nodes[0], 'wallets/BTC/transfer', 'POST', expected_status=500, json=post_data)

    @timeout(20)
    async def test_transfer(self):
        """
        Test transferring assets
        """
        self.market_community.wallets['BTC'].created = True
        self.market_community.wallets['BTC'].transfer = lambda *_: succeed('abcd')
        post_data = {'amount': 3, 'destination': 'abc'}
        await self.make_request(self.nodes[0], 'wallets/BTC/transfer', 'POST', json=post_data)
