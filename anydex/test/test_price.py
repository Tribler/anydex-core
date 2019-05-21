import unittest

from anydex.core.price import Price


class TestPrice(unittest.TestCase):
    """
    This class contains tests for the Price object.
    """

    def setUp(self):
        self.price1 = Price(4, 2, 'MB', 'BTC')
        self.price2 = Price(3, 1, 'MB', 'BTC')
        self.price3 = Price(8, 4, 'MB', 'BTC')

    def test_str(self):
        """
        Test the str method of a Price object
        """
        self.assertEqual(str(self.price1), "2 MB/BTC")

    def test_equality(self):
        """
        Test the equality method of a Price object
        """
        self.assertEqual(self.price1, self.price3)
        self.assertNotEqual(self.price1, self.price2)
        self.assertNotEqual(self.price1, 2)
        self.assertFalse(self.price1 == 2)

    def test_cmp(self):
        """
        Test comparison of a Price object
        """
        self.assertTrue(self.price1 < self.price2)
        self.assertFalse(self.price1 > self.price2)
