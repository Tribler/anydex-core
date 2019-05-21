from __future__ import absolute_import

import unittest

from core.assetamount import AssetAmount
from core.assetpair import AssetPair
from core.message import TraderId
from core.order import OrderId, OrderNumber
from core.payment import Payment
from core.payment_id import PaymentId
from core.timeout import Timestamp
from core.trade import Trade
from core.transaction import StartTransaction, Transaction, TransactionId, TransactionNumber
from core.transaction_manager import TransactionManager
from core.transaction_repository import MemoryTransactionRepository
from core.wallet_address import WalletAddress


class TransactionManagerTestSuite(unittest.TestCase):
    """Transaction manager test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository(b'0' * 20)
        self.transaction_manager = TransactionManager(self.memory_transaction_repository)

        self.transaction_id = TransactionId(TraderId(b'0' * 20), TransactionNumber(1))
        self.transaction = Transaction(self.transaction_id, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')),
                                       OrderId(TraderId(b'3' * 20), OrderNumber(2)),
                                       OrderId(TraderId(b'2' * 20), OrderNumber(1)), Timestamp(0))
        self.proposed_trade = Trade.propose(TraderId(b'0' * 20),
                                            OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(2)),
                                            AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')),
                                            Timestamp(1462224447117))
        self.start_transaction = StartTransaction(TraderId(b'0' * 20),
                                                  TransactionId(TraderId(b'0' * 20), TransactionNumber(1)),
                                                  OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                                  OrderId(TraderId(b'1' * 20), OrderNumber(2)), 1235,
                                                  AssetPair(AssetAmount(20, 'BTC'), AssetAmount(20, 'MB')),
                                                  Timestamp(0))

    def test_create_from_proposed_trade(self):
        # Test for create from a proposed trade
        transaction = self.transaction_manager.create_from_proposed_trade(self.proposed_trade)
        self.assertEquals(transaction, self.transaction_manager.find_by_id(transaction.transaction_id))

    def test_find_by_id(self):
        # Test for find by id
        self.assertEquals(None, self.transaction_manager.find_by_id(self.transaction_id))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals(self.transaction, self.transaction_manager.find_by_id(self.transaction_id))

    def test_find_all(self):
        # Test for find all
        self.assertEquals([], list(self.transaction_manager.find_all()))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEquals([self.transaction], list(self.transaction_manager.find_all()))

    def test_create_from_start_transaction(self):
        # Test for create from start transaction
        transaction = self.transaction_manager.create_from_start_transaction(self.start_transaction)
        self.assertEquals(transaction, self.transaction_manager.find_by_id(transaction.transaction_id))

    def test_create_payment_message(self):
        """
        Test the creation of a payment message
        """
        self.transaction.incoming_address = WalletAddress('abc')
        self.transaction.outgoing_address = WalletAddress('def')
        self.transaction.partner_incoming_address = WalletAddress('ghi')
        self.transaction.partner_outgoing_address = WalletAddress('jkl')
        payment_msg = self.transaction_manager.create_payment_message(TraderId(b'0' * 20),
                                                                      PaymentId('abc'), self.transaction,
                                                                      AssetAmount(1, 'BTC'),
                                                                      True)
        self.assertIsInstance(payment_msg, Payment)
