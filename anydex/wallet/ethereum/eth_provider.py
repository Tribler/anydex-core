import abc
from datetime import datetime
from time import sleep

import requests
from web3 import Web3

from anydex.wallet.ethereum.eth_database import Transaction
from anydex.wallet.node.node import create_node, CannotCreateNodeException
from anydex.wallet.provider import NotSupportedOperationException
from anydex.wallet.provider import Provider
from anydex.wallet.provider import RequestLimit, Blocked, RateExceeded, RequestException, ConnectionException


class EthereumProvider(Provider, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_transaction_count(self, address):
        """
        Retrieve the number of transactions created by this address
        :param address: address from which to retrieve the transaction count
        :return: the number of sent transactions
        """
        return

    def estimate_gas(self):
        """
        Estimate the amount of gas needed for this transaction.
        :param tx: the transaction for which to estimate the gas
        :return: the estimated gas
        """
        return 21000  # just return the gas limit for simple transactions

    @abc.abstractmethod
    def get_gas_price(self):
        """
        Retrieve the current gas price
        :return: the current gas price
        """
        return

    @abc.abstractmethod
    def get_transactions(self, address, start_block=None, end_block=None):
        """
        Retrieve all the transactions associated with the given address

        Note: depending on the implementation start_block and end_block might not be needed.
        :param start_block: block to start searching from
        :param end_block: block where to stop searching
        :param address: The address of which to retrieve the transactions
        :return: A list of all transactions retrieved
        """
        return

    @abc.abstractmethod
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
        return

    @abc.abstractmethod
    def get_latest_blocknr(self):
        """
        Retrieve the latest block's number
        :return: latest block number
        """


class Web3Provider(EthereumProvider):
    """
    Wrapper around Web3. Used for directly connecting to nodes.
    TODO: check for failed requests.
    TODO: use filters
    (this is not suported by all nodes) to get transactions https://web3py.readthedocs.io/en/stable/filters.html
    """

    def _check_connection(self):
        """
        Check the connection to the node
        """
        if not self.w3.isConnected():
            raise ConnectionException(f"We were not able to establish a connection with the node")

    def __init__(self, url):
        self.w3 = Web3(Web3.HTTPProvider(url))
        self._check_connection()

    def get_transaction_count(self, address):
        self._check_connection()
        return self.w3.eth.getTransactionCount(address)

    # def estimate_gas(self, tx):
    #     self.check_connection()
    #     return self.w3.eth.estimateGas(tx)

    def get_gas_price(self):
        self._check_connection()
        return self.w3.eth.gasPrice

    def submit_transaction(self, raw_tx):
        self._check_connection()
        return self.w3.eth.sendRawTransaction(raw_tx)

    def get_balance(self, address):
        self._check_connection()
        return self.w3.eth.getBalance(address)

    def get_latest_blocknr(self):
        self._check_connection()
        return self.w3.eth.blockNumber

    def get_transactions(self, address, start_block, stop_block):
        raise NotSupportedOperationException()

    def get_transactions_received(self, address, start_block, stop_block):
        raise NotSupportedOperationException()


class EthereumBlockchairProvider(EthereumProvider):
    """
    wrapper around blockchair: https://blockchair.com/api/docs
    TODO: check for the rate limit and also check mempool for tx?
    """

    def __init__(self, base_url='https://api.blockchair.com/', network='ethereum'):
        self.base_url = f"{base_url}{network}"
        self.network = network

    def send_request(self, path, data=None, method='get'):
        """
        Makes a request to the specified path.

        This method was created to have one place where all calls to the requests library are made
        , to reduce the possibility of errors.

        :param path: the path after the base url
        :param data: Data that is send with the request. It is sent as url params if the method is get
        and in the body if the method is post
        :param method: The type of the request (get, post...)
        :return: the response object
        """
        response = None
        if not data:
            data = {}
        if method == 'get':
            response = requests.get(f'{self.base_url}{path}', data)
        elif method == 'post':
            response = requests.post(f'{self.base_url}{path}', data)
        else:
            raise RequestException(f'Unsupported method: {method} ')
        self._check_response(response)
        return response

    def get_balance(self, address):
        response = self.send_request(f"/dashboards/address/{address}")
        return int(response.json()["data"][address.lower()]["address"]["balance"])

    def get_transaction_count(self, address):
        # Todo: return also unconfirmed txs
        response = self.send_request(f"/dashboards/address/{address}")
        return response.json()["data"][address.lower()]["address"]["transaction_count"]

    # def estimate_gas(self, tx):
    #     # Todo estimate the gas better or just set to the max for smiple transactions (21000)
    #     response = self.send_request("/stats")
    #     return response.json()["data"]["median_simple_transaction_fee_24h"]

    def get_gas_price(self):
        response = self.send_request("/stats")
        return response.json()["data"]["mempool_median_gas_price"]

    def submit_transaction(self, raw_tx):
        response = self.send_request("/push/transactions", data={"data": raw_tx}, method="post")
        return response.json()["data"]["transaction_hash"]

    def get_transactions_received(self, address):
        response = self.send_request("/transactions", data={"q": f"recipient({address})"})
        response_mempool = self.send_request("/mempool/transactions", data={"q": f"recipient({address})"})
        txs = response.json()["data"] + response_mempool.json()["data"]
        return self._normalize_transactions(txs)

    def get_transactions(self, address):
        response = self.send_request(f'/dashboards/address/{address}')
        return int(response.json()['data'][address.lower()]['address']['balance'])

    def get_latest_blocknr(self):
        response = self.send_request('/stats')
        return response.json()['data']['best_block_height']

    def get_transaction_count(self, address):
        response = self.send_request(f'/dashboards/address/{address}')
        return response.json()['data'][address.lower()]['address']['transaction_count']

    # def estimate_gas(self, tx):
    #     # Todo estimate the gas better or just set to the max for smiple transactions (21000)
    #     response = self.send_request('/stats')
    #     return response.json()['data']['median_simple_transaction_fee_24h']

    def get_gas_price(self):
        response = self.send_request('/stats')
        return response.json()['data']['mempool_median_gas_price']

    def submit_transaction(self, raw_tx):
        response = self.send_request('/push/transactions', data={'data': raw_tx}, method='post')
        return response.json()['data']['transaction_hash']

    def get_transactions_received(self, address, start_block=None, end_block=None):
        response = self.send_request('/transactions', data={'q': f'recipient({address})'})
        response_mempool = self.send_request('/mempool/transactions', data={'q': f'recipient({address})'})
        txs = response.json()['data'] + response_mempool.json()['data']
        return self._normalize_transactions(txs)

    def get_transactions(self, address, start_block=None, end_block=None):
        sent = self.send_request('/transactions', data={'q': f'sender({address})'})
        sent_data = sent.json()['data']
        sent_mempool = self.send_request('/mempool/transactions', data={'q': f'sender({address})'})
        sent_mempool_data = sent_mempool.json()['data']
        txs = sent_data + sent_mempool_data
        return self._normalize_transactions(txs) + self.get_transactions_received(address)

    def _check_response(self, response):
        """
        Checks the response for errors, such as exceeding request limits.
        :param response: the response object
        """
        # status codes are described in : https://blockchair.com/api/docs
        # 402, 429 : if you exceed the request limit
        # 430, 434, 503 : if you have been blocked
        # 435: if 5 request/second are sent
        request_exceeded = [402, 429]
        blocked_codes = [430, 434, 503]
        if response.status_code in request_exceeded:
            raise RequestLimit(
                'The server indicated the request limit has been exceeded')
        if response.status_code in blocked_codes:
            raise Blocked('The server has blocked you')
        if response.status_code == 435:
            raise RateExceeded('You are sending requests too fast')
        if response.status_code != 200:
            raise RequestException(f'something went wrong, status code was : {response.status_code}')

    def _normalize_transactions(self, txs):
        """
        Turns a list of txs from blockchair into the tx format of the wallet.
        :param txs: Txs from blockchair
        :return: list of Transaction objects
        """
        normalized_txs = []
        for tx in txs:
            normalized_txs.append(self._normalize_transaction(tx))
        return normalized_txs

    def _normalize_transaction(self, tx) -> Transaction:
        """
        Turns the tx from blockchair into the tx format of the wallet.
        :param tx: Tx from blockchair
        :return: Transaction object
        """

        return Transaction(
            block_number=tx['block_id'],
            hash=tx['hash'],
            date_time=datetime.fromisoformat(tx['time']),
            to=tx['recipient'],
            from_=tx['sender'],
            value=tx['value'],
            gas_price=tx['gas_price'],
            gas=tx['gas_used'],
            nonce=tx['nonce'],
            is_pending=tx['block_id'] is None
        )


class EthereumBlockcypherProvider(EthereumProvider):
    """
    Wrapper around blockcypher
    """

    def __init__(self, api_url='https://api.blockcypher.com/'):
        self.base_url = f'{api_url}v1/eth/main/'

    def send_request(self, path, data=None, method="get"):
        """
        Makes a request to the specified path.

        This method was created to have one place where all calls to the requests library are made
        , to reduce the possibility of errors.

        :param path: the path after the base url
        :param data: Data that is send with the request. It is sent as url params if the method is get
        and in the body if the method is post
        :param method: The type of the request (get, post...)
        :return: the response object
        """
        if not data:
            data = {}
        response = None
        if method == 'get':
            response = requests.get(f'{self.base_url}{path}', data)
        elif method == 'post':
            response = requests.post(f'{self.base_url}{path}', data)
        else:
            raise RequestException(f'Unsupported method: {method} ')
        self._check_response(response)
        return response

    def get_latest_blocknr(self):
        response = self.send_request('')
        return response.json()['height']

    def get_transaction_count(self, address):
        response = self.send_request(f'addrs/{address}/balance')
        return response.json()['final_n_tx']

    # def estimate_gas(self, tx):
    #     pass

    def get_gas_price(self):
        response = self.send_request('')
        return response.json()['medium_gas_price']

    def get_balance(self, address):
        response = self.send_request(f'addrs/{address[2:]}/balance')  # they expect the addres without 0x
        return response.json()['balance']

    def get_transactions(self, address, start_block=None, end_block=None):
        raise NotSupportedOperationException()

    def get_transactions_received(self, address, start_block=None, end_block=None):
        raise NotSupportedOperationException()

    def submit_transaction(self, tx):
        raise NotSupportedOperationException()

    def _check_response(self, response):
        """
        Checks the response for errors, such as exceeding request limits.
        :param response: the response object
        """
        # 429 request limit : 3/sec 200/h
        if response.status_code == 429:
            raise RateExceeded(
                'The server indicated the rate limit has been reached')
        if response.status_code != 200:
            raise RequestException(f'something went wrong, status code was : {response.status_code}')


class EtherscanProvider(EthereumProvider):
    """
    Wrapper around the etherscan api.
    The testnet available through etherscan is the ropsten testnet.
    """

    def __init__(self, network='ethereum'):
        if network == 'testnet':
            self.base_url = 'https://api-ropsten.etherscan.io/api'
        elif network == 'ethereum':
            self.base_url = 'https://api.etherscan.io/api'
        else:
            raise ValueError(f'expected ethereum or testnet but got : {network}')
        self.network = network

    def _send_request(self, data=None, method='get'):
        """
       Makes a request to the specified path.

       This method was created to have one place where all calls to the requests library are made
       , to reduce the possibility of errors.

       :param path: the path after the base url
       :param data: Data that is send with the request. It is sent as url params if the method is get
       and in the body if the method is post
       :param method: The type of the request (get, post...)
       :return: the response object
        """
        headers = {
            'User-Agent': 'Anydex'
        }
        if not data:
            data = {}
        response = None
        if method == 'get':
            response = requests.get(self.base_url, data=data, headers=headers)
        elif method == 'post':
            response = requests.post(self.base_url, data=data, headers=headers)
        else:
            raise ValueError(f'expected get or post but got: {method}')
        self._check_response(response)
        return response

    def get_transaction_count(self, address):
        data = {
            'module': 'proxy',
            'action': 'eth_getTransactionCount',
            'address': address
        }
        response = self._send_request(data=data)
        return int(response.json()['result'], 16)

    def get_gas_price(self):
        data = {
            'module': 'gastracker',
            'action': 'gasoracle'
        }
        response = self._send_request(data=data)
        result = response.json()['result']
        propose_gas_price = int(result['ProposeGasPrice'])
        return propose_gas_price

    def get_transactions(self, address, start_block=None, end_block=None):
        # does not include pending transactions
        data = {
            'module': 'account',
            'action': 'txlist',
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

    def get_transactions_received(self, address, start_block=None, end_block=None):
        raise NotSupportedOperationException()

    def get_latest_blocknr(self):
        data = {
            'module': 'proxy',
            'action': 'eth_blockNumber',
        }
        response = self._send_request(data=data)
        return int(response.json()['result'], 16)

    def submit_transaction(self, tx):
        data = {
            'module': 'proxy',
            'action': 'eth_sendRawTransaction',
            'hex': tx
        }
        response = self._send_request(data=data, method='post')
        return response.json()['result']

    def get_balance(self, address):
        data = {
            'module': 'account',
            'action': 'balance',
            'address': address,
            'tag': 'latest'
        }
        response = self._send_request(data=data)
        return int(response.json()['result'])

    def _normalize_transactions(self, txs):
        """"
        Turns a list of txs from etherscan into the tx format of the wallet.
        :param txs: Txs from etherscan
        :return: list of Transaction objects
        """
        normalized_txs = []
        for tx in txs:
            normalized_txs.append(self._normalize_transaction(tx))
        return normalized_txs

    def _normalize_transaction(self, tx) -> Transaction:
        """
        Turns the tx from etherscan into the tx format of the wallet.
        :param tx: Tx from etherscan
        :return: Transaction object
        """

        return Transaction(
            block_number=tx['blockNumber'],
            hash=tx['hash'],
            date_time=datetime.utcfromtimestamp(int(tx['timeStamp'])),
            to=tx['to'],
            from_=tx['from'],
            value=tx['value'],
            gas_price=tx['gasPrice'],
            gas=tx['gasUsed'],
            nonce=tx['nonce'],
            is_pending=False  # etherscan transactions are allways confirmed

        )

    def _check_response(self, response):
        """
        Check the respsonse for errors
        :param response: response object
        """
        if response.status_code != 200:
            raise RequestException(f'something went wrong, status code was : {response.status_code}')

        try:  # etherscan might not always return the "status"
            if response.json()['status'] == '0' and response.json()['message'].startswith('NOTOK'):
                raise RequestException(f'something went wrong, message was : {response.json()["message"]}')
        except KeyError:
            pass


class AutoEthereumProvider(EthereumProvider):
    """"
    This class chooses the provider to use to make the request.
    If one provider does not work, then it tries another one.
    """

    def __init__(self):
        try:
            node = create_node('ethereum')
            address = f'{node.host}:{node.port}' if node.port else node.host
            web3 = Web3Provider(address)
        except (ConnectionException, CannotCreateNodeException):
            web3 = None

        blockchair = EthereumBlockchairProvider()
        blockcypher = EthereumBlockcypherProvider()
        etherscan = EtherscanProvider()
        self.providers = {
            'get_transaction_count': [web3, etherscan, blockcypher, blockchair],
            'get_gas_price': [web3, etherscan, blockcypher, blockchair],
            'get_transactions': [blockchair, etherscan],
            'get_transactions_received': [blockchair],
            'get_latest_blocknr': [web3, blockcypher, etherscan, blockchair],
            'submit_transaction': [web3, etherscan, blockchair],
            'get_balance': [web3, etherscan, blockcypher, blockchair]
        }

    def _make_request(self, fun, *args, **kwargs):
        """
        Try to use one of the provider to make the request.
        :param fun: request to make
        :param args: request params
        :param retry: amount of times to retry
        :return: the request response
        Todo: implement mechanism to ignore certain providers when we have been blocked by them
        """
        providers = self.providers[fun]
        if not providers:
            raise NotSupportedOperationException(f'this operation is not supported: {fun}')
        for provider in providers:
            if provider:
                try:
                    return provider.__getattribute__(fun)(*args)
                except (RequestException, NotSupportedOperationException):
                    pass
        retry = kwargs.pop('retry', 1)
        if retry > 0:
            sleep(0.2)
            return self._make_request(fun, *args, retry=retry - 1)
        raise RequestException(f'something went wrong, request : {fun}')

    def get_transaction_count(self, address):
        return self._make_request('get_transaction_count', address)

    def get_gas_price(self):
        return self._make_request('get_gas_price')

    def get_transactions(self, address, start_block=None, end_block=None):
        return self._make_request('get_transactions', address, start_block, end_block)

    def get_transactions_received(self, address, start_block=None, end_block=None):
        return self._make_request('get_transactions_received', address, start_block, end_block)

    def get_latest_blocknr(self):
        return self._make_request('get_latest_blocknr')

    def submit_transaction(self, tx):
        return self._make_request('submit_transaction', tx)

    def get_balance(self, address):
        return self._make_request('get_balance', address)


class AutoTestnetEthereumProvider(AutoEthereumProvider):
    """
        This class chooses the provider to use to make the request.
        If one provider does not work, then it tries another one.
        Note: the ropsten testnet is used.
    """

    def __init__(self):
        # try:
        #     node = create_node(Cryptocurrency.ETHEREUM)
        #     address = f"{node.host}:{node.port}" if node.port else node.host
        #     web3 = Web3Provider(address)
        # except (ConnectionException, CannotCreateNodeException):
        #     web3 = None

        # blockchair = EthereumBlockchairProvider()
        # blockcypher = EthereumBlockcypherProvider(network="testnet")
        web3 = Web3Provider('https://ropsten-rpc.linkpool.io/')  # Todo fix config so we don't have to hardcode this.
        etherscan = EtherscanProvider('testnet')
        self.providers = {
            'get_transaction_count': [web3, etherscan],
            'get_gas_price': [web3, etherscan],
            'get_transactions': [etherscan],
            'get_transactions_received': [],
            'get_latest_blocknr': [web3, etherscan],
            'submit_transaction': [web3, etherscan],
            'get_balance': [web3, etherscan]
        }
