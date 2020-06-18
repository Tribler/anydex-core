import json
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto
from time import time
from urllib.parse import urlparse

from ipv8.util import fail

from anydex.config import get_anydex_configuration
from anydex.wallet.cryptocurrency import Cryptocurrency

_logger = logging.getLogger(__name__)


class Source(Enum):
    """
    Enum representing possible provider source for nodes.
    Currently supports nodes provided by users or by AnyDex.
    """

    DEFAULT = auto()
    USER = auto()


class HostConfig:
    """
    Holds attributes adherent to the host configuration.
    """

    def __init__(self, host: str, port: int, protocol: str = 'http'):
        self.host = host
        self.port = port
        self.protocol = protocol


class Node:
    """
    Concrete class to create nodes from.
    A node is an abstraction for a node component in a cryptocurrency network.
    `testnet` field will be used to determine whether to look for nodes in default hosts file.

    Each cryptocurrency should allow for a user-provided node implementation, as well as
    a DefaultNode-class implementation.
    """

    def __init__(self, name: str, host_config: HostConfig, source: Source, network: Cryptocurrency,
                 latency: float, username='', password='', testnet=False):
        self.name = name
        self.host = host_config.host
        self.port = host_config.port
        self.source = source
        self.network = network
        self.latency = latency
        self.protocol = host_config.protocol
        self.username = username
        self.password = password
        self.testnet = testnet

    def __repr__(self):
        return f'{self.name}\n' \
               f'address: {self.host}:{self.port}\n' \
               f'source: {self.source}\n' \
               f'network: {self.network.value}\n' \
               f'latency: {self.latency}\n' \
               f'protocol: {self.protocol}'


def create_node(network: Cryptocurrency, testnet=False) -> Node:
    """
    Constructs a Node from user-provided parameters if key is present in `config.py`-dictionary.
    Else: constructs Node picked from set of default nodes provided by AnyDex.

    Return CannotCreateNodeException if required parameters miss from user Node-config: host, port

    :param testnet: testnet node or not
    :param network: instance of Cryptocurrency enum
    :return: Node
    """
    config = get_anydex_configuration()
    params = {'network': network}

    if 'node' in config:
        _logger.info('Parsing user node config')

        node_config = config['node_config']
        params['source'] = Source.USER
        params['name'] = node_config.get('name', '')

        try:
            protocol, username, password, host, port = _parse_url(node_config['host'])
        except KeyError:
            return fail(CannotCreateNodeException('Missing key `host` from node config'))

        if port is None:
            return fail(CannotCreateNodeException('Missing port from `host` in node config'))

        params['protocol'] = protocol if protocol else 'http'
        params['username'] = username if username else ''
        params['password'] = password if username else ''

        _, params['latency'] = determine_latency(node_config['host'])

        params['host_config'] = HostConfig(host, port, params['protocol'])
    else:
        _logger.info('Finding best host from pool of default hosts')

        params['source'] = Source.DEFAULT
        params['name'] = ''

        default_hosts = read_default_hosts()

        try:
            if testnet:
                network_hosts = default_hosts[network.value]['testnet']
                params['testnet'] = True
            else:
                network_hosts = default_hosts[network.value]['non_testnet']
        except KeyError:
            return fail(CannotCreateNodeException(f'Missing default nodes for {network.value}'))

        # host format: protocol://username:password@domain:port
        selected_host, latency = select_best_host(network_hosts)
        protocol, username, password, host, port = _parse_url(selected_host)

        if username:
            params['username'] = username
        if password:
            params['password'] = password

        if protocol:
            params['host_config'] = HostConfig(host, port, protocol)
        else:
            params['host_config'] = HostConfig(host, port)

        params['latency'] = latency

    node = Node(**params)
    _logger.info('Using following node:\n%s', node)
    return node


class CannotCreateNodeException(Exception):
    """
    Raise exception from `create_node` if configuration is lacking.
    """


def read_default_hosts():
    """
    Read default nodes for each cryptocurrency from `hosts.json`.

    :return: return dictionary of cryptocurrency network and corresponding hosts
    """
    nodes = dict()

    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

    with open(os.path.join(__location__, 'hosts.json')) as file:
        try:
            nodes = json.loads(file.read())
        except json.JSONDecodeError as err:
            _logger.error('Default nodes file could not be decoded: %s', err)

    return nodes


def select_best_host(hosts) -> tuple:
    """
    Returns the host with the lowest latency of all hosts.
    Makes use of ThreadPoolExecutor to test in multi-threaded approach.

    :param hosts: list of host names including ports
    :return: tuple of host and latency
    """
    with ThreadPoolExecutor() as executor:
        latencies = executor.map(determine_latency, hosts)

    best_host = sorted(list(latencies), key=lambda el: el[1])[0]
    return best_host


def determine_latency(host: str) -> tuple:
    """
    Returns latency to server with address passed as parameter.
    Attempts to connect to `host` while timing the roundtrip.

    :param host: format protocol://username:password@domain
    :return: tuple of host and latency in ms as float
    """
    cfg = get_anydex_configuration()
    timeout = cfg['node_config']['timeout']

    retry: int = cfg['node_config']['retry']
    durations = []

    _, _, _, address, port = _parse_url(host)
    port = port if port else 80
    if address is None:
        return host, float('inf')

    for _ in range(retry):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # does not support IPv6 addresses
        sock.settimeout(timeout)

        start_time = time()
        try:
            _logger.info('Determining latency for %s at port %d', address, port)
            sock.connect((address, port))
            sock.shutdown(socket.SHUT_RD)
        except socket.timeout:
            _logger.warning('Ping attempt to host %s timed out after %f seconds', address, timeout)
            return host, float('inf')
        except OSError as err:
            _logger.error('Could not connect to host: %s', err)
            return host, float('inf')
        durations.append(time() - start_time)

    return host, round(_avg(durations) * 1000, 2)


def _avg(elements: list):
    return sum(elements) / len(elements)


def _parse_url(url: str) -> tuple:
    """
    Return parsed tuple of url components.

    :return: tuple of protocol, username, password, host and port
    """
    parsed = urlparse(url)
    protocol = parsed.scheme
    username = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port
    return protocol, username, password, host, port
