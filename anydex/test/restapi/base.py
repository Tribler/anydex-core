from anydex.core.community import MarketCommunity
from anydex.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from anydex.restapi.root_endpoint import RootEndpoint

from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.test.REST.rest_base import RESTTestBase, MockRestIPv8, partial_cls
from ipv8.REST.rest_manager import RESTManager


class MarketRESTTestBase(RESTTestBase):
    NUM_NODES = 1

    async def setUp(self):
        super(MarketRESTTestBase, self).setUp()
        await self.initialize([partial_cls(TrustChainCommunity, working_directory=':memory:'),
                               partial_cls(MarketCommunity, working_directory=':memory:')], 1)

        self.market_community = self.nodes[0].get_overlay(MarketCommunity)
        self.market_community.trustchain = self.nodes[0].get_overlay(TrustChainCommunity)

    async def create_node(self, *args, **kwargs):
        ipv8 = MockRestIPv8(u"curve25519", overlay_classes=self.overlay_classes, *args, **kwargs)
        self.rest_manager = RESTManager(ipv8, root_endpoint_class=RootEndpoint)
        ipv8.rest_manager = self.rest_manager
        await self.rest_manager.start(0)
        ipv8.rest_port = self.rest_manager.site._server.sockets[0].getsockname()[1]

        dum1_wallet = DummyWallet1()
        dum2_wallet = DummyWallet2()
        dum1_wallet.MONITOR_DELAY = 0
        dum2_wallet.MONITOR_DELAY = 0

        wallets = {'DUM1': dum1_wallet, 'DUM2': dum2_wallet}

        market_community = ipv8.get_overlay(MarketCommunity)
        market_community.wallets = wallets
        market_community.settings.single_trade = False
        market_community.clearing_policies = []

        return ipv8
