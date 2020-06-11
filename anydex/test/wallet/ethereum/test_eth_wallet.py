import time
from datetime import datetime

from sqlalchemy.orm import session as db_session

from anydex.test.base import AbstractServer
from anydex.test.util import MockObject
from anydex.wallet.ethereum.eth_db import Key, Transaction
from anydex.wallet.ethereum.eth_wallet import EthereumWallet, EthereumTestnetWallet


class TestEthereumWallet(AbstractServer):

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def test_create_wallet(self):
        """
        Test the creation of the wallet
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        addr = wallet._session.query(Key.address).first()[0]
        self.assertEqual(addr, wallet.account.address)
        self.assertIsNotNone(wallet.account)
        self.assertTrue(wallet.created)

    def test_create_wallet_allready_created(self):
        """
        Test the creation of the wallet when the wallet is already created
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        self.assertIsNotNone(wallet.account)
        self.assertTrue(wallet.created)
        future = wallet.create_wallet()
        self.assertIsInstance(future.exception(), RuntimeError)

    def test_get_name(self):
        """
        Test for get_name
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        self.assertEqual("ethereum", wallet.get_name())

    async def test_get_balance_not_created(self):
        """
        Test for getting a balance of a wallet that has not been created
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        balance = {
            'available': 0,
            'pending': 0,
            'currency': 'ETH',
            'precision': 18
        }
        self.assertEqual(balance, await wallet.get_balance())

    async def test_get_balance(self):
        """
        Test for getting the balance of a created wallet.
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        mock_obj = MockObject()
        mock_obj.get_balance = lambda *_: 992
        wallet.provider = mock_obj
        wallet.get_transactions = lambda *_: []
        wallet._update_database = lambda *_: None
        wallet.get_outgoing_amount = lambda *_: 0
        wallet.get_incoming_amount = lambda *_: 0
        balance = {
            'available': 992,
            'pending': 0,
            'currency': 'ETH',
            'precision': 18
        }
        self.assertEqual(balance, await wallet.get_balance())

    def test_get_outgoing_amount(self):
        """
        Test for the get_outgoing_amount function.
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        wallet._session.add(
            Transaction(is_pending=True, value=100, from_=wallet.account.address, hash=wallet.generate_txid()))
        wallet._session.add(
            Transaction(is_pending=True, value=200, from_=wallet.account.address, hash=wallet.generate_txid()))
        self.assertEqual(300, wallet.get_outgoing_amount())

    def test_get_incoming_amount(self):
        """
        Test for the get_incoming_amount function
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        wallet._session.add(
            Transaction(is_pending=True, value=100, to=wallet.account.address, hash=wallet.generate_txid()))
        wallet._session.add(
            Transaction(is_pending=True, value=200, to=wallet.account.address, hash=wallet.generate_txid()))
        self.assertEqual(300, wallet.get_incoming_amount())

    def test_get_address_not_created(self):
        """
        Test for getting the address of the wallet when it's not yet created
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        self.assertEqual("", wallet.get_address())

    def test_get_address(self):
        """
        Test for getting the address of the wallet when it's created
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        self.assertEqual(wallet.account.address, wallet.get_address())

    def test_precision(self):
        """
        Test for the precision function
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        self.assertEqual(18, wallet.precision())

    def test_get_identifier(self):
        """
        Test for get identifier
        """

        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        self.assertEqual("ETH", wallet.get_identifier())

    async def test_get_transactions(self):
        """
        Test for get transactions
        """

        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        tx = Transaction(hash="0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060",
                         date_time=datetime(2015, 8, 7, 3, 30, 33),
                         from_=wallet.get_address(),
                         to="0x5df9b87991262f6ba471f09758cde1c0fc1de734",
                         gas=5,
                         gas_price=5,
                         nonce=0,
                         is_pending=False,
                         value=31337,
                         block_number=46147)
        mock_provider = MockObject()
        mock_provider.get_latest_blocknr = lambda *_: 46147
        mock_provider.get_transactions = lambda *_, **x: [tx]
        wallet.provider = mock_provider

        transactions = await wallet.get_transactions()
        tx_dict = {
            'id': tx.hash,
            'outgoing': True,
            'from': wallet.get_address(),
            'to': "0x5df9b87991262f6ba471f09758cde1c0fc1de734",
            'amount': 31337,
            'fee_amount': 25,
            'currency': 'ETH',
            'timestamp': time.mktime(datetime(2015, 8, 7, 3, 30, 33).timetuple()),
            'description': f'Confirmations: {1}'
        }
        self.assertEqual([tx_dict], transactions)

    def test_get_transaction_count(self):
        """
        Test get transaction count
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        tx = Transaction(hash="0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060",
                         date_time=datetime(2015, 8, 7, 3, 30, 33),
                         from_=wallet.get_address(),
                         to="0x5df9b87991262f6ba471f09758cde1c0fc1de734",
                         gas=5,
                         gas_price=5,
                         nonce=5,
                         is_pending=True,
                         value=31337,
                         block_number=46147)
        wallet._session.add(tx)
        self.assertEqual(6, wallet.get_transaction_count())

    def test_get_transaction_count_zero_tx(self):
        """
        Test get transaction count when the wallet has sent 0 transactions
        """
        wallet = EthereumWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        wallet.create_wallet()
        self.assertEqual(0, wallet.get_transaction_count())


class TestTestnetEthereumWallet(AbstractServer):

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def test_get_idetifier(self):
        """
        Test for get identifier
        """
        wallet = EthereumTestnetWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        self.assertEqual("TETH", wallet.get_identifier())

    def test_get_name(self):
        """
        Test for get_name
        """
        wallet = EthereumTestnetWallet(self.session_base_dir, True)  # Trick the wallet to not use the default provider
        self.assertEqual("Testnet ETH", wallet.get_name())
