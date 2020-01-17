import logging

from ipv8.taskmanager import TaskManager


class TickEntry(TaskManager):
    """Class for representing a tick in the order book"""

    def __init__(self, tick, price_level):
        """
        :param tick: A tick to represent in the order book
        :param price_level: A price level to place the tick in
        :type tick: Tick
        :type price_level: PriceLevel
        """
        super(TickEntry, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self._tick = tick
        self._price_level = price_level
        self._prev_tick = None
        self._next_tick = None
        self.available_for_matching = 0
        self.update_available_for_matching()
        self._blocked_for_matching = set()

    @property
    def tick(self):
        """
        :rtype: Tick
        """
        return self._tick

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._tick.order_id

    @property
    def assets(self):
        """
        :rtype: AssetPair
        """
        return self._tick.assets

    @property
    def traded(self):
        """
        :rtype int
        """
        return self._tick.traded

    @traded.setter
    def traded(self, new_traded):
        self._tick.traded = new_traded
        self.update_available_for_matching()

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self.assets.price

    def block_for_matching(self, order_id):
        """
        Temporarily block an order id for matching
        """
        if order_id in self._blocked_for_matching:
            self._logger.debug("Not blocking %s for matching; already blocked", order_id)
            return

        def unblock_order_id(unblock_id):
            self._logger.debug("Unblocking order id %s", unblock_id)
            self._blocked_for_matching.remove(unblock_id)

        self._logger.debug("Blocking %s for tick %s", order_id, self.order_id)
        self._blocked_for_matching.add(order_id)
        self.register_task("unblock_%s" % order_id, unblock_order_id, order_id, delay=10)

    def is_blocked_for_matching(self, order_id):
        """
        Return whether the order_id is blocked for matching
        """
        return order_id in self._blocked_for_matching

    def is_valid(self):
        """
        Return if the tick is still valid

        :return: True if valid, False otherwise
        :rtype: bool
        """
        return self._tick.is_valid()

    def price_level(self):
        """
        :return: The price level the tick was placed in
        :rtype: PriceLevel
        """
        return self._price_level

    @property
    def prev_tick(self):
        """
        :rtype: TickEntry
        """
        return self._prev_tick

    @prev_tick.setter
    def prev_tick(self, new_prev_tick):
        """
        :param new_prev_tick: The new previous tick
        :type new_prev_tick: TickEntry
        """
        self._prev_tick = new_prev_tick

    @property
    def next_tick(self):
        """
        :rtype: TickEntry
        """
        return self._next_tick

    @next_tick.setter
    def next_tick(self, new_next_tick):
        """
        :param new_next_tick: The new previous tick
        :type new_next_tick: TickEntry
        """
        self._next_tick = new_next_tick

    def update_available_for_matching(self):
        self.available_for_matching = self._tick._assets.first._amount - self._tick._traded

    def __str__(self):
        """
        format: <quantity>\t@\t<price>
        :rtype: str
        """
        return "%s\t@\t%g %s" % (self._tick.assets.first, self._tick.price.amount,
                                         self._tick.assets.second.asset_id)
