import logging

from ipv8.database import database_blob

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


class TickWasNotReserved(Exception):
    """Used for throwing exception when a tick was not reserved"""
    pass


class OrderNumber(object):
    """Immutable class for representing the number of an order."""

    def __init__(self, order_number):
        """
        :param order_number: Integer representing the number of an order
        :type order_number: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(OrderNumber, self).__init__()

        if not isinstance(order_number, int):
            raise ValueError("Order number must be an integer")

        self.order_number = order_number

    def __int__(self):
        return self.order_number

    def __str__(self):
        return "%s" % self.order_number

    def __eq__(self, other):
        return self.order_number == other.order_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.order_number)


class OrderId(object):
    """Immutable class for representing the id of an order."""

    def __init__(self, trader_id, order_number):
        """
        :param trader_id: The trader id who created the order
        :param order_number: The number of the order created
        :type trader_id: TraderId
        :type order_number: OrderNumber
        """
        super(OrderId, self).__init__()

        self.trader_id = trader_id
        self.order_number = order_number
        self._hash = hash((self.trader_id, self.order_number))

    def __str__(self):
        """
        format: <trader_id>.<order_number>
        """
        return "%s.%d" % (self.trader_id.as_hex(), self.order_number)

    def __bytes__(self):
        return b"%s.%d" % (self.trader_id.as_hex().encode('utf-8'), self.order_number)

    def __eq__(self, other):
        return self.trader_id == other.trader_id and self.order_number == other.order_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._hash


class Order(object):
    """Class for representing an ask or a bid created by the user"""

    def __init__(self, order_id, assets, timeout, timestamp, is_ask):
        """
        :param order_id: An order id to identify the order
        :param assets: The assets to exchange in this order
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the order was created
        :param is_ask: A bool to indicate if this order is an ask
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        """
        super(Order, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._order_id = order_id
        self._assets = assets
        self._reserved_quantity = 0
        self._traded_quantity = 0
        self._received_quantity = 0
        self._timeout = timeout
        self._timestamp = timestamp
        self._completed_timestamp = None
        self._is_ask = is_ask
        self._reserved_ticks = {}
        self._cancelled = False
        self._verified = False
        self.broadcast_peers = []

    @classmethod
    def from_database(cls, data, reserved_ticks):
        """
        Create an Order object based on information in the database.
        """
        (trader_id, order_number, asset1_amount, asset1_type, asset2_amount, asset2_type, traded_quantity,
         received_quantity, timeout, order_timestamp, completed_timestamp, is_ask, cancelled, verified) = data

        order_id = OrderId(TraderId(bytes(trader_id)), OrderNumber(order_number))
        order = cls(order_id, AssetPair(AssetAmount(asset1_amount, asset1_type.decode()),
                                        AssetAmount(asset2_amount, asset2_type.decode())),
                    Timeout(timeout), Timestamp(order_timestamp), bool(is_ask))
        order._traded_quantity = traded_quantity
        order._received_quantity = received_quantity
        order._cancelled = bool(cancelled)
        order._verified = verified
        if completed_timestamp:
            order._completed_timestamp = Timestamp(completed_timestamp)

        for reserved_order_id, quantity in reserved_ticks:
            order.reserved_ticks[reserved_order_id] = quantity
            order._reserved_quantity += quantity

        return order

    def to_database(self):
        """
        Returns a database representation of an Order object.
        :rtype: tuple
        """
        completed_timestamp = int(self.completed_timestamp) if self.completed_timestamp else None
        return (database_blob(bytes(self.order_id.trader_id)), str(self.order_id.order_number),
                self.assets.first.amount, self.assets.first.asset_id, self.assets.second.amount,
                self.assets.second.asset_id, self.traded_quantity, self._received_quantity,
                int(self.timeout), int(self.timestamp), completed_timestamp, self.is_ask(), self._cancelled,
                self._verified)

    @property
    def reserved_ticks(self):
        """
        :rtype: Dictionary[OrderId: int]
        """
        return self._reserved_ticks

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
    def total_quantity(self):
        """
        Return the total amount of assets.
        :rtype: long
        """
        return self.assets.first.amount

    @property
    def available_quantity(self):
        """
        Return the quantity that is not reserved
        :rtype: long
        """
        return self.total_quantity - self._reserved_quantity - self._traded_quantity

    @property
    def reserved_quantity(self):
        """
        Return the reserved quantity of the order
        :rtype: long
        """
        return self._reserved_quantity

    @property
    def traded_quantity(self):
        """
        Return the traded quantity of the order
        :rtype: long
        """
        return self._traded_quantity

    @property
    def timeout(self):
        """
        Return when the order is going to expire
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp

    @property
    def completed_timestamp(self):
        """
        :return: the timestamp of completion of this order, None if this order is not completed (yet).
        :rtype: Timestamp
        """
        return self._completed_timestamp

    def is_ask(self):
        """
        :return: True if message is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    @property
    def cancelled(self):
        """
        :return: whether the order has been cancelled or not.
        :rtype: bool
        """
        return self._cancelled

    @property
    def verified(self):
        """
        :return: whether the order has been verified by an external matchmaker or not.
        :rtype: bool
        """
        return self._verified

    def is_complete(self):
        """
        :return: True if the order is completed. We consider the order completed if we have received the assets
        we are interested in.
        :rtype: bool
        """
        return self._traded_quantity >= self.assets.first.amount and self._received_quantity >= self.assets.second.amount

    @property
    def status(self):
        """
        Return the status of this order. Can be one of these: "open", "completed", "expired" or "cancelled"
        :return: The status of this order
        :rtype: str
        """
        if not self.verified:
            return "unverified"
        if self._cancelled:
            return "cancelled"
        elif self.is_complete():
            return "completed"
        elif self._timeout.is_timed_out(self._timestamp):
            return "expired"
        return "open"

    def has_acceptable_price(self, proposal_assets):
        """
        Return whether an incoming trade proposal has an acceptable price.
        :rtype: bool
        """
        my_price = self.assets.price
        other_price = proposal_assets.price
        return (self.is_ask() and (
                    my_price <= other_price or abs(float(my_price.frac - other_price.frac)) < 0.0001)) or (
                           not self.is_ask() and (
                               my_price >= other_price or abs(float(my_price.frac - other_price.frac)) < 0.0001))

    def set_verified(self):
        """
        Mark the order as verified.
        """
        self._verified = True

    def reserve_quantity_for_tick(self, order_id, quantity):
        """
        :param order_id: The order id from another peer that the quantity needs to be reserved for
        :param quantity: The quantity to reserve
        :type order_id: OrderId
        :type quantity: int
        :return: True if the quantity was reserved, False otherwise
        :rtype: bool
        """
        if self.available_quantity >= quantity:
            self._reserved_quantity += quantity
            if order_id not in self._reserved_ticks:
                self._reserved_ticks[order_id] = quantity
            else:
                self._reserved_ticks[order_id] += quantity
        else:
            raise ValueError("Order %s does not have enough available quantity for reservation", self.order_id)

        self._logger.debug("Reserved %d quantity for order id %s (own order id: %s),"
                           "total quantity: %d, traded quantity: %d, reserved quantity: %d",
                           quantity, str(order_id), str(self.order_id), self.total_quantity, self.traded_quantity,
                           self.reserved_quantity)

    def release_quantity_for_tick(self, order_id, quantity):
        """
        Release all quantity for a specific tick.
        :param order_id: The order id from another peer that the quantity needs to be released for
        :type order_id: OrderId
        :raises TickWasNotReserved: Thrown when the tick was not reserved first
        """
        if order_id not in self._reserved_ticks:
            raise TickWasNotReserved()

        if self._reserved_quantity >= quantity:
            self._reserved_quantity -= quantity
            self._reserved_ticks[order_id] -= quantity
            assert self.available_quantity >= 0, str(self.available_quantity)

            if self._reserved_ticks[order_id] <= 0:  # Remove the quantity if it's zero
                del self._reserved_ticks[order_id]
        else:
            raise ValueError("Not enough reserved quantity for order id %s" % order_id)

        self._logger.debug("Released quantity for order id %s (own order id: %s),"
                           "total quantity: %d, traded quantity: %d, reserved quantity: %d",
                           str(order_id), str(self.order_id), self.total_quantity, self.traded_quantity,
                           self.reserved_quantity)

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(self._timestamp) and not self._cancelled

    def cancel(self):
        self._cancelled = True

    def add_trade(self, other_order_id, transferred_assets):
        self._logger.debug("Adding trade for order %s with quantity %s (other id: %s)",
                           str(self.order_id), transferred_assets, str(other_order_id))

        if transferred_assets.asset_id == self.assets.first.asset_id:
            self._traded_quantity += transferred_assets.amount
            self.release_quantity_for_tick(other_order_id, transferred_assets.amount)
        else:
            self._received_quantity += transferred_assets.amount

        if self.is_complete():
            self._completed_timestamp = Timestamp.now()

    def to_network(self):
        """
        Return network representation of the order
        """
        return (
            self._order_id.trader_id,
            self._timestamp,
            self._order_id.order_number,
            self._assets,
            self._timeout,
            self._traded_quantity
        )

    def to_dictionary(self):
        """
        Return a dictionary representation of this order.
        """
        completed_timestamp = int(self.completed_timestamp) if self.completed_timestamp else None
        return {
            "trader_id": self.order_id.trader_id.as_hex(),
            "order_number": int(self.order_id.order_number),
            "assets": self.assets.to_dictionary(),
            "reserved_quantity": self.reserved_quantity,
            "traded": self.traded_quantity,
            "timeout": int(self.timeout),
            "timestamp": int(self.timestamp),
            "completed_timestamp": completed_timestamp,
            "is_ask": self.is_ask(),
            "cancelled": self.cancelled,
            "status": self.status
        }

    def to_status_dictionary(self):
        """
        Return a dictionary representation of this order (suitable for saving on the TrustChain)
        """
        return {
            "trader_id": self.order_id.trader_id.as_hex(),
            "order_number": int(self.order_id.order_number),
            "assets": self.assets.to_dictionary(),
            "traded": self.traded_quantity,
            "timeout": int(self.timeout),
            "timestamp": int(self.timestamp)
        }
