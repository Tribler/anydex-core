from __future__ import absolute_import

import util.json_util as json
from core import VERSION
from restapi.base_market_endpoint import BaseMarketEndpoint


class StateEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding the state of the dex.
    """

    def render_GET(self, request):
        return json.twisted_dumps({"version": VERSION})
