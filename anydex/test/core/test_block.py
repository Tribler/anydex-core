import pytest

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


@pytest.fixture
def ask():
    return Ask(OrderId(TraderId(b'0' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0), True)


@pytest.fixture
def bid():
    return Ask(OrderId(TraderId(b'1' * 20), OrderNumber(1)),
               AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timeout(30), Timestamp(0), False)


@pytest.fixture
def accepted_trade():
    return AcceptedTrade(TraderId(b'0' * 20), OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                         OrderId(TraderId(b'1' * 20), OrderNumber(1)), 1234,
                         AssetPair(AssetAmount(30, 'BTC'), AssetAmount(30, 'MB')), Timestamp(0))


@pytest.fixture
def tick_block(ask):
    tick_block = MarketBlock()
    tick_block.type = b'ask'
    tick_block.transaction = {'tick': ask.to_block_dict()}
    return tick_block


@pytest.fixture
def cancel_block():
    cancel_block = MarketBlock()
    cancel_block.type = b'cancel_order'
    cancel_block.transaction = {'trader_id': 'a' * 20, 'order_number': 1}
    return cancel_block


@pytest.fixture
def tx_init_block(accepted_trade):
    tx_init_block = MarketBlock()
    tx_init_block.type = b'tx_init'
    tx_init_block.transaction = {
        'tx': accepted_trade.to_block_dictionary()
    }
    return tx_init_block


@pytest.fixture
def tx_done_block(ask, bid, accepted_trade):
    tx_done_block = MarketBlock()
    tx_done_block.type = b'tx_done'
    transaction = Transaction.from_accepted_trade(accepted_trade, TransactionId(b'a' * 32))
    tx_done_block.transaction = {
        'ask': ask.to_block_dict(),
        'bid': bid.to_block_dict(),
        'tx': transaction.to_block_dictionary()
    }


@pytest.fixture
def payment_block():
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
    payment_block = MarketBlock()
    payment_block.type = b'tx_payment'
    payment_block.transaction = {'payment': payment}
    return payment_block


def test_tick_block(tick_block):
    """
    Test whether a tick block can be correctly verified
    """
    assert tick_block.is_valid_tick_block()

    tick_block.transaction['tick']['timeout'] = -1
    assert not tick_block.is_valid_tick_block()
    tick_block.transaction['tick']['timeout'] = 3600

    tick_block.type = b'test'
    assert not tick_block.is_valid_tick_block()

    tick_block.type = b'ask'
    tick_block.transaction['test'] = tick_block.transaction.pop('tick')
    assert not tick_block.is_valid_tick_block()

    tick_block.transaction['tick'] = tick_block.transaction.pop('test')
    tick_block.transaction['tick'].pop('timeout')
    assert not tick_block.is_valid_tick_block()

    tick_block.transaction['tick']['timeout'] = "300"
    assert not tick_block.is_valid_tick_block()

    tick_block.transaction['tick']['timeout'] = 300
    tick_block.transaction['tick']['trader_id'] = 'g' * 21
    assert not tick_block.is_valid_tick_block()

    # Make the asset pair invalid
    assets = tick_block.transaction['tick']['assets']
    tick_block.transaction['tick']['trader_id'] = 'a' * 40
    assets['test'] = assets.pop('first')
    assert not tick_block.is_valid_tick_block()

    assets['first'] = assets.pop('test')
    assets['first']['test'] = assets['first'].pop('amount')
    assert not tick_block.is_valid_tick_block()

    assets['first']['amount'] = assets['first']['test']
    assets['second']['test'] = assets['second'].pop('amount')
    assert not tick_block.is_valid_tick_block()

    assets['second']['amount'] = assets['second']['test']
    assets['first']['amount'] = 3.4
    assert not tick_block.is_valid_tick_block()

    assets['first']['amount'] = 2 ** 64
    assert not tick_block.is_valid_tick_block()

    assets['first']['amount'] = 3
    assets['second']['type'] = 4
    assert not tick_block.is_valid_tick_block()


def test_cancel_block(cancel_block):
    """
    Test whether a cancel block can be correctly verified
    """
    assert cancel_block.is_valid_cancel_block()

    cancel_block.type = b'cancel'
    assert not cancel_block.is_valid_cancel_block()

    cancel_block.type = b'cancel_order'
    cancel_block.transaction.pop('trader_id')
    assert not cancel_block.is_valid_cancel_block()

    cancel_block.transaction['trader_id'] = 3
    assert not cancel_block.is_valid_cancel_block()


def test_tx_init_block(tx_init_block):
    """
    Test whether a tx_init/tx_done block can be correctly verified
    """
    assert tx_init_block.is_valid_tx_init_done_block()

    tx_init_block.type = b'test'
    assert not tx_init_block.is_valid_tx_init_done_block()

    tx_init_block.type = b'tx_init'
    tx_init_block.transaction['tx'].pop('trader_id')
    assert not tx_init_block.is_valid_tx_init_done_block()

    tx_init_block.transaction['tx']['trader_id'] = 'a' * 40
    tx_init_block.transaction['tx']['test'] = 3
    assert not tx_init_block.is_valid_tx_init_done_block()

    tx_init_block.transaction['tx'].pop('test')
    tx_init_block.transaction['tx']['trader_id'] = 'a'
    assert not tx_init_block.is_valid_tx_init_done_block()

    tx_init_block.transaction['tx']['trader_id'] = 'a' * 40
    tx_init_block.transaction['tx']['assets']['first']['amount'] = 3.4
    assert not tx_init_block.is_valid_tx_init_done_block()


def test_tx_payment_block(payment_block):
    """
    Test whether a tx_payment block can be correctly verified
    """
    assert payment_block.is_valid_tx_payment_block()

    payment_block.type = b'test'
    assert not payment_block.is_valid_tx_payment_block()

    payment_block.type = b'tx_payment'
    payment_block.transaction['test'] = payment_block.transaction.pop('payment')
    assert not payment_block.is_valid_tx_payment_block()

    payment_block.transaction['payment'] = payment_block.transaction.pop('test')
    payment_block.transaction['payment'].pop('address_to')
    assert not payment_block.is_valid_tx_payment_block()

    payment_block.transaction['payment']['address_to'] = 'a'
    payment_block.transaction['payment']['test'] = 'a'
    assert not payment_block.is_valid_tx_payment_block()

    payment_block.transaction['payment'].pop('test')
    payment_block.transaction['payment']['address_to'] = 3
    assert not payment_block.is_valid_tx_payment_block()

    payment_block.transaction['payment']['address_to'] = 'a'
    payment_block.transaction['payment']['trader_id'] = 'a' * 39
    assert not payment_block.is_valid_tx_payment_block()


def test_is_valid_asset_pair():
    """
    Test the method to verify whether an asset pair is valid
    """
    assert not MarketBlock.is_valid_asset_pair({'a': 'b'})
    assert not MarketBlock.is_valid_asset_pair({'first': {'amount': 3, 'type': 'DUM1'}, 'second': {'amount': 3}})
    assert not MarketBlock.is_valid_asset_pair({'first': {'type': 'DUM1'}, 'second': {'amount': 3, 'type': 'DUM2'}})
    assert not MarketBlock.is_valid_asset_pair({'first': {'amount': "4", 'type': 'DUM1'},
                                                'second': {'amount': 3, 'type': 'DUM2'}})
    assert not MarketBlock.is_valid_asset_pair({'first': {'amount': 4, 'type': 'DUM1'},
                                                'second': {'amount': "3", 'type': 'DUM2'}})
    assert not MarketBlock.is_valid_asset_pair({'first': {'amount': -4, 'type': 'DUM1'},
                                                'second': {'amount': 3, 'type': 'DUM2'}})
