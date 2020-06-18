import unittest

import anydex.wallet.node.node as node
from anydex.wallet.cryptocurrency import Cryptocurrency


class TestNode(unittest.TestCase):
    """
    Test the Node class.
    """

    def setUp(self):
        self.test_url = 'https://www.tribler.org'
        self.host = 'www.tribler.org'

        self.hosts = node.read_default_hosts()

        self.ethereum_hosts = []
        for ethereum_host in self.hosts['ethereum']['non_testnet']:
            _, _, _, host, _ = node._parse_url(ethereum_host)
            self.ethereum_hosts.append(host)

        self.monero_hosts = []
        for ethereum_host in self.hosts['monero']['non_testnet']:
            _, _, _, host, _ = node._parse_url(ethereum_host)
            self.monero_hosts.append(host)

    def test_avg(self):
        """
        Test getting average of elements in a list.
        """
        elements = [1, 2.3, 4, 5]
        self.assertEqual(3.075, node._avg(elements))

    def test_parse_url(self):
        """
        Test url parse.
        Verify correct components are returned.
        """
        result = node._parse_url(self.test_url)
        self.assertEqual(5, len(result))

        self.assertEqual('https', result[0])
        self.assertEqual(self.host, result[3])
        self.assertIsNone(result[1])
        self.assertIsNone(result[2])
        self.assertIsNone(result[4])

    def test_source(self):
        """
        Verify correct values are set for Enum components.
        """
        src = node.Source.USER
        self.assertEqual(2, src.value)

    def test_host_config(self):
        """
        Verify instantiation of HostConfig instance.
        """
        host_config = node.HostConfig(self.host, 80, 'https')

        self.assertEqual(self.host, host_config.host)
        self.assertEqual(80, host_config.port)
        self.assertEqual('https', host_config.protocol)

    def test_node_instantiation(self):
        """
        Verify correct instantiation of Node instance.
        """
        host_config = node.HostConfig(self.host, 80, 'https')
        test_node = node.Node('test_node', host_config, node.Source.USER, Cryptocurrency.MONERO,
                              20.2, 'test_username')  # leave password void

        self.assertEqual('', test_node.password)
        self.assertEqual(host_config.host, test_node.host)

    def test_create_node_default_hosts_many(self):
        """
        Verify `create_node` function creates a valid Node instance.
        Node instance should belong to the Monero cryptocurrency.
        Verify process for many provides node hosts.
        """
        test_node = node.create_node(Cryptocurrency.MONERO)
        self.assertEqual('', test_node.name)
        self.assertIsNotNone(test_node.host)
        self.assertIn(test_node.host, self.monero_hosts)
        self.assertEqual(Cryptocurrency.MONERO, test_node.network)

    def test_create_node_default_hosts_few(self):
        """
        Verify `create_node` function creates a valid Node instance.
        Node instance should belong to the Ethereum cryptocurrency.
        Verify process for just a few node hosts.
        """
        test_node = node.create_node(Cryptocurrency.ETHEREUM)
        self.assertEqual('', test_node.name)
        self.assertIn(test_node.host, self.ethereum_hosts)
        self.assertEqual(Cryptocurrency.ETHEREUM, test_node.network)

    def test_create_node_non_existent_network(self):
        """
        Verify that `create_node` fails in case of faulty `network`.
        """
        with self.assertRaises(AttributeError):
            node.create_node('test_network')
