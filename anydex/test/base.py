from __future__ import absolute_import

import logging
import os
import random
import shutil
import string

import six

import twisted
from twisted.internet import interfaces, reactor
from twisted.internet.base import BasePort
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.task import deferLater
from twisted.internet.tcp import Client
from twisted.trial import unittest
from twisted.web.http import HTTPChannel

from anydex.test.instrumentation import WatchDog
from anydex.test.util import process_unhandled_exceptions, process_unhandled_twisted_exceptions

TESTS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class BaseTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)
        self._tempdirs = []
        self.maxDiff = None  # So we see full diffs when using assertEquals

    def tearDown(self):
        while self._tempdirs:
            temp_dir = self._tempdirs.pop()
            os.chmod(temp_dir, 0o700)
            shutil.rmtree(six.text_type(temp_dir), ignore_errors=False)

    def temporary_directory(self, suffix=''):
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        temp = os.path.join(TESTS_DIR, "temp", self.__class__.__name__ + suffix + random_string)
        self._tempdirs.append(temp)
        os.makedirs(temp)
        return temp


class AbstractServer(BaseTestCase):

    def __init__(self, *args, **kwargs):
        super(AbstractServer, self).__init__(*args, **kwargs)
        twisted.internet.base.DelayedCall.debug = True

        self.watchdog = WatchDog()

        # Enable Deferred debugging
        from twisted.internet.defer import setDebugging
        setDebugging(True)

    @inlineCallbacks
    def setUp(self):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session_base_dir = self.temporary_directory(suffix="_tribler_test_session_")
        self.state_dir = os.path.join(self.session_base_dir, u"dot.Tribler")

        # Wait until the reactor has started
        reactor_deferred = Deferred()

        reactor.callWhenRunning(reactor_deferred.callback, None)

        self.watchdog.start()
        yield reactor_deferred
        pass

    @inlineCallbacks
    def checkReactor(self, phase, *_):
        delayed_calls = reactor.getDelayedCalls()
        if delayed_calls:
            self._logger.error("The reactor was dirty during %s:", phase)
            for dc in delayed_calls:
                self._logger.error(">     %s", dc)
                dc.cancel()

        has_network_selectables = False
        for item in reactor.getReaders() + reactor.getWriters():
            if isinstance(item, HTTPChannel) or isinstance(item, Client):
                has_network_selectables = True
                break

        if has_network_selectables:
            # TODO(Martijn): we wait a while before we continue the check since network selectables
            # might take some time to cleanup. I'm not sure what's causing this.
            yield deferLater(reactor, 0.2, lambda: None)

        # This is the same check as in the _cleanReactor method of Twisted's Trial
        selectable_strings = []
        for sel in reactor.removeAll():
            if interfaces.IProcessTransport.providedBy(sel):
                self._logger.error("Sending kill signal to %s", repr(sel))
                sel.signalProcess('KILL')
            selectable_strings.append(repr(sel))

        self.assertFalse(selectable_strings,
                         "The reactor has leftover readers/writers during %s: %r" % (phase, selectable_strings))

        # Check whether we have closed all the sockets
        open_readers = reactor.getReaders()
        for reader in open_readers:
            self.assertNotIsInstance(reader, BasePort)

        # Check whether the threadpool is clean
        tp_items = len(reactor.getThreadPool().working)
        if tp_items > 0:  # Print all stacks to debug this issue
            self.watchdog.print_all_stacks()
        self.assertEqual(tp_items, 0, "Still items left in the threadpool")

    @inlineCallbacks
    def tearDown(self):
        process_unhandled_exceptions()
        process_unhandled_twisted_exceptions()

        self.watchdog.join(2)
        if self.watchdog.is_alive():
            self._logger.critical("The WatchDog didn't stop!")
            self.watchdog.print_all_stacks()
            raise RuntimeError("Couldn't stop the WatchDog")

        yield self.checkReactor("tearDown")

        super(AbstractServer, self).tearDown()

    def getStateDir(self, nr=0):
        state_dir = self.state_dir + (str(nr) if nr else '')
        if not os.path.exists(state_dir):
            os.mkdir(state_dir)
        return state_dir
