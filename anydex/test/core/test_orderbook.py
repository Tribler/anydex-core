import pytest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.orderbook import OrderBook
from anydex.core.price import Price
from anydex.core.tick import Ask, Bid
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


@pytest.fixture
def ask():
    return Ask(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())


@pytest.fixture
def ask2():
    return Ask(OrderId(TraderId(b'1' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(400, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())


@pytest.fixture
def bid():
    return Bid(OrderId(TraderId(b'2' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(200, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())


@pytest.fixture
def bid2():
    return Bid(OrderId(TraderId(b'3' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(300, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now())


@pytest.mark.asyncio
async def order_book():
    order_book = OrderBook()
    yield order_book
    await order_book.shutdown_task_manager()


def test_timeouts(ask, bid, order_book):
    """
    Test the timeout functions of asks/bids
    """
    order_book.insert_ask(ask)
    assert order_book.timeout_ask(ask.order_id) == ask

    order_book.insert_bid(bid)
    assert order_book.timeout_bid(bid.order_id) == bid

    order_book.on_invalid_tick_insert()


def test_ask_insertion(ask2, order_book):
    # Test for ask insertion
    order_book.insert_ask(ask2)
    assert order_book.tick_exists(ask2.order_id)
    assert order_book.ask_exists(ask2.order_id)
    assert not order_book.bid_exists(ask2.order_id)
    assert order_book.get_ask(ask2.order_id).tick == ask2


def test_get_tick(ask, bid, order_book):
    """
    Test the retrieval of a tick from the order book
    """
    order_book.insert_ask(ask)
    order_book.insert_bid(bid)
    assert order_book.get_tick(ask.order_id)
    assert order_book.get_tick(bid.order_id)


def test_ask_removal(ask2, order_book):
    # Test for ask removal
    order_book.insert_ask(ask2)
    assert order_book.tick_exists(ask2.order_id)
    order_book.remove_ask(ask2.order_id)
    assert not order_book.tick_exists(ask2.order_id)


def test_bid_insertion(bid2, order_book):
    # Test for bid insertion
    order_book.insert_bid(bid2)
    assert order_book.tick_exists(bid2.order_id)
    assert order_book.bid_exists(bid2.order_id)
    assert not order_book.ask_exists(bid2.order_id)
    assert order_book.get_bid(bid2.order_id).tick == bid2


def test_bid_removal(bid2, order_book):
    # Test for bid removal
    order_book.insert_bid(bid2)
    assert order_book.tick_exists(bid2.order_id)
    order_book.remove_bid(bid2.order_id)
    assert not order_book.tick_exists(bid2.order_id)


def test_properties(ask2, bid2, order_book):
    # Test for properties
    order_book.insert_ask(ask2)
    order_book.insert_bid(bid2)
    assert order_book.get_bid_ask_spread('MB', 'BTC') == Price(-25, 1000, 'MB', 'BTC')


def test_ask_price_level(ask, order_book):
    order_book.insert_ask(ask)
    price_level = order_book.get_ask_price_level('MB', 'BTC')
    assert price_level.depth == 100


def test_bid_price_level(bid2, order_book):
    # Test for tick price
    order_book.insert_bid(bid2)
    price_level = order_book.get_bid_price_level('MB', 'BTC')
    assert price_level.depth == 300


def test_ask_side_depth(ask, ask2, order_book):
    # Test for ask side depth
    order_book.insert_ask(ask)
    order_book.insert_ask(ask2)
    assert order_book.ask_side_depth(Price(3, 10, 'MB', 'BTC')) == 100
    assert order_book.get_ask_side_depth_profile('MB', 'BTC') == \
           [(Price(75, 1000, 'MB', 'BTC'), 400), (Price(3, 10, 'MB', 'BTC'), 100)]


def test_bid_side_depth(bid, bid2, order_book):
    # Test for bid side depth
    order_book.insert_bid(bid)
    order_book.insert_bid(bid2)
    assert order_book.bid_side_depth(Price(1, 10, 'MB', 'BTC')) == 300
    assert order_book.get_bid_side_depth_profile('MB', 'BTC') == \
           [(Price(1, 10, 'MB', 'BTC'), 300), (Price(15, 100, 'MB', 'BTC'), 200)]


def test_remove_tick(ask2, bid2, order_book):
    # Test for tick removal
    order_book.insert_ask(ask2)
    order_book.insert_bid(bid2)
    order_book.remove_tick(ask2.order_id)
    assert not order_book.tick_exists(ask2.order_id)
    order_book.remove_tick(bid2.order_id)
    assert not order_book.tick_exists(bid2.order_id)


def test_get_order_ids(ask, bid, order_book):
    """
    Test the get order IDs function in order book
    """
    assert not order_book.get_order_ids()
    order_book.insert_ask(ask)
    order_book.insert_bid(bid)
    assert len(order_book.get_order_ids()) == 2


def test_update_ticks(ask, bid, order_book):
    """
    Test updating ticks in an order book
    """
    order_book.insert_ask(ask)
    order_book.insert_bid(bid)

    ask_dict = {
        "trader_id": ask.order_id.trader_id.as_hex(),
        "order_number": int(ask.order_id.order_number),
        "assets": ask.assets.to_dictionary(),
        "traded": 100,
        "timeout": 3600,
        "timestamp": int(Timestamp.now())
    }
    bid_dict = {
        "trader_id": bid.order_id.trader_id.as_hex(),
        "order_number": int(bid.order_id.order_number),
        "assets": bid.assets.to_dictionary(),
        "traded": 100,
        "timeout": 3600,
        "timestamp": int(Timestamp.now())
    }

    ask_dict["traded"] = 50
    bid_dict["traded"] = 50
    order_book.completed_orders = []
    order_book.update_ticks(ask_dict, bid_dict, 100)
    assert len(order_book.asks) == 1
    assert len(order_book.bids) == 1


def test_str(ask, bid, order_book):
    # Test for order book string representation
    order_book.insert_ask(ask)
    order_book.insert_bid(bid)

    assert str(order_book) == \
           '------ Bids -------\n'\
           '200 BTC\t@\t0.15 MB\n\n'\
           '------ Asks -------\n'\
           '100 BTC\t@\t0.3 MB\n\n'
