import pytest

from anydex.core.matching_engine import MatchingEngine, PriceTimeStrategy
from anydex.core.orderbook import OrderBook


@pytest.fixture
@pytest.mark.asyncio
async def order_book():
    order_book = OrderBook()
    yield order_book
    await order_book.shutdown_task_manager()


@pytest.fixture
def strategy(order_book):
    return PriceTimeStrategy(order_book)


@pytest.fixture
def matching_engine(order_book):
    return MatchingEngine(PriceTimeStrategy(order_book))
