import time
from datetime import datetime

from sqlalchemy.orm import session as db_session

from anydex.test.base import AbstractServer
from anydex.test.util import MockObject
from anydex.wallet.ethereum.eth_database import Key, Transaction
from anydex.wallet.ethereum.eth_wallet import EthereumWallet, EthereumTestnetWallet


class TestEthereumWallet(AbstractServer):

    def setUp(self):
        super(TestEthereumWallet, self).setUp()
        self.wallet = self.new_wallet()
        self.identifier = 'ETH'
        self.name = 'ethereum'

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def new_wallet(self):
        return EthereumWallet(self.session_base_dir)

    def test_get_identifier(self):
        """
        Test for get identifier
        """
        self.assertEqual(self.identifier, self.wallet.get_identifier())

    def test_get_name(self):
        """
        Test for get_name
        """
        self.assertEqual(self.name, self.wallet.get_name())

    def test_create_wallet(self):
        """
        Test the creation of the wallet
        """
        self.wallet.create_wallet()
        addr = self.wallet._session.query(Key.address).first()[0]
        self.assertEqual(addr, self.wallet.account.address)
        self.assertIsNotNone(self.wallet.account)
        self.assertTrue(self.wallet.created)

    def test_create_wallet_already_created(self):
        """
        Test the creation of the wallet when the wallet is already created
        """
        self.wallet.create_wallet()
        self.assertIsNotNone(self.wallet.account)
        self.assertTrue(self.wallet.created)
        future = self.wallet.create_wallet()
        self.assertIsInstance(future.exception(), RuntimeError)

    async def test_get_balance_not_created(self):
        """
        Test for getting a balance of a wallet that has not been created
        """
        balance = {
            'available': 0,
            'pending': 0,
            'currency': self.identifier,
            'precision': 18
        }
        self.assertEqual(balance, await self.wallet.get_balance())

    async def test_get_balance(self):
        """
        Test for getting the balance of a created wallet.
        """
        self.wallet.create_wallet()
        mock_obj = MockObject()
        mock_obj.get_balance = lambda *_: 992
        self.wallet.provider = mock_obj
        self.wallet.get_transactions = lambda *_: []
        self.wallet._update_database = lambda *_: None
        self.wallet.get_outgoing_amount = lambda *_: 0
        self.wallet.get_incoming_amount = lambda *_: 0
        balance = {
            'available': 992,
            'pending': 0,
            'currency': self.identifier,
            'precision': 18
        }
        self.assertEqual(balance, await self.wallet.get_balance())

    def test_get_outgoing_amount(self):
        """
        Test for the get_outgoing_amount function.
        """
        self.wallet.create_wallet()
        self.wallet._session.add(
            Transaction(is_pending=True, value=100, from_=self.wallet.account.address,
                        hash=self.wallet.generate_txid()))
        self.wallet._session.add(
            Transaction(is_pending=True, value=200, from_=self.wallet.account.address,
                        hash=self.wallet.generate_txid()))
        self.assertEqual(300, self.wallet.get_outgoing_amount())

    def test_get_incoming_amount(self):
        """
        Test for the get_incoming_amount function
        """
        self.wallet.create_wallet()
        self.wallet._session.add(
            Transaction(is_pending=True, value=100, to=self.wallet.account.address, hash=self.wallet.generate_txid()))
        self.wallet._session.add(
            Transaction(is_pending=True, value=200, to=self.wallet.account.address, hash=self.wallet.generate_txid()))
        self.assertEqual(300, self.wallet.get_incoming_amount())

    def test_get_address_not_created(self):
        """
        Test for getting the address of the wallet when it's not yet created
        """
        self.assertEqual('', self.wallet.get_address().result())

    def test_get_address(self):
        """
        Test for getting the address of the wallet when it's created
        """
        self.wallet.create_wallet()
        self.assertEqual(self.wallet.account.address, self.wallet.get_address().result())

    def test_precision(self):
        """
        Test for the precision function
        """
        self.assertEqual(18, self.wallet.precision())

    async def test_get_transactions(self):
        """
        Test for get transactions
        """
        self.wallet.create_wallet()
        tx = Transaction(
            hash="0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060",
            date_time=datetime(2015, 8, 7, 3, 30, 33),
            from_=self.wallet.get_address().result(),
            to="0x5df9b87991262f6ba471f09758cde1c0fc1de734",
            gas=5,
            gas_price=5,
            nonce=0,
            is_pending=False,
            value=31337,
            block_number=46147
        )
        mock_provider = MockObject()
        mock_provider.get_latest_blocknr = lambda *_: 46147
        mock_provider.get_transactions = lambda *_, **x: [tx]
        self.wallet.provider = mock_provider

        transactions = await self.wallet.get_transactions()
        tx_dict = {
            'id': tx.hash,
            'outgoing': True,
            'from': self.wallet.get_address().result(),
            'to': "0x5df9b87991262f6ba471f09758cde1c0fc1de734",
            'amount': 31337,
            'fee_amount': 25,
            'currency': self.identifier,
            'timestamp': time.mktime(datetime(2015, 8, 7, 3, 30, 33).timetuple()),
            'description': f'Confirmations: {1}'
        }
        self.assertEqual([tx_dict], transactions)

    def test_get_transaction_count(self):
        """
        Test get transaction count
        """
        self.wallet.create_wallet()
        tx = Transaction(
            hash="0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060",
            date_time=datetime(2015, 8, 7, 3, 30, 33),
            from_=self.wallet.get_address().result(),
            to="0x5df9b87991262f6ba471f09758cde1c0fc1de734",
            gas=5,
            gas_price=5,
            nonce=5,
            is_pending=True,
            value=31337,
            block_number=46147
        )
        self.wallet._session.add(tx)
        self.assertEqual(6, self.wallet.get_transaction_count())

    def test_get_transaction_count_zero_tx(self):
        """
        Test get transaction count when the wallet has sent 0 transactions
        """
        self.wallet.create_wallet()
        self.assertEqual(0, self.wallet.get_transaction_count())


class TestTestnetEthereumWallet(TestEthereumWallet):

    def setUp(self):
        super(TestEthereumWallet, self).setUp()
        self.wallet = self.new_wallet()
        self.identifier = 'TETH'
        self.name = 'testnet ethereum'

    def new_wallet(self):
        return EthereumTestnetWallet(self.session_base_dir)
