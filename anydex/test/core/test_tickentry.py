import pytest

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


@pytest.fixture
def price_level():
    return PriceLevel(Price(100, 1, 'MB', 'BTC'))


@pytest.fixture
async def tick_entry(price_level):
    tick = Tick(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), Timeout(0), Timestamp(0), True)
    tick_entry = TickEntry(tick, price_level)
    yield tick_entry
    await tick_entry.shutdown_task_manager()


@pytest.fixture
async def tick_entry2(price_level):
    tick = Tick(OrderId(TraderId(b'0' * 20), OrderNumber(2)),
                AssetPair(AssetAmount(63400, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now(), True)
    tick_entry = TickEntry(tick, price_level)
    yield tick_entry
    await tick_entry.shutdown_task_manager()


def test_price_level(price_level, tick_entry):
    assert price_level == tick_entry.price_level()


def test_next_tick(price_level, tick_entry, tick_entry2):
    # Test for next tick
    assert not tick_entry.next_tick
    price_level.append_tick(tick_entry)
    price_level.append_tick(tick_entry2)
    assert tick_entry.next_tick == tick_entry2


def test_prev_tick(price_level, tick_entry, tick_entry2):
    # Test for previous tick
    assert not tick_entry.prev_tick
    price_level.append_tick(tick_entry)
    price_level.append_tick(tick_entry2)
    assert tick_entry2.prev_tick == tick_entry


def test_str(tick_entry):
    # Test for tick string representation
    assert str(tick_entry) == '60 BTC\t@\t0.5 MB'


def test_is_valid(tick_entry, tick_entry2):
    # Test for is valid
    assert not tick_entry.is_valid()
    assert tick_entry2.is_valid()


def test_block_for_matching(tick_entry):
    """
    Test blocking of a match
    """
    tick_entry.block_for_matching(OrderId(TraderId(b'a' * 20), OrderNumber(3)))
    assert len(tick_entry._blocked_for_matching) == 1

    # Try to add it again - should be ignored
    tick_entry.block_for_matching(OrderId(TraderId(b'a' * 20), OrderNumber(3)))
    assert len(tick_entry._blocked_for_matching) == 1
