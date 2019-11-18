from binascii import unhexlify

from aiohttp import web

from ipv8.REST.base_endpoint import HTTP_NOT_FOUND, Response

from anydex.core.transaction import TransactionId
from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class TransactionsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding (past) transactions in the market community.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_transactions),
                             web.get('/{transaction_id}/payments', self.get_payments)])

    async def get_transactions(self, request):
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
        return Response({"transactions": [transaction.to_block_dictionary() for transaction in transactions]})

    async def get_payments(self, request):
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
        transaction_id = TransactionId(unhexlify(request.match_info['transaction_id']))
        transaction = self.get_market_community().transaction_manager.find_by_id(transaction_id)

        if not transaction:
            return Response({"error": "transaction not found"}, status=HTTP_NOT_FOUND)

        return Response({"payments": [payment.to_dictionary() for payment in transaction.payments]})
