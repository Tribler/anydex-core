import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.timestamp import Timestamp
from anydex.core.transaction import Transaction, TransactionId
from anydex.core.transaction_repository import MemoryTransactionRepository


class MemoryTransactionRepositoryTestSuite(unittest.TestCase):
    """Memory transaction repository test cases."""

    def setUp(self):
        # Object creation
        self.memory_transaction_repository = MemoryTransactionRepository(b'0' * 20)
        self.transaction_id = TransactionId(b'a' * 32)
        self.transaction = Transaction(self.transaction_id, AssetPair(AssetAmount(10, 'BTC'), AssetAmount(10, 'MB')),
                                       OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                       OrderId(TraderId(b'2' * 20), OrderNumber(2)), Timestamp(0))

    def test_find_by_id(self):
        # Test for find by id
        self.assertEqual(None, self.memory_transaction_repository.find_by_id(self.transaction_id))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEqual(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))

    def test_delete_by_id(self):
        # Test for delete by id
        self.memory_transaction_repository.add(self.transaction)
        self.assertEqual(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))
        self.memory_transaction_repository.delete_by_id(self.transaction_id)
        self.assertEqual(None, self.memory_transaction_repository.find_by_id(self.transaction_id))

    def test_find_all(self):
        # Test for find all
        self.assertEqual([], list(self.memory_transaction_repository.find_all()))
        self.memory_transaction_repository.add(self.transaction)
        self.assertEqual([self.transaction], list(self.memory_transaction_repository.find_all()))

    def test_update(self):
        # Test for update
        self.memory_transaction_repository.add(self.transaction)
        self.memory_transaction_repository.update(self.transaction)
        self.assertEqual(self.transaction, self.memory_transaction_repository.find_by_id(self.transaction_id))
