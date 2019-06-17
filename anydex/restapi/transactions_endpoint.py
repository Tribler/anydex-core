from __future__ import absolute_import

from binascii import unhexlify

from twisted.web import http

import anydex.util.json_util as json
from anydex.core.transaction import TransactionId
from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class TransactionsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding (past) transactions in the market community.
    """

    def getChild(self, path, request):
        return SpecificTransactionEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /market/transactions

        A GET request to this endpoint will return all performed transactions in the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/transactions

            **Example response**:

            .. sourcecode:: javascript

                {
                    "transactions": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "order_number": 4,
                        "partner_trader_id": "34c406358ba05e5883a75da3f009477e4ca699a9",
                        "partner_order_number": 1,
                        "assets" {
                            "first": {
                                "amount": 3,
                                "type": "BTC",
                            },
                            "second": {
                                "amount": 3,
                                "type": "MB",
                            }
                        },
                        "transferred" {
                            "first": {
                                "amount": 3,
                                "type": "BTC",
                            },
                            "second": {
                                "amount": 3,
                                "type": "MB",
                            }
                        }
                        "timestamp": 1493906434.627721,
                        "payment_complete": False
                    ]
                }
        """
        transactions = self.get_market_community().transaction_manager.find_all()
        return json.twisted_dumps({"transactions": [transaction.to_block_dictionary() for transaction in transactions]})


class SpecificTransactionEndpoint(BaseMarketEndpoint):
    """
    This class handles requests for a specific transaction.
    """

    def __init__(self, session, path):
        BaseMarketEndpoint.__init__(self, session)
        self.transaction_id = path

        child_handler_dict = {b"payments": TransactionPaymentsEndpoint}
        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(self.session, self.transaction_id))


class TransactionPaymentsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests for the payments of a specific transaction.
    """

    def __init__(self, session, transaction_id):
        BaseMarketEndpoint.__init__(self, session)
        self.transaction_id = TransactionId(unhexlify(transaction_id))

    def render_GET(self, request):
        """
        .. http:get:: /market/transactions/(string:transaction_id)/payments

        A GET request to this endpoint will return all payments tied to a specific transaction.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/transactions/
                12c406358ba05e5883a75da3f009477e4ca699a9/3/payments

            **Example response**:

            .. sourcecode:: javascript

                {
                    "payments": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "transaction_number": 3,
                        "price": 10,
                        "price_type": "MC",
                        "quantity": 10,
                        "quantity_type": "BTC",
                        "transferred_quantity": 4,
                        "payment_id": "abcd",
                        "address_from": "my_mc_address",
                        "address_to": "my_btc_address",
                        "timestamp": 1493906434.627721,
                    ]
                }
        """
        transaction = self.get_market_community().transaction_manager.find_by_id(self.transaction_id)

        if not transaction:
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "transaction not found"})

        return json.twisted_dumps({"payments": [payment.to_dictionary() for payment in transaction.payments]})
