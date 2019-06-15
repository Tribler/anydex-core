from __future__ import absolute_import
from __future__ import division

import os
import signal
import sys

import anydex  # To set the IPv8 path

from autobahn.twisted import WebSocketServerFactory

from ipv8.attestation.trustchain.community import TrustChainTestnetCommunity
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.peerdiscovery.discovery import RandomWalk

from ipv8_service import IPv8

from twisted.application.service import IServiceMaker, MultiService
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg

from zope.interface import implementer

from anydex.config import get_anydex_configuration
from anydex.core.community import MarketTestnetCommunity
from anydex.restapi.rest_manager import RESTManager
from anydex.restapi.websocket import AnyDexWebsocketProtocol
from anydex.wallet.dummy_wallet import DummyWallet1, DummyWallet2


class Options(usage.Options):
    optParameters = [
        ["statedir", "s", ".", "Use an alternate statedir", str],
        ["apiport", "p", 8085, "Use an alternative port for the REST api", int],
    ]
    optFlags = [
        ["no-rest-api", "a", "Autonomous: disable the REST api"],
        ["no-matchmaker", "--no-matchmaker", "disable matchmaker functionality"],
        ["statistics", "s", "Enable IPv8 overlay statistics"],
        ["testnet", "t", "Join the testnet"],
    ]


@implementer(IPlugin, IServiceMaker)
class AnyDexServiceMaker(object):
    tapname = "anydex"
    description = "AnyDex plugin"
    options = Options

    def __init__(self):
        """
        Initialize the variables of the AnyDexServiceMaker and the logger.
        """
        self.ipv8 = None
        self.restapi = None
        self.trustchain = None
        self.dht = None
        self.market = None
        self.wallets = {}
        self._stopping = False

    def start_anydex(self, options):
        """
        Main method to startup AnyDex.
        """
        config = get_anydex_configuration()

        if options["statedir"]:
            # If we use a custom state directory, update various variables
            for key in config["keys"]:
                key["file"] = os.path.join(options["statedir"], key["file"])

            for community in config["overlays"]:
                if community["class"] == "TrustChainCommunity":
                    community["initialize"]["working_directory"] = options["statedir"]

        if 'testnet' in options and options['testnet']:
            for community in config["overlays"]:
                if community["class"] == "TrustChainCommunity":
                    community["class"] = "TrustChainTestnetCommunity"

        self.ipv8 = IPv8(config, enable_statistics=options['statistics'])

        def signal_handler(sig, _):
            msg("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                if self.restapi:
                    self.restapi.stop()
                self.ipv8.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        msg("Starting AnyDex")

        if not options['no-rest-api']:
            self.restapi = RESTManager(self.ipv8)
            reactor.callLater(0.0, self.restapi.start, options['apiport'])

            factory = WebSocketServerFactory(u"ws://127.0.0.1:9000")
            factory.protocol = AnyDexWebsocketProtocol
            reactor.listenTCP(9000, factory)

        # Get Trustchain + DHT overlays
        for overlay in self.ipv8.overlays:
            if isinstance(overlay, TrustChainTestnetCommunity):
                self.trustchain = overlay
            elif isinstance(overlay, DHTDiscoveryCommunity):
                self.dht = overlay

        # Initialize wallets
        dummy_wallet1 = DummyWallet1()
        self.wallets[dummy_wallet1.get_identifier()] = dummy_wallet1

        dummy_wallet2 = DummyWallet2()
        self.wallets[dummy_wallet2.get_identifier()] = dummy_wallet2

        # Load market community
        self.market = MarketTestnetCommunity(self.trustchain.my_peer, self.ipv8.endpoint, self.ipv8.network,
                                             trustchain=self.trustchain,
                                             dht=self.dht,
                                             wallets=self.wallets,
                                             working_directory=options["statedir"],
                                             record_transactions=False,
                                             is_matchmaker=not options["no-matchmaker"])

        self.ipv8.overlays.append(self.market)
        self.ipv8.strategies.append((RandomWalk(self.market), 20))

    def makeService(self, options):
        """
        Construct a IPv8 service.
        """
        ipv8_service = MultiService()
        ipv8_service.setName("AnyDex")

        reactor.callWhenRunning(self.start_anydex, options)

        return ipv8_service


if __name__ == '__main__':

    options = Options()
    Options.parseOptions(options, sys.argv[1:])
    AnyDexServiceMaker().makeService(options)
    reactor.run()
