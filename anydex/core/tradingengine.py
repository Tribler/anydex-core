class TradingEngine(object):
    """
    This class implements the trading engine which interacts with the order matching/negotiation middleware.
    It will be invoked when a trade has been negotiated between two parties.
    """

    def __init__(self, matching_community=None):
        self.pending_trades = []
        self.completed_trades = []
        self.matching_community = matching_community

    def trade(self, trade):
        raise NotImplementedError()
