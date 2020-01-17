import logging
from asyncio import CancelledError, coroutine, ensure_future, iscoroutine

from ipv8.taskmanager import delay_runner

logger = logging.getLogger(__name__)


def call_later(delay, func, *args, ignore_errors=False):
    if not iscoroutine(func):
        func = coroutine(func)

    task = ensure_future(delay_runner(delay, func, *args))
    if ignore_errors:
        add_default_callback(task)
    return task


def add_default_callback(task):
    def done_cb(future):
        try:
            future.result()
        except CancelledError:
            pass
        except Exception as e:
            logging.error('Task raised exception: %s', e)

    return task.add_done_callback(done_cb)
