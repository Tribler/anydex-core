import pytest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import Order, OrderId, OrderNumber
from anydex.core.tick import Ask, Bid
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


@pytest.fixture
def bid():
    return Bid(OrderId(TraderId(b'0' * 20), OrderNumber(5)),
               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())


@pytest.fixture
def ask():
    return Ask(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())


@pytest.fixture
def ask_order():
    return Order(OrderId(TraderId(b'9' * 20), OrderNumber(11)),
                 AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now(), True)


@pytest.fixture
def bid_order():
    return Order(OrderId(TraderId(b'9' * 20), OrderNumber(13)),
                 AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now(), False)


def test_empty_match_order(strategy, ask_order, bid_order):
    """
    Test for match order with an empty order book
    """
    assert not strategy.match(bid_order.order_id, bid_order.price, bid_order.available_quantity, False)
    assert not strategy.match(ask_order.order_id, ask_order.price, ask_order.available_quantity, True)


def test_match_order_other_price(order_book, strategy, bid_order):
    """
    Test whether two ticks with different price types are not matched
    """
    ask = Ask(OrderId(TraderId(b'1' * 20), OrderNumber(4)),
              AssetPair(AssetAmount(3000, 'A'), AssetAmount(3000, 'MB')), Timeout(100), Timestamp.now())
    order_book.insert_ask(ask)
    assert not strategy.match(bid_order.order_id, bid_order.price, bid_order.available_quantity, False)


def test_match_order_other_quantity(order_book, strategy, bid_order):
    """
    Test whether two ticks with different quantity types are not matched
    """
    ask = Ask(OrderId(TraderId(b'1' * 20), OrderNumber(4)),
              AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'C')), Timeout(100), Timestamp.now())

    order_book.insert_ask(ask)
    assert not strategy.match(bid_order.order_id, bid_order.price, bid_order.available_quantity, False)


def test_match_order_ask(order_book, strategy, ask_order, bid):
    """
    Test matching an ask order
    """
    order_book.insert_bid(bid)
    matching_ticks = strategy.match(ask_order.order_id, ask_order.price, ask_order.available_quantity, True)
    assert matching_ticks
    assert order_book.get_tick(bid.order_id) == matching_ticks[0]


def test_match_order_bid(order_book, strategy, bid_order, ask):
    """
    Test matching a bid order
    """
    order_book.insert_ask(ask)
    matching_ticks = strategy.match(bid_order.order_id, bid_order.price, bid_order.available_quantity, False)
    assert matching_ticks
    assert order_book.get_tick(ask.order_id) == matching_ticks[0]


def test_match_order_divided(order_book, strategy, ask):
    """
    Test for match order divided over two ticks
    """
    order_book.insert_ask(ask)

    ask2 = Ask(OrderId(TraderId(b'1' * 20), OrderNumber(2)),
               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())
    bid_order2 = Order(OrderId(TraderId(b'9' * 20), OrderNumber(14)),
                       AssetPair(AssetAmount(6000, 'BTC'), AssetAmount(60, 'MB')), Timeout(100), Timestamp.now(), False)
    order_book.insert_ask(ask2)
    matching_ticks = strategy.match(bid_order2.order_id, bid_order2.price, bid_order2.available_quantity, False)
    assert len(matching_ticks) == 2


def test_match_order_partial_ask(order_book, strategy, bid_order, ask):
    """
    Test partial matching of a bid order with the matching engine
    """
    ask.traded = 1000
    order_book.insert_ask(ask)
    matching_ticks = strategy.match(bid_order.order_id, bid_order.price, bid_order.available_quantity, False)
    assert len(matching_ticks) == 1


def test_match_order_partial_bid(order_book, strategy, ask_order, bid):
    """
    Test partial matching of an ask order with the matching engine
    """
    bid.traded = 1000
    order_book.insert_bid(bid)
    matching_ticks = strategy.match(ask_order.order_id, ask_order.price, ask_order.available_quantity, True)
    assert len(matching_ticks) == 1


def test_bid_blocked_for_matching(order_book, strategy, ask_order, bid):
    """
    Test whether a bid tick is not matched when blocked for matching
    """
    order_book.insert_bid(bid)
    order_book.get_tick(bid.order_id).block_for_matching(ask_order.order_id)
    matching_ticks = strategy.match(ask_order.order_id, ask_order.price, ask_order.available_quantity, True)
    assert not matching_ticks


def test_ask_blocked_for_matching(order_book, strategy, bid_order, ask):
    """
    Test whether an ask tick is not matched when blocked for matching
    """
    order_book.insert_ask(ask)
    order_book.get_tick(ask.order_id).block_for_matching(bid_order.order_id)
    matching_ticks = strategy.match(bid_order.order_id, bid_order.price, bid_order.available_quantity, False)
    assert not matching_ticks
