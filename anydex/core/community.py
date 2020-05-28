import random
from asyncio import Future, ensure_future, gather, get_event_loop
from base64 import b64decode
from binascii import hexlify, unhexlify
from functools import wraps

from ipv8.attestation.trustchain.listener import BlockListener
from ipv8.attestation.trustchain.payload import HalfBlockBroadcastPayload, HalfBlockPairBroadcastPayload,\
    HalfBlockPairPayload
from ipv8.community import Community, lazy_wrapper
from ipv8.dht import DHTError
from ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from ipv8.messaging.payload_headers import GlobalTimeDistributionPayload
from ipv8.peer import Peer
from ipv8.requestcache import NumberCache, RandomNumberCache, RequestCache
from ipv8.util import succeed

from anydex.core import DeclineMatchReason, DeclinedTradeReason, MAX_ORDER_TIMEOUT
from anydex.core.block import MarketBlock
from anydex.core.bloomfilter import BloomFilter
from anydex.core.clearing_policy import SingleTradeClearingPolicy
from anydex.core.database import MarketDB
from anydex.core.match_queue import MatchPriorityQueue
from anydex.core.matching_engine import MatchingEngine, PriceTimeStrategy
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.order_manager import OrderManager
from anydex.core.order_repository import DatabaseOrderRepository, MemoryOrderRepository
from anydex.core.orderbook import DatabaseOrderBook, OrderBook
from anydex.core.payload import DeclineMatchPayload, DeclineTradePayload, InfoPayload, MatchPayload,\
    OrderStatusRequestPayload, OrderStatusResponsePayload, OrderbookSyncPayload, PingPongPayload, PublicKeyPayload,\
    TradePayload, WalletInfoPayload
from anydex.core.payment import Payment
from anydex.core.payment_id import PaymentId
from anydex.core.settings import MarketSettings
from anydex.core.tick import Ask, Bid, Tick
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp
from anydex.core.trade import AcceptedTrade, CounterTrade, DeclinedTrade, ProposedTrade, Trade
from anydex.core.transaction import Transaction, TransactionId
from anydex.core.transaction_manager import TransactionManager
from anydex.core.transaction_repository import DatabaseTransactionRepository,\
    MemoryTransactionRepository
from anydex.core.wallet_address import WalletAddress
from anydex.util.asyncio import call_later
from anydex.wallet.tc_wallet import TrustchainWallet


# Message definitions
MSG_MATCH = 7
MSG_MATCH_DECLINE = 9
MSG_PROPOSED_TRADE = 10
MSG_DECLINED_TRADE = 11
MSG_COUNTER_TRADE = 12
MSG_ACCEPT_TRADE = 13
MSG_WALLET_INFO = 14
MSG_ORDER_QUERY = 16
MSG_ORDER_RESPONSE = 17
MSG_BOOK_SYNC = 19
MSG_PING = 20
MSG_PONG = 21
MSG_MATCH_DONE = 22
MSG_PK_QUERY = 23
MSG_PK_RESPONSE = 24


def synchronized(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        with self.trustchain.receive_block_lock:
            return f(self, *args, **kwargs)
    return wrapper


class MatchCache(NumberCache):
    """
    This cache keeps track of incoming match messages for a specific order.
    """

    def __init__(self, community, order):
        super(MatchCache, self).__init__(community.request_cache, "match", int(order.order_id.order_number))
        self.community = community
        self.order = order
        self.matches = {}
        self.schedule_propose = None
        self.schedule_task = None
        self.schedule_task_done = False
        self.outstanding_request = None
        self.received_responses_ids = set()
        self.queue = MatchPriorityQueue(self.order)

    @property
    def timeout_delay(self):
        return 7200.0

    def add_match(self, match_payload):
        """
        Add a match to the queue.
        """
        if self.order.status != "open":
            self._logger.info("Ignoring match payload, order %s not open anymore", self.order.order_id)
            return

        other_order_id = OrderId(match_payload.trader_id, match_payload.order_number)
        if other_order_id not in self.matches:
            self.matches[other_order_id] = []

        # We do not want to add the match twice
        exists = False
        for match_payload in self.matches[other_order_id]:
            match_order_id = OrderId(match_payload.trader_id, match_payload.order_number)
            if match_order_id == other_order_id:
                exists = True
                break

        if not exists:
            self.matches[other_order_id].append(match_payload)

        if not self.queue.contains_order(other_order_id) and not (self.outstanding_request and self.outstanding_request[2] == other_order_id):
            self._logger.debug("Adding match payload with own order id %s and other id %s to queue",
                               self.order.order_id, other_order_id)
            self.queue.insert(0, match_payload.assets.price, other_order_id)

        if not self.schedule_task:
            # Schedule a timer
            self._logger.info("Scheduling batch match of order %s" % str(self.order.order_id))
            self.schedule_task = call_later(self.community.settings.match_window,
                                            self.start_process_matches, ignore_errors=True)
        elif self.schedule_task_done and not self.outstanding_request:
            # If we are currently not processing anything and the schedule task is done, process the matches
            self.process_match()

    def start_process_matches(self):
        """
        Start processing the batch of matches.
        """
        self.schedule_task_done = True
        self._logger.info("Processing incoming matches for order %s", self.order.order_id)

        # It could be that the order has already been completed while waiting - we should let the matchmaker know
        if self.order.status != "open":
            self._logger.info("Order %s is already fulfilled - notifying matchmakers", self.order.order_id)
            for _, matches in self.matches.iteritems():
                for match_payload in matches:
                    # Send a declined trade back
                    other_order_id = OrderId(match_payload.trader_id, match_payload.order_number)
                    self.community.send_decline_match_message(self.order, other_order_id,
                                                              match_payload.matchmaker_trader_id,
                                                              DeclineMatchReason.ORDER_COMPLETED)
            self.matches = {}
            return

        self.process_match()

    def process_match(self):
        """
        Process the first eligible match. First, we sort the list based on price.
        """
        if self.order.available_quantity == 0:
            self._logger.debug("No available quantity for order when processing!")
            return

        item = self.queue.delete()
        if not item:
            self._logger.info("Done with processsing match queue for order %s!", self.order.order_id)
        else:
            retries, _, other_order_id = item
            self.outstanding_request = item
            if retries == 0:
                # To prevent all traders from proposing at the same time, we want a small delay
                delay = random.uniform(0, 0)
            else:
                delay = random.uniform(1, 2)
            self.schedule_propose = call_later(delay,
                                               self.community.accept_match_and_propose,
                                               self.order, other_order_id, ignore_errors=True)

    def received_decline_trade(self, other_order_id, decline_reason):
        """
        The counterparty refused to trade - update the cache accordingly.
        """
        self.received_responses_ids.add(other_order_id)
        if decline_reason == DeclinedTradeReason.ORDER_COMPLETED and other_order_id in self.matches:
            # Let the matchmakers know that the order is complete
            for match_payload in self.matches[other_order_id]:
                self.community.send_decline_match_message(self.order,
                                                          other_order_id,
                                                          match_payload.matchmaker_trader_id,
                                                          DeclineMatchReason.OTHER_ORDER_COMPLETED)
        elif decline_reason == DeclinedTradeReason.ORDER_CANCELLED and other_order_id in self.matches:
            # Let the matchmakers know that the order is cancelled
            for match_payload in self.matches[other_order_id]:
                self.community.send_decline_match_message(self.order,
                                                          other_order_id,
                                                          match_payload.matchmaker_trader_id,
                                                          DeclineMatchReason.OTHER_ORDER_CANCELLED)
        elif decline_reason == DeclinedTradeReason.ADDRESS_LOOKUP_FAIL and other_order_id in self.matches:
            # Let the matchmakers know that the address resolution failed
            for match_payload in self.matches[other_order_id]:
                self.community.send_decline_match_message(self.order,
                                                          other_order_id,
                                                          match_payload.matchmaker_trader_id,
                                                          DeclineMatchReason.OTHER)
        elif decline_reason in [DeclinedTradeReason.ORDER_RESERVED, DeclinedTradeReason.ALREADY_TRADING] and \
                self.outstanding_request:
            # Add it to the queue again
            self._logger.debug("Adding entry (%d, %s, %s) to matching queue again", *self.outstanding_request)
            self.queue.insert(self.outstanding_request[0] + 1, self.outstanding_request[1], self.outstanding_request[2])
        elif decline_reason == DeclinedTradeReason.NO_AVAILABLE_QUANTITY and self.outstanding_request:
            # Re-add the item to the queue, with the same priority
            self.queue.insert(self.outstanding_request[0], self.outstanding_request[1], self.outstanding_request[2])

        self.outstanding_request = None

        if self.order.status == "open":
            self.process_match()

    def remove_order(self, order_id):
        """
        Remove all entries from the queue that match the passed order id.
        """
        to_remove = []
        for item in self.queue.queue:
            if item[2] == order_id:
                to_remove.append(item)

        for item in to_remove:
            self.queue.queue.remove(item)

    def did_trade(self, transaction, block):
        """
        We just performed a trade with a counterparty.
        """
        self.outstanding_request = None
        other_order_id = transaction.partner_order_id
        if other_order_id not in self.matches:
            return

        self.received_responses_ids.add(other_order_id)

        for match_payload in self.matches[other_order_id]:
            self._logger.info("Sending transaction completed (order %s) to matchmaker %s", transaction.order_id,
                              match_payload.matchmaker_trader_id.as_hex())

            linked_block = self.community.trustchain.persistence.get_linked(block) or block
            global_time = self.community.claim_global_time()
            dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
            payload = HalfBlockPairPayload.from_half_blocks(block, linked_block).to_pack_list()
            packet = self.community._ez_pack(self.community._prefix, MSG_MATCH_DONE, [dist, payload], False)
            self.community.endpoint.send(self.community.lookup_ip(match_payload.matchmaker_trader_id), packet)

        if self.order.status == "open":
            self.process_match()


class ProposedTradeRequestCache(NumberCache):
    """
    This cache keeps track of outstanding proposed trade messages.
    """
    def __init__(self, community, proposed_trade):
        super(ProposedTradeRequestCache, self).__init__(community.request_cache, "proposed-trade",
                                                        proposed_trade.proposal_id)
        self.community = community
        self.proposed_trade = proposed_trade

    def on_timeout(self):
        # Just remove the reserved quantity from the order
        order = self.community.order_manager.order_repository.find_by_id(self.proposed_trade.order_id)
        proposed_assets = self.proposed_trade.assets
        owned_assets = proposed_assets.first.amount if order.is_ask() else proposed_assets.first.amount
        order.release_quantity_for_tick(self.proposed_trade.recipient_order_id, owned_assets)
        self.community.order_manager.order_repository.update(order)

        # Let the match cache know about the timeout
        cache = self.community.request_cache.get("match", int(order.order_id.order_number))
        if cache:
            cache.received_decline_trade(self.proposed_trade.recipient_order_id, DeclinedTradeReason.OTHER)


class OrderStatusRequestCache(RandomNumberCache):

    def __init__(self, community, request_future):
        super(OrderStatusRequestCache, self).__init__(community.request_cache, "order-status-request")
        self.request_future = request_future

    @property
    def timeout_delay(self):
        return 20.0

    def on_timeout(self):
        self._logger.warning("No response in time from remote peer when requesting order status")


class PublicKeyRequestCache(RandomNumberCache):

    def __init__(self, community, trader_id, request_future):
        super(PublicKeyRequestCache, self).__init__(community.request_cache, "pk-request")
        self.trader_id = trader_id
        self.request_future = request_future

    @property
    def timeout_delay(self):
        return 20.0

    def on_timeout(self):
        self._logger.warning("No response in time from remote peer when requesting public key")


class PingRequestCache(RandomNumberCache):
    """
    This request cache keeps track of outstanding ping messages to matchmakers.
    """
    TIMEOUT_DELAY = 5.0

    def __init__(self, community, request_future):
        super(PingRequestCache, self).__init__(community.request_cache, "ping")
        self.request_future = request_future

    @property
    def timeout_delay(self):
        return PingRequestCache.TIMEOUT_DELAY

    def on_timeout(self):
        self.request_future.set_result(False)


class MarketCommunity(Community, BlockListener):
    """
    Community for general asset trading.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3ab5bb7dc5a3a61de442585122b24c9f752469a212dc6d8ffa3d42bbf9c2f8d10"
                                 "ba569b270f615ef78aeff0547f38745d22af268037ad64935ee7c054b7921b23b"))
    PROTOCOL_VERSION = 4
    BLOCK_CLASS = MarketBlock
    DB_NAME = 'market'

    def __init__(self, *args, **kwargs):
        self.is_matchmaker = kwargs.pop('is_matchmaker', True)
        self.wallets = kwargs.pop('wallets', {})
        self.trustchain = kwargs.pop('trustchain')
        self.record_transactions = kwargs.pop('record_transactions', False)
        market_block_types = [b'ask', b'bid', b'cancel_order', b'tx_init', b'tx_payment', b'tx_done']
        self.trustchain.settings.block_types_bc_disabled |= set(market_block_types)
        self.trustchain.add_listener(self, market_block_types)
        self.dht = kwargs.pop('dht', None)
        self.use_database = kwargs.pop('use_database', True)
        self.settings = MarketSettings()
        self.fixed_broadcast_set = []  # Optional list of fixed peers that will receive market messages

        db_working_dir = kwargs.pop('working_directory', '')

        Community.__init__(self, *args, **kwargs)
        BlockListener.__init__(self)

        self._use_main_thread = True  # Market community is unable to deal with thread pool message processing yet
        self.mid = self.my_peer.mid
        self.mid_register = {}
        self.pk_register = {}
        self.order_book = None
        self.market_database = MarketDB(db_working_dir, self.DB_NAME)
        self.matching_engine = None
        self.transaction_manager = None
        self.use_local_address = False
        self.matching_enabled = True
        self.use_incremental_payments = False
        self.matchmakers = set()
        self.request_cache = RequestCache()
        self.cancelled_orders = set()  # Keep track of cancelled orders so we don't add them again to the orderbook.
        self.sent_matches = set()
        self.clearing_policies = []

        if self.settings.single_trade:
            self.clearing_policies.append(SingleTradeClearingPolicy(self))

        if self.use_database:
            order_repository = DatabaseOrderRepository(self.mid, self.market_database)
            transaction_repository = DatabaseTransactionRepository(self.mid, self.market_database)
        else:
            order_repository = MemoryOrderRepository(self.mid)
            transaction_repository = MemoryTransactionRepository(self.mid)

        self.order_manager = OrderManager(order_repository)
        self.transaction_manager = TransactionManager(transaction_repository)

        if self.is_matchmaker:
            self.enable_matchmaker()

        # Register messages
        self.decode_map.update({
            chr(MSG_MATCH): self.received_match,
            chr(MSG_MATCH_DECLINE): self.received_decline_match,
            chr(MSG_PROPOSED_TRADE): self.received_proposed_trade,
            chr(MSG_DECLINED_TRADE): self.received_decline_trade,
            chr(MSG_COUNTER_TRADE): self.received_counter_trade,
            chr(MSG_ACCEPT_TRADE): self.received_accept_trade,
            chr(MSG_WALLET_INFO): self.received_wallet_info,
            chr(MSG_ORDER_QUERY): self.received_order_status_request,
            chr(MSG_ORDER_RESPONSE): self.received_order_status,
            chr(MSG_BOOK_SYNC): self.received_orderbook_sync,
            chr(MSG_PING): self.received_ping,
            chr(MSG_PONG): self.received_pong,
            chr(MSG_MATCH_DONE): self.received_matched_tx_complete,
            chr(MSG_PK_QUERY): self.received_trader_pk_request,
            chr(MSG_PK_RESPONSE): self.received_trader_pk_response
        })

        self.logger.info("Market community initialized with mid %s", hexlify(self.mid))

    async def get_address_for_trader(self, trader_id):
        """
        Fetch the address for a trader.
        If not available in the local storage, perform a DHT request to fetch the address of the peer with a
        specified trader ID.
        Return a Deferred that fires either with the address or None if the peer could not be found in the DHT.
        """
        if bytes(trader_id) == self.mid:
            return self.get_ipv8_address()
        address = self.lookup_ip(trader_id)
        if address:
            return address

        self.logger.info("Address for trader %s not found locally, doing DHT request", trader_id.as_hex())

        if not self.dht:
            raise RuntimeError("DHT not available")

        try:
            peers = await self.dht.connect_peer(bytes(trader_id))
        except DHTError:
            self._logger.warning("Unable to get address for trader %s", trader_id.as_hex())
            return

        if peers:
            self.update_ip(trader_id, peers[0].address)
            return peers[0].address

    def get_peer_from_mid(self, peer_mid):
        """
        Find a peer by mid.
        """
        peers = self.network.verified_peers
        matches = [p for p in peers if p.mid == peer_mid]
        return matches[0] if matches else None

    async def should_sign(self, block):
        """
        Check whether we should sign the incoming block.
        """
        tx = block.transaction
        if block.type == b"tx_payment":
            txid = TransactionId(unhexlify(tx["payment"]["transaction_id"]))
            transaction = self.transaction_manager.find_by_id(txid)
            if not transaction or not block.is_valid_tx_payment_block():
                return False

            if not transaction.trading_peer:
                transaction.trading_peer = self.get_peer_from_mid(bytes(transaction.partner_order_id.trader_id))

            # Start polling for the payment
            asset_id = tx["payment"]["transferred"]["type"]
            if asset_id not in self.wallets or not self.wallets[asset_id].created:
                self.logger.warning("Wallet for asset %s not found - not signing payment message", asset_id)
                return False

            wallet = self.wallets[asset_id]
            payment = Payment.from_block(block)
            await wallet.monitor_transaction(payment.payment_id.payment_id)
            transaction.add_payment(payment)
            self.transaction_manager.transaction_repository.update(transaction)

            order = self.order_manager.order_repository.find_by_id(transaction.order_id)
            order.add_trade(transaction.partner_order_id, payment.transferred_assets)
            self.order_manager.order_repository.update(order)

            if not transaction.is_payment_complete():
                self.register_anonymous_task('send_payment_%s' % id(transaction), self.send_payment, transaction)

            # TODO MULTIPLE INVOCATIONS!!

            return True

        elif block.type == b"tx_init":
            if not block.is_valid_tx_init_done_block():
                self.logger.info("Block %s not valid!", block)
                return False

            # Create a transaction, based on the information in the block
            if not self.transaction_manager.find_by_id(TransactionId(block.hash)):
                transaction = Transaction.from_tx_init_block(block)
                transaction.trading_peer = Peer(block.public_key,
                                                address=self.lookup_ip(transaction.partner_order_id.trader_id))
                self.transaction_manager.transaction_repository.add(transaction)

            return True
        elif block.type == b"tx_done":
            txid = TransactionId(unhexlify(tx["tx"]["transaction_id"]))
            transaction = self.transaction_manager.find_by_id(txid)
            return transaction and block.is_valid_tx_init_done_block()

        return False  # Unknown block type

    def enable_matchmaker(self):
        """
        Enable this node to be a matchmaker
        """
        if self.use_database:
            self.order_book = DatabaseOrderBook(self.market_database)
            self.order_book.restore_from_database()
        else:
            self.order_book = OrderBook()
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))
        self.is_matchmaker = True

    def disable_matchmaker(self):
        """
        Disable the matchmaker status of this node
        """
        self.order_book = None
        self.matching_engine = None
        self.is_matchmaker = False

    def create_introduction_request(self, socket_address, extra_bytes=b''):
        extra_payload = InfoPayload(TraderId(self.mid), Timestamp.now(), self.is_matchmaker)
        extra_bytes = self.serializer.pack_multiple(extra_payload.to_pack_list())[0]
        return super(MarketCommunity, self).create_introduction_request(socket_address, extra_bytes)

    def create_introduction_response(self, lan_socket_address, socket_address, identifier,
                                     introduction=None, extra_bytes=b''):
        extra_payload = InfoPayload(TraderId(self.mid), Timestamp.now(), self.is_matchmaker)
        extra_bytes = self.serializer.pack_multiple(extra_payload.to_pack_list())[0]
        return super(MarketCommunity, self).create_introduction_response(lan_socket_address, socket_address,
                                                                         identifier, introduction, extra_bytes)

    def parse_extra_bytes(self, extra_bytes, peer):
        if not extra_bytes:
            return False

        payload = self.serializer.unpack_to_serializables([InfoPayload], extra_bytes)[0]
        self.update_ip(payload.trader_id, peer.address)

        if payload.is_matchmaker:
            self.add_matchmaker(peer)

    def introduction_request_callback(self, peer, dist, payload):
        if self.is_matchmaker and peer.address not in self.network.blacklist:
            self.send_orderbook_sync(peer)
        self.parse_extra_bytes(payload.extra_bytes, peer)

    def introduction_response_callback(self, peer, dist, payload):
        if self.is_matchmaker and peer.address not in self.network.blacklist:
            self.send_orderbook_sync(peer)
        self.parse_extra_bytes(payload.extra_bytes, peer)

    def send_orderbook_sync(self, peer):
        """
        Send an orderbook sync message to a specific peer.
        """
        self.logger.debug("Sending orderbook sync to peer %s", peer)
        bloomfilter = self.get_orders_bloomfilter()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderbookSyncPayload(TraderId(self.mid), Timestamp.now(), bloomfilter).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_BOOK_SYNC, [auth, payload])
        self.endpoint.send(peer.address, packet)

    def get_orders_bloomfilter(self):
        order_ids = [bytes(order_id) for order_id in self.order_book.get_order_ids()]
        orders_bloom_filter = BloomFilter(0.005, max(len(order_ids), 1), prefix=b' ')
        if order_ids:
            orders_bloom_filter.add_keys(order_ids)
        return orders_bloom_filter

    async def unload(self):
        # Clear match caches
        for match_cache in self.get_match_caches():
            if match_cache.schedule_task:
                match_cache.schedule_task.cancel()
            if match_cache.schedule_propose:
                match_cache.schedule_propose.cancel()

        self.request_cache.clear()

        # Save the ticks to the database
        if self.is_matchmaker:
            if self.use_database:
                self.order_book.save_to_database()
            await self.order_book.shutdown_task_manager()
        self.market_database.close()
        await super(MarketCommunity, self).unload()

    def get_ipv8_address(self):
        """
        Returns the address of the IPV8 instance. This method is here to make the experiments on the DAS5 succeed;
        direct messaging is not possible there with a wan address so we are using the local address instead.
        """
        return self.my_estimated_lan if self.use_local_address else self.my_estimated_wan

    def get_order_addresses(self, order):
        """
        Return a tuple of incoming and outgoing payment address of an order.
        """
        if order.is_ask():
            return (WalletAddress(self.wallets[order.assets.second.asset_id].get_address()),
                    WalletAddress(self.wallets[order.assets.first.asset_id].get_address()))
        else:
            return (WalletAddress(self.wallets[order.assets.first.asset_id].get_address()),
                    WalletAddress(self.wallets[order.assets.second.asset_id].get_address()))

    def match_order_ids(self, order_ids):
        """
        Attempt to match the ticks with the provided order ids
        :param order_ids: The order ids to match
        """
        for order_id in order_ids:
            if self.order_book.tick_exists(order_id):
                self.match(self.order_book.get_tick(order_id))

    def match(self, tick):
        """
        Try to find a match for a specific tick and send proposed trade messages if there is a match
        :param tick: The tick to find matches for
        :return The number of matches found
        """
        if not self.matching_enabled:
            return 0

        order_tick_entry = self.order_book.get_tick(tick.order_id)
        if tick.assets.first.amount - tick.traded <= 0:
            self.logger.debug("Tick %s does not have any quantity to match!", tick.order_id)
            return 0

        matched_ticks = self.matching_engine.match(order_tick_entry)
        self.send_match_messages(matched_ticks, tick.order_id)
        return len(matched_ticks)

    def lookup_ip(self, trader_id):
        """
        Lookup the ip for the public key to send a message to a specific node

        :param trader_id: The public key of the node to send to
        :type trader_id: TraderId
        :return: The ip and port tuple: (<ip>, <port>)
        :rtype: tuple
        """
        return self.mid_register.get(trader_id)

    def update_ip(self, trader_id, ip):
        """
        Update the public key to ip mapping

        :param trader_id: The public key of the node
        :param ip: The ip and port of the node
        :type trader_id: TraderId
        :type ip: tuple
        """
        self.logger.debug("Updating ip of trader %s to (%s, %s)", trader_id.as_hex(), ip[0], ip[1])
        self.mid_register[trader_id] = ip

    def process_tick_block(self, block):
        """
        Process a TradeChain block containing a tick, only if we have a verified order.
        :param block: The TradeChain block containing the tick
        """
        if not block.is_valid_tick_block():
            self._logger.warning("Invalid tick block received!")
            return

        tick = Ask.from_block(block) if block.type == b'ask' else Bid.from_block(block)
        ensure_future(self.on_tick(tick))

    def process_tx_init_block(self, block):
        """
        Process a TrustChain block containing a transaction initialisation
        :param block: The TrustChain block containing the transaction initialisation
        """
        if not block.is_valid_tx_init_done_block():
            self._logger.warning("Invalid tx_init block received!")
            return

        if self.is_matchmaker:
            tx_dict = block.transaction
            order_id1 = OrderId(TraderId(unhexlify(tx_dict["tx"]["trader_id"])),
                                OrderNumber(tx_dict["tx"]["order_number"]))
            order_id2 = OrderId(TraderId(unhexlify(tx_dict["tx"]["partner_trader_id"])),
                                OrderNumber(tx_dict["tx"]["partner_order_number"]))
            self.match_order_ids([order_id1, order_id2])

    def process_tx_payment_block(self, block):
        """
        Process a TrustChain block containing a payment.
        :param block: The TrustChain block containing the payment info.
        """
        if block.link_public_key == self.my_peer.public_key.key_to_bin():
            transaction_id = TransactionId(unhexlify(block.transaction["payment"]["transaction_id"]))
            transaction = self.transaction_manager.find_by_id(transaction_id)
            if not transaction:
                self.logger.warning("Could not find transaction associated for signed payment block %s", block)
                return

            if transaction.is_payment_complete():
                order = self.order_manager.order_repository.find_by_id(transaction.order_id)

                def on_tx_done_signed(future):
                    """
                    We received the signed block from the counterparty, wrap everything up
                    """
                    block = future.result()
                    self.send_matched_transaction_completed(transaction, block)

                def build_tx_done_block(future):
                    other_order_dict = future.result()
                    my_order_dict = order.to_status_dictionary()

                    if order.is_ask():
                        ask_order_dict = my_order_dict
                        bid_order_dict = other_order_dict
                    else:
                        ask_order_dict = other_order_dict
                        bid_order_dict = my_order_dict

                    ensure_future(self.create_new_tx_done_block(transaction.trading_peer, ask_order_dict,
                                                                bid_order_dict, transaction)).\
                        add_done_callback(on_tx_done_signed)

                self.send_order_status_request(transaction.partner_order_id).add_done_callback(build_tx_done_block)

    def process_tx_done_block(self, block):
        """
        Process a TrustChain block containing a transaction completion
        :param block: The TradeChain block containing the transaction completion
        """
        if not block.is_valid_tx_init_done_block():
            self._logger.warning("Invalid tx_done block received!")
            return

        if block.link_public_key == self.my_peer.public_key.key_to_bin():
            # If we have signed an incoming tx_done block, notify the matchmaker about this
            transaction_id = TransactionId(unhexlify(block.transaction["tx"]["transaction_id"]))
            transaction = self.transaction_manager.find_by_id(transaction_id)
            if transaction:
                self.send_matched_transaction_completed(transaction, block)
        elif self.is_matchmaker:
            tx_dict = block.transaction
            transferred_quantity = tx_dict["tx"]["transferred"]["first"]["amount"]
            self.order_book.update_ticks(tx_dict["ask"], tx_dict["bid"], transferred_quantity)
            ask_order_id = OrderId(TraderId(unhexlify(tx_dict["ask"]["trader_id"])),
                                   OrderNumber(tx_dict["ask"]["order_number"]))
            bid_order_id = OrderId(TraderId(unhexlify(tx_dict["bid"]["trader_id"])),
                                   OrderNumber(tx_dict["bid"]["order_number"]))
            self.match_order_ids([ask_order_id, bid_order_id])

    def process_cancel_order_block(self, block):
        """
        Process a TradeChain block containing a order cancellation
        :param block: The TradeChain block containing the order cancellation
        """
        if not block.is_valid_cancel_block():
            self._logger.warning("Invalid cancel block received!")
            return

        order_id = OrderId(TraderId(unhexlify(block.transaction["trader_id"])),
                           OrderNumber(block.transaction["order_number"]))
        if self.is_matchmaker and self.order_book.tick_exists(order_id):
            self.order_book.remove_tick(order_id)
            self.cancelled_orders.add(order_id)

    @lazy_wrapper(OrderbookSyncPayload)
    def received_orderbook_sync(self, peer, payload):
        if not self.is_matchmaker:
            return

        ticks = []
        for order_id in self.order_book.get_order_ids():
            if bytes(order_id) not in payload.bloomfilter:
                is_ask = self.order_book.ask_exists(order_id)
                entry = self.order_book.get_ask(order_id) if is_ask else self.order_book.get_bid(order_id)
                ticks.append(entry)

        for entry in random.sample(ticks, min(len(ticks), self.settings.num_order_sync)):
            # Send the block pair associated with this tick
            tick_block = self.trustchain.persistence.get_block_with_hash(entry.tick.block_hash)
            if tick_block:
                self.trustchain.send_block(tick_block, address=peer.address)

    def ping_peer(self, peer):
        """
        Ping a specific peer. Return a deferred that fires with a boolean value whether the peer responded within time.
        """
        future = Future()
        cache = PingRequestCache(self, future)
        self.request_cache.add(cache)
        self.send_ping(peer, cache.number)
        return future

    def send_ping(self, peer, identifier):
        """
        Send a ping message with an identifier to a specific peer.
        """
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PingPongPayload(TraderId(self.mid), Timestamp.now(), identifier).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_PING, [auth, payload])
        self.endpoint.send(peer.address, packet)

    @lazy_wrapper(PingPongPayload)
    def received_ping(self, peer, payload):
        self.send_pong(peer, payload.identifier)

    def send_pong(self, peer, identifier):
        """
        Send a pong message with an identifier to a specific peer.
        """
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PingPongPayload(TraderId(self.mid), Timestamp.now(), identifier).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_PONG, [auth, payload])
        self.endpoint.send(peer.address, packet)

    @lazy_wrapper(PingPongPayload)
    def received_pong(self, _, payload):
        if not self.request_cache.has("ping", payload.identifier):
            self.logger.warning("ping cache with id %s not found", payload.identifier)
            return

        cache = self.request_cache.pop("ping", payload.identifier)
        get_event_loop().call_soon_threadsafe(cache.request_future.set_result, True)

    def verify_offer_creation(self, assets, timeout):
        """
        Verify whether we are creating a valid order.
        This method raises a RuntimeError if the created order is not valid.
        """
        if assets.first.asset_id == assets.second.asset_id:
            raise RuntimeError("You cannot trade between the same wallet")

        if assets.first.asset_id not in self.wallets or not self.wallets[assets.first.asset_id].created:
            raise RuntimeError("Please create a %s wallet first" % assets.first.asset_id)

        if assets.second.asset_id not in self.wallets or not self.wallets[assets.second.asset_id].created:
            raise RuntimeError("Please create a %s wallet first" % assets.second.asset_id)

        asset1_min_unit = self.wallets[assets.first.asset_id].min_unit()
        if assets.first.amount < asset1_min_unit:
            raise RuntimeError("The assets to trade should be higher than or equal to the min unit of this asset (%s)."
                               % assets.first)

        asset2_min_unit = self.wallets[assets.second.asset_id].min_unit()
        if assets.second.amount < asset2_min_unit:
            raise RuntimeError("The assets to trade should be higher than or equal to the min unit of this asset (%s)."
                               % assets.second)

        if timeout < 0:
            raise RuntimeError("The timeout for this order should be positive")

        if timeout > MAX_ORDER_TIMEOUT:
            raise RuntimeError("The timeout for this order should be less than a day")

    async def create_ask(self, assets, timeout):
        """
        Create an ask order (sell order)

        :param assets: The assets to exchange
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type assets: AssetPair
        :type timeout: int
        :return: The created order
        :rtype: Order
        """
        self.verify_offer_creation(assets, timeout)

        # Create the order
        order = self.order_manager.create_ask_order(assets, Timeout(timeout))
        order.set_verified()
        self.order_manager.order_repository.update(order)

        # Create the tick
        tick = Tick.from_order(order)

        blocks = await self.create_new_tick_block(tick)
        block, _ = blocks
        order.broadcast_peers = self.broadcast_block(block)
        if self.is_matchmaker:
            tick.block_hash = block.hash
            # Search for matches
            self.order_book.insert_ask(tick)
            self.match(tick)
        return order

    async def create_bid(self, assets, timeout):
        """
        Create an ask order (sell order)

        :param assets: The assets to exchange
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type assets: AssetPair
        :type timeout: int
        :return: The created order
        :rtype: Order
        """
        self.verify_offer_creation(assets, timeout)

        # Create the order
        order = self.order_manager.create_bid_order(assets, Timeout(timeout))
        order.set_verified()
        self.order_manager.order_repository.update(order)

        # Create the tick
        tick = Tick.from_order(order)

        blocks = await self.create_new_tick_block(tick)
        block, _ = blocks
        self.logger.info("Bid created with asset pair %s", assets)
        order.broadcast_peers = self.broadcast_block(block)
        if self.is_matchmaker:
            tick.block_hash = block.hash
            # Search for matches
            self.order_book.insert_bid(tick)
            self.match(tick)
        return order

    def broadcast_block(self, block):
        """
        Broadcast a block with market information to matchmakers.
        :param block: The block to broadcast.
        :return The peers this block was sent to.
        """
        global_time = self.claim_global_time()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
        payload = HalfBlockBroadcastPayload.from_half_block(block, self.settings.ttl).to_pack_list()
        packet = self._ez_pack(self.trustchain._prefix, 5, [dist, payload], False)
        if self.fixed_broadcast_set:
            broadcast_peers = self.fixed_broadcast_set
        else:
            broadcast_peers = random.sample(self.matchmakers, min(len(self.matchmakers), self.settings.fanout))

        for peer in broadcast_peers:
            self.endpoint.send(peer.address, packet)
        self.trustchain.relayed_broadcasts.add(block.block_id)

        return broadcast_peers

    def broadcast_block_pair(self, block1, block2):
        """
        Broadcast a block with market information to matchmakers.
        :param block1: The first part of the block pair to broadcast.
        :param block2: The second part of the block pair to broadcast.
        :return The peers this block was sent to.
        """
        global_time = self.claim_global_time()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
        payload = HalfBlockPairBroadcastPayload.from_half_blocks(block1, block2, self.settings.ttl).to_pack_list()
        packet = self._ez_pack(self.trustchain._prefix, 6, [dist, payload], False)
        if self.fixed_broadcast_set:
            broadcast_peers = self.fixed_broadcast_set
        else:
            broadcast_peers = random.sample(self.matchmakers, min(len(self.matchmakers), self.settings.fanout))

        for peer in broadcast_peers:
            self.endpoint.send(peer.address, packet)
        self.trustchain.relayed_broadcasts.add(block1.block_id)

        return broadcast_peers

    def received_block(self, block):
        """
        We received a block for the market community.
        Process it accordingly, after checking the version number first.
        """
        if block.transaction.get("version") != self.PROTOCOL_VERSION:
            return

        if block.type in (b"ask", b"bid"):
            self.process_tick_block(block)
        elif block.type == b"tx_init":
            self.process_tx_init_block(block)
        elif block.type == b"tx_payment":
            self.process_tx_payment_block(block)
        elif block.type == b"tx_done":
            self.process_tx_done_block(block)
        elif block.type == b"cancel_order":
            self.process_cancel_order_block(block)

    def add_matchmaker(self, matchmaker):
        """
        Add a matchmaker to the set of known matchmakers. Also check whether there are pending deferreds.
        """
        if matchmaker.public_key.key_to_bin() == self.my_peer.public_key.key_to_bin():
            return

        self.matchmakers.add(matchmaker)

    @synchronized
    def create_new_tick_block(self, tick):
        """
        Create a block on TradeChain defining a new tick (either ask or bid).

        :param tick: The tick we want to persist to the TradeChain.
        :type tick: Tick
        :return: A MarketBlock with the order details.
        :rtype: MarketBlock
        """
        tx_dict = {
            "tick": tick.to_block_dict(),
            "version": self.PROTOCOL_VERSION
        }
        block_type = b'ask' if tick.is_ask() else b'bid'
        return self.trustchain.create_source_block(block_type=block_type, transaction=tx_dict)

    @synchronized
    def create_new_cancel_order_block(self, order):
        """
        Create a block on TradeChain defining a cancellation of an order.

        :param order: The tick order to cancel
        :type order: Order
        :return: A MarketBlock with the cancellation details.
        :rtype: MarketBlock
        """
        tx_dict = {
            "trader_id": order.order_id.trader_id.as_hex(),
            "order_number": int(order.order_id.order_number),
            "version": self.PROTOCOL_VERSION
        }
        return self.trustchain.create_source_block(block_type=b'cancel_order', transaction=tx_dict)

    @synchronized
    def create_new_tx_init_block(self, peer, accepted_trade):
        """
        Create a block on TradeChain defining initiation of a transaction.

        :param: peer: The peer to send the block to
        :param: ask_order_dict: A dictionary containing the status of the ask order
        :param: bid_order_dict: A dictionary containing the status of the bid order
        :param accepted_trade: Details on the accepted trade
        :type peer: Peer
        :type accepted_trade: AcceptedTrade
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "tx": accepted_trade.to_block_dictionary(),
            "version": self.PROTOCOL_VERSION
        }
        block_future = self.trustchain.sign_block(peer, peer.public_key.key_to_bin(),
                                                  block_type=b'tx_init', transaction=tx_dict)
        transaction_future = Future()

        def on_tx_init_signed(future):
            try:
                blocks = future.result()
            except Exception as e:
                self.logger.error("Future resulted in error: %s", e)
                return

            transaction_id = TransactionId(blocks[1].hash)
            transaction = Transaction.from_accepted_trade(accepted_trade, transaction_id)
            transaction.trading_peer = peer
            self.transaction_manager.transaction_repository.add(transaction)
            transaction_future.set_result(transaction)

        block_future.add_done_callback(on_tx_init_signed)
        return transaction_future

    @synchronized
    async def create_new_tx_payment_block(self, peer, payment):
        """
        Create a block on TrustChain with information about a specific payment.

        :param peer: The peer that we did this transaction with
        :param payment: The payment to record
        :type peer: Peer
        :type payment: Payment
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "payment": payment.to_dictionary(),
            "version": self.PROTOCOL_VERSION
        }
        blocks = await self.trustchain.sign_block(peer, peer.public_key.key_to_bin(),
                                                  block_type=b'tx_payment', transaction=tx_dict)
        return blocks[0]

    @synchronized
    async def create_new_tx_done_block(self, peer, ask_order_dict, bid_order_dict, transaction):
        """
        Create a block on TradeChain defining completion of a transaction.

        :param: peer: The peer to send the block to
        :param: ask_order_dict: A dictionary containing the status of the ask order
        :param: bid_order_dict: A dictionary containing the status of the bid order
        :param transaction: The transaction that has been completed
        :type peer: Peer
        :type transaction: Transaction
        :type ask_order_dict: dict
        :type bid_order_dict: dict
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "ask": ask_order_dict,
            "bid": bid_order_dict,
            "tx": transaction.to_block_dictionary(),
            "version": self.PROTOCOL_VERSION
        }
        blocks = await self.trustchain.sign_block(peer, peer.public_key.key_to_bin(),
                                                  block_type=b'tx_done', transaction=tx_dict)
        return blocks[0]

    async def on_tick(self, tick):
        """
        Process an incoming tick.
        :param tick: the received tick to process
        """
        self.logger.debug("%s received from trader %s, asset pair: %s", type(tick),
                          tick.order_id.trader_id.as_hex(), tick.assets)

        if self.is_matchmaker:
            insert_method = self.order_book.insert_ask if isinstance(tick, Ask) else self.order_book.insert_bid

            if not self.order_book.tick_exists(tick.order_id) and tick.order_id not in self.cancelled_orders:
                self.logger.info("Inserting tick %s from %s, asset pair: %s", tick, tick.order_id, tick.assets)
                insert_method(tick)

                if self.order_book.tick_exists(tick.order_id):
                    # Check for new matches against the orders of this node
                    for order in self.order_manager.order_repository.find_all():
                        order_tick_entry = self.order_book.get_tick(order.order_id)
                        if not order.is_valid() or not order_tick_entry:
                            continue

                        self.match(order_tick_entry.tick)

                    # Only after we have matched our own orders, do the matching with other ticks if necessary
                    self.match(tick)

    def send_match_messages(self, matching_ticks, order_id):
        for tick_entry in matching_ticks:
            self.send_match_message(tick_entry.tick, order_id)

    def send_match_message(self, tick, recipient_order_id):
        """
        Send a match message to a specific node
        :param tick: The matched tick
        :param recipient_order_id: The order id of the recipient, matching the tick
        """
        if (recipient_order_id, tick.order_id) in self.sent_matches:
            return
        self.sent_matches.add((recipient_order_id, tick.order_id))

        payload_tup = tick.to_network()

        # Add recipient order number, matched quantity, trader ID of the matched person, our own trader ID and match ID
        my_id = TraderId(self.mid)
        payload_tup += (recipient_order_id.order_number, tick.order_id.trader_id, my_id)

        async def get_address():
            try:
                address = await self.get_address_for_trader(recipient_order_id.trader_id)
            except RuntimeError:
                address = None

            if not address:
                return

            self.logger.info("Sending match message for order id %s and tick order id %s to trader %s",
                             str(recipient_order_id), str(tick.order_id), recipient_order_id.trader_id.as_hex())

            auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
            payload = MatchPayload(*payload_tup).to_pack_list()

            packet = self._ez_pack(self._prefix, MSG_MATCH, [auth, payload])
            self.endpoint.send(address, packet)

        self.register_task('get_address_for_trader_%s-%s' % (recipient_order_id, tick.order_id), get_address,
                           delay=random.uniform(0, self.settings.match_send_interval))

    @lazy_wrapper(MatchPayload)
    def received_match(self, peer, payload):
        """
        We received a match message from a matchmaker.
        """
        self.logger.info("We received a match message from %s for order %s.%s (matched against %s.%s)",
                         payload.matchmaker_trader_id.as_hex(), TraderId(self.mid).as_hex(),
                         payload.recipient_order_number, payload.trader_id.as_hex(), payload.order_number)

        # We got a match, check whether we can respond to this match
        self.update_ip(payload.matchmaker_trader_id, peer.address)
        self.add_matchmaker(peer)

        self.process_match_payload(payload)

    def process_match_payload(self, payload):
        """
        Process a match payload.
        """
        order_id = OrderId(TraderId(self.mid), payload.recipient_order_number)
        order = self.order_manager.order_repository.find_by_id(order_id)
        if not order:
            self.logger.warning("Cannot find order %s in order repository!", order_id)
            return

        if order.status != "open":
            # Send a declined match back so the matchmaker removes the order from their book
            decline_reason = DeclineMatchReason.ORDER_COMPLETED if order.status != "open" \
                else DeclineMatchReason.OTHER

            other_order_id = OrderId(payload.match_trader_id, payload.recipient_order_number)
            self.send_decline_match_message(order, other_order_id, payload.matchmaker_trader_id, decline_reason)
            return

        cache = self.request_cache.get("match", int(payload.recipient_order_number))
        if not cache:
            cache = MatchCache(self, order)
            self.request_cache.add(cache)

        # Add the match to the cache and process it
        cache.add_match(payload)

    async def accept_match_and_propose(self, order, other_order_id):
        """
        Accept an incoming match payload and propose a trade to the counterparty
        """
        if order.available_quantity == 0:
            self.logger.info("No available quantity for order %s - not sending outgoing proposal", order.order_id)

            # Notify the match cache
            cache = self.request_cache.get("match", int(order.order_id.order_number))
            if cache:
                cache.received_decline_trade(other_order_id, DeclinedTradeReason.NO_AVAILABLE_QUANTITY)
            return

        # Pre-actively reserve the available quantity in the order
        propose_quantity = order.available_quantity
        order.reserve_quantity_for_tick(other_order_id, propose_quantity)
        self.order_manager.order_repository.update(order)

        futures = [policy.should_trade(other_order_id.trader_id) for policy in self.clearing_policies]
        results = await gather(*futures, return_exceptions=True)

        should_trade = True
        decline_reason = DeclinedTradeReason.ALREADY_TRADING
        for result in results:
            if isinstance(result, Exception):
                self.logger.info("Clearing policy failed with exception for order %s - %s", order.order_id, result)
                should_trade = False
                break
            elif not result:
                self.logger.info("Clearing policy failed for order %s - %s", order.order_id, result)
                should_trade = False
                break

        if not should_trade:
            # Release the quantity again
            order.release_quantity_for_tick(other_order_id, propose_quantity)
            self.order_manager.order_repository.update(order)

            # Notify the match cache
            cache = self.request_cache.get("match", int(order.order_id.order_number))
            if cache:
                cache.received_decline_trade(other_order_id, decline_reason)
            return

        # Otherwise, propose!
        await self.propose_trade(order, other_order_id, propose_quantity)

    async def propose_trade(self, order, other_order_id, propose_quantity):
        propose_quantity_scaled = order.assets.proportional_downscale(first=propose_quantity)

        propose_trade = Trade.propose(
            TraderId(self.mid),
            order.order_id,
            other_order_id,
            propose_quantity_scaled,
            Timestamp.now()
        )

        # Fetch the address of the target peer (we are not guaranteed to know it at this point since we might have
        # received the order indirectly)
        try:
            address = await self.get_address_for_trader(propose_trade.recipient_order_id.trader_id)
        except RuntimeError:
            address = None

        if address:
            self.send_proposed_trade(propose_trade, address)
        else:
            order.release_quantity_for_tick(other_order_id, propose_quantity)

            # Notify the match cache
            cache = self.request_cache.get("match", int(order.order_id.order_number))
            if cache:
                cache.received_decline_trade(other_order_id, DeclinedTradeReason.ADDRESS_LOOKUP_FAIL)

    def send_decline_match_message(self, order, other_order_id, matchmaker_trader_id, decline_reason):
        address = self.lookup_ip(matchmaker_trader_id)

        self.logger.info("Sending decline match message for order %s to trader %s (ip: %s, port: %s)",
                         order.order_id, matchmaker_trader_id.as_hex(), *address)

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = (TraderId(self.mid), Timestamp.now(), order.order_id.order_number, other_order_id, decline_reason)
        payload = DeclineMatchPayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_MATCH_DECLINE, [auth, payload])
        self.endpoint.send(address, packet)

    @lazy_wrapper(DeclineMatchPayload)
    def received_decline_match(self, _, payload):
        order_id = OrderId(payload.trader_id, payload.order_number)
        matched_order_id = payload.other_order_id
        self.logger.info("Received decline-match message for tick %s matched with %s, reason %s", order_id,
                         matched_order_id, payload.decline_reason)

        # It could be that one or both matched tick(s) have already been removed from the order book by a
        # tx_done block. We have to account for that and act accordingly.
        tick_entry = self.order_book.get_tick(order_id)
        matched_tick_entry = self.order_book.get_tick(matched_order_id)

        if tick_entry and matched_tick_entry:
            tick_entry.block_for_matching(matched_tick_entry.order_id)
            matched_tick_entry.block_for_matching(tick_entry.order_id)

        if matched_tick_entry and (payload.decline_reason == DeclineMatchReason.OTHER_ORDER_COMPLETED or
                                   payload.decline_reason == DeclineMatchReason.OTHER_ORDER_CANCELLED):
            self.order_book.remove_tick(matched_tick_entry.order_id)
            self.order_book.completed_orders.add(matched_tick_entry.order_id)
            self.on_order_completed(matched_tick_entry.order_id)

        if payload.decline_reason == DeclineMatchReason.ORDER_COMPLETED and tick_entry:
            self.order_book.remove_tick(tick_entry.order_id)
            self.order_book.completed_orders.add(tick_entry.order_id)
        elif tick_entry:
            # Search for a new match
            self.match(tick_entry.tick)

    async def cancel_order(self, order_id, broadcast=True):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and (order.status == "open" or order.status == "unverified"):
            self.order_manager.cancel_order(order_id)

            if self.is_matchmaker:
                self.order_book.remove_tick(order_id)

            if order.verified:
                blocks = await self.create_new_cancel_order_block(order)
                if broadcast:
                    self.broadcast_block(blocks[0])

    def on_order_completed(self, order_id):
        """
        An order has been completed. Update the match caches accordingly
        """
        for cache in self.get_match_caches():
            cache.remove_order(order_id)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade, address):
        payload = proposed_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, proposed_trade))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()

        self.logger.debug("Sending proposed trade with own order id %s and other order id %s to trader "
                          "%s, asset pair %s", str(proposed_trade.order_id),
                          str(proposed_trade.recipient_order_id), proposed_trade.recipient_order_id.trader_id.as_hex(),
                          proposed_trade.assets)

        packet = self._ez_pack(self._prefix, MSG_PROPOSED_TRADE, [auth, payload])
        self.endpoint.send(address, packet)

    def check_trade_payload_validity(self, payload):
        if bytes(payload.recipient_order_id.trader_id) != self.mid:
            return False, "this payload is not meant for this node"

        if not self.order_manager.order_repository.find_by_id(payload.recipient_order_id):
            return False, "order does not exist"

        return True, ''

    def get_outstanding_proposals(self, order_id, partner_order_id):
        return [(proposal_id, cache) for proposal_id, cache in self.request_cache._identifiers.items()
                if isinstance(cache, ProposedTradeRequestCache)
                and cache.proposed_trade.order_id == order_id
                and cache.proposed_trade.recipient_order_id == partner_order_id]

    def get_match_caches(self):
        """
        Return all match caches.
        """
        return [cache for cache in self.request_cache._identifiers.values() if isinstance(cache, MatchCache)]

    @lazy_wrapper(TradePayload)
    async def received_proposed_trade(self, peer, payload):
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of proposed trade payload failed: %s", validation[1])
            return

        proposed_trade = ProposedTrade.from_network(payload)

        self.logger.debug("Proposed trade received from trader %s for order %s",
                          proposed_trade.trader_id.as_hex(), str(proposed_trade.recipient_order_id))

        # Update the known IP address of the sender of this proposed trade
        self.update_ip(proposed_trade.trader_id, peer.address)

        order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

        # We can have a race condition where an ask/bid is created simultaneously on two different nodes.
        # In this case, both nodes first send a proposed trade and then receive a proposed trade from the other
        # node. To counter this, we have the following check.
        outstanding_proposals = self.get_outstanding_proposals(order.order_id, proposed_trade.order_id)
        if outstanding_proposals:
            # Discard current outstanding proposed trade and continue
            for proposal_id, _ in outstanding_proposals:
                request = self.request_cache.get("proposed-trade", int(proposal_id.split(':')[1]))
                eq_and_ask = order.assets.first.amount == request.proposed_trade.assets.first.amount and order.is_ask()
                have_largest_order = order.assets.first.amount > request.proposed_trade.assets.first.amount
                if eq_and_ask or have_largest_order:
                    self.logger.info("Discarding current outstanding proposals for order %s", proposed_trade.order_id)
                    self.request_cache.pop("proposed-trade", int(proposal_id.split(':')[1]))
                    request.on_timeout()

        if order.available_quantity == 0:
            # No quantity available in this order, decline
            decline_reason = DeclinedTradeReason.ORDER_COMPLETED if order.status == "completed" else DeclinedTradeReason.ORDER_RESERVED
            declined_trade = Trade.decline(TraderId(self.mid), Timestamp.now(), proposed_trade, decline_reason)
            self.send_decline_trade(declined_trade)
            return

        # Pre-actively reserve quantity in the order
        quantity_in_propose = proposed_trade.assets.first.amount
        should_counter = quantity_in_propose > order.available_quantity
        reserve_quantity = min(quantity_in_propose, order.available_quantity)
        order.reserve_quantity_for_tick(proposed_trade.order_id, reserve_quantity)
        self.order_manager.order_repository.update(order)

        result = await self.should_accept_propose_trade(peer, proposed_trade, order)
        should_trade, decline_reason = result
        if not should_trade:
            declined_trade = Trade.decline(TraderId(self.mid), Timestamp.now(), proposed_trade, decline_reason)
            self.logger.debug("Declined trade made for order id: %s and id: %s "
                              "(valid? %s, available quantity of order: %s, reserved: %s, traded: %s), reason: %s",
                              str(declined_trade.order_id), str(declined_trade.recipient_order_id),
                              order.is_valid(), order.available_quantity, order.reserved_quantity,
                              order.traded_quantity, decline_reason)
            self.send_decline_trade(declined_trade)
            order.release_quantity_for_tick(proposed_trade.order_id, reserve_quantity)
            self.order_manager.order_repository.update(order)
        else:
            if not should_counter:  # Enough quantity left
                self.accept_proposed_trade(proposed_trade)
            else:  # Not all quantity can be traded
                new_pair = order.assets.proportional_downscale(first=reserve_quantity)
                counter_trade = Trade.counter(TraderId(self.mid), new_pair, Timestamp.now(), proposed_trade)
                self.logger.debug("Counter trade made with asset pair %s for proposed trade", counter_trade.assets)
                self.send_counter_trade(counter_trade)

    async def should_accept_propose_trade(self, peer, proposed_trade, my_order):
        # First, check some basic conditions
        should_trade = False
        decline_reason = DeclinedTradeReason.OTHER
        if not my_order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif my_order.status == "expired":
            decline_reason = DeclinedTradeReason.ORDER_EXPIRED
        elif my_order.status == "cancelled":
            decline_reason = DeclinedTradeReason.ORDER_CANCELLED
        elif not my_order.has_acceptable_price(proposed_trade.assets):
            self.logger.info("Unacceptable price for order %s - %s vs %s", my_order.order_id,
                             proposed_trade.assets, my_order.assets)
            decline_reason = DeclinedTradeReason.UNACCEPTABLE_PRICE
        else:
            should_trade = True

        if not should_trade:
            return False, decline_reason

        # Invoke the clearing policies.
        futures = [policy.should_trade(proposed_trade.trader_id) for policy in self.clearing_policies]
        results = await gather(*futures, return_exceptions=True)
        should_trade = all([result and not isinstance(result, Exception) for result in results])
        decline_reason = None if should_trade else DeclinedTradeReason.ALREADY_TRADING
        return should_trade, decline_reason

    def send_decline_trade(self, declined_trade):
        payload = declined_trade.to_network()

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = DeclineTradePayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_DECLINED_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(declined_trade.recipient_order_id.trader_id), packet)

    @lazy_wrapper(DeclineTradePayload)
    def received_decline_trade(self, _, payload):
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of decline trade payload failed: %s", validation[1])
            return

        declined_trade = DeclinedTrade.from_network(payload)

        if not self.request_cache.has("proposed-trade", declined_trade.proposal_id):
            self.logger.warning("declined trade cache with id %s not found", declined_trade.proposal_id)
            return

        request = self.request_cache.pop("proposed-trade", declined_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(declined_trade.recipient_order_id)
        proposed_assets = request.proposed_trade.assets
        proposed_owned = proposed_assets.first.amount
        order.release_quantity_for_tick(declined_trade.order_id, proposed_owned)
        self.order_manager.order_repository.update(order)

        # Just remove the tick with the order id of the other party and try to find a new match
        self.logger.debug("Received decline trade (proposal id: %d, reason: %d)",
                          declined_trade.proposal_id, declined_trade.decline_reason)

        other_order_id = OrderId(payload.trader_id, payload.order_number)

        # Update the cache which will inform the related matchmakers
        cache = self.request_cache.get("match", int(order.order_id.order_number))
        if cache:
            cache.received_decline_trade(other_order_id, payload.decline_reason)

        # We want to remove this order from all the other caches too if the order is completed or cancelled
        if payload.decline_reason == DeclinedTradeReason.ORDER_COMPLETED or payload.decline_reason == DeclinedTradeReason.ORDER_CANCELLED:
            for cache in self.get_match_caches():
                cache.remove_order(other_order_id)

    # Counter trade
    def send_counter_trade(self, counter_trade):
        payload = counter_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, counter_trade))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_COUNTER_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(counter_trade.recipient_order_id.trader_id), packet)

    @lazy_wrapper(TradePayload)
    def received_counter_trade(self, _, payload):
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of counter trade payload failed: %s", validation[1])
            return

        counter_trade = CounterTrade.from_network(payload)

        if not self.request_cache.has("proposed-trade", counter_trade.proposal_id):
            self.logger.warning("proposed trade cache with id %s not found", counter_trade.proposal_id)
            return

        request = self.request_cache.pop("proposed-trade", counter_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(counter_trade.recipient_order_id)
        self.logger.info("Received counter trade for order %s (quantity: %d)", order.order_id,
                         counter_trade.assets.first.amount)
        should_decline = True
        decline_reason = 0
        if not order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif not order.has_acceptable_price(counter_trade.assets):
            self.logger.info("Unacceptable price for order %s - %s vs %s", order.order_id,
                             counter_trade.assets, order.assets)
            decline_reason = DeclinedTradeReason.UNACCEPTABLE_PRICE
        else:
            should_decline = False

        if should_decline:
            declined_trade = Trade.decline(TraderId(self.mid), Timestamp.now(), counter_trade, decline_reason)
            self.logger.debug("Declined trade made for order id: %s and id: %s ",
                              str(declined_trade.order_id), str(declined_trade.recipient_order_id))
            self.send_decline_trade(declined_trade)

            # Release the quantity from the tick
            proposed_assets = request.proposed_trade.assets
            proposed_owned = proposed_assets.first.amount

            order.release_quantity_for_tick(declined_trade.recipient_order_id, proposed_owned)
            self.order_manager.order_repository.update(order)
        else:
            proposed_assets = request.proposed_trade.assets
            proposed_owned = proposed_assets.first.amount
            counter_assets = counter_trade.assets
            counter_owned = counter_assets.first.amount

            order.release_quantity_for_tick(counter_trade.order_id, proposed_owned)
            order.reserve_quantity_for_tick(counter_trade.order_id, counter_owned)
            self.order_manager.order_repository.update(order)
            self.accept_proposed_trade(counter_trade)

    def accept_proposed_trade(self, proposed_trade):
        accepted_trade = Trade.accept(TraderId(self.mid), Timestamp.now(), proposed_trade)
        payload = accepted_trade.to_network()

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_ACCEPT_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(proposed_trade.order_id.trader_id), packet)

    @lazy_wrapper(TradePayload)
    async def received_accept_trade(self, peer, payload):
        accepted_trade = AcceptedTrade.from_network(payload)

        if not self.request_cache.has("proposed-trade", accepted_trade.proposal_id):
            self.logger.warning("No proposed-trade cache found for proposal id %d", accepted_trade.proposal_id)
            return

        self.request_cache.pop("proposed-trade", accepted_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(accepted_trade.recipient_order_id)
        if not order:
            return

        incoming_address, outgoing_address = self.get_order_addresses(order)

        # Create a tx_init block to capture that we are going to initiate a transaction
        transaction = await self.create_new_tx_init_block(peer, accepted_trade)
        self.send_wallet_info(transaction, incoming_address, outgoing_address)

    def send_order_status_request(self, order_id):
        self.logger.debug("Sending order status request to trader %s (number: %d)",
                          order_id.trader_id.as_hex(), order_id.order_number)

        request_future = Future()
        cache = self.request_cache.add(OrderStatusRequestCache(self, request_future))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderStatusRequestPayload(TraderId(self.mid), Timestamp.now(), order_id, cache.number).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_ORDER_QUERY, [auth, payload])
        self.endpoint.send(self.lookup_ip(order_id.trader_id), packet)

        return request_future

    @lazy_wrapper(OrderStatusRequestPayload)
    def received_order_status_request(self, peer, payload):
        order = self.order_manager.order_repository.find_by_id(payload.order_id)

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()

        order_payload = list(order.to_network())
        order_payload.append(payload.identifier)
        new_payload = OrderStatusResponsePayload(*order_payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_ORDER_RESPONSE, [auth, new_payload])
        self.endpoint.send(peer.address, packet)

    @lazy_wrapper(OrderStatusResponsePayload)
    def received_order_status(self, _, payload):
        request = self.request_cache.pop("order-status-request", payload.identifier)

        # Convert the order status to a dictionary that is saved on TradeChain
        order_dict = {
            "trader_id": payload.trader_id.as_hex(),
            "order_number": int(payload.order_number),
            "assets": payload.assets.to_dictionary(),
            "traded": payload.traded,
            "timeout": int(payload.timeout),
            "timestamp": int(payload.timestamp),
        }

        get_event_loop().call_soon_threadsafe(request.request_future.set_result, order_dict)

    def send_wallet_info(self, transaction, incoming_address, outgoing_address):
        # Update the transaction with the address information
        transaction.incoming_address = incoming_address
        transaction.outgoing_address = outgoing_address

        self.logger.debug("Sending wallet info to trader %s (incoming address: %s, outgoing address: %s",
                          transaction.partner_order_id.trader_id.as_hex(), incoming_address, outgoing_address)

        payload = (TraderId(self.mid), Timestamp.now(), transaction.transaction_id, incoming_address, outgoing_address)
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()

        new_payload = WalletInfoPayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_WALLET_INFO, [auth, new_payload])
        self.endpoint.send(self.lookup_ip(transaction.partner_order_id.trader_id), packet)

        transaction.sent_wallet_info = True
        self.transaction_manager.transaction_repository.update(transaction)

    @lazy_wrapper(WalletInfoPayload)
    async def received_wallet_info(self, _, payload):
        self.logger.info("Received wallet info from trader %s", payload.trader_id.as_hex())

        transaction = self.transaction_manager.find_by_id(payload.transaction_id)
        transaction.received_wallet_info = True
        if not transaction.trading_peer:
            transaction.trading_peer = self.get_peer_from_mid(bytes(transaction.partner_order_id.trader_id))

        transaction.partner_outgoing_address = payload.outgoing_address
        transaction.partner_incoming_address = payload.incoming_address

        if not transaction.sent_wallet_info:
            order = self.order_manager.order_repository.find_by_id(transaction.order_id)
            incoming_address, outgoing_address = self.get_order_addresses(order)
            self.send_wallet_info(transaction, incoming_address, outgoing_address)
        else:
            self.logger.info("Wallet info exchanged for transaction %s - starting payments",
                             transaction.transaction_id.as_hex())
            self.register_anonymous_task('send_payment_%s' % id(transaction), self.send_payment, transaction)

        self.transaction_manager.transaction_repository.update(transaction)

    async def send_payment(self, transaction):
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)

        transfer_amount = transaction.next_payment(order.is_ask())
        asset_id = transfer_amount.asset_id

        wallet = self.wallets[asset_id]
        if not wallet or not wallet.created:
            raise RuntimeError("No %s wallet present" % asset_id)

        # While this conditional is not very pretty, the alternative is to move all this logic to the wallet which
        # requires the wallet to know about transactions, the market community and IPv8.
        if isinstance(wallet, TrustchainWallet):
            peer = Peer(b64decode(str(transaction.partner_incoming_address)),
                        address=self.lookup_ip(transaction.partner_order_id.trader_id))
            transfer_coro = wallet.transfer(transfer_amount.amount, peer)
        else:
            transfer_coro = wallet.transfer(transfer_amount.amount, str(transaction.partner_incoming_address))

        try:
            txid = await transfer_coro
        except Exception as e:
            # When a payment fails, log the error.
            self.logger.error("Payment of %s to %s failed: (%s) %s", transfer_amount,
                              str(transaction.partner_incoming_address), type(e), e)
            return

        payment = Payment(TraderId(self.mid), transaction.transaction_id, transfer_amount,
                          wallet.get_address(), str(transaction.partner_incoming_address), PaymentId(txid),
                          Timestamp.now())

        # Add it to the transaction
        transaction.add_payment(payment)
        self.transaction_manager.transaction_repository.update(transaction)

        order.add_trade(transaction.partner_order_id, payment.transferred_assets)
        self.order_manager.order_repository.update(order)

        await self.create_new_tx_payment_block(transaction.trading_peer, payment)
        self.logger.info("Payment with id %s acknowledged by counterparty!", payment.payment_id)

    def send_matched_transaction_completed(self, transaction, block):
        """
        Let the matchmaker know that the transaction has been completed.
        :param transaction: The completed transaction.
        :param block: The block created by this peer defining the transaction.
        """
        cache = self.request_cache.get("match", int(transaction.order_id.order_number))
        if cache and cache.order.status != "open":
            # Remove the match request cache
            self.request_cache.pop("match", int(transaction.order_id.order_number))
        elif cache:
            cache.did_trade(transaction, block)

    def received_matched_tx_complete(self, _, data):
        self.logger.debug("Received transaction-completed message as a matchmaker")
        if not self.is_matchmaker:
            return

        _, payload = self._ez_unpack_noauth(HalfBlockPairPayload, data)
        block1, block2 = self.trustchain.get_block_class(payload.type1).from_pair_payload(payload, self.serializer)
        self.trustchain.validate_persist_block(block1)
        self.trustchain.validate_persist_block(block2)

        # Update ticks in order book, release the reserved quantity and find a new match
        tx_dict = block1.transaction
        quantity = tx_dict["tx"]["transferred"]["first"]["amount"]
        self.order_book.update_ticks(tx_dict["ask"], tx_dict["bid"], quantity)
        ask_order_id = OrderId(TraderId(unhexlify(tx_dict["ask"]["trader_id"])),
                               OrderNumber(tx_dict["ask"]["order_number"]))
        bid_order_id = OrderId(TraderId(unhexlify(tx_dict["bid"]["trader_id"])),
                               OrderNumber(tx_dict["bid"]["order_number"]))
        self.match_order_ids([ask_order_id, bid_order_id])

        # Broadcast the pair of blocks
        self.broadcast_block_pair(block1, block2)

        order_id = OrderId(TraderId(unhexlify(tx_dict["tx"]["trader_id"])), OrderNumber(tx_dict["tx"]["order_number"]))
        tick_entry_sender = self.order_book.get_tick(order_id)
        if tick_entry_sender:
            self.match(tick_entry_sender.tick)

    def send_trader_pk_request(self, trader_id):
        if trader_id in self.pk_register:
            return succeed(self.pk_register[trader_id])

        self.logger.debug("Sending public key status request to trader %s", trader_id.as_hex())

        request_future = Future()
        cache = self.request_cache.add(PublicKeyRequestCache(self, trader_id, request_future))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PublicKeyPayload(TraderId(self.mid), Timestamp.now(), cache.number).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_PK_QUERY, [auth, payload])
        self.endpoint.send(self.lookup_ip(trader_id), packet)

        return request_future

    @lazy_wrapper(PublicKeyPayload)
    def received_trader_pk_request(self, peer, payload):
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        new_payload = PublicKeyPayload(TraderId(self.mid), Timestamp.now(), payload.identifier).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_PK_RESPONSE, [auth, new_payload])
        self.endpoint.send(peer.address, packet)

    @lazy_wrapper(PublicKeyPayload)
    def received_trader_pk_response(self, peer, payload):
        request = self.request_cache.pop("pk-request", payload.identifier)
        self.pk_register[request.trader_id] = peer.public_key
        request.request_future.set_result(peer.public_key)


class MarketTestnetCommunity(MarketCommunity):
    """
    This community defines a testnet for the market.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3a6cd2860aa07739ea53c02b6d40a6682e38a4610a76aeacc6c479022502231"
                                 "424b88aac37f4ec1274e3f89fa8d324be08c11c10b63c1b8662be7d602ae0a26457"))
    DB_NAME = 'market_testnet'
