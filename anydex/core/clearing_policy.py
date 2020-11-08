import abc
import logging
from binascii import hexlify, unhexlify

from ipv8.peer import Peer


class ClearingPolicy(metaclass=abc.ABCMeta):
    """
    The clearing policy determines whether we should trade with a specific counterparty.
    """

    def __init__(self, community):
        """
        Initialize a clearing policy.
        :param community: The MarketCommunity, used to fetch information from.
        """
        self.community = community
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    async def should_trade(self, trader_id):
        """
        :param trader_id: The ID of the trader.
        :type trader_id: TraderId
        :return: A Deferred that fires with a boolean whether we should trade or not.
        """
        return True


class SingleTradeClearingPolicy(ClearingPolicy):
    """
    This policy limits a trading partner to a maximum number of outstanding trades with risky counterparties at once.
    This is achieved by a crawl/inspection of the TrustChain records of a counterparty.
    """

    def __init__(self, community, max_concurrent_trades):
        ClearingPolicy.__init__(self, community)
        self.max_concurrent_trades = max_concurrent_trades

    async def should_trade(self, trader_id):
        """
        We first fetch the latest block of the counterparty and then determine whether we can trade with this party.
        """
        self.logger.info("Triggering clearing policy for trade with trader %s", trader_id.as_hex())

        address = await self.community.get_address_for_trader(trader_id)
        if not address:
            self.logger.info("Clearing policy is unable to determine address of trader %s", trader_id.as_hex())
            return False

        # Get the public key of the peer
        peer_pk = await self.community.send_trader_pk_request(trader_id)
        peer = Peer(peer_pk, address=address)

        blocks = await self.community.trustchain.send_crawl_request(peer, peer_pk.key_to_bin(), -1, -1)
        if not blocks:
            return False

        block = blocks[0]
        if block.type not in [b"ask", b"bid", b"cancel_order", b"tx_init", b"tx_payment", b"tx_done"]:
            self.logger.info("Unknown last block type %s, not trading with this counterparty", block.type)
            return False

        # The block must contain a responsibilities array
        do_trade = block.transaction["responsibilities"] < self.max_concurrent_trades
        if do_trade:
            self.logger.info("Will trade with trader %s (responsible trades: %d)",
                             trader_id.as_hex(), block.transaction["responsibilities"])
        else:
            self.logger.info("Will NOT trade with trader %s (responsible trades: %d)",
                             trader_id.as_hex(), block.transaction["responsibilities"])
        return do_trade
