import os
from datetime import datetime

from sqlalchemy.orm import session as db_session

from anydex.test.base import AbstractServer
from anydex.wallet.ethereum.eth_wallet import EthereumDb, Transaction


class TestEthereumDb(AbstractServer):
    def setUp(self):
        super().setUp()
        self.db = EthereumDb(os.path.join(self.session_base_dir, 'eth.db'))

    async def tearDown(self):
        db_session.close_all_sessions()
        await super().tearDown()

    def test_get_outgoing_amount(self):
        """
        Test for the get_outgoing_amount function.
        """
        self.db.add(
            Transaction(is_pending=True, value=100, from_='xxx',
                        hash='xxx', token_identifier='ETH'))
        self.db.add(
            Transaction(is_pending=True, value=200, from_='xxx',
                        hash='aaa', token_identifier='ETH'))
        self.assertEqual(300, self.db.get_outgoing_amount('xxx', 'ETH'))

    def test_get_incoming_amount(self):
        """
        Test for the get_incoming_amount function
        """
        self.db.add(
            Transaction(is_pending=True, value=100, to='xxx', hash='xxx', token_identifier='ETH'))
        self.db.add(
            Transaction(is_pending=True, value=200, to='xxx', hash='aaa', token_identifier='ETH'))
        self.assertEqual(300, self.db.get_incoming_amount('xxx', 'ETH'))

    def test_get_wallet_private_key_no_key(self):
        """
        Test for get_wallet_private_key when the key isn't stored in the db.
        """
        self.assertEqual(None, self.db.get_wallet_private_key('xxx'))

    def test_get_wallet_private_key_key(self):
        """
        Test for get_wallet_private_key when the key is stored in the db.
        """
        self.db.add_key('xxx', b'key', 'xxx')
        self.assertEqual(b'key', self.db.get_wallet_private_key('xxx'))

    def test_get_transaction_count(self):
        """
        Test get transaction count
        """
        tx = Transaction(
            hash='0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060',
            date_time=datetime(2015, 8, 7, 3, 30, 33),
            from_='xxx',
            to='0x5df9b87991262f6ba471f09758cde1c0fc1de734',
            gas=5,
            gas_price=5,
            nonce=5,
            is_pending=True,
            value=31337,
            block_number=46147
        )
        self.db.add(tx)
        self.assertEqual(6, self.db.get_transaction_count('xxx'))

    def test_get_transaction_count_zero_tx(self):
        """
        Test get transaction count when the wallet has sent 0 transactions
        """

        self.assertEqual(0, self.db.get_transaction_count('xxx'))
