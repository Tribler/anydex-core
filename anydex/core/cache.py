import random

from ipv8.messaging.payload_headers import GlobalTimeDistributionPayload
from ipv8.requestcache import NumberCache, RandomNumberCache

from anydex.core import DeclineMatchReason, DeclinedTradeReason
from anydex.core.defs import MSG_MATCH_DONE
from anydex.core.match_queue import MatchPriorityQueue
from anydex.core.order import OrderId
from anydex.trustchain.payload import HalfBlockPairPayload
from anydex.util.asyncio import call_later


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
            dist = GlobalTimeDistributionPayload(global_time)
            payload = HalfBlockPairPayload.from_half_blocks(block, linked_block)
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
