import pytest

from anydex.wallet.dummy_wallet import BaseDummyWallet, DummyWallet1, DummyWallet2
from anydex.wallet.wallet import InsufficientFunds


@pytest.fixture
async def dummy_wallet():
    dummy_wallet = BaseDummyWallet()
    yield dummy_wallet
    await dummy_wallet.shutdown_task_manager()


def test_wallet_id(dummy_wallet):
    """
    Test the identifier of a dummy wallet
    """
    assert dummy_wallet.get_identifier() == 'DUM'
    assert DummyWallet1().get_identifier() == 'DUM1'
    assert DummyWallet2().get_identifier() == 'DUM2'


def test_wallet_name(dummy_wallet):
    """
    Test the name of a dummy wallet
    """
    assert dummy_wallet.get_name() == 'Dummy'
    assert DummyWallet1().get_name() == 'Dummy 1'
    assert DummyWallet2().get_name() == 'Dummy 2'


@pytest.mark.timeout(10)
def test_create_wallet(dummy_wallet):
    """
    Test the creation of a dummy wallet
    """
    dummy_wallet.create_wallet()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_get_balance(dummy_wallet):
    """
    Test fetching the balance of a dummy wallet
    """
    balance = await dummy_wallet.get_balance()
    assert isinstance(balance, dict)


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_transfer(dummy_wallet):
    """
    Test the transfer of money from a dummy wallet
    """
    await dummy_wallet.transfer(dummy_wallet.balance - 1, None)
    transactions = await dummy_wallet.get_transactions()
    assert len(transactions) == 1


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_transfer_invalid(dummy_wallet):
    """
    Test whether transferring a too large amount of money from a dummy wallet raises an error
    """
    with pytest.raises(InsufficientFunds):
        await dummy_wallet.transfer(dummy_wallet.balance + 1, None)


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_monitor(dummy_wallet):
    """
    Test the monitor loop of a transaction wallet
    """
    dummy_wallet.MONITOR_DELAY = 1
    await dummy_wallet.monitor_transaction("3.0")


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_monitor_instant(dummy_wallet):
    """
    Test an instant the monitor loop of a transaction wallet
    """
    dummy_wallet.MONITOR_DELAY = 0
    await dummy_wallet.monitor_transaction("3.0")


def test_address(dummy_wallet):
    """
    Test the address of a dummy wallet
    """
    assert isinstance(dummy_wallet.get_address(), str)


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_get_transaction(dummy_wallet):
    """
    Test the retrieval of transactions of a dummy wallet
    """
    transactions = await dummy_wallet.get_transactions()
    assert isinstance(transactions, list)


def test_min_unit(dummy_wallet):
    """
    Test the minimum unit of a dummy wallet
    """
    assert dummy_wallet.min_unit() == 1


def test_generate_txid(dummy_wallet):
    """
    Test the generation of a random transaction id
    """
    assert dummy_wallet.generate_txid(10)
    assert len(dummy_wallet.generate_txid(20)) == 20
