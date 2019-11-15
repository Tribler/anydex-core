import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.order_manager import OrderManager
from anydex.core.order_repository import MemoryOrderRepository
from anydex.core.timeout import Timeout


class PortfolioTestSuite(unittest.TestCase):
    """OrderManager test cases."""

    def setUp(self):
        # Object creation
        self.order_manager = OrderManager(MemoryOrderRepository(b'0' * 20))

    def test_create_ask_order(self):
        # Test for create ask order
        ask_order = self.order_manager.create_ask_order(
            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), Timeout(0))
        self.assertTrue(ask_order.is_ask())
        self.assertEqual(OrderId(TraderId(b'0' * 20), OrderNumber(1)), ask_order.order_id)
        self.assertEqual(AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), ask_order.assets)
        self.assertEqual(100, ask_order.total_quantity)
        self.assertEqual(0, int(ask_order.timeout))

    def test_create_bid_order(self):
        # Test for create bid order
        bid_order = self.order_manager.create_bid_order(
            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), Timeout(0))
        self.assertFalse(bid_order.is_ask())
        self.assertEqual(OrderId(TraderId(b'0' * 20), OrderNumber(1)), bid_order.order_id)
        self.assertEqual(AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), bid_order.assets)
        self.assertEqual(100, bid_order.total_quantity)
        self.assertEqual(0, int(bid_order.timeout))

    def test_cancel_order(self):
        # test for cancel order
        order = self.order_manager.create_ask_order(
            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), Timeout(0))
        self.order_manager.cancel_order(order.order_id)
