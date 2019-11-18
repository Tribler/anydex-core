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
from anydex.test.base import AbstractServer


class TickEntryTestSuite(AbstractServer):
    """TickEntry test cases."""

    async def setUp(self):
        super(TickEntryTestSuite, self).setUp()

        # Object creation
        tick = Tick(OrderId(TraderId(b'0' * 20), OrderNumber(1)), AssetPair(AssetAmount(60, 'BTC'),
                                                                            AssetAmount(30, 'MB')),
                    Timeout(0), Timestamp(0), True)
        tick2 = Tick(OrderId(TraderId(b'0' * 20), OrderNumber(2)),
                     AssetPair(AssetAmount(63400, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now(), True)

        self.price_level = PriceLevel(Price(100, 1, 'MB', 'BTC'))
        self.tick_entry = TickEntry(tick, self.price_level)
        self.tick_entry2 = TickEntry(tick2, self.price_level)

    async def tearDown(self):
        await self.tick_entry.shutdown_task_manager()
        await self.tick_entry2.shutdown_task_manager()
        await super(TickEntryTestSuite, self).tearDown()

    def test_price_level(self):
        self.assertEqual(self.price_level, self.tick_entry.price_level())

    def test_next_tick(self):
        # Test for next tick
        self.assertEqual(None, self.tick_entry.next_tick)
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEqual(self.tick_entry2, self.tick_entry.next_tick)

    def test_prev_tick(self):
        # Test for previous tick
        self.assertEqual(None, self.tick_entry.prev_tick)
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEqual(self.tick_entry, self.tick_entry2.prev_tick)

    def test_str(self):
        # Test for tick string representation
        self.assertEqual('60 BTC\t@\t0.5 MB', str(self.tick_entry))

    def test_is_valid(self):
        # Test for is valid
        self.assertFalse(self.tick_entry.is_valid())
        self.assertTrue(self.tick_entry2.is_valid())

    def test_block_for_matching(self):
        """
        Test blocking of a match
        """
        self.tick_entry.block_for_matching(OrderId(TraderId(b'a' * 20), OrderNumber(3)))
        self.assertEqual(len(self.tick_entry._blocked_for_matching), 1)

        # Try to add it again - should be ignored
        self.tick_entry.block_for_matching(OrderId(TraderId(b'a' * 20), OrderNumber(3)))
        self.assertEqual(len(self.tick_entry._blocked_for_matching), 1)
