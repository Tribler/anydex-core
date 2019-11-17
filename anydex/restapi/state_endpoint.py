from aiohttp import web

from ipv8.REST.base_endpoint import Response

from anydex.core import VERSION
from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class StateEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding the state of the dex.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_state)])

    async def get_state(self, request):
        return Response({"version": VERSION})
