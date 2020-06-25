import argparse
import os
import signal
import sys
from asyncio import ensure_future, get_event_loop, sleep

from ipv8.attestation.trustchain.community import TrustChainCommunity, TrustChainTestnetCommunity  # noqa
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.peerdiscovery.discovery import RandomWalk

from ipv8_service import IPv8

from anydex.config import get_anydex_configuration
from anydex.core.community import MarketTestnetCommunity
from anydex.restapi.rest_manager import RESTManager
from anydex.wallet.dummy.dummy_wallet import DummyWallet1, DummyWallet2
from anydex.wallet.ethereum.eth_wallet import EthereumTestnetWallet, EthereumWallet
from anydex.wallet.iota.iota_wallet import IotaTestnetWallet, IotaWallet
from anydex.wallet.monero.xmr_wallet import MoneroTestnetWallet, MoneroWallet
from anydex.wallet.stellar.xlm_wallet import StellarTestnetWallet, StellarWallet


class AnyDexService(object):

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

    async def start_anydex(self, options):
        """
        Main method to startup AnyDex.
        """
        config = get_anydex_configuration()

        if options.statedir:
            # If we use a custom state directory, update various variables
            for key in config["keys"]:
                key["file"] = os.path.join(options.statedir, key["file"])

            for community in config["overlays"]:
                if community["class"] == "TrustChainCommunity":
                    community["initialize"]["working_directory"] = options.statedir

        if options.testnet:
            for community in config["overlays"]:
                if community["class"] == "TrustChainCommunity":
                    community["class"] = "TrustChainTestnetCommunity"

        self.ipv8 = IPv8(config, enable_statistics=options.statistics)
        await self.ipv8.start()

        print("Starting AnyDex")

        if not options.no_rest_api:
            self.restapi = RESTManager(self.ipv8)
            await self.restapi.start(options.apiport)

        async def signal_handler(sig):
            print("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                if self.restapi:
                    await self.restapi.stop()
                    self.restapi = None
                await self.ipv8.stop()
                get_event_loop().stop()

        signal.signal(signal.SIGINT, lambda sig, _: ensure_future(signal_handler(sig)))
        signal.signal(signal.SIGTERM, lambda sig, _: ensure_future(signal_handler(sig)))

        # Get Trustchain + DHT overlays
        for overlay in self.ipv8.overlays:
            # Logger level required by bitcoinlib import
            overlay.logger.setLevel('INFO')
            if isinstance(overlay, (TrustChainCommunity, TrustChainTestnetCommunity)):
                self.trustchain = overlay
            elif isinstance(overlay, DHTDiscoveryCommunity):
                self.dht = overlay

        # Initialize dummy wallets
        dummy_wallet1 = DummyWallet1()
        self.wallets[dummy_wallet1.get_identifier()] = dummy_wallet1

        dummy_wallet2 = DummyWallet2()
        self.wallets[dummy_wallet2.get_identifier()] = dummy_wallet2

        # Bitcoinlib imports required to be later due to logger overlap
        from anydex.wallet.bitcoinlib.bitcoinlib_wallets import BitcoinTestnetWallet, BitcoinWallet, LitecoinWallet, \
            LitecoinTestnetWallet, DashWallet, DashTestnetWallet

        # Initialize bitcoin wallets
        btc_wallet = BitcoinWallet(os.path.join(options.statedir, 'sqlite'))
        btc_wallet.create_wallet()
        self.wallets[btc_wallet.get_identifier()] = btc_wallet

        btc_testnet_wallet = BitcoinTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        btc_testnet_wallet.create_wallet()
        self.wallets[btc_testnet_wallet.get_identifier()] = btc_testnet_wallet

        # Initialize litecoin wallets
        ltc_wallet = LitecoinWallet(os.path.join(options.statedir, 'sqlite'))
        ltc_wallet.create_wallet()
        self.wallets[ltc_wallet.get_identifier()] = ltc_wallet

        ltc_testnet_wallet = LitecoinTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        ltc_testnet_wallet.create_wallet()
        self.wallets[ltc_testnet_wallet.get_identifier()] = ltc_testnet_wallet

        # Initialize dash wallets
        dash_wallet = DashWallet(os.path.join(options.statedir, 'sqlite'))
        dash_wallet.create_wallet()
        self.wallets[dash_wallet.get_identifier()] = dash_wallet

        # DASH TESTNET HAS NO PROVIDERS IN BITCOINLIB
        # dash_testnet_wallet = DashTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        # dash_testnet_wallet.create_wallet()
        # self.wallets[dash_testnet_wallet.get_identifier()] = dash_testnet_wallet

        # Initialize ethereum wallets
        eth_wallet = EthereumWallet(os.path.join(options.statedir, 'sqlite'))
        eth_wallet.create_wallet()
        self.wallets[eth_wallet.get_identifier()] = eth_wallet

        eth_testnet_wallet = EthereumTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        eth_testnet_wallet.create_wallet()
        self.wallets[eth_testnet_wallet.get_identifier()] = eth_testnet_wallet

        # Initialize iota wallets
        iota_wallet = IotaWallet(os.path.join(options.statedir, 'sqlite'))
        iota_wallet.create_wallet()
        self.wallets[iota_wallet.get_identifier()] = iota_wallet

        iota_testnet_wallet = IotaTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        iota_testnet_wallet.create_wallet()
        self.wallets[iota_testnet_wallet.get_identifier()] = iota_testnet_wallet

        # Initialize monero wallets
        # xmr_wallet = MoneroWallet(os.path.join(options.statedir, 'sqlite'))
        # xmr_wallet.create_wallet()
        # self.wallets[xmr_wallet.get_identifier()] = xmr_wallet

        # xmr_testnet_wallet = MoneroTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        # xmr_testnet_wallet.create_wallet()
        # self.wallets[xmr_testnet_wallet.get_identifier()] = xmr_testnet_wallet

        # Initialize stellar wallets
        xlm_wallet = StellarWallet(os.path.join(options.statedir, 'sqlite'))
        xlm_wallet.create_wallet()
        self.wallets[xlm_wallet.get_identifier()] = xlm_wallet

        xlm_testnet_wallet = StellarTestnetWallet(os.path.join(options.statedir, 'sqlite'))
        xlm_testnet_wallet.create_wallet()
        self.wallets[xlm_testnet_wallet.get_identifier()] = xlm_testnet_wallet

        # Load market community
        self.market = MarketTestnetCommunity(self.trustchain.my_peer, self.ipv8.endpoint, self.ipv8.network,
                                             trustchain=self.trustchain,
                                             dht=self.dht,
                                             wallets=self.wallets,
                                             working_directory=options.statedir,
                                             record_transactions=False,
                                             is_matchmaker=not options.no_matchmaker)

        self.ipv8.overlays.append(self.market)
        self.ipv8.strategies.append((RandomWalk(self.market), 20))


def main(argv):
    parser = argparse.ArgumentParser(add_help=False, description='AnyDex')
    parser.add_argument(
        '--help', '-h', action='help', default=argparse.SUPPRESS, help='Show this help message and exit')
    parser.add_argument(
        '--no-rest-api', '-a', action='store_const', default=False, const=True, help='Autonomous: disable the REST api')
    parser.add_argument(
        '--no-matchmaker', action='store_const', default=False, const=True, help='Disable matchmaker functionality')
    parser.add_argument(
        '--statistics', action='store_const', default=False, const=True, help='Enable IPv8 overlay statistics')
    parser.add_argument(
        '--testnet', '-t', action='store_const', default=False, const=True, help='Join the testnet')
    parser.add_argument(
        '--statedir', '-s', default='.', type=str, help='Use an alternate statedir')
    parser.add_argument(
        '--apiport', '-p', default=8090, type=int, help='Use an alternative port for the REST api')

    args = parser.parse_args(sys.argv[1:])
    service = AnyDexService()

    loop = get_event_loop()
    coro = service.start_anydex(args)
    ensure_future(coro)

    if sys.platform == 'win32':
        # Unfortunately, this is needed on Windows for Ctrl+C to work consistently.
        # Should no longer be needed in Python 3.8.
        async def wakeup():
            while True:
                await sleep(1)
        ensure_future(wakeup())

    loop.run_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
