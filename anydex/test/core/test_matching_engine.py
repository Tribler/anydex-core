import pytest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.tick import Ask, Bid
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


@pytest.fixture
def ask():
    return Ask(OrderId(TraderId(b'2' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp.now())


@pytest.fixture
def bid():
    return Bid(OrderId(TraderId(b'4' * 20), OrderNumber(2)),
               AssetPair(AssetAmount(3000, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp.now())


def insert_ask(order_book, amount1, amount2):
    """
    Insert an ask in the order book with a specific price and quantity
    """
    new_ask = Ask(OrderId(TraderId(b'2' * 20), OrderNumber(len(order_book.asks) + 1)),
                  AssetPair(AssetAmount(amount1, 'BTC'), AssetAmount(amount2, 'MB')), Timeout(30), Timestamp.now())
    order_book.insert_ask(new_ask)
    return new_ask


def insert_bid(order_book, amount1, amount2):
    """
    Insert a bid with a specific price and quantity
    """
    new_bid = Bid(OrderId(TraderId(b'3' * 20), OrderNumber(len(order_book.bids) + 1)),
                  AssetPair(AssetAmount(amount1, 'BTC'), AssetAmount(amount2, 'MB')), Timeout(30), Timestamp.now())
    order_book.insert_bid(new_bid)
    return new_bid


def test_empty_match_order_empty(order_book, matching_engine, ask, bid):
    """
    Test whether matching in an empty order book returns no matches
    """
    order_book.insert_ask(ask)
    assert not matching_engine.match(order_book.get_ask(ask.order_id))
    order_book.remove_ask(ask.order_id)

    order_book.insert_bid(bid)
    assert not matching_engine.match(order_book.get_bid(bid.order_id))


def test_match_order_bid(order_book, matching_engine, ask, bid):
    """
    Test matching a bid order
    """
    order_book.insert_ask(ask)
    order_book.insert_bid(bid)
    matching_ticks = matching_engine.match(order_book.get_bid(bid.order_id))
    assert len(matching_ticks) == 1


def test_match_order_ask(order_book, matching_engine, ask, bid):
    """
    Test matching an ask order
    """
    order_book.insert_bid(bid)
    order_book.insert_ask(ask)
    matching_ticks = matching_engine.match(order_book.get_ask(ask.order_id))
    assert len(matching_ticks) == 1


def test_multiple_price_levels_asks(order_book, matching_engine):
    """
    Test matching when there are asks in multiple price levels
    """
    insert_ask(order_book, 50, 350)
    insert_ask(order_book, 18, 72)
    insert_ask(order_book, 100, 700)

    my_bid = insert_bid(order_book, 200, 2000)
    matching_ticks = matching_engine.match(order_book.get_bid(my_bid.order_id))

    assert len(matching_ticks) == 3


def test_multiple_price_levels_bids(order_book, matching_engine):
    """
    Test matching when there are bids in multiple price levels
    """
    insert_bid(order_book, 50, 200)
    insert_bid(order_book, 18, 72)
    insert_bid(order_book, 100, 400)

    my_ask = insert_ask(order_book, 200, 200)
    matching_ticks = matching_engine.match(order_book.get_ask(my_ask.order_id))

    assert len(matching_ticks) == 3


def test_price_time_priority_asks(order_book, matching_engine):
    """
    Test whether the price-time priority works correctly
    """
    insert_ask(order_book, 20, 100)
    insert_ask(order_book, 25, 125)
    insert_ask(order_book, 10, 50)

    my_bid = insert_bid(order_book, 50, 250)
    matching_ticks = matching_engine.match(order_book.get_bid(my_bid.order_id))

    assert len(matching_ticks) == 3
    assert matching_ticks[-1].assets.first.amount == 10


def test_price_time_priority_bids(order_book, matching_engine):
    """
    Test whether the price-time priority works correctly
    """
    insert_bid(order_book, 20, 100)
    insert_bid(order_book, 25, 125)
    insert_bid(order_book, 10, 50)

    my_ask = insert_ask(order_book, 50, 250)
    matching_ticks = matching_engine.match(order_book.get_ask(my_ask.order_id))

    assert len(matching_ticks) == 3
    assert matching_ticks[-1].assets.first.amount == 10


def test_matching_multiple_levels(order_book, matching_engine):
    """
    Test a matching with multiple price levels
    """
    insert_bid(order_book, 10, 60)
    insert_bid(order_book, 10, 50)
    my_ask = insert_ask(order_book, 30, 180)
    matching_ticks = matching_engine.match(order_book.get_ask(my_ask.order_id))
    assert len(matching_ticks) == 1
