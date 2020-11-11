from __future__ import annotations

from typing import Dict


class AssetAmount:
    """
    This class represents a specific number of assets. It contains various utility methods to add/substract asset
    amounts.
    """

    def __init__(self, amount: int, asset_id: str) -> None:
        """
        :param amount: Integer representation of the asset amount
        :param asset_id: Identifier of the asset type of this amount
        """
        if not isinstance(amount, int):
            raise ValueError("Price must be an integer")

        if not isinstance(asset_id, str):
            raise ValueError("Asset id must be a string")

        self._amount = amount
        self._asset_id = asset_id

    @property
    def asset_id(self) -> str:
        return self._asset_id

    @property
    def amount(self) -> int:
        return self._amount

    def __str__(self) -> str:
        return "%d %s" % (self.amount, self.asset_id)

    def __add__(self, other: AssetAmount) -> AssetAmount:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.__class__(self.amount + other.amount, self.asset_id)
        else:
            return NotImplemented

    def __sub__(self, other: AssetAmount) -> AssetAmount:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.__class__(self.amount - other.amount, self.asset_id)
        else:
            return NotImplemented

    def __lt__(self, other: AssetAmount) -> bool:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.amount < other.amount
        else:
            return NotImplemented

    def __le__(self, other: AssetAmount) -> bool:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.amount <= other.amount
        else:
            return NotImplemented

    def __eq__(self, other: AssetAmount) -> bool:
        if not isinstance(other, AssetAmount) or self.asset_id != other.asset_id:
            return NotImplemented
        else:
            return self.amount == other.amount

    def __ne__(self, other: AssetAmount) -> bool:
        return not self.__eq__(other)

    def __gt__(self, other: AssetAmount) -> bool:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.amount > other.amount
        else:
            return NotImplemented

    def __ge__(self, other: AssetAmount) -> bool:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.amount >= other.amount
        else:
            return NotImplemented

    def __floordiv__(self, other: AssetAmount) -> AssetAmount:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.__class__(self.amount // other.amount, self.asset_id)
        else:
            return NotImplemented

    def __truediv__(self, other: AssetAmount) -> AssetAmount:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.__class__(self.amount // other.amount, self.asset_id)
        else:
            return NotImplemented

    def __mod__(self, other: AssetAmount) -> AssetAmount:
        if isinstance(other, AssetAmount) and self.asset_id == other.asset_id:
            return self.__class__(self.amount % other.amount, self.asset_id)
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash((self.amount, self.asset_id))

    def to_dictionary(self) -> Dict:
        return {
            "amount": self.amount,
            "type": self.asset_id
        }
