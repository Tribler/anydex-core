import unittest

import pytest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.match_queue import MatchPriorityQueue
from anydex.core.message import TraderId
from anydex.core.order import Order, OrderId, OrderNumber
from anydex.core.price import Price
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


@pytest.fixture
def ask_order():
    order_id = OrderId(TraderId(b'3' * 20), OrderNumber(1))
    return Order(order_id, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                 Timeout(3600), Timestamp.now(), True)


@pytest.fixture
def bid_order():
    order_id = OrderId(TraderId(b'3' * 20), OrderNumber(1))
    return Order(order_id, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                 Timeout(3600), Timestamp.now(), False)


@pytest.fixture
def queue(ask_order):
    return MatchPriorityQueue(ask_order)


def test_priority(bid_order, queue):
    """
    Test the priority mechanism of the queue
    """
    order_id = OrderId(TraderId(b'1' * 20), OrderNumber(1))
    other_order_id = OrderId(TraderId(b'2' * 20), OrderNumber(1))
    queue.insert(1, Price(1, 1, 'DUM1', 'DUM2'), order_id, other_order_id)
    queue.insert(0, Price(1, 1, 'DUM1', 'DUM2'), order_id, other_order_id)
    queue.insert(2, Price(1, 1, 'DUM1', 'DUM2'), order_id, other_order_id)

    item1 = queue.delete()
    item2 = queue.delete()
    item3 = queue.delete()
    assert item1[0] == 0
    assert item2[0] == 1
    assert item3[0] == 2

    # Same retries, different prices
    queue.insert(1, Price(1, 1, 'DUM1', 'DUM2'), order_id, other_order_id)
    queue.insert(1, Price(1, 2, 'DUM1', 'DUM2'), order_id, other_order_id)
    queue.insert(1, Price(1, 3, 'DUM1', 'DUM2'), order_id, other_order_id)

    item1 = queue.delete()
    item2 = queue.delete()
    item3 = queue.delete()
    assert item1[1] == Price(1, 1, 'DUM1', 'DUM2')
    assert item2[1] == Price(1, 2, 'DUM1', 'DUM2')
    assert item3[1] == Price(1, 3, 'DUM1', 'DUM2')

    # Test with bid order
    queue = MatchPriorityQueue(bid_order)
    queue.insert(1, Price(1, 1, 'DUM1', 'DUM2'), order_id, other_order_id)
    queue.insert(1, Price(1, 2, 'DUM1', 'DUM2'), order_id, other_order_id)
    queue.insert(1, Price(1, 3, 'DUM1', 'DUM2'), order_id, other_order_id)

    item1 = queue.delete()
    item2 = queue.delete()
    item3 = queue.delete()
    assert item1[1] == Price(1, 3, 'DUM1', 'DUM2')
    assert item2[1] == Price(1, 2, 'DUM1', 'DUM2')
    assert item3[1] == Price(1, 1, 'DUM1', 'DUM2')
