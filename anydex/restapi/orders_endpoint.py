from aiohttp import web

from ipv8.REST.base_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, Response

from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class OrdersEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding your orders in the market community.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_orders),
                             web.post('/{order_number}/cancel', self.cancel_order)])

    async def get_orders(self, request):
        """
        .. http:get:: /market/orders

        A GET request to this endpoint will return all your orders in the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/orders

            **Example response**:

            .. sourcecode:: javascript

                {
                    "orders": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "timestamp": 1493906434.627721,
                        "assets" {
                            "first": {
                                "amount": 3,
                                "type": "BTC",
                            },
                            "second": {
                                "amount": 3,
                                "type": "MB",
                            }
                        }
                        "reserved_quantity": 0,
                        "is_ask": False,
                        "timeout": 3600,
                        "traded": 0,
                        "order_number": 1,
                        "completed_timestamp": null,
                        "cancelled": False,
                        "status": "open"
                    }]
                }
        """
        orders = self.get_market_community().order_manager.order_repository.find_all()
        return Response({"orders": [order.to_dictionary() for order in orders]})

    async def cancel_order(self, request):
        """
        .. http:get:: /market/orders/(string:order_number)/cancel

        A POST request to this endpoint will cancel a specific order.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/orders/3/cancel

            **Example response**:

            .. sourcecode:: javascript

                {
                    "cancelled": True
                }
        """
        market_community = self.get_market_community()
        order_number = request.match_info['order_number']
        order_id = OrderId(TraderId(market_community.mid), OrderNumber(int(order_number)))
        order = market_community.order_manager.order_repository.find_by_id(order_id)

        if not order:
            return Response({"error": "order not found"}, status=HTTP_NOT_FOUND)

        if order.status != "open" and order.status != "unverified":
            return Response({"error": "only open and unverified orders can be cancelled"}, status=HTTP_BAD_REQUEST)

        await market_community.cancel_order(order_id)
        return Response({"cancelled": True})
