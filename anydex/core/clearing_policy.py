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
    This policy limits a trading partner to a single outstanding trade at once.
    This is achieved by a crawl/inspection of the TrustChain records of a counterparty.
    """

    def __init__(self, community):
        ClearingPolicy.__init__(self, community)
        self.currently_crawling = set()

    async def should_trade(self, trader_id):
        """
        We first crawl the chain of the counterparty and then determine whether we can trade with this party.
        """
        address = await self.community.get_address_for_trader(trader_id)
        if not address:
            self.logger.info("Clearing policy is unable to determine address of trader %s", trader_id.as_hex())
            return False

        # Get the public key of the peer
        peer_pk = await self.community.send_trader_pk_request(trader_id)
        peer = Peer(peer_pk, address=address)

        # If we are currently crawling this peer already, it means we got another propose trade for another of the
        # traders orders. Refuse to trade for this one then.
        if trader_id in self.currently_crawling:
            self.logger.info("Clearing policy not accepting trade with trader %s - we are already crawling this peer",
                             trader_id.as_hex())
            return False

        # Crawl the chain and validate the blocks
        self.logger.info("Starting crawl of chain of trader %s" % trader_id.as_hex())
        self.currently_crawling.add(trader_id)
        await self.community.trustchain.crawl_chain(peer)

        self.logger.debug("Crawl of trader %s done - validating trade status", trader_id.as_hex())
        self.currently_crawling.remove(trader_id)

        blocks = self.community.trustchain.persistence.get_latest_blocks(peer.public_key.key_to_bin(), limit=1000)
        blocks.sort(key=lambda block: block.sequence_number)

        tx_status = {}  # Keep track of the status of each transaction

        for block in blocks:
            if block.type == b'tx_init':
                if block.link_sequence_number != 0:
                    # Get the original block
                    tx_init_block = self.community.trustchain.persistence.get_linked(block)
                else:
                    tx_init_block = block

                if not tx_init_block:
                    continue

                txid = tx_init_block.hash
                # We allow trading with this partner if it counter-signed the tx_init block, which means that
                # it should not go first during asset exchange.
                tx_status[txid] = block.link_sequence_number != 0
            elif block.type == b'tx_payment':
                txid = unhexlify(block.transaction["payment"]["transaction_id"])
                if txid not in tx_status:
                    self.logger.warning("Found payment block without having tx_init block for transaction %s!",
                                        hexlify(txid))
                    continue

                if block.link_sequence_number != 0:
                    tx_status[txid] = False
                else:
                    tx_status[txid] = True
            elif block.type == b'tx_done':
                txid = unhexlify(block.transaction["tx"]["transaction_id"])
                if txid not in tx_status:
                    self.logger.warning("Found tx_done block without having tx_init block for transaction %s!",
                                        hexlify(txid))
                    continue

                tx_status[txid] = True

        # If there is any transaction for which this party currently holds the token, do not trade
        return all(tx_status.values())
