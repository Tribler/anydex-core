from asyncio import ensure_future
from urllib.parse import quote_plus

from aiohttp import ClientSession

from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from anydex.core.community import MarketCommunity
from anydex.restapi.rest_manager import RESTManager
from anydex.test.util import get_random_port
from anydex.wallet.dummy_wallet import DummyWallet1, DummyWallet2


def urlencode(data):
    # Convert all keys and values in the data to utf-8 unicode strings
    utf8_items = []
    for key, value in data.items():
        if isinstance(value, list):
            utf8_items.extend([urlencode_single(key, list_item) for list_item in value if value])
        else:
            utf8_items.append(urlencode_single(key, value))

    data = "&".join(utf8_items)
    return data.encode('utf-8')


def urlencode_single(key, value):
    utf8_key = quote_plus(str(key).encode('utf-8'))
    # Convert bool values to ints
    if isinstance(value, bool):
        value = int(value)
    utf8_value = quote_plus(str(value).encode('utf-8'))
    return "%s=%s" % (utf8_key, utf8_value)


class TestRestApiBase(TestBase):
    __testing__ = False
    NUM_NODES = 1

    def setUp(self):
        super(TestRestApiBase, self).setUp()

        self.expected_response_code = 200
        self.expected_response_json = None
        self.should_check_equality = True
        self.restapi = None

        self.initialize(MarketCommunity, self.NUM_NODES)
        for node in self.nodes:
            node.overlay._use_main_thread = True

    async def tearDown(self):
        await self.restapi.stop()
        await super(TestRestApiBase, self).tearDown()

    def create_node(self):
        dum1_wallet = DummyWallet1()
        dum2_wallet = DummyWallet2()
        dum1_wallet.MONITOR_DELAY = 0
        dum2_wallet.MONITOR_DELAY = 0

        wallets = {'DUM1': dum1_wallet, 'DUM2': dum2_wallet}

        mock_ipv8 = MockIPv8(u"curve25519", MarketCommunity, create_trustchain=True, create_dht=True,
                             is_matchmaker=True, wallets=wallets, use_database=False, working_directory=u":memory:")

        mock_ipv8.overlay.settings.single_trade = False
        mock_ipv8.overlay.clearing_policies = []
        mock_ipv8.overlays = [mock_ipv8.overlay]

        # Start REST API
        self.restapi = RESTManager(mock_ipv8)
        random_port = get_random_port()
        ensure_future(self.restapi.start(random_port))

        return mock_ipv8

    async def do_request(self, endpoint, expected_code=200, expected_json=None,
                         request_type='GET', post_data=None, json_response=True):
        self.expected_response_code = expected_code
        self.expected_response_json = expected_json

        url = 'http://localhost:%d/%s' % (self.restapi.port, endpoint)
        headers = {'User-Agent': 'AnyDex'}

        async with ClientSession() as session:
            async with session.request(request_type, url, data=post_data, headers=headers) as response:
                status = response.status
                response = await response.json(content_type=None) if json_response else await response.read()

        self.assertEqual(status, self.expected_response_code)
        if status not in (200, 400, 500):
            return

        if response is not None and self.should_check_equality:
            self.assertDictEqual(self.expected_response_json, response)
        return response
