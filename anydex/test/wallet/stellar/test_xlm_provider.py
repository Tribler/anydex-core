from datetime import datetime
from unittest import TestCase

import stellar_sdk
from stellar_sdk.client.response import Response
from stellar_sdk.exceptions import NotFoundError

from anydex.wallet.provider import ConnectionException, RequestException
from anydex.wallet.stellar.xlm_db import Transaction
from anydex.wallet.stellar.xlm_provider import HorizonProvider
from anydex.test.util import MockObject


class TestHorizonProvider(TestCase):
    """
    Tests for the Horizon provider.
    These tests only test our code and do send requests to any server.
    """
    # The content of these responses might be incorrect / omitted
    sample_submit_tx_response = {
        "memo": "2324",  # links omitted
        "id": "36df85cf7c8947fd251714bacd69b5df89945abe02337a2a0d3f5fefd1cc8c83",
        "paging_token": "2399336235282432",
        "successful": True,
        "hash": "36df85cf7c8947fd251714bacd69b5df89945abe02337a2a0d3f5fefd1cc8c83",
        "ledger": 558639,
        "created_at": "2020-06-03T15:47:39Z",
        "source_account": "GA6XQF5FLTHFYJLWFUAAHVS3NIO35Y7GE7THZNCXUJOPDW3TYUACWCH5",
        "source_account_sequence": "1978008533467156",
        "fee_account": "GA6XQF5FLTHFYJLWFUAAHVS3NIO35Y7GE7THZNCXUJOPDW3TYUACWCH5",
        "fee_charged": "100",
        "max_fee": "100",
        "operation_count": 1,
        "envelope_xdr": "AAAAAgAAAAA9eBelXM5cJXYtAAPWW2odvuPmJ",
        "result_xdr": "AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=",
        "result_meta_xdr": "AAAAAgAAAAIAAAADAAiGLwAAAAAAAAAAPXgXpVzOXCV2LQAD1ltqHb7j5ifmfLRXolzx23PFACsAAAATpNgAsAAHBv",
        "fee_meta_xdr": "AAAAAgAAAAMACITLAAAAAAAAAAA9eBelXM5cJXYtAAPWW2odvuPmJ+Z8tFeiXPHbc8UAKwAAABOk2AEUAAcG/QAAABMAA",
        "memo_type": "id",
        "signatures": [
            "V6XapCWcsf2rym9qJcti9+qcnFHXUiJG4ClwgZu8xaOBeCQmbEwWooR3ofUNQrozzk3W1sZLlpZoGr6AxbqlDA=="
        ]
    }
    sample_get_txs_response = {
        "_embedded": {
            "records": [
                {
                    "memo": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                    "id": "96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98",
                    "paging_token": "113942965512118272",
                    "successful": True,
                    "hash": "96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98",
                    "ledger": 26529414,
                    "created_at": "2019-10-29T00:50:35Z",
                    "source_account": "GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH",
                    "source_account_sequence": "112092925529161789",
                    "fee_account": "GDQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH",
                    "fee_charged": "100",
                    "max_fee": "100",
                    "operation_count": 1,
                    "envelope_xdr": "/+rC9v5kk2KPJe53/gIdWF+792HYg5yTTmhJII97YgM+Be8yponPH0YjMjeYphewI",
                    "result_xdr": "AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAA=",
                    "result_meta_xdr": "/+/+/+/+",
                    "fee_meta_xdr": "/++=",
                    "memo_type": "hash",
                    "signatures": [
                        "VC9cKPCBhxKYKUO5ZRmhRPqwvb+ZJNijyXud/4CHVhfu/dh2IOck05oSSCPe2IDPgXvMqaJzx9GIzI3mKYXsCA=="
                    ],
                    "valid_after": "1970-01-01T00:00:00Z"
                }
            ]
        }
    }

    sample_account_response = {
        "id": "GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW",
        "account_id": "GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW",
        "sequence": "113942965513805922",
        "subentry_count": 0,
        "last_modified_ledger": 29958133,
        "last_modified_time": "2020-06-03T21:25:56Z",
        "thresholds": {
            "low_threshold": 0,
            "med_threshold": 0,
            "high_threshold": 0
        },
        "flags": {
            "auth_required": False,
            "auth_revocable": False,
            "auth_immutable": False
        },
        "balances": [
            {
                "balance": "25.0779942",
                "buying_liabilities": "0.0000000",
                "selling_liabilities": "0.0000000",
                "asset_type": "native"
            }
        ],
        "signers": [
            {
                "weight": 1,
                "key": "GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW",
                "type": "ed25519_public_key"
            }
        ],
        "data": {},
        "paging_token": "GBOQNX4VWQMVN6C7NB5UL2CEV6AGVTM6LWQIXDRU6OBRMUNBTOMNSOAW"
    }
    sample_legder_response = {
        "_embedded": {
            "records": [
                {
                    "id": "63d98f536ee68d1b27b5b89f23af5311b7569a24faf1403ad0b52b633b07be99",
                    "paging_token": "4294967296",
                    "hash": "63d98f536ee68d1b27b5b89f23af5311b7569a24faf1403ad0b52b633b07be99",
                    "sequence": 1,
                    "successful_transaction_count": 0,
                    "failed_transaction_count": 0,
                    "operation_count": 0,
                    "closed_at": "1970-01-01T00:00:00Z",
                    "total_coins": "100000000000.0000000",
                    "fee_pool": "0.0000000",
                    "base_fee_in_stroops": 100,
                    "base_reserve_in_stroops": 100000000,
                    "max_tx_set_size": 100,
                    "protocol_version": 0,
                    "header_xdr": "/ySKB7DnD9H20xjB+"
                }
            ]
        }
    }

    def setUp(self):
        self.provider = HorizonProvider("")

    def test_submit_transaction(self):
        self.provider.server.submit_transaction = lambda *_: self.sample_submit_tx_response
        dummy_hash = self.provider.submit_transaction('XXX')
        self.assertEqual(dummy_hash, '36df85cf7c8947fd251714bacd69b5df89945abe02337a2a0d3f5fefd1cc8c83')

    def test_get_transactions(self):
        mock = MockObject()
        fun = lambda *_: mock  # the library we use uses the builder pattern
        mock.for_account = fun
        mock.include_failed = fun
        mock.limit = fun
        mock.call = lambda *_: self.sample_get_txs_response
        self.provider.server.transactions = lambda: mock
        tx = Transaction(hash='96ad71731b1b46fceb0f1c32adbcc16a93cefad1e6eb167efe8a8c8e4e0cbb98',
                         ledger_nr=26529414,
                         date_time=datetime.fromisoformat('2019-10-29T00:50:35'),
                         source_account='DQWI6FKB72DPOJE4CGYCFQZKRPQQIOYXRMZ5KEVGXMG6UUTGJMBCASH',
                         operation_count=1,
                         transaction_envelope="AAAAAOFkeKoP9De5JOCNgRYZVF8IIdi8WZ6olTXYb1KTMlgRAAAAZAGOO"
                                              "+wAAAA9AAAAAQAAAAAAAAAAAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                                              "AAAAAAAAAAAAAAABAAAAAQAAAADhZHiqD/Q3uSTgjYEWGVRfCCHYvFmeqJU12G9SkzJYEQA"
                                              "AAAAAAAAAXQbflbQZVvhfaHtF6ESvgGrNnl2gi44084MWUaGbmNkAAAAAAcnDgAAAAAAAAA"
                                              "ABHvBc2AAAAEBUL1wo8IGHEpgpQ7llGaFE+rC9v5kk2KPJe53/gIdWF+792HYg5yTTmhJII"
                                              "97YgM+Be8yponPH0YjMjeYphewI",
                         fee=100,
                         is_pending=False,
                         succeeded=True,
                         sequence_number=112092925529161789,
                         min_time_bound=datetime.fromisoformat('1970-01-01T00:00:00'))
        self.assertEqual([tx], self.provider.get_transactions('XXX'))

    def test_get_balance(self):
        mock = MockObject()
        fun = lambda *_: mock  # the library we use uses the builder pattern
        mock.account_id = fun
        mock.call = lambda *_: self.sample_account_response
        self.provider.server.accounts = fun
        self.assertEqual('25.0779942', self.provider.get_balance('XXX'))

    def test_base_fee(self):
        self.provider.server.fetch_base_fee = lambda: 100

        self.assertEqual(100, self.provider.get_base_fee())

    def test_get_ledger_height(self):
        mock = MockObject()
        fun = lambda *_: mock  # the library we use uses the builder pattern
        self.provider.server.ledgers = fun
        mock.limit = fun
        mock.order = fun
        mock.call = lambda: self.sample_legder_response
        self.assertEqual(1, self.provider.get_ledger_height())

    def test_get_account_sequence(self):
        mock = MockObject()
        fun = lambda *_: mock  # the library we use uses the builder pattern
        mock.account_id = fun
        mock.call = lambda *_: self.sample_account_response
        self.provider.server.accounts = fun
        self.assertEqual(113942965513805922, self.provider.get_account_sequence('XXX'))

    def test_check_account_created_not_created(self):
        """
        Test for check_account_created where the account has not been created.
        """

        def raise_not_found(*_):
            response = Response(9, '', {}, '')
            raise NotFoundError(response)

        self.provider.server.load_account = raise_not_found

        self.assertFalse(self.provider.check_account_created('XXX'))

    def test_check_account_created_created(self):
        """
        Test for check_account_created where the account has0 been created.
        """

        self.provider.server.load_account = lambda *_: None

        self.assertTrue(self.provider.check_account_created('XXX'))

    def test_make_request_connection_error(self):
        """
        Test for _make_request where the api call raises a Connection error
        :return:
        """

        def raise_connection_error():
            raise stellar_sdk.exceptions.ConnectionError()

        self.assertRaises(ConnectionException, self.provider._make_request, raise_connection_error)

    def test_make_request_not_found_error(self):
        """
        Test for _make_request where the api call raises a NotFoundError
        :return:
        """

        def raise_not_found_error():
            response = Response(9, '', {}, '')  # dummy response
            raise stellar_sdk.exceptions.NotFoundError(response)

        self.assertRaises(RequestException, self.provider._make_request, raise_not_found_error)

    def test_make_request_bad_request_error(self):
        """
        Test for _make_request where the api call raises a BadRequestError
        :return:
        """

        def raise_not_found_error():
            response = Response(9, '', {}, '')  # dummy response
            raise stellar_sdk.exceptions.BadRequestError(response)

        self.assertRaises(RequestException, self.provider._make_request, raise_not_found_error)

    def test_make_request_bad_response_error(self):
        """
        Test for _make_request where the api call raises a BadResponseError
        :return:
        """

        def raise_not_found_error():
            response = Response(9, '', {}, '')  # dummy response
            raise stellar_sdk.exceptions.BadResponseError(response)

        self.assertRaises(RequestException, self.provider._make_request, raise_not_found_error)
