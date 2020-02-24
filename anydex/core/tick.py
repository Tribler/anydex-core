import time

from ipv8.database import database_blob

from anydex.core import MAX_ORDER_TIMEOUT
from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


class Tick(object):
    """
    Abstract tick class for representing a order on another node. This tick is replicating the order sitting on
    the node it belongs to.
    """
    TIME_TOLERANCE = 10 * 1000  # A small tolerance for the timestamp, to account for network delays

    def __init__(self, order_id, assets, timeout, timestamp, is_ask, traded=0):
        """
        Don't use this class directly, use one of the class methods

        :param order_id: A order id to identify the order this tick represents
        :param assets: The assets being sold/bought
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the tick was created
        :param is_ask: A bool to indicate if this tick is an ask
        :param traded: How much assets have been traded already
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        :type traded: int
        """
        self._order_id = order_id
        self._assets = assets
        self._timeout = timeout
        self._timestamp = timestamp
        self._is_ask = is_ask
        self._traded = traded

    @classmethod
    def from_database(cls, data):
        trader_id, order_number, asset1_amount, asset1_type, asset2_amount, asset2_type, timeout, timestamp,\
        is_ask, traded = data

        tick_cls = Ask if is_ask else Bid
        order_id = OrderId(TraderId(trader_id), OrderNumber(order_number))
        return tick_cls(order_id, AssetPair(AssetAmount(asset1_amount, str(asset1_type)),
                                            AssetAmount(asset2_amount, str(asset2_type))),
                        Timeout(timeout), Timestamp(timestamp), traded=traded)

    def to_database(self):
        return (database_blob(bytes(self.order_id.trader_id)), int(self.order_id.order_number),
                self.assets.first.amount, str(self.assets.first.asset_id), self.assets.second.amount,
                str(self.assets.second.asset_id), int(self.timeout), int(self.timestamp), self.is_ask(),
                self.traded)

    @classmethod
    def from_order(cls, order):
        """
        Create a tick from an order

        :param order: The order that this tick represents
        :return: The created tick
        :rtype: Tick
        """
        if order.is_ask():
            return Ask(order.order_id, order.assets, order.timeout, order.timestamp, traded=order.traded_quantity)
        else:
            return Bid(order.order_id, order.assets, order.timeout, order.timestamp, traded=order.traded_quantity)

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @property
    def assets(self):
        """
        :rtype: AssetPair
        """
        return self._assets

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self.assets.price

    @property
    def timeout(self):
        """
        Return when the tick is going to expire
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        Return the timestamp of the order
        :rtype: Timestamp
        """
        return self._timestamp

    def is_ask(self):
        """
        :return: True if this tick is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    @property
    def traded(self):
        """
        Return how much assets have been traded already
        :rtype int
        """
        return self._traded

    @traded.setter
    def traded(self, new_traded):
        """
        :param new_traded: The new amount of traded assets
        :type new_traded: int
        """
        self._traded = new_traded

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return (
            not self._timeout.is_timed_out(self._timestamp)
            and int(time.time() * 1000) >= int(self.timestamp) - self.TIME_TOLERANCE
            and int(self._timeout) <= MAX_ORDER_TIMEOUT
        )

    def to_network(self):
        """
        Return network representation of the tick
        """
        return (
            self._order_id.trader_id,
            self._timestamp,
            self._order_id.order_number,
            self._assets,
            self._timeout,
            self._traded,
            self._is_ask
        )

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this tick.
        """
        return {
            "trader_id": self.order_id.trader_id.as_hex(),
            "order_number": int(self.order_id.order_number),
            "assets": self.assets.to_dictionary(),
            "timeout": int(self.timeout),
            "timestamp": int(self.timestamp),
            "traded": self.traded,
        }

    @classmethod
    def from_network(cls, payload):
        """
        Create a tick from an OrderPayload.
        """
        if payload.is_ask:
            return Ask(OrderId(payload.trader_id, payload.order_number), payload.assets, payload.timeout,
                       payload.timestamp, payload.traded)
        else:
            return Bid(OrderId(payload.trader_id, payload.order_number), payload.assets, payload.timeout,
                       payload.timestamp, payload.traded)

    def __str__(self):
        """
        Return the string representation of this tick.
        """
        return "<%s P: %f, Q: %s, O: %s>" % \
               (self.__class__.__name__, float(self.price.amount), self.assets.first, str(self.order_id))


class Ask(Tick):
    """Represents an ask from a order located on another node."""

    def __init__(self, order_id, assets, timeout, timestamp, traded=0):
        """
        :param order_id: A order id to identify the order this tick represents
        :param assets: The assets being sold/bought
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :param traded: How much assets have been traded already
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type traded: int
        """
        super(Ask, self).__init__(order_id, assets, timeout, timestamp, True, traded=traded)


class Bid(Tick):
    """Represents a bid from a order located on another node."""

    def __init__(self, order_id, assets, timeout, timestamp, traded=0):
        """
        :param order_id: A order id to identify the order this tick represents
        :param assets: The assets being sold/bought
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :param traded: How much assets have been traded already
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type traded: int
        """
        super(Bid, self).__init__(order_id, assets, timeout, timestamp, False, traded=traded)
