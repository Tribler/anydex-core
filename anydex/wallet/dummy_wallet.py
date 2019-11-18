import string
from random import choice

from ipv8.util import succeed

from anydex.wallet.wallet import InsufficientFunds, Wallet


class BaseDummyWallet(Wallet):
    """
    This is a dummy wallet that is primarily used for testing purposes
    """
    MONITOR_DELAY = 1

    def __init__(self):
        super(BaseDummyWallet, self).__init__()

        self.balance = 1000
        self.created = True
        self.unlocked = True
        self.address = ''.join([choice(string.ascii_lowercase) for _ in range(10)])
        self.transaction_history = []

    def get_name(self):
        return 'Dummy'

    def get_identifier(self):
        return 'DUM'

    def create_wallet(self, *args, **kwargs):
        return succeed(None)

    def get_balance(self):
        return succeed({
            'available': self.balance,
            'pending': 0,
            'currency': self.get_identifier(),
            'precision': self.precision()
        })

    async def transfer(self, quantity, candidate):
        self._logger.info("Transferring %s %s to %s from dummy wallet", quantity, self.get_identifier(), candidate)

        balance = await self.get_balance()
        if balance['available'] < quantity:
            raise InsufficientFunds()
        self.balance -= quantity
        self.transaction_history.append({
            'id': str(quantity),
            'outgoing': True,
            'from': self.address,
            'to': '',
            'amount': quantity,
            'fee_amount': 0.0,
            'currency': self.get_identifier(),
            'timestamp': '',
            'description': ''
        })
        return str(quantity)

    def monitor_transaction(self, transaction_id):
        """
        Monitor an incoming transaction with a specific ID.
        """
        def on_transaction_done():
            self.transaction_history.append({
                'id': transaction_id,
                'outgoing': True,
                'from': '',
                'to': self.address,
                'amount': float(str(transaction_id)),
                'fee_amount': 0.0,
                'currency': self.get_identifier(),
                'timestamp': '',
                'description': ''
            })

            self.balance += float(str(transaction_id))  # txid = amount of money transferred

        if self.MONITOR_DELAY == 0:
            return succeed(on_transaction_done())
        else:
            return self.register_anonymous_task('monitor_transaction', on_transaction_done, delay=self.MONITOR_DELAY)

    def get_address(self):
        return self.address

    def get_transactions(self):
        return succeed(self.transaction_history)

    def min_unit(self):
        return 1

    def precision(self):
        return 0


class DummyWallet1(BaseDummyWallet):

    def get_name(self):
        return 'Dummy 1'

    def get_identifier(self):
        return 'DUM1'


class DummyWallet2(BaseDummyWallet):

    def __init__(self):
        super(DummyWallet2, self).__init__()
        self.balance = 10000

    def get_name(self):
        return 'Dummy 2'

    def get_identifier(self):
        return 'DUM2'

    def precision(self):
        return 1
