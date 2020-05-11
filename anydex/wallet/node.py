from anydex.config import get_anydex_configuration


class Node:
    """
    Concrete class to create nodes from.
    A node is an abstraction for a node component in a cryptocurrency network.

    Each cryptocurrency should allow for a user-provided node implementation, as well as
    a DefaultNode-class implementation.
    """

    def __init__(self, name, host, port, source, network, country, latency=float('inf')):
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


def create_node() -> Node:
    config = get_anydex_configuration()
    params = {}

    if 'node' in config:
        node_config = config['node']

        # TODO implement user-provided node
        pass
    else:
        # TODO propose candidate default nodes to user
        pass

    return Node(**params)


class MissingParameterException(Exception):
    pass


class ParameterValidationError(Exception):
    pass
