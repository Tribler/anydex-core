from datetime import datetime
from decimal import Decimal
from time import mktime

import monero.backends.jsonrpc
from monero.transaction import Payment, OutgoingPayment, IncomingPayment, Transaction
from requests.exceptions import ConnectionError

from anydex.test.base import AbstractServer
from anydex.test.util import MockObject
from anydex.wallet.cryptocurrency import Cryptocurrency
from anydex.wallet.monero.xmr_wallet import MoneroWallet, MoneroTestnetWallet, WalletConnectionError
from anydex.wallet.wallet import InsufficientFunds

TEST_HASH = 'test_transaction_hash'
# see https://monerodocs.org/public-address/standard-address/ for source and explanation
TEST_ADDRESS = '4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYTRj5UzqtReoS44qo9mtmXCqY45DJ852K5Jv2684Rge'
# retrieved from https://monero-python.readthedocs.io/en/latest/transactions.html
TEST_TXID = 'e9a71c01875bec20812f71d155bfabf42024fde3ec82475562b817dcc8cbf8dc'
TEST_PID = 'test_paymentid'


def succeed_backend():
    mock_backend = MockObject()
    mock_backend.accounts = lambda *_: [monero.account.Account(mock_backend, 0)]
    mock_backend.addresses = lambda **_: [TEST_ADDRESS]
    mock_backend.new_address = lambda **_: (TEST_ADDRESS, 1)
    monero.backends.jsonrpc.JSONRPCWallet.__new__ = lambda *_, **__: mock_backend


def fail_backend():
    mock_backend = MockObject()

    def fail_request():
        raise ConnectionError

    mock_backend.accounts = lambda *_: fail_request()
    monero.backends.jsonrpc.JSONRPCWallet.__new__ = lambda *_, **__: mock_backend


class TestMoneroWallet(AbstractServer):

    def test_wallet_fields(self):
        """
        Verify correct values set for fields in Monero non-TESTNET wallet instance.
        """
        MoneroWallet.TESTNET = False
        w = MoneroWallet(host='192.168.178.1')
        self.assertEqual('monero', w.network)
        self.assertEqual(0, w.min_confirmations)
        self.assertEqual('192.168.178.1', w.host)
        self.assertEqual(18081, w.port)
        self.assertIsNone(w.wallet)
        w.cancel_all_pending_tasks()

    async def test_wallet_connection_alive_fail(self):
        """
        Test _wallet_connection_alive method in case wallet is not created yet.
        """
        w = MoneroWallet()
        fail_backend()
        self.assertFalse(w._wallet_connection_alive())
        w.cancel_all_pending_tasks()

    async def test_wallet_connection_alive_success(self):
        """
        Test _wallet_connection_alive method in case wallet is has been created.
        """
        w = MoneroWallet()
        succeed_backend()
        result = w.create_wallet()
        self.assertIsNone(result.result())
        self.assertTrue(w.created)
        self.assertTrue(w._wallet_connection_alive())
        w.cancel_all_pending_tasks()

    def test_get_name(self):
        """
        Test `get_name` method on Monero wallet.
        """
        w = MoneroWallet()
        self.assertEqual(Cryptocurrency.MONERO.value, w.get_name())
        w.cancel_all_pending_tasks()

    async def test_wallet_creation_fail(self):
        """
        Verify wallet create method in case `wallet-rpc-server` is not running.
        """
        w = MoneroWallet()  # use default host, port configuration
        fail_backend()
        self.assertAsyncRaises(WalletConnectionError, w.create_wallet())
        self.assertFalse(w.created)
        w.cancel_all_pending_tasks()

    async def test_wallet_creation_success(self):
        """
        Verify wallet create method in case `wallet-rpc-server` is running on correct host/port.
        """
        w = MoneroWallet()  # use default host, port configuration
        succeed_backend()
        result = w.create_wallet()
        self.assertIsNone(result.result())
        self.assertTrue(w.created)
        w.cancel_all_pending_tasks()

    async def test_wallet_creation_success_node(self):
        """
        Verify host and port parameters set to Wallet backend.
        """
        test_host = '192.168.178.1'
        test_port = 1903

        w = MoneroWallet(host=test_host, port=test_port)
        succeed_backend()
        result = w.create_wallet()
        self.assertIsNone(result.result())
        self.assertEqual(test_host, w.host)
        self.assertEqual(test_port, w.port)
        w.cancel_all_pending_tasks()

    async def test_get_balance_no_wallet(self):
        """
        Check balance in case no connection to wallet exists yet.
        """
        w = MoneroWallet()
        self.assertDictEqual({
            'available': 0,
            'pending': 0,
            'currency': 'XMR',
            'precision': 12
        }, await w.get_balance())
        w.cancel_all_pending_tasks()

    async def test_get_balance_wallet(self):
        """
        Check balance in case wallet connection exists.
        """
        w = MoneroWallet()
        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None
        mock_wallet.balance = lambda unlocked: 20.2

        w.wallet = mock_wallet

        self.assertDictEqual({
            'available': 20.2,
            'pending': 0,
            'currency': 'XMR',
            'precision': 12
        }, await w.get_balance())
        w.cancel_all_pending_tasks()

    async def test_transfer_no_wallet(self):
        """
        Attempt XMR transfer in case no wallet exists.
        """
        w = MoneroWallet()
        result = await w.transfer(20.2, 'test_address',
                                  payment_id='test_id',
                                  priority=1,
                                  unlock_time=0)
        self.assertIsNone(result.result())
        w.cancel_all_pending_tasks()

    async def test_transfer_wallet_enough(self):
        """
        Attempt XMR transfer in case wallet exists and enough XMR available.
        """
        w = MoneroWallet()
        succeed_backend()
        await w.create_wallet()

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None
        mock_wallet.balance = lambda unlocked: 20.2

        mock_transaction = MockObject()
        mock_transaction.hash = TEST_HASH

        mock_wallet.transfer = lambda *_, **__: mock_transaction

        w.wallet = mock_wallet

        result = await w.transfer(20.1, 'test_address',
                                  payment_id='test_id',
                                  priority=1,
                                  unlock_time=0)
        self.assertEqual(TEST_HASH, result.result())
        w.cancel_all_pending_tasks()

    async def test_transfer_wallet_not_enough(self):
        """
        Attempt XMR transfer in case not enough XMR available.
        """
        w = MoneroWallet()
        succeed_backend()
        await w.create_wallet()

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None
        mock_wallet.balance = lambda unlocked: 20.2

        w.wallet = mock_wallet

        self.assertAsyncRaises(InsufficientFunds, w.transfer(47.8, 'test_address',
                                                             payment_id='test_id',
                                                             priority=1,
                                                             unlock_time=0))
        w.cancel_all_pending_tasks()

    async def test_transfer_multiple_no_wallet(self):
        """
        Make multiple transfers, but no wallet initialized.
        """
        w = MoneroWallet()

        transfers = [
            (TEST_ADDRESS, Decimal('20.2')),
            (TEST_ADDRESS, Decimal('7.8'))
        ]

        self.assertAsyncRaises(WalletConnectionError, w.transfer_multiple(transfers, priority=3))
        w.cancel_all_pending_tasks()

    async def test_transfer_multiple_wallet(self):
        """
        Make multiple transfers at once, enough balance.
        """
        w = MoneroWallet()

        transfers = [
            (TEST_ADDRESS, Decimal('20.2')),
            (TEST_ADDRESS, Decimal('7.8'))
        ]

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda: None
        mock_wallet.balance = lambda **_: 57.3
        mock_wallet.transfer_multiple = \
            lambda *_, **__: [(Transaction(hash=TEST_HASH), Decimal('20.2')),
                              (Transaction(hash=TEST_HASH), Decimal('7.8'))]

        w.wallet = mock_wallet

        hashes = await w.transfer_multiple(transfers, priority=3)
        self.assertEqual(2, len(hashes.result()))
        w.cancel_all_pending_tasks()

    async def test_transfer_multiple_wallet_not_enough(self):
        """
        Make multiple transfers at once, but not enough balance.
        """
        w = MoneroWallet()

        transfers = [
            (TEST_ADDRESS, Decimal('20.2')),
            (TEST_ADDRESS, Decimal('7.8'))
        ]

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda: None
        mock_wallet.balance = lambda **_: 21.3
        w.wallet = mock_wallet

        self.assertAsyncRaises(InsufficientFunds, await w.transfer_multiple(transfers, priority=3))
        w.cancel_all_pending_tasks()

    def test_get_address_no_wallet(self):
        """
        Get Monero wallet address without wallet initialized.
        """
        w = MoneroWallet()
        addr = w.get_address()
        self.assertEqual('', addr)
        w.cancel_all_pending_tasks()

    def test_get_address_wallet(self):
        """
        Get Monero wallet address with wallet initialized.
        """
        w = MoneroWallet()
        mock_wallet = MockObject()
        mock_wallet.refresh = lambda: None
        mock_wallet.address = lambda: TEST_ADDRESS
        w.wallet = mock_wallet
        addr = w.get_address()
        self.assertEqual(TEST_ADDRESS, addr)
        w.cancel_all_pending_tasks()

    def test_get_transactions_no_wallet(self):
        """
        Attempt retrieval of transactions from Monero wallet in case wallet does not exist.
        """
        w = MoneroWallet()
        self.assertAsyncRaises(WalletConnectionError, w.get_transactions())
        w.cancel_all_pending_tasks()

    async def test_get_transactions_wallet(self):
        """
        Test retrieval of transactions from Monero wallet in case wallet does exist.
        """
        w = MoneroWallet()

        timestamp = datetime.now()

        p1 = IncomingPayment(amount=30.3, payment_id=TEST_PID, local_address=TEST_ADDRESS)
        p1.transaction = Transaction(hash=TEST_HASH, height=120909, fee=1, timestamp=timestamp,
                                     confirmations=21)

        p2 = IncomingPayment(amount=12.7, payment_id=TEST_PID, local_address=TEST_ADDRESS)
        p2.transaction = Transaction(hash=TEST_HASH, height=118909, fee=1, timestamp=timestamp,
                                     confirmations=17)

        ts = mktime(timestamp.timetuple())

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda: None
        mock_wallet.incoming = lambda **_: [p1]
        mock_wallet.outgoing = lambda **_: [p2]
        w.wallet = mock_wallet

        transactions = await w.get_transactions()

        self.assertDictEqual({
            'id': TEST_HASH,
            'outgoing': False,
            'from': '',
            'to': TEST_ADDRESS,
            'amount': 30.3,
            'fee_amount': 1,
            'currency': 'XMR',
            'timestamp': ts,
            'description': 'Confirmations: 21'
        }, transactions.result()[0])

        self.assertDictEqual({
            'id': TEST_HASH,
            'outgoing': False,
            'from': '',
            'to': TEST_ADDRESS,
            'amount': 12.7,
            'fee_amount': 1,
            'currency': 'XMR',
            'timestamp': ts,
            'description': 'Confirmations: 17'
        }, transactions.result()[1])
        w.cancel_all_pending_tasks()

    async def test_get_payments(self):
        """
        Get all payments (incoming and outgoing) corresponding to the wallet.
        """
        w = MoneroWallet()
        succeed_backend()
        await w.create_wallet()

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None

        p1 = Payment(amount=30.3, payment_id=TEST_PID)
        p1.transaction = Transaction(hash=TEST_HASH, height=120909)

        p2 = Payment(amount=12.7, payment_id=TEST_PID)
        p2.transaction = Transaction(has=TEST_HASH, height=118909)

        mock_wallet.incoming = lambda **_: [p1]
        mock_wallet.outgoing = lambda **_: [p2]

        w.wallet = mock_wallet

        payments = await w._get_payments()
        self.assertEqual(2, len(payments))
        w.cancel_all_pending_tasks()

    def test_normalize_transaction_incoming_payment(self):
        """
        Test for Payment instance being IncomingPayment.
        Verify monero.transaction.Transaction instances are correctly formatted.
        """
        w = MoneroWallet()
        payment = IncomingPayment()
        payment.local_address = TEST_ADDRESS
        payment.amount = 9.2

        timestamp = datetime.now()

        mock_transaction = MockObject()
        mock_transaction.hash = TEST_HASH
        mock_transaction.fee = 0.78
        ts = mktime(timestamp.timetuple())
        mock_transaction.timestamp = timestamp
        mock_transaction.confirmations = 12

        payment.transaction = mock_transaction

        self.assertDictEqual({
            'id': TEST_HASH,
            'outgoing': False,
            'from': '',
            'to': TEST_ADDRESS,
            'amount': 9.2,
            'fee_amount': 0.78,
            'currency': 'XMR',
            'timestamp': ts,
            'description': 'Confirmations: 12'
        }, w._normalize_transaction(payment))
        w.cancel_all_pending_tasks()

    def test_normalize_transaction_outgoing_payment(self):
        """
        Verify monero.transaction.Transaction instances are correctly formatted.
        """
        w = MoneroWallet()
        payment = OutgoingPayment()
        payment.local_address = TEST_ADDRESS
        payment.amount = 11.8

        timestamp = datetime.now()

        mock_transaction = MockObject()
        mock_transaction.hash = TEST_HASH
        mock_transaction.fee = 0.3
        ts = mktime(timestamp.timetuple())
        mock_transaction.timestamp = timestamp
        mock_transaction.confirmations = 23

        payment.transaction = mock_transaction

        self.assertDictEqual({
            'id': TEST_HASH,
            'outgoing': True,
            'from': TEST_ADDRESS,
            'to': '',
            'amount': 11.8,
            'fee_amount': 0.3,
            'currency': 'XMR',
            'timestamp': ts,
            'description': 'Confirmations: 23'
        }, w._normalize_transaction(payment))
        w.cancel_all_pending_tasks()

    def test_get_incoming_payments_no_wallet(self):
        """
        Get incoming payments for Monero wallet in case no wallet exists.
        """
        w = MoneroWallet()
        self.assertAsyncRaises(WalletConnectionError, w.get_incoming_payments())
        w.cancel_all_pending_tasks()

    async def test_get_incoming_payments_wallet(self):
        """
        Get incoming payments for Monero wallet in case wallet exists.
        """
        w = MoneroWallet()

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None
        mock_wallet.incoming = lambda **_: [Payment()]
        w.wallet = mock_wallet

        result = await w.get_incoming_payments()

        self.assertIsNotNone(result)
        self.assertTrue(isinstance(result[0], Payment))
        w.cancel_all_pending_tasks()

    def test_get_outgoing_payments_no_wallet(self):
        """
        Get outgoing payments for Monero wallet in case no wallet exists.
        """
        w = MoneroWallet()
        self.assertAsyncRaises(WalletConnectionError, w.get_outgoing_payments())
        w.cancel_all_pending_tasks()

    async def test_get_outgoing_payments_wallet(self):
        """
        Get outgoing payments for Monero wallet in case wallet exists.
        """
        w = MoneroWallet()

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None
        mock_wallet.outgoing = lambda **_: [Payment()]
        w.wallet = mock_wallet

        result = await w.get_outgoing_payments(False)

        self.assertIsNotNone(result)
        self.assertTrue(isinstance(result[0], Payment))
        w.cancel_all_pending_tasks()

    def test_min_unit(self):
        """
        Verify minimal transfer unit.
        """
        w = MoneroWallet()
        self.assertEqual(1, w.min_unit())  # 1 piconero
        w.cancel_all_pending_tasks()

    def test_precision(self):
        """
        Verify Monero default precision.
        """
        w = MoneroWallet()
        self.assertEqual(12, w.precision())
        w.cancel_all_pending_tasks()

    def test_get_identifier(self):
        """
        Verify correct identifier is returned.
        """
        w = MoneroWallet()
        self.assertEqual('XMR', w.get_identifier())
        w.cancel_all_pending_tasks()

    def test_get_confirmations_no_wallet(self):
        """
        Verify number of confirmations returned in case wallet does not exist.
        """
        w = MoneroWallet()
        self.assertIsNone(w.wallet)
        p = Payment()
        self.assertAsyncRaises(WalletConnectionError, w.get_confirmations(p))
        w.cancel_all_pending_tasks()

    async def test_get_confirmations_wallet(self):
        """
        Verify number of confirmations returned in case wallet does exist.
        """
        w = MoneroWallet()
        self.assertIsNone(w.wallet)
        succeed_backend()
        await w.create_wallet()
        self.assertIsNotNone(w.wallet)

        mock_wallet = MockObject()
        mock_wallet.refresh = lambda *_: None
        mock_wallet.confirmations = lambda *_: 4
        w.wallet = mock_wallet

        p = Payment()
        self.assertEqual(4, await w.get_confirmations(p))
        w.cancel_all_pending_tasks()

    def test_new_address(self):
        """
        Test creation of new address in main wallet account.
        """
        w = MoneroWallet()

        succeed_backend()
        w.create_wallet()
        self.assertListEqual([TEST_ADDRESS], w.get_addresses())
        self.assertEqual(TEST_ADDRESS, w.generate_subaddress())

    def test_get_addresses(self):
        """
        Test retrieval of addresses in main wallet account.
        """
        w = MoneroWallet()

        succeed_backend()
        w.create_wallet()
        addresses = w.get_addresses()

        self.assertEqual(1, len(addresses))
        self.assertListEqual([TEST_ADDRESS], addresses)


class TestTestnetMoneroWallet(AbstractServer):

    def test_wallet_fields(self):
        """
        Verify Testnet Wallet-specific values for wallet fields.
        """
        w = MoneroTestnetWallet()
        self.assertTrue(w.TESTNET)
        self.assertEqual('tribler_testnet', w.wallet_name)
        w.cancel_all_pending_tasks()

    def test_get_name(self):
        """
        Ensure name of Monero testnet wallet differs from regular Monero wallet.
        """
        w = MoneroTestnetWallet()
        self.assertEqual('Testnet XMR', w.get_name())
        w.cancel_all_pending_tasks()

    def test_get_identifier(self):
        """
        Ensure identifier of Monero testnet wallet is equivalent to `TXMR`
        """
        w = MoneroTestnetWallet()
        self.assertEqual('TXMR', w.get_identifier())
        w.cancel_all_pending_tasks()
