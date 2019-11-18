import logging
import os
import random
import shutil
import string
from asyncio import current_task, get_event_loop

import asynctest

from anydex.test.instrumentation import WatchDog
from anydex.test.util import process_unhandled_asyncio_exceptions, process_unhandled_exceptions

TESTS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class BaseTestCase(asynctest.TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)
        self._tempdirs = []
        self.maxDiff = None  # So we see full diffs when using assertEquals

    def tearDown(self):
        while self._tempdirs:
            temp_dir = self._tempdirs.pop()
            os.chmod(temp_dir, 0o700)
            shutil.rmtree(str(temp_dir), ignore_errors=False)

    def temporary_directory(self, suffix=''):
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        temp = os.path.join(TESTS_DIR, "temp", self.__class__.__name__ + suffix + random_string)
        self._tempdirs.append(temp)
        os.makedirs(temp)
        return temp


class AbstractServer(BaseTestCase):

    def __init__(self, *args, **kwargs):
        super(AbstractServer, self).__init__(*args, **kwargs)
        get_event_loop().set_debug(True)

        self.watchdog = WatchDog()

    def setUp(self):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session_base_dir = self.temporary_directory(suffix="_tribler_test_session_")
        self.state_dir = os.path.join(self.session_base_dir, u"dot.Tribler")
        self.watchdog.start()

    async def checkLoop(self, phase, *_):
        # Only in Python 3.7+..
        try:
            from asyncio import all_tasks
        except ImportError:
            return

        tasks = [t for t in all_tasks(get_event_loop()) if t is not current_task()]
        if tasks:
            self._logger.error("The event loop was dirty during %s:", phase)
        for task in tasks:
            self._logger.error(">     %s", task)

    async def tearDown(self):
        process_unhandled_exceptions()
        process_unhandled_asyncio_exceptions()

        self.watchdog.join(2)
        if self.watchdog.is_alive():
            self._logger.critical("The WatchDog didn't stop!")
            self.watchdog.print_all_stacks()
            raise RuntimeError("Couldn't stop the WatchDog")

        await self.checkLoop("tearDown")

        super(AbstractServer, self).tearDown()

    def getStateDir(self, nr=0):
        state_dir = self.state_dir + (str(nr) if nr else '')
        if not os.path.exists(state_dir):
            os.mkdir(state_dir)
        return state_dir
