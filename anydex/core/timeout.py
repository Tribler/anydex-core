import time


class Timeout:
    """Used for having a validated instance of a timeout that we can easily check if it still valid."""

    def __init__(self, timeout: int):
        """
        :param timeout: Integer representation of a timeout
        :type timeout: int
        :raises TypeError: Thrown when the type of timeout is invalid
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        if not isinstance(timeout, int):
            raise TypeError("Timeout must be an integer")

        if timeout < 0:
            raise ValueError("Timeout must be positive or zero")

        self._timeout = timeout

    def is_timed_out(self, timestamp):
        """
        Return if a timeout has occurred

        :param timestamp: A timestamp
        :type timestamp: Timestamp
        :return: True if timeout has occurred, False otherwise
        :rtype: bool
        """
        return int(time.time() * 1000) - int(timestamp) >= self._timeout * 1000

    def __int__(self):
        return self._timeout

    def __hash__(self):
        return hash(self._timeout)
