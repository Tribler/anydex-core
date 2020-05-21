from anydex.wallet.abstract_bitcoinlib_wallet import ConcreteBitcoinlibWallet, TestnetBitcoinlibWallet


class BitcoinWallet(ConcreteBitcoinlibWallet):
    """
    This class is responsible for handling your bitcoin wallet.
    """
    def __init__(self, wallet_dir):
        super(BitcoinWallet, self).__init__(wallet_dir, network='bitcoin')


class BitcoinTestnetWallet(TestnetBitcoinlibWallet):
    """
    This wallet represents testnet Bitcoin.
    """
    def __init__(self, wallet_dir):
        super(BitcoinTestnetWallet, self).__init__(wallet_dir, network='testnet')


class LitecoinWallet(ConcreteBitcoinlibWallet):
    """
    This class is responsible for handling your Litecoin wallet.
    """
    def __init__(self, wallet_dir):
        super(LitecoinWallet, self).__init__(wallet_dir, network='litecoin')


class LitecoinTestnetWallet(TestnetBitcoinlibWallet):
    """
    This wallet represents testnet Litecoin.
    """
    def __init__(self, wallet_dir):
        super(LitecoinTestnetWallet, self).__init__(wallet_dir, network='litecoin_testnet')


class DashWallet(ConcreteBitcoinlibWallet):
    """
    This class is responsible for handling your Dash wallet.
    """
    def __init__(self, wallet_dir):
        super(DashWallet, self).__init__(wallet_dir, network='dash')


class DashTestnetWallet(TestnetBitcoinlibWallet):
    """
    This wallet represents testnet Dash.
    """
    def __init__(self, wallet_dir):
        super(DashTestnetWallet, self).__init__(wallet_dir, network='dash_testnet')
