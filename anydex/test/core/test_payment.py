import unittest

from anydex.core.assetamount import AssetAmount
from anydex.core.message import TraderId
from anydex.core.payment import Payment
from anydex.core.payment_id import PaymentId
from anydex.core.timestamp import Timestamp
from anydex.core.transaction import TransactionId
from anydex.core.wallet_address import WalletAddress


class PaymentTestSuite(unittest.TestCase):
    """Payment test cases."""

    def setUp(self):
        # Object creation
        self.payment = Payment(TraderId(b'0' * 20),
                               TransactionId(b'a' * 32),
                               AssetAmount(3, 'BTC'),
                               WalletAddress('a'), WalletAddress('b'),
                               PaymentId('aaa'), Timestamp(4000))

    def test_to_dictionary(self):
        """
        Test the dictionary representation of a payment
        """
        self.assertDictEqual(self.payment.to_dictionary(), {
            "trader_id": "30" * 20,
            "transaction_id": "61" * 32,
            "transferred": {
                "amount": 3,
                "type": "BTC"
            },
            "payment_id": 'aaa',
            "address_from": 'a',
            "address_to": 'b',
            "timestamp": 4000,
        })
