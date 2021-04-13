import os

import pytest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.database import LATEST_DB_VERSION, MarketDB
from anydex.core.message import TraderId
from anydex.core.order import Order, OrderId, OrderNumber
from anydex.core.payment import Payment
from anydex.core.payment_id import PaymentId
from anydex.core.tick import Tick
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp
from anydex.core.transaction import Transaction, TransactionId
from anydex.core.wallet_address import WalletAddress


@pytest.fixture
def db(tmpdir):
    os.makedirs(os.path.join(tmpdir, "sqlite"))
    db = MarketDB(tmpdir, 'market')
    yield db
    db.close()


@pytest.fixture
def order1():
    order_id1 = OrderId(TraderId(b'3' * 20), OrderNumber(4))
    return Order(order_id1, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                 Timeout(3600), Timestamp.now(), True)


@pytest.fixture
def order2():
    order_id2 = OrderId(TraderId(b'4' * 20), OrderNumber(5))
    order2 = Order(order_id2, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                   Timeout(3600), Timestamp.now(), False)
    order2.reserve_quantity_for_tick(OrderId(TraderId(b'3' * 20), OrderNumber(4)), 3)
    return order2


@pytest.fixture
def payment():
    transaction_id = TransactionId(b'a' * 32)
    payment = Payment(TraderId(b'0' * 20), transaction_id, AssetAmount(5, 'BTC'),
                      WalletAddress('abc'), WalletAddress('def'), PaymentId("abc"), Timestamp(20000))
    return payment


@pytest.fixture
def transaction(payment):
    transaction_id = TransactionId(b'a' * 32)
    transaction = Transaction(transaction_id, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')),
                              OrderId(TraderId(b'0' * 20), OrderNumber(1)),
                              OrderId(TraderId(b'1' * 20), OrderNumber(2)), Timestamp(20000))

    transaction.add_payment(payment)
    return transaction


def test_add_get_order(db, order1, order2):
    """
    Test the insertion and retrieval of an order in the database
    """
    db.add_order(order1)
    db.add_order(order2)
    orders = db.get_all_orders()
    assert len(orders) == 2

    # Verify that the assets are correctly decoded
    assets = orders[0].assets
    assert assets.first.asset_id == "BTC"
    assert assets.second.asset_id == "EUR"


def test_get_specific_order(db, order1):
    """
    Test the retrieval of a specific order
    """
    order_id = OrderId(TraderId(b'3' * 20), OrderNumber(4))
    assert not db.get_order(order_id)
    db.add_order(order1)
    assert db.get_order(order_id)


def test_delete_order(db, order1):
    """
    Test the deletion of an order from the database
    """
    db.add_order(order1)
    assert len(db.get_all_orders()) == 1
    db.delete_order(order1.order_id)
    assert not db.get_all_orders()


def test_get_next_order_number(db, order1):
    """
    Test the retrieval of the next order number from the database
    """
    assert db.get_next_order_number() == 1
    db.add_order(order1)
    assert db.get_next_order_number() == 5


def test_add_delete_reserved_ticks(db, order1, order2):
    """
    Test the retrieval, addition and deletion of reserved ticks in the database
    """
    db.add_reserved_tick(order1.order_id, order2.order_id, order1.total_quantity)
    assert len(db.get_reserved_ticks(order1.order_id)) == 1
    db.delete_reserved_ticks(order1.order_id)
    assert not db.get_reserved_ticks(order1.order_id)


def test_add_get_transaction(db, transaction):
    """
    Test the insertion and retrieval of a transaction in the database
    """
    db.add_transaction(transaction)
    transactions = db.get_all_transactions()
    assert len(transactions) == 1
    assert len(db.get_payments(transaction.transaction_id)) == 1

    # Verify that the assets are correctly decoded
    assets = transactions[0].assets
    assert assets.first.asset_id == "BTC"
    assert assets.second.asset_id == "MB"


def test_insert_or_update_transaction(db, transaction):
    """
    Test the conditional insertion or update of a transaction in the database
    """
    # Test insertion
    db.insert_or_update_transaction(transaction)
    transactions = db.get_all_transactions()
    assert len(transactions) == 1

    # Test try to update with older timestamp
    before_trans1 = Transaction(transaction.transaction_id, transaction.assets,
                                transaction.order_id, transaction.partner_order_id,
                                Timestamp(int(transaction.timestamp) - 1000))
    db.insert_or_update_transaction(before_trans1)
    transaction = db.get_transaction(transaction.transaction_id)
    assert int(transaction.timestamp) == int(transaction.timestamp)

    # Test update with newer timestamp
    after_trans1 = Transaction(transaction.transaction_id, transaction.assets,
                               transaction.order_id, transaction.partner_order_id,
                               Timestamp(int(transaction.timestamp) + 1000))
    db.insert_or_update_transaction(after_trans1)
    transaction = db.get_transaction(transaction.transaction_id)
    assert int(transaction.timestamp) == int(after_trans1.timestamp)


def test_get_specific_transaction(db, transaction):
    """
    Test the retrieval of a specific transaction
    """
    transaction_id = TransactionId(b'a' * 32)
    assert not db.get_transaction(transaction_id)
    db.add_transaction(transaction)
    assert db.get_transaction(transaction_id)


def test_delete_transaction(db, transaction):
    """
    Test the deletion of a transaction from the database
    """
    db.add_transaction(transaction)
    assert len(db.get_all_transactions()) == 1
    db.delete_transaction(transaction.transaction_id)
    assert not db.get_all_transactions()


def test_add_get_payment(db, payment, transaction):
    """
    Test the insertion and retrieval of a payment in the database
    """
    db.add_payment(payment)
    payments = db.get_payments(transaction.transaction_id)
    assert payments

    # Verify that the assets are correctly decoded
    assert payments[0].transferred_assets.asset_id == "BTC"


def test_add_remove_tick(db, order1, order2):
    """
    Test addition, retrieval and deletion of ticks in the database
    """
    ask = Tick.from_order(order1)
    db.add_tick(ask)
    bid = Tick.from_order(order2)
    db.add_tick(bid)

    assert len(db.get_ticks()) == 2

    db.delete_all_ticks()
    assert not db.get_ticks()


def test_check_database(db):
    """
    Test the check of the database
    """
    assert db.check_database(b"%d" % LATEST_DB_VERSION) == LATEST_DB_VERSION


def test_get_upgrade_script(db):
    """
    Test fetching the upgrade script of the database
    """
    assert db.get_upgrade_script(1)


def test_db_upgrade(db):
    db.execute(u"DROP TABLE orders;")
    db.execute(u"DROP TABLE ticks;")
    db.execute(u"CREATE TABLE orders(x INTEGER PRIMARY KEY ASC);")
    db.execute(u"CREATE TABLE ticks(x INTEGER PRIMARY KEY ASC);")
    assert db.check_database(b"1") == 5
