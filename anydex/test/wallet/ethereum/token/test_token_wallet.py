import pathlib

from anydex.test.wallet.ethereum.test_eth_wallet import TestEthereumWallet
from anydex.wallet.ethereum.token.token_wallet import TokenWallet, TokenTestnetWallet
from .abi import abi as python_abi

token = {'identifier': 'TLINK',
         'name': 'Testnet ChainLink Token',
         'precision': 18,
         'contract_address': '0x20fE562d797A42Dcb3399062AE9546cd06f63280'}


class TestTokenWallet(TestEthereumWallet):
    def setUp(self):
        super().setUp()
        self.wallet = self.new_wallet()
        self.identifier = 'TW'
        self.name = 'token wallet'

    def new_wallet(self):
        return TokenWallet('0x20fE562d797A42Dcb3399062AE9546cd06f63280', 'TW', 'token wallet', 18, True,
                           self.session_base_dir)  # trick wallet to not use default provider

    def test_abi_from_json_default(self):
        """
        Test for abi_from_json with the default path
        """
        abi = TokenWallet.abi_from_json()
        self.assertEqual(python_abi, abi)

    def test_abi_from_json_path(self):
        """
        Test for abi_from_json with a given path to file
        """
        path_to_file = pathlib.Path.joinpath(pathlib.Path(__file__).parent.absolute(), 'abi.json')
        abi = TokenWallet.abi_from_json(path_to_file)
        self.assertEqual(python_abi, abi)

    def test_from_dicts_dict(self):
        """
        Test for from_dicts with a dict as parameter
        """
        wallets = TokenWallet.from_dicts(token, self.session_base_dir)
        self.assertEqual(1, len(wallets))
        wallet = wallets[0]
        self.assertEqual('TLINK', wallet.get_identifier())
        self.assertEqual('Testnet ChainLink Token', wallet.get_name())
        self.assertEqual(18, wallet.precision())

    def test_from_dicts_dicts(self):
        """
        Test for from_dicts with a list as parameter
        """
        wallets = TokenWallet.from_dicts(token, self.session_base_dir)
        self.assertEqual(1, len(wallets))
        wallet = wallets[0]
        self.assertEqual('TLINK', wallet.get_identifier())
        self.assertEqual('Testnet ChainLink Token', wallet.get_name())
        self.assertEqual(18, wallet.precision())

    def test_from_dict(self):
        wallet = TokenWallet.from_dict(token, self.session_base_dir)
        self.assertEqual('TLINK', wallet.get_identifier())
        self.assertEqual('Testnet ChainLink Token', wallet.get_name())
        self.assertEqual(18, wallet.precision())

    def test_from_json_default(self):
        """
        Test for from_json with the default json file (tokens.json)
        """
        wallet = self.wallet.from_json(self.session_base_dir)[0]
        self.assertEqual('LINK', wallet.get_identifier())


class TestTestnetTokenWallet(TestTokenWallet):
    def new_wallet(self):
        return TokenTestnetWallet('0x20fE562d797A42Dcb3399062AE9546cd06f63280', 'TW', 'token wallet', 18, True,
                                  self.session_base_dir)  # trick wallet to not use default provider

    def test_from_json_default(self):
        """
        Test for from_json with the default json file (tokens_testnet.json)
        """
        wallet = self.wallet.from_json(self.session_base_dir)[0]
        self.assertEqual('TLINK', wallet.get_identifier())
