from aiohttp import web

from ipv8.REST.base_endpoint import Response

from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class MatchmakersEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding your known matchmakers in the market community.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_matchmakers)])

    async def get_matchmakers(self, request):
        """
        .. http:get:: /market/matchmakers

        A GET request to this endpoint will return all known matchmakers.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/matchmakers

            **Example response**:

            .. sourcecode:: javascript

                {
                    "matchmakers": [{
                        "ip": "131.249.48.3",
                        "port": 7008
                    }]
                }
        """
        matchmakers = self.get_market_community().matchmakers
        matchmakers_json = [{"ip": mm.address[0], "port": mm.address[1]} for mm in matchmakers]
        return Response({"matchmakers": matchmakers_json})
