import logging
import socket
from enum import Enum, auto
from ipaddress import ip_address, IPv4Address
from time import time

from anydex.config import get_anydex_configuration

_logger = logging.getLogger(__name__)


class Source(Enum):
    """
    Enum representing possible provider source for nodes.
    Currently supports nodes provided by users or by AnyDex.
    """

    DEFAULT = auto()
    USER = auto()


class Cryptocurrency(Enum):
    """
    Enum representing curerntly implemented cryptocurrencies.
    """

    BITCOIN = auto()
    BANDWIDTH_TOKEN = auto()
    ETHEREUM = auto()
    RIPPLE = auto()
    LITECOIN = auto()
    IOTA = auto()
    MONERO = auto()
    ZCASH = auto()


class Node:
    """
    Concrete class to create nodes from.
    A node is an abstraction for a node component in a cryptocurrency network.

    Each cryptocurrency should allow for a user-provided node implementation, as well as
    a DefaultNode-class implementation.
    """

    def __init__(self, name: str, host: str, port: int, source: Source,
                 network: Cryptocurrency, country: str, latency: float):
        self.name = name
        self.host = host
        self.port = port
        self.source = source
        self.network = network
        self.country = country
        self.latency = latency

    def __repr__(self):
        return f'{self.name}\n' \
               f'address: {self.host}:{self.port}\n' \
               f'network: {self.network}\n' \
               f'country: {self.country}\n' \
               f'latency: {self.latency}'


def create_node(network: Cryptocurrency) -> Node:
    """
    Constructs a Node from user-provided parameters if key is present in `config.py`-dictionary.
    Else: constructs Node picked from set of default nodes provided by AnyDex.

    Raise MissingParameterException if required parameters miss from user Node-config: host, port

    :param network: instance of Cryptocurrency enum
    :return: Node
    """
    config = get_anydex_configuration()
    params = {'network': network}

    if 'node' in config:
        _logger.info('Parsing user node config')

        node_config = config['node']
        params['source'] = Source.USER
        params['name'] = node_config.get('name', '')

        try:
            params['host'] = node_config['host']
        except KeyError:
            raise MissingParameterException('Missing key `host` from node config')

        try:
            params['port'] = node_config['port']
        except KeyError:
            raise MissingParameterException('Missing key `port` from node config')

        # TODO determine country location
        # country = 'US'
        params['country'] = ''
    else:
        _logger.info('Finding best node from default node pool')

        params['source'] = Source.DEFAULT
        params['name'] = ''

        # TODO select best default node for user
        pass

        # TODO determine country location
        # country = 'US'
        params['country'] = ''

    params['latency'] = determine_latency(params['host'], params['port'])

    node = Node(**params)
    _logger.info(f'Using following node:\n{node}')
    return node


class MissingParameterException(Exception):
    pass


def determine_latency(host: str, port: int) -> float:
    """
    Returns latency to server with address passed as parameter.
    Attempts to connect to `port` at `host` while timing the roundtrip.

    :param host
    :param port
    :return: latency in ms as float
    """
    try:
        addr = ip_address(host)
    except ValueError:
        return float('inf')

    if isinstance(addr, IPv4Address):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    else:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

    cfg = get_anydex_configuration()
    timeout = cfg['default_node']['timeout']
    sock.settimeout(timeout)

    start_time = time()

    try:
        sock.connect((host, port))
        sock.shutdown(socket.SHUT_RD)
    except socket.timeout:
        _logger.warning(f'Ping attempt to host {host} timed out after {timeout} seconds')
        return float('inf')
    except OSError:
        return float('inf')

    return round((time() - start_time) * 1000, 2)
