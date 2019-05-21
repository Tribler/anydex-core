from fractions import Fraction


class Price(object):
    """
    This class represents a price in the market.
    The price is simply a fraction that expresses one asset in another asset.
    For instance, 0.5 MB/BTC means that one exchanges 0.5 MB for 1 BTC.
    """

    def __init__(self, num, denom, num_type, denom_type):
        self.num = num
        self.denom = denom
        self.num_type = num_type
        self.denom_type = denom_type
        self.frac = Fraction(num, denom)
        self.amount = float(self.frac)

    def __str__(self):
        return "%g %s/%s" % (self.amount, self.num_type, self.denom_type)

    def __lt__(self, other):
        if isinstance(other, Price) and self.num_type == other.num_type and self.denom_type == other.denom_type:
            return self.amount < other.amount
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Price) and self.num_type == other.num_type and self.denom_type == other.denom_type:
            return self.amount <= other.amount
        else:
            return NotImplemented

    def __ne__(self, other):
        if not isinstance(other, Price) or self.num_type != other.num_type or self.denom_type != other.denom_type:
            return NotImplemented
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Price) and self.num_type == other.num_type and self.denom_type == other.denom_type:
            return self.amount > other.amount
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Price) and self.num_type == other.num_type and self.denom_type == other.denom_type:
            return self.amount >= other.amount
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Price) or self.num_type != other.num_type or self.denom_type != other.denom_type:
            return NotImplemented
        else:
            return self.frac == other.frac

    def __hash__(self):
        return hash((hash(self.frac), self.num_type, self.denom_type))
