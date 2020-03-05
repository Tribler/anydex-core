# Sync policies
SYNC_POLICY_NONE = 0
SYNC_POLICY_NEIGHBOURS = 1

# Dissemination policies
DISSEMINATION_POLICY_NEIGHBOURS = 0
DISSEMINATION_POLICY_RANDOM = 1


class MatchingSettings(object):
    """
    Object that defines various settings for the matching behaviour.
    """
    def __init__(self):
        self.ttl = 1
        self.fanout = 20
        self.match_window = 0  # How much time we wait before accepting a specific match
        self.match_send_interval = 0  # How long we should wait with sending a match message (to avoid overloading a peer)
        self.sync_interval = 30  # Synchronization interval
        self.num_order_sync = 10  # How many orders to sync at most
        self.first_matches_own_orders = False

        self.sync_policy = SYNC_POLICY_NONE
        self.dissemination_policy = DISSEMINATION_POLICY_NEIGHBOURS
