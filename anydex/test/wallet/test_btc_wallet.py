import datetime

from ipv8.util import succeed

import pytest

from sqlalchemy.orm import session as db_session

from anydex.test.util import MockObject
from anydex.wallet.btc_wallet import BitcoinTestnetWallet, BitcoinWallet


@pytest.fixture
async def wallet(tmpdir):
    wallet = BitcoinTestnetWallet(tmpdir)
    yield wallet
    await wallet.shutdown_task_manager()
    db_session.close_all_sessions()


@pytest.mark.timeout(10)
async def test_btc_wallet(wallet, tmpdir):
    """
    Test the creating, opening, transactions and balance query of a Bitcoin (testnet) wallet
    """
    await wallet.create_wallet()
    assert wallet.wallet
    assert wallet.get_address()

    wallet.wallet.utxos_update = lambda **_: None  # We don't want to do an actual HTTP request here
    wallet.wallet.balance = lambda **_: 3
    balance = await wallet.get_balance()

    assert balance == {'available': 3, 'pending': 0, 'currency': 'BTC', 'precision': 8}
    wallet.wallet.transactions_update = lambda **_: None  # We don't want to do an actual HTTP request here
    transactions = await wallet.get_transactions()
    assert not transactions

    wallet.get_transactions = lambda: succeed([{"id": "abc"}])
    await wallet.monitor_transaction("abc")


def test_btc_wallet_name(wallet):
    """
    Test the name of a Bitcoin wallet
    """
    assert wallet.get_name() == 'Testnet BTC'


def test_btc_wallet_identfier(wallet):
    """
    Test the identifier of a Bitcoin wallet
    """
    assert wallet.get_identifier() == 'TBTC'


def test_btc_wallet_address(wallet):
    """
    Test the address of a Bitcoin wallet
    """
    assert wallet.get_address() == ''


def test_btc_wallet_unit(wallet):
    """
    Test the mininum unit of a Bitcoin wallet
    """
    assert wallet.min_unit() == 100000


@pytest.mark.asyncio
async def test_btc_balance_no_wallet(wallet):
    """
    Test the retrieval of the balance of a BTC wallet that is not created yet
    """
    balance = await wallet.get_balance()
    assert balance == {'available': 0, 'pending': 0, 'currency': 'BTC', 'precision': 8}


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_btc_wallet_transfer(wallet):
    """
    Test that the transfer method of a BTC wallet works
    """
    await wallet.create_wallet()
    wallet.get_balance = lambda: succeed({'available': 100000, 'pending': 0, 'currency': 'BTC', 'precision': 8})
    mock_tx = MockObject()
    mock_tx.hash = 'a' * 20
    wallet.wallet.send_to = lambda *_: mock_tx
    await wallet.transfer(3000, '2N8hwP1WmJrFF5QWABn38y63uYLhnJYJYTF')


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_btc_wallet_create_error(wallet):
    """
    Test whether an error during wallet creation is handled
    """
    await wallet.create_wallet()  # This should work
    with pytest.raises(Exception):
        await wallet.create_wallet()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_btc_wallet_transfer_no_funds(wallet):
    """
    Test that the transfer method of a BTC wallet raises an error when we don't have enough funds
    """
    await wallet.create_wallet()
    wallet.wallet.utxos_update = lambda **_: None  # We don't want to do an actual HTTP request here
    with pytest.raises(Exception):
        await wallet.transfer(3000, '2N8hwP1WmJrFF5QWABn38y63uYLhnJYJYTF')


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_get_transactions(wallet):
    """
    Test whether transactions in bitcoinlib are correctly returned
    """
    raw_tx = '02000000014bca66ebc0e3ab0c5c3aec6d0b3895b968497397752977dfd4a2f0bc67db6810000000006b483045022100fc' \
             '93a034db310fbfead113283da95e980ac7d867c7aa4e6ef0aba80ef321639e02202bc7bd7b821413d814d9f7d6fc76ff46' \
             'b9cd3493173ef8d5fac40bce77a7016d01210309702ce2d5258eacc958e5a925b14de912a23c6478b8e2fb82af43d20212' \
             '14f3feffffff029c4e7020000000001976a914d0115029aa5b2d2db7afb54a6c773ad536d0916c88ac90f4f70000000000' \
             '1976a914f0eabff37e597b930647a3ec5e9df2e0fed0ae9888ac108b1500'

    mock_wallet = MockObject()
    mock_wallet.transactions_update = lambda **_: None
    mock_wallet._session = MockObject()

    mock_all = MockObject()
    mock_all.all = lambda *_: [(raw_tx, 3, datetime.datetime(2012, 9, 16, 0, 0), 12345)]
    mock_filter = MockObject()
    mock_filter.filter = lambda *_: mock_all
    mock_wallet._session.query = lambda *_: mock_filter
    wallet.wallet = mock_wallet
    wallet.wallet.wallet_id = 3

    mock_key = MockObject()
    mock_key.address = 'n3Uogo82Tyy76ZNuxmFfhJiFqAUbJ5BPho'
    wallet.wallet.keys = lambda **_: [mock_key]
    wallet.created = True

    transactions = await wallet.get_transactions()
    assert transactions
    assert transactions[0]["fee_amount"] == 12345
    assert transactions[0]["amount"] == 16250000


@pytest.mark.asyncio
async def test_real_btc_wallet_name(tmpdir):
    """
    Test the name of a Bitcoin wallet
    """
    wallet = BitcoinWallet(tmpdir)
    assert wallet.get_name() == 'Bitcoin'
    await wallet.shutdown_task_manager()
    db_session.close_all_sessions()


@pytest.mark.asyncio
async def test_real_btc_wallet_identfier(tmpdir):
    """
    Test the identifier of a Bitcoin wallet
    """
    wallet = BitcoinWallet(tmpdir)
    assert wallet.get_identifier() == 'BTC'
    await wallet.shutdown_task_manager()
    db_session.close_all_sessions()
