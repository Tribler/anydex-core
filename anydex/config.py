import copy

default = {
    'address': '0.0.0.0',
    'port': 8090,
    'keys': [
        {
            'alias': "main key",
            'generation': u"curve25519",
            'file': u"ec.pem"
        }
    ],
    'logger': {
        'level': "INFO"
    },
    'walker_interval': 0.5,
    'overlays': [
        {
            'class': 'DiscoveryCommunity',
            'key': "main key",
            'walkers': [
                {
                    'strategy': "RandomWalk",
                    'peers': 20,
                    'init': {
                        'timeout': 3.0
                    }
                },
                {
                    'strategy': "RandomChurn",
                    'peers': -1,
                    'init': {
                        'sample_size': 8,
                        'ping_interval': 10.0,
                        'inactive_time': 27.5,
                        'drop_time': 57.5
                    }
                },
                {
                    'strategy': "PeriodicSimilarity",
                    'peers': -1,
                    'init': {}
                }
            ],
            'initialize': {},
            'on_start': [
                ('resolve_dns_bootstrap_addresses', )
            ]
        },
        {
            'class': 'TrustChainCommunity',
            'key': "main key",
            'walkers': [{
                'strategy': "EdgeWalk",
                'peers': 20,
                'init': {
                    'edge_length': 4,
                    'neighborhood_size': 6,
                    'edge_timeout': 3.0
                }
            }],
            'initialize': {},
            'on_start': []
        },
        {
            'class': 'DHTDiscoveryCommunity',
            'key': "main key",
            'walkers': [{
                'strategy': "RandomWalk",
                'peers': 20,
                'init': {
                    'timeout': 3.0
                }
            }],
            'initialize': {},
            'on_start': []
        }
    ]
}


def get_anydex_configuration():
    return copy.deepcopy(default)


__all__ = ['get_anydex_configuration']
