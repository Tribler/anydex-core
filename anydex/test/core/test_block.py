from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.block import MarketBlock
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.tick import Ask
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp
from anydex.core.trade import AcceptedTrade
from anydex.core.transaction import Transaction, TransactionId
from anydex.test.base import BaseTestCase


class TestMarketBlock(BaseTestCase):
    """
    This class contains tests for a TrustChain block as used in the market.
    """

    def setUp(self):
        BaseTestCase.setUp(self)

        self.ask = Ask(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                       AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0), True)
        self.bid = Ask(OrderId(TraderId(b'1' * 20), OrderNumber(1)),
                       AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0), False)
        self.accepted_trade = AcceptedTrade(TraderId(b'0' * 20), OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                                            OrderId(TraderId(b'1' * 20), OrderNumber(1)), 1234,
                                            AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timestamp(0))
        self.transaction = Transaction.from_accepted_trade(self.accepted_trade, TransactionId(b'a' * 32))

        ask_tx = self.ask.to_block_dict()
        bid_tx = self.bid.to_block_dict()

        self.tick_block = MarketBlock()
        self.tick_block.type = b'ask'
        self.tick_block.transaction = {'tick': ask_tx}

        self.cancel_block = MarketBlock()
        self.cancel_block.type = b'cancel_order'
        self.cancel_block.transaction = {'trader_id': 'a' * 20, 'order_number': 1}

        self.tx_init_block = MarketBlock()
        self.tx_init_block.type = b'tx_init'
        self.tx_init_block.transaction = {
            'tx': self.accepted_trade.to_block_dictionary()
        }

        self.tx_done_block = MarketBlock()
        self.tx_done_block.type = b'tx_done'
        self.tx_done_block.transaction = {
            'ask': ask_tx,
            'bid': bid_tx,
            'tx': self.transaction.to_block_dictionary()
        }

        payment = {
            'trader_id': 'a' * 40,
            'transaction_id': 'a' * 64,
            'transferred': {
                'amount': 3,
                'type': 'BTC'
            },
            'payment_id': 'a',
            'address_from': 'a',
            'address_to': 'b',
            'timestamp': 1234,
        }
        self.payment_block = MarketBlock()
        self.payment_block.type = b'tx_payment'
        self.payment_block.transaction = {'payment': payment}

    def test_tick_block(self):
        """
        Test whether a tick block can be correctly verified
        """
        self.assertTrue(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['timeout'] = -1
        self.assertFalse(self.tick_block.is_valid_tick_block())
        self.tick_block.transaction['tick']['timeout'] = 3600

        self.tick_block.type = b'test'
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.type = b'ask'
        self.tick_block.transaction['test'] = self.tick_block.transaction.pop('tick')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick'] = self.tick_block.transaction.pop('test')
        self.tick_block.transaction['tick'].pop('timeout')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['timeout'] = "300"
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction['tick']['timeout'] = 300
        self.tick_block.transaction['tick']['trader_id'] = 'g' * 21
        self.assertFalse(self.tick_block.is_valid_tick_block())

        # Make the asset pair invalid
        assets = self.tick_block.transaction['tick']['assets']
        self.tick_block.transaction['tick']['trader_id'] = 'a' * 40
        assets['test'] = assets.pop('first')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first'] = assets.pop('test')
        assets['first']['test'] = assets['first'].pop('amount')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first']['amount'] = assets['first']['test']
        assets['second']['test'] = assets['second'].pop('amount')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['second']['amount'] = assets['second']['test']
        assets['first']['amount'] = 3.4
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first']['amount'] = 2 ** 64
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets['first']['amount'] = 3
        assets['second']['type'] = 4
        self.assertFalse(self.tick_block.is_valid_tick_block())

    def test_cancel_block(self):
        """
        Test whether a cancel block can be correctly verified
        """
        self.assertTrue(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.type = b'cancel'
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.type = b'cancel_order'
        self.cancel_block.transaction.pop('trader_id')
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.transaction['trader_id'] = 3
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

    def test_tx_init_block(self):
        """
        Test whether a tx_init/tx_done block can be correctly verified
        """
        self.assertTrue(self.tx_init_block.is_valid_tx_init_done_block())

        self.tx_init_block.type = b'test'
        self.assertFalse(self.tx_init_block.is_valid_tx_init_done_block())

        self.tx_init_block.type = b'tx_init'
        self.tx_init_block.transaction['tx'].pop('trader_id')
        self.assertFalse(self.tx_init_block.is_valid_tx_init_done_block())

        self.tx_init_block.transaction['tx']['trader_id'] = 'a' * 40
        self.tx_init_block.transaction['tx']['test'] = 3
        self.assertFalse(self.tx_init_block.is_valid_tx_init_done_block())

        self.tx_init_block.transaction['tx'].pop('test')
        self.tx_init_block.transaction['tx']['trader_id'] = 'a'
        self.assertFalse(self.tx_init_block.is_valid_tx_init_done_block())

        self.tx_init_block.transaction['tx']['trader_id'] = 'a' * 40
        self.tx_init_block.transaction['tx']['assets']['first']['amount'] = 3.4
        self.assertFalse(self.tx_init_block.is_valid_tx_init_done_block())

    def test_tx_payment_block(self):
        """
        Test whether a tx_payment block can be correctly verified
        """
        self.assertTrue(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.type = b'test'
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.type = b'tx_payment'
        self.payment_block.transaction['test'] = self.payment_block.transaction.pop('payment')
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment'] = self.payment_block.transaction.pop('test')
        self.payment_block.transaction['payment'].pop('address_to')
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment']['address_to'] = 'a'
        self.payment_block.transaction['payment']['test'] = 'a'
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment'].pop('test')
        self.payment_block.transaction['payment']['address_to'] = 3
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction['payment']['address_to'] = 'a'
        self.payment_block.transaction['payment']['trader_id'] = 'a' * 39
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

    def test_is_valid_asset_pair(self):
        """
        Test the method to verify whether an asset pair is valid
        """
        self.assertFalse(MarketBlock.is_valid_asset_pair({'a': 'b'}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': 3, 'type': 'DUM1'},
                                                          'second': {'amount': 3}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'type': 'DUM1'},
                                                          'second': {'amount': 3, 'type': 'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': "4", 'type': 'DUM1'},
                                                          'second': {'amount': 3, 'type': 'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': 4, 'type': 'DUM1'},
                                                          'second': {'amount': "3", 'type': 'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({'first': {'amount': -4, 'type': 'DUM1'},
                                                          'second': {'amount': 3, 'type': 'DUM2'}}))
