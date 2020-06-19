import time
from datetime import datetime

from ipv8.util import succeed
from sqlalchemy.orm import session as db_session
from stellar_sdk import Keypair

from anydex.test.base import AbstractServer
from anydex.test.util import MockObject, timeout
from anydex.wallet.stellar.xlm_database import Secret, Transaction
from anydex.wallet.stellar.xlm_wallet import StellarWallet, StellarTestnetWallet
from anydex.wallet.wallet import InsufficientFunds


class TestStellarWallet(AbstractServer):
    """
    Test class containing the common tests for the testnet and normal stellar wallet.
    """

    def setUp(self):
        super().setUp()
        mock = MockObject()
        mock.get_account_sequence = lambda *_: 100
        self.wallet = StellarWallet(self.session_base_dir, mock)
        self.identifier = 'XLM'
        self.name = 'stellar'

        self.tx = Transaction(
            hash='96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98',
            ledger_nr=26529414,
            date_time=datetime.fromisoformat('2020-06-05T08:45:33'),
            source_account='GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH',
            operation_count=1,
            transaction_envelope="AAAAAOFkeKoP9De5JOCNgRYZVF8IIdi8WZ6olTXYb1KTMlgRAAAAZAGOO+wAAAA9AAAAAQAAAAAAAAAA"
                                 "AAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAADhZHiq"
                                 "D/Q3uSTgjYEWGVRfCCHYvFmeqJU12G9SkzJYEQAAAAAAAAAAXQbflbQZVvhfaHtF6ESvgGrNnl2gi440"
                                 "84MWUaGbmNkAAAAAAcnDgAAAAAAAAAABHvBc2AAAAEBUL1wo8IGHEpgpQ7llGaFE+rC9v5kk2KPJe53/"
                                 "gIdWF+792HYg5yTTmhJII97YgM+Be8yponPH0YjMjeYphewI",
            fee=100,
            is_pending=False,
            succeeded=True,
            sequence_number=112092925529161789,
            min_time_bound=datetime.fromisoformat('1970-01-01T00:00:00')
        )

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def new_wallet(self):
        mock = MockObject()
        mock.get_account_sequence = lambda *_: 100
        mock.check_account_created = lambda *_: None
        return StellarWallet(self.session_base_dir, mock)

    def create_wallet(self):
        """
        Create the wallet
        """
        self.wallet.get_sequence_number = lambda: 100
        self.wallet.create_wallet()
        self.wallet.created_on_network = True

    def test_get_identifier(self):
        self.assertEqual(self.identifier, self.wallet.get_identifier())

    def test_get_name(self):
        self.assertEqual(self.name, self.wallet.get_name())

    def test_create_wallet(self):
        """
        Test for wallet creation
        """
        self.create_wallet()
        addr = self.wallet.database.session.query(Secret.address).first()[0]
        self.assertIsNotNone(self.wallet.keypair)
        self.assertTrue(self.wallet.created)
        result = self.wallet.get_address()
        self.assertEqual(addr, result.result())

    def test_init_wallet_created(self):
        """
        Test for the wallet constructor when the wallet is already created
        """
        self.wallet.check_and_update_created_on_network = lambda *_: None
        self.create_wallet()

        wallet = self.new_wallet()
        self.assertEqual(wallet.created, True)

    def test_create_wallet_already_created(self):
        """
        Test for wallet creation where we tried to create a wallet that is  already created
        """
        self.create_wallet()
        future = self.wallet.create_wallet()

        self.assertIsInstance(future.exception(), RuntimeError)

    async def test_get_balance_not_created(self):
        """
        Test for getting balance when the wallet has not yet been created
        """
        balance = {
            'available': 0,
            'pending': 0,
            'currency': self.identifier,
            'precision': 7
        }
        self.wallet.check_and_update_created_on_network = lambda *_: None
        self.assertEquals(balance, await self.wallet.get_balance())

    async def test_get_balance(self):
        """
        Test for getting the balance when the wallet has been created
        """
        self.create_wallet()
        self.wallet.provider.get_balance = lambda *_, **x: 100
        balance = {
            'available': 100 * 1e7,  # balance form api is not in the lowest denomination
            'pending': 0,
            'currency': self.identifier,
            'precision': 7
        }
        self.assertEquals(balance, await self.wallet.get_balance())

    def test_get_sequence_number_db(self):
        """
        Test for getting sequence number from the database
        """
        self.wallet.database.session.add(
            Transaction(sequence_number=10000, succeeded=True, source_account=f'sequence {self.wallet.testnet}'))
        self.wallet.database.session.commit()
        self.wallet.get_address = lambda: succeed(f'sequence {self.wallet.testnet}')
        sequence_nr = self.wallet.get_sequence_number()
        self.assertEqual(10000, sequence_nr)

    def test_get_sequence_number_api(self):
        """
        Test for getting sequence number from the api
        """

        self.assertEqual(100, self.wallet.get_sequence_number())

    def test_get_address_not_created(self):
        """
        Test for get_address when the wallet has not been created
        """
        result = self.wallet.get_address().result()
        self.assertEqual('', result)

    def test_get_address_created(self):
        """
        Test for get_address when the wallet has been created
        """
        secret = 'SD7FUHVVDQ3NSMTFI4EQ6JRPKABZUZHTKH6N7AEQMKZQDEMO7SZFOBXN'
        address = 'GCEYPGQX75YWCWL77NOWWHHMGS2R5DP2FAOWLT65NSORFXZHQIDDCOO7'
        self.create_wallet()
        self.wallet.keypair = Keypair.from_secret(secret)
        result = self.wallet.get_address().result()
        self.assertEqual(address, result)

    def test_precision(self):
        self.assertEqual(7, self.wallet.precision())

    async def test_get_transactions_not_created(self):
        """
        Test for get_transactions when wallet has not been created
        """
        self.wallet.created_on_network = False
        self.wallet.check_and_update_created_on_network = lambda *_: None
        self.assertEqual([], await self.wallet.get_transactions())

    async def test_get_transactions_created(self):
        """
        Test for get_transactions when wallet has been created
        """
        self.wallet.database.insert_transaction(self.tx)
        self.wallet.get_address = lambda: succeed('GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW')
        self.wallet.provider = MockObject()
        self.wallet.provider.get_ledger_height = lambda: 26529414
        self.wallet.provider.get_transactions = lambda *_: []
        self.wallet.created = True
        self.wallet.created_on_network = True
        payment_dict = {
            'id': '96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98',  # use tx hash for now
            'outgoing': False,
            'from': 'GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH',
            'to': 'GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW',
            'amount': 30000000,
            'fee_amount': 100,
            'currency': self.identifier,
            'timestamp': None,  # timestamp is timezone specific
            'description': f'confirmations: 1'
        }

        payments_from_wallet = await self.wallet.get_transactions()
        payments_from_wallet[0]['timestamp'] = None  # timestamp is timezone specific

        self.assertEqual([payment_dict], payments_from_wallet)

    @timeout(5)
    async def test_monitor_transactions_found(self):
        """
        Test for monitor_transactions when the transaction is found
        :return:
        """
        self.wallet.created = True
        self.wallet.created_on_network = True
        self.wallet.database.insert_transaction(self.tx)
        self.wallet.get_address = lambda: succeed('GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH')
        self.wallet.provider = MockObject()
        self.wallet.provider.get_ledger_height = lambda: 26529414
        self.wallet.provider.get_transactions = lambda *_: []

        self.assertIsNone(await self.wallet.monitor_transaction(
            '96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98', interval=1))

    @timeout(5)
    async def test_monitor_transactions_not_found(self):
        """
        Test for monitor_transactions when the transaction is not found
        """
        self.wallet.created = True
        self.wallet.get_address = lambda: succeed('GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW')
        self.wallet.provider = MockObject()
        self.wallet.provider.get_ledger_height = lambda: 26529414
        self.wallet.provider.get_transactions = lambda *_: []

        future = self.wallet.monitor_transaction(
            '96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98', interval=1)
        # the monitor transaction runs every 5 secs so this should be enough
        time.sleep(2)
        self.assertFalse(future.done())

    async def test_transfer_no_balance(self):
        """
        Test for transfer when we don't have enough balance
        """
        self.wallet.get_balance = lambda: succeed({'available': 1})
        self.wallet.provider.get_base_fee = lambda *_: 1
        with self.assertRaises(InsufficientFunds):
            await self.wallet.transfer(10, 'xxx')

    def test_min_unit(self):
        self.assertEqual(1e7, self.wallet.min_unit())

    async def test_merge_account(self):
        self.create_wallet()
        self.wallet.provider.get_base_fee = lambda *_: 100
        self.wallet.provider.submit_transaction = lambda *_: 'random_hash'
        self.assertEqual('random_hash',
                         await self.wallet.merge_account('GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH'))


class TestStellarTestnetWallet(TestStellarWallet):

    def setUp(self):
        super().setUp()
        mock = MockObject()
        mock.get_account_sequence = lambda *_: 100
        self.wallet = StellarTestnetWallet(self.session_base_dir, mock)
        self.identifier = 'TXLM'
        self.name = 'testnet stellar'

        self.tx = Transaction(
            hash='96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98',
            ledger_nr=26529414,
            date_time=datetime.fromisoformat('2020-06-05T08:45:33'),
            source_account='GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH',
            operation_count=1,
            transaction_envelope="AAAAAOFkeKoP9De5JOCNgRYZVF8IIdi8WZ6olTXYb1KTMlgRAAAAZAGOO+wAAAA9AAAAAQAAAAAAAAAA"
                                 "AAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAADhZHiq"
                                 "D/Q3uSTgjYEWGVRfCCHYvFmeqJU12G9SkzJYEQAAAAAAAAAAXQbflbQZVvhfaHtF6ESvgGrNnl2gi440"
                                 "84MWUaGbmNkAAAAAAcnDgAAAAAAAAAABHvBc2AAAAEBUL1wo8IGHEpgpQ7llGaFE+rC9v5kk2KPJe53/"
                                 "gIdWF+792HYg5yTTmhJII97YgM+Be8yponPH0YjMjeYphewI",
            fee=100,
            is_pending=False,
            succeeded=True,
            sequence_number=112092925529161789,
            min_time_bound=datetime.fromisoformat('1970-01-01T00:00:00')
        )

    def new_wallet(self):
        mock = MockObject()
        mock.get_account_sequence = lambda *_: 100
        mock.check_account_created = lambda *_: None
        return StellarTestnetWallet(self.session_base_dir, mock)
