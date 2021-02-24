import bisect
from itertools import chain
from typing import Any, Dict, Generator, List, Tuple # pylint: disable=unused-import

from anydex.core.price import Price  # pylint: disable=unused-import
from anydex.core.pricelevel import PriceLevel


class PriceLevelList:
    """
    Sorted doubly linked dictionary implementation.
    """

    def __init__(self):
        self._price_list: List[float] = []  # type: List[float]
        self._price_level_dictionary: Dict[float, PriceLevel] = {}  # type: Dict[float, PriceLevel]

    def insert(self, price_level: PriceLevel) -> None:  # type: (PriceLevel) -> None
        """
        :type price_level: PriceLevel
        """
        bisect.insort(self._price_list, price_level.price)
        self._price_level_dictionary[price_level.price] = price_level

    def remove(self, price: Price) -> None:  # type: (Price) -> None
        """
        :type price: Price
        """
        self._price_list.remove(price)
        del self._price_level_dictionary[price]

    def succ_item(self, price: Price) -> PriceLevel:  # type: (Price) -> PriceLevel
        """
        Returns the price level where price_level.price is successor to given price

        :type price: Price
        :rtype: PriceLevel
        """
        index = self._price_list.index(price) + 1
        if index >= len(self._price_list):
            raise IndexError
        succ_price = self._price_list[index]
        return self._price_level_dictionary[succ_price]

    def prev_item(self, price: Price) -> PriceLevel:  # type: (Price) -> PriceLevel
        """
        Returns the price level where price_level.price is predecessor to given price

        :type price: Price
        :rtype: PriceLevel
        """
        index = self._price_list.index(price) - 1
        if index < 0:
            raise IndexError
        prev_price = self._price_list[index]
        return self._price_level_dictionary[prev_price]

    def min_key(self) -> Price:  # type: () -> Price
        """
        Return the lowest price in the price level list

        :rtype: Price
        """
        return self._price_list[0]

    def max_key(self) -> Price:  # type: () -> Price
        """
        Return the highest price in the price level list

        :rtype: Price
        """
        return self._price_list[-1]

    def items(self, reverse: bool=False) -> List[Tuple[Price, PriceLevel]]:  # type: (bool) -> List[Tuple[Price, PriceLevel]]
        """
        Returns a sorted list (on price) of price_levels

        :param reverse: When true returns the reversed sorted list of price, price_level tuples
        :type reverse: bool
        :rtype: List[Tuple[Price, PriceLevel]]
        """
        price_list = self._price_list if not reverse else reversed(self._price_list)
        return [self._price_level_dictionary[price] for price in price_list]

    def items_iter(self, reverse: bool=False) -> Generator[Tuple[Price, PriceLevel], None, None]: # type: (bool) -> Generator[Tuple[Price, PriceLevel], None, None]
        """
        An iterator version of @PriceLevelList.items()
        
        :param reverse: When true returns the reversed sorted list of price, price_level tuples
        :type reverse: bool
        :rtype Generator[Tuple[Price, PriceLevel], None, None]
        """
        price_list = self._price_list if not reverse else reversed(self._price_list)
        for price in price_list:
            yield self._price_level_dictionary[price]

    def get_ticks_list(self) -> List[Any]:  # type: () -> List[Any]
        """
        Returns a list describing all ticks.
        :return: list
        """
        return list(tick.tick.to_dictionary() for tick in chain.from_iterable(self.items_iter()))
