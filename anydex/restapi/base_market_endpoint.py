from ipv8.REST.base_endpoint import BaseEndpoint

from anydex.core.community import MarketCommunity


class BaseMarketEndpoint(BaseEndpoint):
    """
    This class can be used as a base class for all Market community endpoints.
    """

    def get_market_community(self):
        for overlay in self.session.overlays:
            if isinstance(overlay, MarketCommunity):
                return overlay

        raise RuntimeError("Market community not found!")
