import abc


class Provider(metaclass=abc.ABCMeta):
    """
    Abstract class to create providers from.
    A provider is an abstraction used to interact with the blockchain.

    For each cryptocurrency, a new abstract class specific to that
    cryptocurrency should be created and any method specific to the cryptocurrency should be specified.
    That class can than be subclassed and implemented.
    """

    @abc.abstractmethod
    def submit_transaction(self, tx):
        """
        Submit a signed transaction to the network
        :param tx: the signed transaction to submit to the network
        :return: the transaction hash
        """
        return

    @abc.abstractmethod
    def get_balance(self, address):
        """
        Get the balance of the given address
        :param address: address to get the balance of
        :return: the balance
        """
        return

    @abc.abstractmethod
    def get_transactions(self, address):
        """
        Retrieve all the transactions associated with the given address
        :param address: The address of which to retrieve the transactions
        :return: A list of all transactions retrieved
        """
        return


class NotSupportedOperationException(Exception):
    """
    Exception raised whenever a provider operation is not supported by the specific concrete provider.
    """


class RequestException(Exception):
    """
    Used for throwing exceptions relating to requests.
    """


class ConnectionException(RequestException):
    """
    Used for throwing exceptions relating to connections.
    """


class RateExceeded(RequestException):
    """
    Used for throwing exceptions when requests have been sent too fast.
    """


class Blocked(RequestException):
    """
    Used for throwing exceptions when you are blocked by a server.
    """


class RequestLimit(Blocked):
    """
    Used for throwing exceptions when the request limit has been exceeded
    """


class InvalidNode(Exception):
    """
    Used for throwing exceptions when the given node is invalid ( you can't connect to it).
    """
