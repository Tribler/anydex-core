import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.match_queue import MatchPriorityQueue
from anydex.core.message import TraderId
from anydex.core.order import Order, OrderId, OrderNumber
from anydex.core.price import Price
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


class TestMatchQueue(unittest.TestCase):
    """
    This class contains tests for the MatchingPriorityQueue object.
    """

    def setUp(self):
        order_id = OrderId(TraderId(b'3' * 20), OrderNumber(1))
        self.ask_order = Order(order_id, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                         Timeout(3600), Timestamp.now(), True)
        self.bid_order = Order(order_id, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                         Timeout(3600), Timestamp.now(), False)
        self.queue = MatchPriorityQueue(self.ask_order)

    def test_priority(self):
        """
        Test the priority mechanism of the queue
        """
        order_id = OrderId(TraderId(b'1' * 20), OrderNumber(1))
        self.queue.insert(1, Price(1, 1, 'DUM1', 'DUM2'), order_id)
        self.queue.insert(0, Price(1, 1, 'DUM1', 'DUM2'), order_id)
        self.queue.insert(2, Price(1, 1, 'DUM1', 'DUM2'), order_id)

        item1 = self.queue.delete()
        item2 = self.queue.delete()
        item3 = self.queue.delete()
        self.assertEqual(item1[0], 0)
        self.assertEqual(item2[0], 1)
        self.assertEqual(item3[0], 2)

        # Same retries, different prices
        self.queue.insert(1, Price(1, 1, 'DUM1', 'DUM2'), order_id)
        self.queue.insert(1, Price(1, 2, 'DUM1', 'DUM2'), order_id)
        self.queue.insert(1, Price(1, 3, 'DUM1', 'DUM2'), order_id)

        item1 = self.queue.delete()
        item2 = self.queue.delete()
        item3 = self.queue.delete()
        self.assertEqual(item1[1], Price(1, 1, 'DUM1', 'DUM2'))
        self.assertEqual(item2[1], Price(1, 2, 'DUM1', 'DUM2'))
        self.assertEqual(item3[1], Price(1, 3, 'DUM1', 'DUM2'))

        # Test with bid order
        self.queue = MatchPriorityQueue(self.bid_order)
        self.queue.insert(1, Price(1, 1, 'DUM1', 'DUM2'), order_id)
        self.queue.insert(1, Price(1, 2, 'DUM1', 'DUM2'), order_id)
        self.queue.insert(1, Price(1, 3, 'DUM1', 'DUM2'), order_id)

        item1 = self.queue.delete()
        item2 = self.queue.delete()
        item3 = self.queue.delete()
        self.assertEqual(item1[1], Price(1, 3, 'DUM1', 'DUM2'))
        self.assertEqual(item2[1], Price(1, 2, 'DUM1', 'DUM2'))
        self.assertEqual(item3[1], Price(1, 1, 'DUM1', 'DUM2'))