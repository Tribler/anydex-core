import json
import pathlib

from web3 import Web3

from anydex.wallet.ethereum.eth_database import Transaction
from anydex.wallet.ethereum.eth_wallet import AbstractEthereumWallet
from anydex.wallet.ethereum.token.token_provider import TokenProvider
from anydex.wallet.wallet import InsufficientFunds


class AbstractTokenWallet(AbstractEthereumWallet):
    """
    Abstract Wallet for Ethereum Erc-20 Tokens.
    """

    def __init__(self, contract_address, identifier, name, decimals, provider: TokenProvider, db_folder, testnet):
        abi = self.abi_from_json()
        self.identifier = identifier
        self.name = name
        self.decimals = decimals
        self.contract_address = contract_address
        self.contract = Web3().eth.contract(Web3.toChecksumAddress(contract_address), abi=abi)
        self.provider = provider if provider else TokenProvider(contract_address, abi, testnet)
        chain_id = 3 if testnet else 1
        super().__init__(db_folder, testnet, chain_id, self.provider)

    @staticmethod
    def abi_from_json(path_to_file=None):
        """
        Read the abi from the json file

        :param path_to_file: path to abi json file
        :return: abi
        """
        if not path_to_file:
            path_to_file = pathlib.Path.joinpath(pathlib.Path(__file__).parent.absolute(), 'abi.json')
        with open(path_to_file) as abi_file:
            abi_json = json.loads(abi_file.read())
        return abi_json

    @classmethod
    def from_json(cls, db_folder, path_to_file=None):
        """
        Create Token wallets from a json file.

        :param db_folder: path to the database folder
        :param path_to_file: path to the json file uses default if none
        """
        if not path_to_file:
            file_name = 'tokens_testnet.json' if cls == TokenTestnetWallet else 'tokens.json'
            path_to_file = pathlib.Path.joinpath(pathlib.Path(__file__).parent.absolute(), file_name)
        with open(path_to_file) as tokens_file:
            tokens_dict = json.loads(tokens_file.read())
        return cls.from_dicts(tokens_dict, db_folder)

    @classmethod
    def from_dicts(cls, tokens, db_folder):
        """
        Create a list of new wallets from the given dicts.

        :param db_folder: folder enclosing the database file
        :param tokens: a list of dictionaries that contains the token info
        :return: list of created wallets
        """
        wallets = []
        if type(tokens) == dict:  # if it's only one dict and not a list
            return [cls.from_dict(tokens, db_folder)]
        for token in tokens:
            wallets.append(cls.from_dict(token, db_folder, ))
        return wallets

    @classmethod
    def from_dict(cls, token, db_folder):
        """
        Create a new wallet from the given dictionary

        The dict should have these keys:
             identifier: str
             name: str
             precision: int
             contract_address: str


        :param db_folder: folder enclosing the database file
        :param token: a dictionary that contains the token info
        :return: a new instance of this class
        """
        return cls(token['contract_address'], token['identifier'], token['name'], token['precision'], None, db_folder)

    def get_identifier(self):
        return self.identifier

    def get_name(self):
        return self.name

    async def transfer(self, amount, address):
        balance = await self.get_balance()
        if balance['available'] < int(amount):
            raise InsufficientFunds('Insufficient funds')

        self._logger.info('Creating Ethereum Token (%s) payment with amount %f to address %s', self.get_name(), amount,
                          address)
        tx = self.contract.functions.transfer(Web3.toChecksumAddress(address), amount).buildTransaction(
            {'gas': self.provider.estimate_gas(), 'gasPrice': self.provider.get_gas_price(),
             'chainId': self.chain_id})
        tx.update({'nonce': self.database.get_transaction_count(self.get_address().result())})
        s_tx = self.account.sign_transaction(tx)

        # add transaction to database
        self.database.add(
            Transaction(
                from_=self.get_address().result(),
                to=address,
                value=amount,
                gas=tx['gas'],
                nonce=tx['nonce'],
                gas_price=tx['gasPrice'],
                hash=s_tx['hash'].hex(),
                is_pending=True,
                token_identifier=self.get_identifier()
            )
        )

        return self.provider.submit_transaction(s_tx['rawTransaction'].hex())

    def min_unit(self):
        return 1

    def precision(self):
        return self.decimals


class TokenWallet(AbstractTokenWallet):
    """
    Erc-20 token wallet on the main net.
    """

    def __init__(self, contract_address, identifier, name, decimals, provider: TokenProvider, db_folder):
        super().__init__(contract_address, identifier, name, decimals, provider, db_folder, False)


class TokenTestnetWallet(AbstractTokenWallet):
    """
    Erc-20 token wallet on the test net.
    """

    def __init__(self, contract_address, identifier, name, decimals, provider: TokenProvider, db_folder):
        super().__init__(contract_address, identifier, name, decimals, provider, db_folder, True)
