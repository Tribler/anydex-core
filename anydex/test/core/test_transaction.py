import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.payment import Payment
from anydex.core.payment_id import PaymentId
from anydex.core.timestamp import Timestamp
from anydex.core.trade import Trade
from anydex.core.transaction import Transaction, TransactionId
from anydex.core.wallet_address import WalletAddress


class TransactionTestSuite(unittest.TestCase):
    """Transaction test cases."""

    def setUp(self):
        # Object creation
        self.maxDiff = None
        self.transaction_id = TransactionId(b'a' * 32)
        self.transaction = Transaction(self.transaction_id, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(100, 'MB')),
                                       OrderId(TraderId(b'3' * 20), OrderNumber(2)),
                                       OrderId(TraderId(b'2' * 20), OrderNumber(1)), Timestamp(0))
        self.proposed_trade = Trade.propose(TraderId(b'0' * 20),
                                            OrderId(TraderId(b'0' * 20), OrderNumber(2)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(3)),
                                            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(100, 'MB')), Timestamp(0))
        self.payment = Payment(TraderId(b'0' * 20), TransactionId(b'a' * 32),
                               AssetAmount(100, 'MB'), WalletAddress('a'), WalletAddress('b'),
                               PaymentId('aaa'), Timestamp(4))
        self.payment2 = Payment(TraderId(b'0' * 20), TransactionId(b'a' * 32),
                                AssetAmount(100, 'BTC'), WalletAddress('a'), WalletAddress('b'),
                                PaymentId('aaa'), Timestamp(4))

    def test_add_payment(self):
        """
        Test the addition of a payment to a transaction
        """
        self.transaction.add_payment(self.payment)
        self.assertEqual(self.transaction.transferred_assets.first.amount, 0)
        self.assertEqual(self.transaction.transferred_assets.second.amount, 100)
        self.assertTrue(self.transaction.payments)

    def test_next_payment(self):
        """
        Test the process of determining the next payment details during a transaction
        """
        self.assertEqual(self.transaction.next_payment(True), AssetAmount(100, 'BTC'))
        self.assertEqual(self.transaction.next_payment(False), AssetAmount(100, 'MB'))

    def test_is_payment_complete(self):
        """
        Test whether a payment is correctly marked as complete
        """
        self.assertFalse(self.transaction.is_payment_complete())
        self.transaction.add_payment(self.payment)
        self.assertFalse(self.transaction.is_payment_complete())
        self.transaction._transferred_assets = AssetPair(AssetAmount(100, 'BTC'), AssetAmount(100, 'MB'))
        self.assertTrue(self.transaction.is_payment_complete())

    def test_to_dictionary(self):
        """
        Test the to dictionary method of a transaction
        """
        self.assertDictEqual(self.transaction.to_block_dictionary(), {
            'trader_id': "33" * 20,
            'transaction_id': "61" * 32,
            'order_number': 2,
            'partner_trader_id': "32" * 20,
            'partner_order_number': 1,
            'assets': {
                'first': {
                    'amount': 100,
                    'type': 'BTC',
                },
                'second': {
                    'amount': 100,
                    'type': 'MB'
                }
            },
            'transferred': {
                'first': {
                    'amount': 0,
                    'type': 'BTC',
                },
                'second': {
                    'amount': 0,
                    'type': 'MB'
                }
            },
            'timestamp': 0,
        })

    def test_status(self):
        """
        Test the status of a transaction
        """
        self.assertEqual(self.transaction.status, 'pending')

        self.transaction.add_payment(self.payment)
        self.transaction.add_payment(self.payment2)
        self.assertEqual(self.transaction.status, 'completed')
