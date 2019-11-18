import logging

from aiohttp import web

from ipv8.REST.base_endpoint import BaseEndpoint, HTTP_INTERNAL_SERVER_ERROR, Response
from ipv8.REST.root_endpoint import RootEndpoint as IPv8RootEndpoint

from anydex.restapi.asks_bids_endpoint import AsksEndpoint, BidsEndpoint
from anydex.restapi.matchmakers_endpoint import MatchmakersEndpoint
from anydex.restapi.orders_endpoint import OrdersEndpoint
from anydex.restapi.state_endpoint import StateEndpoint
from anydex.restapi.transactions_endpoint import TransactionsEndpoint
from anydex.restapi.wallets_endpoint import WalletsEndpoint


@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
    except Exception as e:
        return Response({"error": {
            "handled": False,
            "code": e.__class__.__name__,
            "message": str(e)
        }}, status=getattr(e, 'status', HTTP_INTERNAL_SERVER_ERROR))
    return response


class RootEndpoint(BaseEndpoint):
    """
    The root endpoint of the HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """

    def __init__(self, enable_ipv8_endpoints=True):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app = web.Application(middlewares=[error_middleware])
        self.session = None
        self.endpoints = {}
        self.setup_routes()

        self.ipv8_endpoint = None
        if enable_ipv8_endpoints:
            self.ipv8_endpoint = IPv8RootEndpoint()
            self.add_endpoint('/ipv8', self.ipv8_endpoint)

    def setup_routes(self):
        endpoints = {'/asks': AsksEndpoint,
                     '/bids': BidsEndpoint,
                     '/transactions': TransactionsEndpoint,
                     '/orders': OrdersEndpoint,
                     '/matchmakers': MatchmakersEndpoint,
                     '/state': StateEndpoint,
                     '/wallets': WalletsEndpoint}
        for path, ep_cls in endpoints.items():
            self.add_endpoint(path, ep_cls())
