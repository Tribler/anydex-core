import unittest

from anydex.core import DeclinedTradeReason
from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.timestamp import Timestamp
from anydex.core.trade import CounterTrade, DeclinedTrade, ProposedTrade, Trade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

    def setUp(self):
        # Object creation
        self.trade = Trade(TraderId(b'0' * 20),
                           OrderId(TraderId(b'0' * 20), OrderNumber(3)),
                           OrderId(TraderId(b'0' * 20), OrderNumber(4)), 1234, Timestamp(1462224447117))

    def test_to_network(self):
        # Test for to network
        self.assertEqual(NotImplemented, self.trade.to_network())


class ProposedTradeTestSuite(unittest.TestCase):
    """Proposed trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(TraderId(b'0' * 20),
                                            OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                            AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447117))

    def test_to_network(self):
        # Test for to network
        self.assertEqual((TraderId(b'0' * 20), Timestamp(1462224447117),
                           OrderNumber(1), OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                           self.proposed_trade.proposal_id,
                           AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB'))), self.proposed_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,),
                                               {"trader_id": TraderId(b'0' * 20),
                                                "order_number": OrderNumber(1),
                                                "recipient_order_id": OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                                "proposal_id": 1234,
                                                "timestamp": Timestamp(1462224447117),
                                                "assets": AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB'))}))

        self.assertEqual(TraderId(b'0' * 20), data.trader_id)
        self.assertEqual(OrderId(TraderId(b'0' * 20), OrderNumber(1)), data.order_id)
        self.assertEqual(OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEqual(1234, data.proposal_id)
        self.assertEqual(AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), data.assets)
        self.assertEqual(Timestamp(1462224447117), data.timestamp)


class DeclinedTradeTestSuite(unittest.TestCase):
    """Declined trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(TraderId(b'0' * 20),
                                            OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                            AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447117))
        self.declined_trade = Trade.decline(TraderId(b'0' * 20),
                                            Timestamp(1462224447117), self.proposed_trade,
                                            DeclinedTradeReason.ORDER_COMPLETED)

    def test_to_network(self):
        # Test for to network
        data = self.declined_trade.to_network()

        self.assertEqual(data[0], TraderId(b'0' * 20))
        self.assertEqual(data[1], Timestamp(1462224447117))
        self.assertEqual(data[2], OrderNumber(2))
        self.assertEqual(data[3], OrderId(TraderId(b'0' * 20), OrderNumber(1)))
        self.assertEqual(data[4], self.proposed_trade.proposal_id)

    def test_from_network(self):
        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,),
                                               {"trader_id": TraderId(b'0' * 20),
                                                "order_number": OrderNumber(1),
                                                "recipient_order_id": OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                                "proposal_id": 1235,
                                                "timestamp": Timestamp(1462224447117),
                                                "decline_reason": 0}))

        self.assertEqual(TraderId(b'0' * 20), data.trader_id)
        self.assertEqual(OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEqual(1235, data.proposal_id)
        self.assertEqual(Timestamp(1462224447117), data.timestamp)

    def test_decline_reason(self):
        """
        Test the declined reason
        """
        self.assertEqual(self.declined_trade.decline_reason, DeclinedTradeReason.ORDER_COMPLETED)


class CounterTradeTestSuite(unittest.TestCase):
    """Counter trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(TraderId(b'0' * 20),
                                            OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                            AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447117))
        self.counter_trade = Trade.counter(TraderId(b'0' * 20), AssetPair(AssetAmount(60, 'BTC'),
                                                                          AssetAmount(30, 'MB')),
                                           Timestamp(1462224447117), self.proposed_trade)

    def test_to_network(self):
        # Test for to network
        self.assertEqual(
            ((TraderId(b'0' * 20), Timestamp(1462224447117), OrderNumber(2),
              OrderId(TraderId(b'0' * 20), OrderNumber(1)), self.proposed_trade.proposal_id,
              AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')))), self.counter_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = CounterTrade.from_network(type('Data', (object,),
                                              {"trader_id": TraderId(b'0' * 20),
                                               "timestamp": Timestamp(1462224447117),
                                               "order_number": OrderNumber(1),
                                               "recipient_order_id": OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                               "proposal_id": 1236,
                                               "assets": AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), }))

        self.assertEqual(TraderId(b'0' * 20), data.trader_id)
        self.assertEqual(OrderId(TraderId(b'0' * 20), OrderNumber(1)), data.order_id)
        self.assertEqual(OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEqual(1236, data.proposal_id)
        self.assertEqual(AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')), data.assets)
        self.assertEqual(Timestamp(1462224447117), data.timestamp)
