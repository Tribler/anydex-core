"""
Test utilities.

Partially based on the code from http://code.activestate.com/recipes/52215/

Author(s): Elric Milon
"""
import logging
import random
import socket
import struct
import sys

from twisted.python.log import addObserver


logger = logging.getLogger(__name__)


class UnhandledExceptionCatcher(object):
    """
    Logs the usual tb information, followed by a listing of all the
    local variables in each frame and mark the test run as failed.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._lines = []
        self.last_exc = None
        self.exc_counter = 0
        sys.excepthook = self.catch_exception

    def _register_exception_line(self, line, *format_args):
        line = line % format_args
        self._lines.append(line)
        self._logger.critical(line)

    def catch_exception(self, type, value, tb):
        """
        Catch unhandled exception, log it and store it to be printed at teardown time too.

        """
        self.exc_counter += 1

        def repr_(value):
            try:
                return repr(value)
            except:
                return "<Error while REPRing value>"
        self.last_exc = repr_(value)
        self._register_exception_line("Unhandled exception raised while running the test: %s %s", type, self.last_exc)

        stack = []
        while tb:
            stack.append(tb.tb_frame)
            tb = tb.tb_next

        self._register_exception_line("Locals by frame, innermost last:")
        for frame in stack:
            self._register_exception_line("%s:%s %s:", frame.f_code.co_filename,
                                          frame.f_lineno, frame.f_code.co_name)
            for key, value in frame.f_locals.items():
                value = repr_(value)
                if len(value) > 500:
                    value = value[:500] + "..."
                self._register_exception_line("| %12s = %s", key, value)

    def check_exceptions(self):
        """
        Log all unhandled exceptions, clear logged exceptions and raise to fail the currently running test.
        """
        if self.exc_counter:
            lines = self._lines
            self._lines = []
            exc_counter = self.exc_counter
            self.exc_counter = 0
            last_exc = self.last_exc
            self.last_exc = 0

            self._logger.critical("The following unhandled exceptions where raised during this test's execution:")
            for line in lines:
                self._logger.critical(line)

            raise Exception("Test raised %d unhandled exceptions, last one was: %s" % (exc_counter, last_exc))


class UnhandledTwistedExceptionCatcher(object):

    def __init__(self):
        self._twisted_exceptions = []

        def unhandled_error_observer(event):
            if event['isError']:
                if 'log_legacy' in event and 'log_text' in event:
                    self._twisted_exceptions.append(event['log_text'])
                elif 'log_failure' in event:
                    self._twisted_exceptions.append(str(event['log_failure']))
                else:
                    self._twisted_exceptions.append('\n'.join("%r: %r" % (key, value)
                                                              for key, value in event.items()))

        addObserver(unhandled_error_observer)

    def check_exceptions(self):
        exceptions = self._twisted_exceptions
        self._twisted_exceptions = []
        num_twisted_exceptions = len(exceptions)
        if num_twisted_exceptions > 0:
            raise Exception("Test raised %d unhandled Twisted exceptions:\n%s"
                            % (num_twisted_exceptions, '\n-------------------\n'.join(exceptions)))


class MockObject(object):
    """
    This class is used to create as base class for fake (mocked) objects.
    """
    pass


def trial_timeout(timeout):
    def trial_timeout_decorator(func):
        func.timeout = timeout
        return func
    return trial_timeout_decorator


CLAIMED_PORTS = []


def get_random_port(socket_type="all", min_port=5000, max_port=60000):
    """Gets a random port number that works.
    @param socket_type: Type of the socket, can be "all", "tcp", or "udp".
    @param min_port: The minimal port number to try with.
    @param max_port: The maximal port number to try with.
    @return: A working port number if exists, otherwise None.
    """
    assert socket_type in ("all", "tcp", "udp"), "Invalid socket type %s" % type(socket_type)
    assert isinstance(min_port, int), "Invalid min_port type %s" % type(min_port)
    assert isinstance(max_port, int), "Invalid max_port type %s" % type(max_port)
    assert 0 < min_port <= max_port <= 65535, "Invalid min_port and mac_port values %s, %s" % (min_port, max_port)

    working_port = None
    try_port = random.randint(min_port, max_port)
    while try_port <= 65535:
        if check_random_port(try_port, socket_type):
            working_port = try_port
            break
        try_port += 1

    if working_port:
        CLAIMED_PORTS.append(working_port)

    logger.debug("Got a working random port %s", working_port)
    return working_port


def check_random_port(port, socket_type="all"):
    """Returns an usable port number that can be bound with by the specific type of socket.
    @param socket_type: Type of the socket, can be "all", "tcp", or "udp".
    @param port: The port to try with.
    @return: True or False indicating if port is available.
    """
    assert socket_type in ("all", "tcp", "udp"), "Invalid socket type %s" % type(socket_type)
    assert isinstance(port, int), "Invalid port type %s" % type(port)
    assert 0 < port <= 65535, "Invalid port value %s" % port

    # only support IPv4 for now
    _family = socket.AF_INET

    _sock_type = None
    if socket_type == "udp":
        _sock_type = socket.SOCK_DGRAM
    elif socket_type == "tcp":
        _sock_type = socket.SOCK_STREAM

    is_port_working = False
    if port in CLAIMED_PORTS:
        return False
    if socket_type == "all":
        # try both UDP and TCP
        if _test_port(_family, socket.SOCK_DGRAM, port):
            is_port_working = _test_port(_family, socket.SOCK_STREAM, port)
    else:
        is_port_working = _test_port(_family, _sock_type, port)

    return is_port_working


def _test_port(family, sock_type, port):
    """Tests if a port is available.
    @param family: The socket family, must be socket.AF_INET.
    @param sock_type: The socket type, can be socket.SOCK_DGRAM or socket.SOCK_STREAM.
    @param port: The port number to test with.
    @return: True if the port is available or there is no problem with the socket, otherwise False.
    """
    assert family in (socket.AF_INET,), "Invalid family value %s" % family
    assert sock_type in (socket.SOCK_DGRAM, socket.SOCK_STREAM), "Invalid sock_type value %s" % sock_type
    assert 0 < port <= 65535, "Invalid port value %s" % port

    s = None
    try:
        s = socket.socket(family, sock_type)
        if sock_type == socket.SOCK_STREAM:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        s.bind(('', port))
        is_port_working = True
    except socket.error as e:
        logger.debug("Port test failed (port=%s, family=%s, type=%s): %s",
                     port, family, sock_type, e)
        is_port_working = False
    finally:
        if s:
            s.close()
    return is_port_working


def autodetect_socket_style():
    if sys.platform.find('linux') < 0:
        return 1
    else:
        try:
            f = open('/proc/sys/net/ipv6/bindv6only', 'r')
            dual_socket_style = int(f.read())
            f.close()
            return int(not dual_socket_style)
        except (IOError, ValueError):
            return 0


_catcher = UnhandledExceptionCatcher()
_twisted_catcher = UnhandledTwistedExceptionCatcher()

process_unhandled_exceptions = _catcher.check_exceptions
process_unhandled_twisted_exceptions = _twisted_catcher.check_exceptions
