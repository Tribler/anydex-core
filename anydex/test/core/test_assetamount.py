import pytest

from anydex.core.assetamount import AssetAmount


@pytest.fixture
def asset_amounts():
    return [AssetAmount(2, 'BTC'), AssetAmount(100, 'BTC'), AssetAmount(0, 'BTC'), AssetAmount(2, 'MC')]


def test_init():
    """
    Test the initialization of a price
    """
    with pytest.raises(ValueError):
        AssetAmount('1', 'MC')
    with pytest.raises(ValueError):
        AssetAmount(1, 2)


def test_addition(asset_amounts):
    # Test for addition
    assert asset_amounts[0] + asset_amounts[1] == AssetAmount(102, 'BTC')
    assert asset_amounts[0] is not (asset_amounts[0] + asset_amounts[1])
    assert asset_amounts[0].__add__(10) == NotImplemented
    assert asset_amounts[0].__add__(asset_amounts[3]) == NotImplemented


def test_subtraction(asset_amounts):
    # Test for subtraction
    assert AssetAmount(98, 'BTC'), asset_amounts[1] - asset_amounts[0]
    assert NotImplemented == asset_amounts[0].__sub__(10)
    assert NotImplemented == asset_amounts[0].__sub__(asset_amounts[3])


def test_comparison(asset_amounts):
    # Test for comparison
    assert asset_amounts[0] < asset_amounts[1]
    assert asset_amounts[1] > asset_amounts[0]
    assert NotImplemented == asset_amounts[0].__le__(10)
    assert NotImplemented == asset_amounts[0].__lt__(10)
    assert NotImplemented == asset_amounts[0].__ge__(10)
    assert NotImplemented == asset_amounts[0].__gt__(10)
    assert NotImplemented == asset_amounts[0].__le__(asset_amounts[3])
    assert NotImplemented == asset_amounts[0].__lt__(asset_amounts[3])
    assert NotImplemented == asset_amounts[0].__ge__(asset_amounts[3])
    assert NotImplemented == asset_amounts[0].__gt__(asset_amounts[3])


def test_equality(asset_amounts):
    # Test for equality
    assert asset_amounts[0] == AssetAmount(2, 'BTC')
    assert asset_amounts[0] != asset_amounts[1]
    assert not (asset_amounts[0] == 2)
    assert not (asset_amounts[0] == asset_amounts[3])


def test_hash(asset_amounts):
    # Test for hashes
    assert asset_amounts[0].__hash__() == AssetAmount(2, 'BTC').__hash__()
    assert asset_amounts[0].__hash__() != asset_amounts[1].__hash__()


def test_str(asset_amounts):
    """
    Test the string representation of a Price object
    """
    assert str(asset_amounts[0]) == "2 BTC"
