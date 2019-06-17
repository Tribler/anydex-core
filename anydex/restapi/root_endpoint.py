from __future__ import absolute_import

from ipv8.REST.base_endpoint import BaseEndpoint
from ipv8.REST.root_endpoint import RootEndpoint as IPv8RootEndpoint

from anydex.restapi.asks_bids_endpoint import AsksEndpoint, BidsEndpoint
from anydex.restapi.matchmakers_endpoint import MatchmakersEndpoint
from anydex.restapi.orders_endpoint import OrdersEndpoint
from anydex.restapi.state_endpoint import StateEndpoint
from anydex.restapi.transactions_endpoint import TransactionsEndpoint
from anydex.restapi.wallets_endpoint import WalletsEndpoint


class RootEndpoint(BaseEndpoint):
    """
    The root endpoint of the HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """

    def __init__(self, session, enable_ipv8_endpoints=True):
        """
        During the initialization of the REST API, we only start the event sockets and the state endpoint.
        We enable the other endpoints after completing the starting procedure.
        """
        super(RootEndpoint, self).__init__()
        self.session = session

        child_handler_dict = {
            b"asks": AsksEndpoint,
            b"bids": BidsEndpoint,
            b"transactions": TransactionsEndpoint,
            b"orders": OrdersEndpoint,
            b"matchmakers": MatchmakersEndpoint,
            b"state": StateEndpoint,
            b"wallets": WalletsEndpoint
        }

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(self.session))

        if enable_ipv8_endpoints:
            self.putChild(b"ipv8", IPv8RootEndpoint(self.session))
