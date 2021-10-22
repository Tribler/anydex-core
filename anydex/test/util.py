"""
Test utilities.

Partially based on the code from http://code.activestate.com/recipes/52215/

Author(s): Elric Milon
"""
import logging
from asyncio import coroutine, iscoroutinefunction, wait_for
from functools import wraps


logger = logging.getLogger(__name__)


class MockObject:
    """
    This class is used to create as base class for fake (mocked) objects.
    """
    pass


def timeout(timeout):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            coro = func if iscoroutinefunction(func) else coroutine(func)
            await wait_for(coro(*args, **kwargs), timeout)
        return wrapper
    return decorator
