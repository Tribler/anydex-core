from __future__ import absolute_import


from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from six import text_type
from six.moves.urllib_parse import quote_plus

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web.client import Agent, HTTPConnectionPool, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer

from zope.interface import implementer

import anydex.util.json_util as json
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
    utf8_key = quote_plus(text_type(key).encode('utf-8'))
    # Convert bool values to ints
    if isinstance(value, bool):
        value = int(value)
    utf8_value = quote_plus(text_type(value).encode('utf-8'))
    return "%s=%s" % (utf8_key, utf8_value)


@implementer(IBodyProducer)
class POSTDataProducer(object):
    """
    This class is used for posting data by the requests made during the tests.
    """
    def __init__(self, data_dict, raw_data):
        self.body = {}
        if data_dict and not raw_data:
            self.body = urlencode(data_dict)
        elif raw_data:
            self.body = raw_data.encode('utf-8')
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def stopProducing(self):
        return succeed(None)


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

        self.connection_pool = HTTPConnectionPool(reactor, False)

    @inlineCallbacks
    def tearDown(self):
        yield self.close_connections()
        yield self.restapi.stop()
        yield super(TestRestApiBase, self).tearDown()

    def close_connections(self):
        return self.connection_pool.closeCachedConnections()

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
        self.restapi.start(random_port)

        return mock_ipv8

    def parse_body(self, body):
        if body is not None and self.should_check_equality:
            self.assertDictEqual(self.expected_response_json, json.twisted_loads(body))
        return body

    def parse_response(self, response):
        self.assertEqual(response.code, self.expected_response_code)
        if response.code in (200, 400, 500):
            return readBody(response)
        return succeed(None)

    def do_request(self, endpoint, expected_code=200, expected_json=None,
                   request_type='GET', post_data='', raw_data=False):
        self.expected_response_code = expected_code
        self.expected_response_json = expected_json

        try:
            request_type = request_type.encode('ascii')
            endpoint = endpoint.encode('ascii')
        except AttributeError:
            pass
        agent = Agent(reactor, pool=self.connection_pool)
        request = agent.request(request_type, b'http://localhost:%d/%s' % (self.restapi.port, endpoint),
                             Headers({'User-Agent': ['AnyDex'],
                                      "Content-Type": ["text/plain; charset=utf-8"]}),
                             POSTDataProducer(post_data, raw_data))

        return request.addCallback(self.parse_response).addCallback(self.parse_body)
