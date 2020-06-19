import os
from datetime import datetime

from sqlalchemy.orm import session as db_session

from anydex.wallet.stellar.xlm_database import StellarDb, Secret, Transaction
from anydex.test.base import AbstractServer


class TestStellarDb(AbstractServer):
    def setUp(self):
        super().setUp()
        self.db = StellarDb(os.path.join(self.session_base_dir, 'stellar.db'))
        self.tx = Transaction(hash='96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98',
                              ledger_nr=26529414,
                              date_time=datetime.fromisoformat('2020-06-05T08:45:33'),
                              source_account='GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH',
                              operation_count=1,
                              transaction_envelope="AAAAAOFkeKoP9De5JOCNgRYZVF8IIdi8WZ6olTXYb1KTMlgRAAAAZAGOO"
                                                   "+wAAAA9AAAAAQAAAAAAAAAAAAAAAAAAAAAAAA"
                                                   "ADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                                                   "AAAAAAAAAAAAAAABAAAAAQAAAADhZHiqD/Q3uSTgjYEWGVRfC"
                                                   "CHYvFmeqJU12G9SkzJYEQA"
                                                   "AAAAAAAAAXQbflbQZVvhfaHtF6ESvgGrNnl2gi44084MWUaGbmNk"
                                                   "AAAAAAcnDgAAAAAAAAA"
                                                   "ABHvBc2AAAAEBUL1wo8IGHEpgpQ7llGaFE+rC9v5kk2KP"
                                                   "Je53/gIdWF+792HYg5yTTmhJII97YgM+Be8yponPH0YjMjeYphewI",
                              fee=100,
                              is_pending=True,
                              succeeded=True,
                              sequence_number=112092925529161789,
                              min_time_bound=datetime.fromisoformat('1970-01-01T00:00:00'))

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def test_get_wallet_secret_no_secret(self):
        """
        Test for get_wallet_secret when there is no secret
        """
        self.assertIsNone(self.db.get_wallet_secret("xxx"))

    def test_get_wallet_secret_secret(self):
        """
        Test for get_wallet_secret when there is a secret
        """
        self.db.session.add(Secret(name='xxx', secret='supersecret', address='xxx'))
        self.assertEqual('supersecret', self.db.get_wallet_secret('xxx'))

    def test_add_secret(self):
        self.db.add_secret('name', 'supersecret', 'xxx')
        secret = self.db.session.query(Secret).first()
        self.assertEqual('name', secret.name)
        self.assertEqual('supersecret', secret.secret)
        self.assertEqual('xxx', secret.address)

    def test_get_outgoing_amount_0(self):
        """
        Test for get_outgoing_amount where there are no outgoing transactions
        """
        self.assertEqual(0, self.db.get_outgoing_amount('xxx'))

    def test_get_outgoing_amount(self):
        """
        Test for get_outgoing_amount where there are outgoing transactions
        """  # using the global tx doesn't work for some reason

        self.db.insert_transaction(self.tx)
        self.assertEqual(30000000,
                         self.db.get_outgoing_amount('GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH'))

    def test_update_db(self):
        """
        Test for update_db where there are no transactions in the database
        """
        self.db.update_db([self.tx])
        txs = self.db.session.query(Transaction).all()

        self.assertEqual(1, len(txs))
        self.assertEqual(self.tx, txs[0])

    def test_update_db_update_pending(self):
        """
        Test for update_db where a pending transaction is updated
        """
        self.tx.is_pending = True
        self.db.update_db([self.tx])
        self.tx.is_pending = False
        self.db.update_db([self.tx])
        txs = self.db.session.query(Transaction).all()

        self.assertEqual(1, len(txs))
        self.assertFalse(txs[0].is_pending)

    def test_get_sequence_number_empty_db(self):
        """
        Test for get_sequence_number where there are no transactions in the database
        """

        self.assertIsNone(self.db.get_sequence_number('xxx'))

    def test_get_sequence_number(self):
        """
        Test for get_sequence_number where there are transactions in the database
        """
        self.db.insert_transaction(self.tx)
        self.assertEqual(112092925529161789, self.db.get_sequence_number(self.tx.source_account))

    def test_get_payments_and_transactions(self):
        """
        Test for get_payments_and_transactions
        """
        self.db.update_db([self.tx])
        txs = self.db.get_payments_and_transactions(self.tx.source_account)

        self.assertEqual(1, len(txs))
        self.assertEqual(self.tx, txs[0][1])
        self.assertEqual(self.tx.source_account, txs[0][0].from_)
