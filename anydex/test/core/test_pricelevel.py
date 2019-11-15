import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.price import Price
from anydex.core.pricelevel import PriceLevel
from anydex.core.tick import Tick
from anydex.core.tickentry import TickEntry
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


class PriceLevelTestSuite(unittest.TestCase):
    """PriceLevel test cases."""

    def setUp(self):
        # Object creation
        tick = Tick(OrderId(TraderId(b'0' * 20), OrderNumber(1)), AssetPair(AssetAmount(60, 'BTC'),
                                                                            AssetAmount(30, 'MC')),
                    Timeout(100), Timestamp.now(), True)
        tick2 = Tick(OrderId(TraderId(b'0' * 20), OrderNumber(2)), AssetPair(AssetAmount(30, 'BTC'),
                                                                             AssetAmount(30, 'MC')),
                     Timeout(100), Timestamp.now(), True)

        self.price_level = PriceLevel(Price(50, 5, 'MC', 'BTC'))
        self.tick_entry1 = TickEntry(tick, self.price_level)
        self.tick_entry2 = TickEntry(tick, self.price_level)
        self.tick_entry3 = TickEntry(tick, self.price_level)
        self.tick_entry4 = TickEntry(tick, self.price_level)
        self.tick_entry5 = TickEntry(tick2, self.price_level)

    def test_appending_length(self):
        # Test for tick appending and length
        self.assertEqual(0, self.price_level.length)
        self.assertEqual(0, len(self.price_level))

        self.price_level.append_tick(self.tick_entry1)
        self.price_level.append_tick(self.tick_entry2)
        self.price_level.append_tick(self.tick_entry3)
        self.price_level.append_tick(self.tick_entry4)

        self.assertEqual(4, self.price_level.length)
        self.assertEqual(4, len(self.price_level))

    def test_tick_removal(self):
        # Test for tick removal
        self.price_level.append_tick(self.tick_entry1)
        self.price_level.append_tick(self.tick_entry2)
        self.price_level.append_tick(self.tick_entry3)
        self.price_level.append_tick(self.tick_entry4)

        self.price_level.remove_tick(self.tick_entry2)
        self.price_level.remove_tick(self.tick_entry1)
        self.price_level.remove_tick(self.tick_entry4)
        self.price_level.remove_tick(self.tick_entry3)
        self.assertEqual(0, self.price_level.length)

    def test_str(self):
        # Test for price level string representation
        self.price_level.append_tick(self.tick_entry1)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEqual('60 BTC\t@\t0.5 MC\n'
                          '60 BTC\t@\t0.5 MC\n', str(self.price_level))
