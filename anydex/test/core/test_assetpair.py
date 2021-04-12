import pytest

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair


@pytest.fixture
def asset_pairs():
    return [AssetPair(AssetAmount(2, 'BTC'), AssetAmount(2, 'MB')),
            AssetPair(AssetAmount(4, 'BTC'), AssetAmount(8, 'MB')),
            AssetPair(AssetAmount(2, 'BTC'), AssetAmount(2, 'MB')),
            AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(13, 'DUM2'))]


def test_init(asset_pairs):
    """
    Test initializing an AssetPair object
    """
    with pytest.raises(ValueError):
        AssetPair(AssetAmount(2, 'MB'), AssetAmount(2, 'BTC'))


def test_equality(asset_pairs):
    """
    Test the equality method of an AssetPair
    """
    assert not (asset_pairs[0] == asset_pairs[1])
    assert asset_pairs[0] == asset_pairs[2]


def test_to_dictionary(asset_pairs):
    """
    Test the method to convert an AssetPair object to a dictionary
    """
    assert {
        "first": {
            "amount": 2,
            "type": "BTC",
        },
        "second": {
            "amount": 2,
            "type": "MB"
        }
    } == asset_pairs[0].to_dictionary()


def test_from_dictionary(asset_pairs):
    """
    Test the method to create an AssetPair object from a given dictionary
    """
    assert AssetPair.from_dictionary({
        "first": {
            "amount": 2,
            "type": "BTC",
        },
        "second": {
            "amount": 2,
            "type": "MB"
        }
    }) == asset_pairs[0]


def test_price(asset_pairs):
    """
    Test creating a price from an asset pair
    """
    assert asset_pairs[0].price.amount == 1
    assert asset_pairs[1].price.amount == 2


def test_proportional_downscale(asset_pairs):
    """
    Test the method to proportionally scale down an asset pair
    """
    assert asset_pairs[1].proportional_downscale(first=1).second.amount == 2
    assert asset_pairs[1].proportional_downscale(second=4).first.amount == 2
    assert asset_pairs[3].proportional_downscale(first=10).second.amount == 13
    assert asset_pairs[3].proportional_downscale(second=13).first.amount == 10


def test_to_str(asset_pairs):
    """
    Test string conversion from an asset pair
    """
    assert "2 BTC 2 MB" == str(asset_pairs[0])
