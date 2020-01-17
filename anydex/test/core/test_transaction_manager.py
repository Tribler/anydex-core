import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.timestamp import Timestamp
from anydex.core.transaction import Transaction, TransactionId
from anydex.core.transaction_manager import TransactionManager
from anydex.core.transaction_repository import MemoryTransactionRepository


class TransactionManagerTestSuite(unittest.TestCase):
    """Transaction manager test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository(b'0' * 20)
        self.transaction_manager = TransactionManager(self.memory_transaction_repository)

        self.transaction_id = TransactionId(b'a' * 32)
        self.transaction = Transaction(self.transaction_id, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')),
                                       OrderId(TraderId(b'3' * 20), OrderNumber(2)),
                                       OrderId(TraderId(b'2' * 20), OrderNumber(1)), Timestamp(0))

    def test_find_by_id(self):
        # Test for find by id
        self.assertEqual(None, self.transaction_manager.find_by_id(self.transaction_id))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEqual(self.transaction, self.transaction_manager.find_by_id(self.transaction_id))

    def test_find_all(self):
        # Test for find all
        self.assertEqual([], list(self.transaction_manager.find_all()))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEqual([self.transaction], list(self.transaction_manager.find_all()))
