from aiohttp import web

from ipv8.REST.base_endpoint import HTTP_BAD_REQUEST, Response

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class BaseAsksBidsEndpoint(BaseMarketEndpoint):
    """
    This class acts as the base class for the asks/bids endpoint.
    """

    @staticmethod
    def create_ask_bid_from_params(parameters):
        """
        Create an ask/bid from the provided parameters in a request. This method returns a tuple with the price,
        quantity and timeout of the ask/bid.
        """
        timeout = int(parameters.get('timeout', 3600))

        first_asset_amount = int(parameters['first_asset_amount'])
        second_asset_amount = int(parameters['second_asset_amount'])

        first_asset_type = parameters['first_asset_type']
        second_asset_type = parameters['second_asset_type']

        return AssetPair(AssetAmount(first_asset_amount, first_asset_type),
                         AssetAmount(second_asset_amount, second_asset_type)), timeout


class AsksEndpoint(BaseAsksBidsEndpoint):
    """
    This class handles requests regarding asks in the market community.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_asks),
                             web.put('', self.create_ask)])

    async def get_asks(self, request):
        """
        .. http:get:: /market/asks

        A GET request to this endpoint will return all ask ticks in the order book of the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/asks

            **Example response**:

            .. sourcecode:: javascript

                {
                    "asks": [{
                        "asset1": "BTC",
                        "asset2": "MB",
                        "ticks": [{
                            "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                            "timeout": 3600,
                            "assets": {
                                "first": {
                                    "amount": 10,
                                    "type": "BTC"
                                },
                                "second": {
                                    "amount": 10,
                                    "type": "MB"
                                }
                            },
                            "traded": 5,
                            "timestamp": 1493905920.68573,
                            "order_number": 1}, ...]
                    }, ...]
                }
        """
        return Response({"asks": self.get_market_community().order_book.asks.get_list_representation()})

    async def create_ask(self, request):
        """
        .. http:put:: /market/asks

        A request to this endpoint will create a new ask order.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/market/asks --data
                "first_asset_amount=10&second_asset_amount=10&first_asset_type=BTC&second_asset_type=MB"

            **Example response**:

            .. sourcecode:: javascript

                {
                     "timestamp": 1547587907.887339,
                     "order_number": 12,
                     "assets": {
                        "second": {
                            "amount": 1000,
                            "type": "MB"
                        },
                        "first": {
                            "amount": 100000,
                            "type": "BTC"
                        }
                    },
                    "timeout": 3600,
                    "trader_id": "9695c9e15201d08586e4230f4a8524799ebcb2d7"
                }
        """
        parameters = await request.post()

        if 'first_asset_amount' not in parameters or 'second_asset_amount' not in parameters:
            return Response({"error": "asset amount parameter missing"}, status=HTTP_BAD_REQUEST)

        if 'first_asset_type' not in parameters or 'second_asset_type' not in parameters:
            return Response({"error": "asset type parameter missing"}, status=HTTP_BAD_REQUEST)

        ask = await self.get_market_community().create_ask(*BaseAsksBidsEndpoint.create_ask_bid_from_params(parameters))
        return Response({
                'assets': ask.assets.to_dictionary(),
                'timestamp': int(ask.timestamp),
                'trader_id': ask.order_id.trader_id.as_hex(),
                'order_number': int(ask.order_id.order_number),
                'timeout': int(ask.timeout)
        })


class BidsEndpoint(BaseAsksBidsEndpoint):
    """
    This class handles requests regarding bids in the market community.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_bids),
                             web.put('', self.create_bid)])

    async def get_bids(self, request):
        """
        .. http:get:: /market/bids

        A GET request to this endpoint will return all bid ticks in the order book of the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/bids

            **Example response**:

            .. sourcecode:: javascript

                {
                    "bids": [{
                        "asset1": "BTC",
                        "asset2": "MB",
                        "ticks": [{
                            "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                            "timeout": 3600,
                            "assets": {
                                "first": {
                                    "amount": 10,
                                    "type": "BTC"
                                },
                                "second": {
                                    "amount": 10,
                                    "type": "MB"
                                }
                            },
                            "traded": 5,
                            "timestamp": 1493905920.68573,
                            "order_number": 1}, ...]
                    }, ...]
                }
        """
        return Response({"bids": self.get_market_community().order_book.bids.get_list_representation()})

    async def create_bid(self, request):
        """
        .. http:put:: /market/bids

        A request to this endpoint will create a new bid order.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/market/bids --data
                "first_asset_amount=10&second_asset_amount=10&first_asset_type=BTC&second_asset_type=MB"

            **Example response**:

            .. sourcecode:: javascript

                {
                     "timestamp": 1547587907.887339,
                     "order_number": 12,
                     "assets": {
                        "second": {
                            "amount": 1000,
                            "type": "MB"
                        },
                        "first": {
                            "amount": 100000,
                            "type": "BTC"
                        }
                    },
                    "timeout": 3600,
                    "trader_id": "9695c9e15201d08586e4230f4a8524799ebcb2d7"
                }
        """
        parameters = await request.post()

        if 'first_asset_amount' not in parameters or 'second_asset_amount' not in parameters:
            return Response({"error": "asset amount parameter missing"}, status=HTTP_BAD_REQUEST)

        if 'first_asset_type' not in parameters or 'second_asset_type' not in parameters:
            return Response({"error": "asset type parameter missing"}, status=HTTP_BAD_REQUEST)

        bid = await self.get_market_community().create_bid(*BaseAsksBidsEndpoint.create_ask_bid_from_params(parameters))
        return Response({
                'assets': bid.assets.to_dictionary(),
                'timestamp': int(bid.timestamp),
                'trader_id': bid.order_id.trader_id.as_hex(),
                'order_number': int(bid.order_id.order_number),
                'timeout': int(bid.timeout)
        })
