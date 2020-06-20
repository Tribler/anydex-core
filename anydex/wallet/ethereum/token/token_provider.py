from anydex.wallet.ethereum.eth_provider import EtherscanProvider, AutoTestnetEthereumProvider, \
    EthereumProvider, AutoEthereumProvider


class TokenProvider(EthereumProvider):

    def __init__(self, contract_address, abi, testnet=False):
        """
        Instantiate TokenProvider attributes.

        :param contract_address: main token contract address
        """
        self.abi = abi  # read in default ERC20 Application Binary Interface
        self._eth_provider = AutoTestnetEthereumProvider() if testnet else AutoEthereumProvider()
        self.w3 = self._eth_provider.web3.w3
        self.contract = self.w3.eth.contract(self.w3.toChecksumAddress(contract_address), abi=self.abi)
        self._etherscan_provider = TokenEtherscanProvider(self.contract, testnet)

    def get_transaction_count(self, address):
        """
        Retrieve the number of transactions created by this address.
        :param address: address from which to retrieve the transaction count
        :return: the number of sent transactions
        """
        return self._eth_provider.get_transaction_count(address)

    def estimate_gas(self):
        """
        Estimate the amount of gas needed for this transaction.
        :return: the estimated gas
        """
        return 50000  # should be enough for token transfers

    def get_gas_price(self):
        """
        Retrieve the current gas price.
        :return: the current gas price
        """
        return self._eth_provider.get_gas_price()

    def get_transactions(self, address, start_block=None, end_block=None):
        """
        Retrieve all the transactions associated with the given address.
        Etherscan Provider is used instead of the AutoEthereumProvider due to its additional `input` field.
        This `input` field can be decoded into destination address and token transfer amount.

        Note: depending on the implementation start_block and end_block might not be needed.
        :param start_block: block to start searching from
        :param end_block: block where to stop searching
        :param address: The address of which to retrieve the transactions
        :return: A list of all transactions retrieved
        """
        return self._etherscan_provider.get_transactions(address, start_block, end_block)

    def get_transactions_received(self, address, start_block=None, end_block=None):
        """
        returns the transactions where you are the recipient.

        In most cases this method will be enough since we should persist transactions when we sent them.
        Note: depending on the implementation start_block and end_block might not be needed.
        :param start_block: block to start searching
        :param end_block: block where to stop searching
        :param address: The address of which to retrieve the transactions
        :return: A list of all transactions retrieved
        """
        return self._eth_provider.get_transactions_received(address, start_block, end_block)

    def get_latest_blocknr(self):
        """
        Retrieve the latest block's number.
        :return: latest block number
        """
        return self._eth_provider.get_latest_blocknr()

    def submit_transaction(self, tx):
        """
        Provide signed transaction for submission to network.

        :param tx: signed transcation (using `w3.eth.account.signTransaction()`)
        """
        tx_hash = self._eth_provider.submit_transaction(tx)
        return tx_hash

    def get_balance(self, address):
        """
        Get balance of given address.
        Divide raw balance by precision count.

        :param address: str representation of an address
        :return: balance
        """
        return self.contract.functions.balanceOf(address).call()

    def get_contract_address(self):
        """
        Get main token address.
        :return: str representation of main token address
        """
        return self.contract.address

    def get_precision(self):
        """
        Get precision in decimal places of token contract.
        :return: precision in int
        """
        return self.contract.functionas.decimals.call()

    def get_raw_total_supply(self):
        """
        Get raw total supply of token contract.
        :return: integer representation of total supply
        """
        return self.contract.functions.totalSupply().call()

    def get_contract_name(self):
        """
        Get name of contract.

        :return: str name
        """
        return self.contract.functions.name().call()

    def get_contract_symbol(self):
        """
        Get token contract symbol.

        :return: str symbol
        """
        return self.contract.functions.symbol().call()


class TokenEtherscanProvider(EtherscanProvider):
    """
    EtherscanProvider returns transaction metadata with a value parameter.
    This value parameter by default refers to the amount of Ether being transferred.

    Additional decoding needs to take place to instead retrieve the token transfer amount.
    This class overrides the `_normalize_transaction` method called in `get_transactions` method.
    Included is an additional decoding step.
    """

    def __init__(self, contract, testnet=False):
        """
        Pass additional contract parameter to allow for input decoding.

        :param contract: passed from __init__ in TokenProvider
        """
        network = 'testnet' if testnet else 'ethereum'
        super().__init__(network)
        self.contract = contract

    def get_transactions(self, address, start_block=None, end_block=None):
        # does not include pending transactions
        data = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': self.contract.address,
            'address': address,
            'sort': 'desc'
        }
        if start_block and end_block:
            data['startblock'] = start_block
            data['endblock'] = end_block
        response = self._send_request(data=data)
        result = response.json()['result']
        # normalize transactions
        return self._normalize_transactions(result)
