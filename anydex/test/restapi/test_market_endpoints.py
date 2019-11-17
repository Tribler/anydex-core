import anydex.util.json_util as json
from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.payment import Payment
from anydex.core.payment_id import PaymentId
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp
from anydex.core.trade import AcceptedTrade
from anydex.core.transaction import Transaction, TransactionId
from anydex.core.wallet_address import WalletAddress
from anydex.test.restapi.base import TestRestApiBase
from anydex.test.util import MockObject, timeout


class TestMarketEndpoint(TestRestApiBase):

    def add_transaction_and_payment(self):
        """
        Add a transaction and a payment to the market
        """
        self.accepted_trade = AcceptedTrade(TraderId(b'0' * 20), OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(1)), 1234,
                                            AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timestamp(0))
        transaction = Transaction.from_accepted_trade(self.accepted_trade, TransactionId(b'a' * 32))

        payment = Payment(TraderId(b'0' * 20), transaction.transaction_id,
                          AssetAmount(20, 'BTC'), WalletAddress('a'), WalletAddress('b'),
                          PaymentId('aaa'), Timestamp(4000))
        transaction.add_payment(payment)
        self.nodes[0].overlay.transaction_manager.transaction_repository.update(transaction)

        return transaction

    def create_fake_block(self):
        """
        Create a dummy block and return it
        """
        block = MockObject()
        block.hash = b'a'
        return block

    @timeout(10)
    async def test_get_asks(self):
        """
        Test whether the API returns the right asks in the order book when performing a request
        """
        await self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        self.should_check_equality = False
        json_response = await self.do_request('asks', expected_code=200)
        self.assertIn('asks', json_response)
        self.assertEqual(len(json_response['asks']), 1)
        self.assertIn('ticks', json_response['asks'][0])
        self.assertEqual(len(json_response['asks'][0]['ticks']), 1)

    @timeout(10)
    async def test_create_ask(self):
        """
        Test whether we can create an ask using the API
        """
        self.should_check_equality = False
        post_data = {
            'first_asset_amount': 10,
            'second_asset_amount': 10,
            'first_asset_type': 'DUM1',
            'second_asset_type': 'DUM2',
            'timeout': 3400
        }
        await self.do_request('asks', expected_code=200, request_type='PUT', post_data=post_data)
        self.assertEqual(len(self.nodes[0].overlay.order_book.asks), 1)

    @timeout(10)
    async def test_create_ask_no_amount(self):
        """
        Test for an error when we don't add an asset amount when creating an ask
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'first_asset_type': 'DUM1', 'second_asset_type': 'DUM2', 'timeout': 3400}
        await self.do_request('asks', expected_code=400, request_type='PUT', post_data=post_data)

    @timeout(10)
    async def test_create_ask_no_type(self):
        """
        Test for an error when we don't add an asset type when creating an ask
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'second_asset_amount': 10, 'second_asset_type': 'DUM2', 'timeout': 3400}
        await self.do_request('asks', expected_code=400, request_type='PUT', post_data=post_data)

    @timeout(10)
    async def test_get_bids(self):
        """
        Test whether the API returns the right bids in the order book when performing a request
        """
        await self.nodes[0].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        self.should_check_equality = False
        json_response = await self.do_request('bids', expected_code=200)
        self.assertIn('bids', json_response)
        self.assertEqual(len(json_response['bids']), 1)
        self.assertIn('ticks', json_response['bids'][0])
        self.assertEqual(len(json_response['bids'][0]['ticks']), 1)

    @timeout(10)
    async def test_create_bid(self):
        """
        Test whether we can create a bid using the API
        """
        self.should_check_equality = False
        post_data = {
            'first_asset_amount': 10,
            'second_asset_amount': 10,
            'first_asset_type': 'DUM1',
            'second_asset_type': 'DUM2',
            'timeout': 3400
        }
        await self.do_request('bids', expected_code=200, request_type='PUT', post_data=post_data)
        self.assertEqual(len(self.nodes[0].overlay.order_book.bids), 1)

    @timeout(10)
    async def test_create_bid_no_amount(self):
        """
        Test for an error when we don't add an asset amount when creating a bid
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'first_asset_type': 'DUM1', 'second_asset_type': 'DUM2', 'timeout': 3400}
        await self.do_request('bids', expected_code=400, request_type='PUT', post_data=post_data)

    @timeout(10)
    async def test_create_bid_no_type(self):
        """
        Test for an error when we don't add an asset type when creating a bid
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'second_asset_amount': 10, 'second_asset_type': 'DUM2', 'timeout': 3400}
        await self.do_request('bids', expected_code=400, request_type='PUT', post_data=post_data)

    @timeout(10)
    async def test_get_transactions(self):
        """
        Test whether the API returns the right transactions in the order book when performing a request
        """
        self.add_transaction_and_payment()
        self.should_check_equality = False
        json_response = await self.do_request('transactions', expected_code=200)
        self.assertIn('transactions', json_response)
        self.assertEqual(len(json_response['transactions']), 1)

    @timeout(10)
    async def test_get_payment_not_found(self):
        """
        Test whether the API returns a 404 when a payment cannot be found
        """
        self.should_check_equality = False
        await self.do_request('market/transactions/%s/3/payments' % ('30' * 20), expected_code=404)

    @timeout(10)
    async def test_get_orders(self):
        """
        Test whether the API returns the right orders when we perform a request
        """

        self.nodes[0].overlay.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(3600))

        self.should_check_equality = False
        json_response = await self.do_request('orders', expected_code=200)
        self.assertIn('orders', json_response)
        self.assertEqual(len(json_response['orders']), 1)

    @timeout(10)
    async def test_get_payments(self):
        """
        Test whether the API returns the right payments when we perform a request
        """
        transaction = self.add_transaction_and_payment()
        self.should_check_equality = False
        json_response = await self.do_request('transactions/%s/payments' % transaction.transaction_id.as_hex(),
                                              expected_code=200)
        self.assertIn('payments', json_response)
        self.assertEqual(len(json_response['payments']), 1)

    @timeout(10)
    async def test_cancel_order_not_found(self):
        """
        Test whether a 404 is returned when we try to cancel an order that does not exist
        """
        self.nodes[0].overlay.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(3600))
        self.should_check_equality = False
        await self.do_request('orders/1234/cancel', request_type='POST', expected_code=404)

    @timeout(10)
    async def test_cancel_order_invalid(self):
        """
        Test whether an error is returned when we try to cancel an order that has expired
        """
        order = self.nodes[0].overlay.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(0))
        order.set_verified()
        self.nodes[0].overlay.order_manager.order_repository.update(order)
        self.should_check_equality = False
        await self.do_request('orders/1/cancel', request_type='POST', expected_code=400)

    @timeout(10)
    async def test_cancel_order(self):
        """
        Test whether an error is returned when we try to cancel an order that has expired
        """
        order = self.nodes[0].overlay.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(3600))

        self.should_check_equality = False
        json_response = await self.do_request('orders/1/cancel', request_type='POST', expected_code=200)
        self.assertTrue(json_response['cancelled'])
        cancelled_order = self.nodes[0].overlay.order_manager.order_repository.find_by_id(order.order_id)
        self.assertTrue(cancelled_order.cancelled)

    @timeout(10)
    async def test_get_matchmakers(self):
        """
        Test the request to fetch known matchmakers
        """
        self.nodes[0].overlay.matchmakers.add(self.nodes[0].overlay.my_peer)
        self.should_check_equality = False
        json_response = await self.do_request('matchmakers', expected_code=200)
        self.assertGreaterEqual(len(json_response['matchmakers']), 1)
