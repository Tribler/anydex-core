import random
from asyncio import Future, get_event_loop, ensure_future
from binascii import hexlify, unhexlify
from functools import wraps

from ipv8.community import Community, lazy_wrapper
from ipv8.dht import DHTError
from ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from ipv8.messaging.payload_headers import GlobalTimeDistributionPayload
from ipv8.peer import Peer
from ipv8.requestcache import NumberCache, RandomNumberCache, RequestCache

from anydex.core import DeclineMatchReason, DeclinedTradeReason, MAX_ORDER_TIMEOUT
from anydex.core.assetpair import AssetPair
from anydex.core.block import MarketBlock
from anydex.core.bloomfilter import BloomFilter
from anydex.core.database import MarketDB
from anydex.core.match_queue import MatchPriorityQueue
from anydex.core.matching_engine import MatchingEngine, PriceTimeStrategy
from anydex.core.message import TraderId
from anydex.core.order import OrderId
from anydex.core.order_manager import OrderManager
from anydex.core.order_repository import DatabaseOrderRepository, MemoryOrderRepository
from anydex.core.orderbook import DatabaseOrderBook, OrderBook
from anydex.core.payload import DeclineMatchPayload, DeclineTradePayload, InfoPayload, MatchPayload, \
    OrderbookSyncPayload, PingPongPayload, TradePayload, CompletedTradePayload, OrderPayload, \
    CancelOrderPayload
from anydex.core.settings import MatchingSettings, SYNC_POLICY_NONE, SYNC_POLICY_NEIGHBOURS,\
    DISSEMINATION_POLICY_NEIGHBOURS, DISSEMINATION_POLICY_RANDOM
from anydex.core.tick import Ask, Bid, Tick
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp
from anydex.core.trade import CounterTrade, DeclinedTrade, ProposedTrade, Trade, StartTrade
from anydex.util.asyncio import call_later


# Message definitions
MSG_CANCEL_ORDER = 5
MSG_ORDER = 6
MSG_MATCH = 7
MSG_MATCH_DECLINE = 9
MSG_PROPOSED_TRADE = 10
MSG_DECLINED_TRADE = 11
MSG_COUNTER_TRADE = 12
MSG_START_TRADE = 13
MSG_BOOK_SYNC = 19
MSG_PING = 20
MSG_PONG = 21
MSG_MATCHED_TRADE_COMPLETE = 22
MSG_COMPLETE_TRADE = 23


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
        self.outstanding_requests = []
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

        if not self.queue.contains_order(other_order_id) and not self.has_outstanding_request_with_order_id(other_order_id):
            self._logger.debug("Adding match payload with own order id %s and other id %s to queue",
                               self.order.order_id, other_order_id)
            self.queue.insert(0, match_payload.assets.price, other_order_id, match_payload.assets.first.amount)

        if not self.schedule_task:
            # Schedule a timer
            self._logger.info("Scheduling batch match of order %s" % str(self.order.order_id))
            self.schedule_task = call_later(self.community.settings.match_window,
                                            self.start_process_matches, ignore_errors=True)
        elif self.schedule_task_done and not self.outstanding_requests:
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
            for _, matches in self.matches.items():
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
        items_processed = 0
        while self.order.available_quantity > 0 and not self.queue.is_empty():
            item = self.queue.delete()
            retries, price, other_order_id, other_quantity = item
            self.outstanding_requests.append(item)
            if retries == 0:
                propose_quantity = min(self.order.available_quantity, other_quantity)
                self.order.reserve_quantity_for_tick(other_order_id, propose_quantity)
                self.community.order_manager.order_repository.update(self.order)
                ensure_future(self.community.accept_match_and_propose(
                    self.order, other_order_id, price, other_quantity, propose_quantity=propose_quantity, should_reserve=False))
            else:
                task_id = "%s-%s" % (self.order.order_id, other_order_id)
                if not self.community.is_pending_task_active(task_id):
                    delay = random.uniform(1, 2)
                    self.community.register_task(task_id, self.community.accept_match_and_propose, self.order, other_order_id, price, other_quantity, delay=delay)
            items_processed += 1

            if items_processed == 20:  # Limit the number of outgoing items when processing
                break

        self._logger.debug("Processed %d items in this batch", items_processed)

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
                self.has_outstanding_request_with_order_id(other_order_id):
            # Add it to the queue again
            outstanding_request = self.get_outstanding_request_with_order_id(other_order_id)
            self._logger.debug("Adding entry (%d, %s, %s, %d) to matching queue again", *outstanding_request)
            self.queue.insert(outstanding_request[0] + 1, outstanding_request[1], outstanding_request[2], outstanding_request[3])
        elif decline_reason == DeclinedTradeReason.NO_AVAILABLE_QUANTITY and \
                self.has_outstanding_request_with_order_id(other_order_id):
            # Re-add the item to the queue, with the same priority
            outstanding_request = self.get_outstanding_request_with_order_id(other_order_id)
            self.queue.insert(outstanding_request[0], outstanding_request[1], outstanding_request[2], outstanding_request[3])

        self.remove_outstanding_requests_with_order_id(other_order_id)

        if self.order.status == "open":
            self.process_match()

    def has_outstanding_request_with_order_id(self, order_id):
        for _, _, item_order_id, _ in self.outstanding_requests:
            if order_id == order_id:
                return True

        return False

    def get_outstanding_request_with_order_id(self, order_id):
        for item in self.outstanding_requests:
            _, _, item_order_id, _ = item
            if order_id == order_id:
                return item

        return None

    def remove_outstanding_requests_with_order_id(self, order_id):
        # Remove outstanding request entries with this order id
        to_remove = []
        for item in self.outstanding_requests:
            _, _, item_order_id, _ = item
            if item_order_id == order_id:
                to_remove.append(item)

        for item in to_remove:
            self.outstanding_requests.remove(item)

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

    def did_trade(self, trade, trade_id):
        """
        We just performed a trade with a counterparty.
        """
        other_order_id = trade.order_id
        self.remove_outstanding_requests_with_order_id(other_order_id)
        if other_order_id not in self.matches:
            return

        self.received_responses_ids.add(other_order_id)

        for match_payload in self.matches[other_order_id]:
            self._logger.info("Sending transaction completed (order %s) to matchmaker %s", trade.order_id, match_payload.matchmaker_trader_id.as_hex())

            auth = BinMemberAuthenticationPayload(self.community.my_peer.public_key.key_to_bin()).to_pack_list()
            payload_content = trade.to_network() + (trade_id,)
            payload = CompletedTradePayload(*payload_content).to_pack_list()
            packet = self.community._ez_pack(self.community._prefix, MSG_MATCHED_TRADE_COMPLETE, [auth, payload])
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

    @property
    def timeout_delay(self):
        return 5.0

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


class MarketCommunity(Community):
    """
    Community for order matching.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3ab5bb7dc5a3a61de442585122b24c9f752469a212dc6d8ffa3d42bbf9c2f8d10"
                                 "ba569b270f615ef78aeff0547f38745d22af268037ad64935ee7c054b7921b23b"))
    PROTOCOL_VERSION = 4
    BLOCK_CLASS = MarketBlock
    DB_NAME = 'market'

    def __init__(self, *args, **kwargs):
        self.trading_engine = kwargs.pop('trading_engine')
        self.trading_engine.matching_community = self
        self.is_matchmaker = kwargs.pop('is_matchmaker', True)
        self.dht = kwargs.pop('dht', None)
        self.use_database = kwargs.pop('use_database', True)
        self.settings = MatchingSettings()
        self.fixed_broadcast_set = []  # Optional list of fixed peers that will receive market messages

        db_working_dir = kwargs.pop('working_directory', '')

        Community.__init__(self, *args, **kwargs)

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
        self.sync_lc = None
        self.new_orders_relayed = set()
        self.cancel_orders_relayed = set()
        self.complete_orders_relayed = set()

        self.num_received_cancel_orders = 0

        self.num_received_orders = 0
        self.num_received_match = 0
        self.num_received_match_decline = 0
        self.num_received_proposed_trade = 0
        self.num_received_declined_trade = 0
        self.num_received_counter_trade = 0
        self.num_received_complete_trade = 0

        self.negotiation_stats = {}

        self.fixed_broadcast_set = []  # Used if we need to broadcast to a fixed set of other peers

        if self.use_database:
            order_repository = DatabaseOrderRepository(self.mid, self.market_database)
        else:
            order_repository = MemoryOrderRepository(self.mid)

        self.order_manager = OrderManager(order_repository)

        if self.is_matchmaker:
            self.enable_matchmaker()
            self.set_sync_policy(self.settings.sync_policy)

        # Register messages
        self.decode_map.update({
            chr(MSG_CANCEL_ORDER): self.received_cancel_order,
            chr(MSG_ORDER): self.received_order,
            chr(MSG_MATCH): self.received_match,
            chr(MSG_MATCH_DECLINE): self.received_decline_match,
            chr(MSG_PROPOSED_TRADE): self.received_proposed_trade,
            chr(MSG_DECLINED_TRADE): self.received_decline_trade,
            chr(MSG_COUNTER_TRADE): self.received_counter_trade,
            chr(MSG_START_TRADE): self.received_start_trade,
            chr(MSG_BOOK_SYNC): self.received_orderbook_sync,
            chr(MSG_PING): self.received_ping,
            chr(MSG_PONG): self.received_pong,
            chr(MSG_MATCHED_TRADE_COMPLETE): self.received_matched_tx_complete,
            chr(MSG_COMPLETE_TRADE): self.received_trade_complete_broadcast,
        })

        self.logger.info("Market community initialized with mid %s", hexlify(self.mid))

    def set_sync_policy(self, policy):
        """
        Set a specific sync policy.
        """
        self.settings.sync_policy = policy
        if policy == SYNC_POLICY_NONE:
            if self.sync_lc:
                self.sync_lc.stop()
                self.sync_lc = None
        elif policy == SYNC_POLICY_NEIGHBOURS:
            if not self.sync_lc:
                self.sync_lc = LoopingCall(self.sync_orderbook)

                # Do not start at the same time
                reactor.callLater(random.uniform(0, 10), self.sync_lc.start, self.settings.sync_interval)

    def sync_orderbook(self):
        """
        Sync the orderbook with another peer, according to a policy.
        """
        if not self.is_matchmaker:
            return

        sync_peer = None
        if self.fixed_broadcast_set:
            sync_peer = random.choice(list(self.fixed_broadcast_set))
        elif self.matchmakers:
            sync_peer = random.choice(list(self.matchmakers))

        if sync_peer and sync_peer.address not in self.network.blacklist:
            self.send_orderbook_sync(sync_peer)

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
        self.parse_extra_bytes(payload.extra_bytes, peer)

    def introduction_response_callback(self, peer, dist, payload):
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

    def on_ask_timeout(self, future_ask):
        pass

    def on_bid_timeout(self, future_bid):
        pass

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
            self.send_order(entry.tick, peer.address)

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

    def broadcast_order(self, order):
        payload_args = order.to_network()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderPayload(*payload_args).to_pack_list()

        send_peers = []
        packet = self._ez_pack(self._prefix, MSG_ORDER, [auth, payload])
        if self.settings.dissemination_policy == DISSEMINATION_POLICY_NEIGHBOURS:
            if self.fixed_broadcast_set:
                send_peers = self.fixed_broadcast_set
            else:
                send_peers = random.sample(self.network.verified_peers,
                                           min(len(self.network.verified_peers), self.settings.fanout))
        elif self.settings.dissemination_policy == DISSEMINATION_POLICY_RANDOM:
            send_peers = random.sample(list(self.matchmakers), min(self.settings.fanout, len(self.matchmakers)))

        order.broadcast_peers = send_peers

        for peer in send_peers:
            self.endpoint.send(peer.address, packet)

    def broadcast_trade_completed(self, trade, trade_id):
        self.logger.debug("Broadcasting trade complete (%s and %s)", trade.order_id, trade.recipient_order_id)

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        global_time = self.claim_global_time()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
        payload_content = trade.to_network() + (trade_id,)
        payload = CompletedTradePayload(*payload_content).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_COMPLETE_TRADE, [auth, dist, payload])
        send_peers = []

        order = self.order_manager.order_repository.find_by_id(
            trade.order_id) or self.order_manager.order_repository.find_by_id(trade.recipient_order_id)
        if order.broadcast_peers:
            send_peers = order.broadcast_peers
        elif self.settings.dissemination_policy == DISSEMINATION_POLICY_NEIGHBOURS:
            if self.fixed_broadcast_set:
                send_peers = self.fixed_broadcast_set
            else:
                send_peers = random.sample(self.network.verified_peers,
                                           min(len(self.network.verified_peers), self.settings.fanout))
        elif self.settings.dissemination_policy == DISSEMINATION_POLICY_RANDOM:
            send_peers = random.sample(list(self.matchmakers),
                                       min(self.settings.fanout, len(self.matchmakers)))

        # Also process it locally if you are a matchmaker
        if self.is_matchmaker:
            # Update ticks in order book, release the reserved quantity and find a new match
            quantity = trade.assets.first.amount
            completed = self.order_book.update_ticks(trade.order_id, trade.recipient_order_id, quantity, trade_id)
            for completed_order_id in completed:
                self.on_order_completed(completed_order_id)
            self.match_order_ids([trade.order_id, trade.recipient_order_id])

        for peer in send_peers:
            self.endpoint.send(peer.address, packet)

    def send_order(self, order, address):
        payload_args = order.to_network()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderPayload(*payload_args).to_pack_list()
        packet = self._ez_pack(self._prefix, MSG_ORDER, [auth, payload])
        self.endpoint.send(address, packet)

    def verify_offer_creation(self, assets, timeout):
        """
        Verify whether we are creating a valid order.
        This method raises a RuntimeError if the created order is not valid.
        """
        if assets.first.asset_id == assets.second.asset_id:
            raise RuntimeError("You cannot trade between the same wallet")

        if timeout < 0:
            raise RuntimeError("The timeout for this order should be positive")

        if timeout > MAX_ORDER_TIMEOUT:
            raise RuntimeError("The timeout for this order should be less than a day")

    def create_ask(self, assets, timeout):
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
        self.order_manager.order_repository.update(order)

        if self.is_matchmaker:
            tick = Tick.from_order(order)
            self.order_book.insert_ask(tick).add_done_callback(self.on_ask_timeout)
            self.match(tick)

        # Broadcast the order
        self.broadcast_order(order)

        self.logger.info("Ask created with asset pair %s", assets)
        return order

    def create_bid(self, assets, timeout):
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
        self.order_manager.order_repository.update(order)

        if self.is_matchmaker:
            tick = Tick.from_order(order)
            self.order_book.insert_bid(tick).add_done_callback(self.on_bid_timeout)
            self.match(tick)

        # Broadcast the order
        self.broadcast_order(order)

        self.logger.info("Bid created with asset pair %s", assets)
        return order

    def add_matchmaker(self, matchmaker):
        """
        Add a matchmaker to the set of known matchmakers. Also check whether there are pending deferreds.
        """
        if matchmaker.public_key.key_to_bin() == self.my_peer.public_key.key_to_bin():
            return

        self.matchmakers.add(matchmaker)

    def on_tick(self, tick):
        """
        Process an incoming tick.
        :param tick: the received tick to process
        """
        self.logger.debug("%s received from trader %s, asset pair: %s", type(tick),
                          tick.order_id.trader_id.as_hex(), tick.assets)

        if self.is_matchmaker:
            insert_method = self.order_book.insert_ask if isinstance(tick, Ask) else self.order_book.insert_bid
            timeout_method = self.on_ask_timeout if isinstance(tick, Ask) else self.on_bid_timeout

            if not self.order_book.tick_exists(tick.order_id) and tick.order_id not in self.cancelled_orders:
                self.logger.info("Inserting tick %s from %s, asset pair: %s", tick, tick.order_id, tick.assets)
                insert_method(tick).add_done_callback(timeout_method)

                if self.order_book.tick_exists(tick.order_id):
                    # Check for new matches against the orders of this node
                    for order in self.order_manager.order_repository.find_all():
                        order_tick_entry = self.order_book.get_tick(order.order_id)
                        if not order.is_valid() or not order_tick_entry:
                            continue

                        if self.settings.first_matches_own_orders:
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

    def received_cancel_order(self, source_address, data):
        """
        We received an order cancellation from the network.
        """
        self.num_received_cancel_orders += 1
        auth, dist, payload = self._ez_unpack_auth(CancelOrderPayload, data)

        order_id = OrderId(payload.trader_id, payload.order_number)

        if self.is_matchmaker and self.order_book.tick_exists(order_id):
            self.order_book.remove_tick(order_id)
            self.cancelled_orders.add(order_id)

    @lazy_wrapper(OrderPayload)
    def received_order(self, peer, payload):
        self.num_received_orders += 1
        tick = Ask.from_network(payload) if payload.is_ask else Bid.from_network(payload)
        self.logger.debug("Received order from %s:%d, order %s", peer.address[0], peer.address[1], peer)
        self.on_tick(tick)

    def received_trade_complete_broadcast(self, source_address, data):
        """
        We received a trade completion from the network.
        :param source_address: The peer we received this payload from.
        :param data: The binary data we received.
        """
        self.num_received_complete_trade += 1
        auth, dist, payload = self._ez_unpack_auth(CompletedTradePayload, data)

        if self.is_matchmaker:
            # Update ticks in order book, release the reserved quantity and find a new match
            quantity = payload.assets.first.amount
            order_id1 = OrderId(TraderId(payload.trader_id), payload.order_number)
            order_id2 = payload.recipient_order_id
            completed = self.order_book.update_ticks(order_id1, order_id2, quantity, payload.trade_id)
            for completed_order_id in completed:
                self.on_order_completed(completed_order_id)
            self.match_order_ids([order_id1, order_id2])

    @lazy_wrapper(MatchPayload)
    def received_match(self, peer, payload):
        """
        We received a match message from a matchmaker.
        """
        self.num_received_match += 1

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

    async def accept_match_and_propose(self, order, other_order_id, other_price, other_quantity, propose_quantity=None, should_reserve=True):
        """
        Accept an incoming match payload and propose a trade to the counterparty
        """
        if should_reserve:
            if order.available_quantity == 0:
                self.logger.info("No available quantity for order %s - not sending outgoing proposal", order.order_id)

                # Notify the match cache
                cache = self.request_cache.get("match", int(order.order_id.order_number))
                if cache:
                    cache.received_decline_trade(other_order_id, DeclinedTradeReason.NO_AVAILABLE_QUANTITY)
                return

            propose_quantity = min(order.available_quantity, other_quantity)
            order.reserve_quantity_for_tick(other_order_id, propose_quantity)
            self.order_manager.order_repository.update(order)

        await self.propose_trade(order, other_order_id, propose_quantity, other_price)

    async def propose_trade(self, order, other_order_id, propose_quantity, other_price):
        # We know that the price of the other order is at least acceptable
        propose_quantity_scaled = AssetPair.from_price(other_price, propose_quantity)

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
            if order.order_id not in self.negotiation_stats:
                self.negotiation_stats[order.order_id] = {"started": 0}
            self.negotiation_stats[order.order_id]["started"] += 1
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
        self.num_received_match_decline += 1
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

    def cancel_order(self, order_id, broadcast=True):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and (order.status == "open" or order.status == "unverified"):
            self.order_manager.cancel_order(order_id)

            if self.is_matchmaker:
                self.order_book.remove_tick(order_id)

            if broadcast:
                auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
                global_time = self.claim_global_time()
                dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
                payload = CancelOrderPayload(order.order_id.trader_id, order.timestamp,
                                             order.order_id.order_number).to_pack_list()
                packet = self._ez_pack(self._prefix, MSG_CANCEL_ORDER, [auth, dist, payload])

                send_peers = []
                if order.broadcast_peers:
                    send_peers = order.broadcast_peers
                elif self.settings.dissemination_policy == DISSEMINATION_POLICY_NEIGHBOURS:
                    if self.fixed_broadcast_set:
                        send_peers = self.fixed_broadcast_set
                    else:
                        send_peers = random.sample(self.network.verified_peers,
                                                   min(len(self.network.verified_peers), self.settings.fanout))
                elif self.settings.dissemination_policy == DISSEMINATION_POLICY_RANDOM:
                    send_peers = random.sample(list(self.matchmakers),
                                               min(self.settings.fanout, len(self.matchmakers)))

                for peer in send_peers:
                    self.endpoint.send(peer.address, packet)

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

        self.logger.info("Sending proposed trade with own order id %s and other order id %s to trader "
                         "%s, asset pair %s", str(proposed_trade.order_id),
                         str(proposed_trade.recipient_order_id), proposed_trade.recipient_order_id.trader_id.as_hex(),
                         proposed_trade.assets)

        packet = self._ez_pack(self._prefix, MSG_PROPOSED_TRADE, [auth, payload])
        self.endpoint.send(address, packet, always_succeed=True)

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
    def received_proposed_trade(self, peer, payload):
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of proposed trade payload failed: %s", validation[1])
            return

        proposed_trade = ProposedTrade.from_network(payload)

        self.logger.debug("Proposed trade received from trader %s for order %s (id: %s)",
                          proposed_trade.trader_id.as_hex(), str(proposed_trade.recipient_order_id),
                          proposed_trade.proposal_id)

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
                if order.is_ask():
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

        should_trade, decline_reason = self.should_accept_propose_trade(peer, proposed_trade, order)
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
                self.start_trade(proposed_trade)
            else:  # Not all quantity can be traded
                new_pair = order.assets.proportional_downscale(first=reserve_quantity)
                counter_trade = Trade.counter(TraderId(self.mid), new_pair, Timestamp.now(), proposed_trade)
                self.logger.debug("Counter trade made with asset pair %s for proposed trade", counter_trade.assets)
                self.send_counter_trade(counter_trade)

    def should_accept_propose_trade(self, peer, proposed_trade, my_order):
        # First, check some basic conditions
        should_trade = False
        decline_reason = DeclinedTradeReason.OTHER
        if not my_order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif my_order.status == "expired":
            decline_reason = DeclinedTradeReason.ORDER_EXPIRED
        elif my_order.status == "cancelled":
            decline_reason = DeclinedTradeReason.ORDER_CANCELLED
        # elif not my_order.has_acceptable_price(proposed_trade.assets):
        #     self.logger.info("Unacceptable price for order %s - %s vs %s", my_order.order_id,
        #                      proposed_trade.assets, my_order.assets)
        #     decline_reason = DeclinedTradeReason.UNACCEPTABLE_PRICE
        else:
            should_trade = True

        if not should_trade:
            return False, decline_reason

        decline_reason = None
        return should_trade, decline_reason

    def send_decline_trade(self, declined_trade):
        payload = declined_trade.to_network()

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = DeclineTradePayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_DECLINED_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(declined_trade.recipient_order_id.trader_id), packet, always_succeed=True)

    @lazy_wrapper(DeclineTradePayload)
    def received_decline_trade(self, _, payload):
        self.num_received_declined_trade += 1
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
        self.endpoint.send(self.lookup_ip(counter_trade.recipient_order_id.trader_id), packet, always_succeed=True)

    @lazy_wrapper(TradePayload)
    def received_counter_trade(self, _, payload):
        self.num_received_counter_trade += 1
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
            order.release_quantity_for_tick(counter_trade.order_id, request.proposed_trade.assets.first.amount)
            order.reserve_quantity_for_tick(counter_trade.order_id, counter_trade.assets.first.amount)
            self.order_manager.order_repository.update(order)

            # Trade!
            self.start_trade(counter_trade)

    # Trade
    def start_trade(self, proposed_trade):
        self.logger.info("Starting trade for orders %s and %s", proposed_trade.order_id,
                         proposed_trade.recipient_order_id)
        self.trading_engine.trade(proposed_trade)

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        start_trade = StartTrade.start(TraderId(self.mid), proposed_trade.assets, Timestamp.now(), proposed_trade)
        payload = TradePayload(*start_trade.to_network()).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_START_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(proposed_trade.order_id.trader_id), packet, always_succeed=True)

    @lazy_wrapper(TradePayload)
    def received_start_trade(self, peer, payload):
        self._logger.info("Received start trade from trader %s" % payload.trader_id.as_hex())
        if not self.request_cache.has(u"proposed-trade", payload.proposal_id):
            self._logger.warning("Do not have propose trade cache for proposal %s!", payload.proposal_id)
            return

        # The recipient_order_id in the start_transaction message is our own order
        order = self.order_manager.order_repository.find_by_id(payload.recipient_order_id)
        if not order:
            self._logger.warning("Recipient order in start trade payload is not ours!")
            return

        self.request_cache.pop(u"proposed-trade", payload.proposal_id)

        self.trading_engine.trade(StartTrade.from_network(payload))

    def on_trade_completed(self, trade, trade_id):
        """
        A trade has been completed. Broadcast details of the trade around the network.
        """
        order = self.order_manager.order_repository.find_by_id(trade.recipient_order_id)
        order.add_trade(trade.order_id, trade.assets.first)

        # Update the cache and inform the matchmakers
        cache = self.request_cache.get(u"match", int(order.order_id.order_number))
        if cache:
            cache.did_trade(trade, trade_id)

        # Let the rest of the network know
        self.broadcast_trade_completed(trade, trade_id)

    @lazy_wrapper(CompletedTradePayload)
    def received_matched_tx_complete(self, peer, payload):
        self.num_received_complete_trade += 1
        self.logger.debug("Received transaction-completed message as a matchmaker")
        if not self.is_matchmaker:
            return

        # Update ticks in order book, release the reserved quantity and find a new match
        quantity = payload.assets.first.amount
        order_id1 = OrderId(TraderId(payload.trader_id), payload.order_number)
        order_id2 = payload.recipient_order_id
        completed = self.order_book.update_ticks(order_id1, order_id2, quantity, payload.trade_id)
        for completed_order_id in completed:
            self.on_order_completed(completed_order_id)

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


class MarketTestnetCommunity(MarketCommunity):
    """
    This community defines a testnet for the market.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3a6cd2860aa07739ea53c02b6d40a6682e38a4610a76aeacc6c479022502231"
                                 "424b88aac37f4ec1274e3f89fa8d324be08c11c10b63c1b8662be7d602ae0a26457"))
    DB_NAME = 'market_testnet'
