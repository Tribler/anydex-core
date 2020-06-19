import abc
from datetime import datetime

import stellar_sdk
from stellar_sdk import Server
from stellar_sdk.exceptions import NotFoundError

from anydex.wallet.provider import ConnectionException, RequestException
from anydex.wallet.provider import Provider
from anydex.wallet.stellar.xlm_database import Transaction


class StellarProvider(Provider, metaclass=abc.ABCMeta):
    """
    Abstract class defining all method a stellar provider needs to have
    """

    @abc.abstractmethod
    def get_ledger_height(self):
        """
        Get the latest ledger nr.

        :return: latest ledger nr.
        """

    @abc.abstractmethod
    def get_base_fee(self):
        """
        Get the base fee of the stellar network.

        :return: base fee
        """

    @abc.abstractmethod
    def get_account_sequence(self, address):
        """
        Get the sequence number of an address

        :param address: address to get the sequence number of
        :return: sequence number
        """

    @abc.abstractmethod
    def submit_transaction(self, tx):
        """
        submit a transaction to the stellar netowrk.

        :param tx: base64 xdr encoded transactions
        :return: the transactin hash
        """

    @abc.abstractmethod
    def check_account_created(self, address) -> bool:
        """
        check if an account is created or not.

        :param address: address of account to check
        :return: true or false if account is created or not
        """


class HorizonProvider(StellarProvider):
    """
    Horizon is a software that allows you to query nodes via http.
    This should be the only thing we need since horizon also indexes the data it holds.
    """

    def __init__(self, horizon_url='https://horizon-testnet.stellar.org/'):
        self.server = Server(horizon_url=horizon_url)

    def _make_request(self, fun, *args, **kwargs):
        """
        Used to make the request to the horizon server.
        It will catch the library specific exceptions and raise the exceptions used in this project.
        :param fun: api call to make
        :param args: args for the api call
        :param kwargs: args for the api call
        :return: response form the api call
        """
        try:
            return fun(*args, **kwargs)
        except stellar_sdk.exceptions.ConnectionError:
            raise ConnectionException('Could not connect to the server')
        except stellar_sdk.exceptions.NotFoundError as e:
            # This exception is used by the check_account_created function
            if fun == self.server.load_account:
                raise e
            raise RequestException('Check the request params, the resource could not be found')
        except stellar_sdk.exceptions.BadRequestError as e:
            raise RequestException('Your request had an error')
        except stellar_sdk.exceptions.BadResponseError:
            raise RequestException('The server response had an error')

    def submit_transaction(self, tx):
        return self._make_request(self.server.submit_transaction, tx)['hash']

    def get_balance(self, address):
        # We only care about the native token right now.
        return self._make_request(self.server.accounts().account_id(address).call)['balances'][0]['balance']

    def get_transactions(self, address):
        response = self._make_request(
            self.server.transactions().for_account(address).limit(200).include_failed(True).call)
        transactions = response['_embedded']['records']
        return self._normalize_transactions(transactions)

    def _normalize_transactions(self, transactions):
        """
        Transform a list of Transactions from the api into the format used in this project
        :param transactions: List of transactions from the api
        :return: A list of Transaction objects
        """
        transactions_to_return = []
        for tx in transactions:
            transactions_to_return.append(self._normalize_transaction(tx))
        return transactions_to_return

    def _normalize_transaction(self, tx) -> Transaction:
        """
        Transform a transaction from the api into a transaction object this project uses.
        :param tx: transaction from api
        :return: Transaction object
        """
        max_time_bound_string = tx.get('valid_before')
        # the date we get from the api ends with z to indicate utc we have to remove this to parse it
        max_time_bound = None if max_time_bound_string is None else datetime.fromisoformat(max_time_bound_string[:-1])
        min_time_bound_string = tx.get('valid_after')
        min_time_bound = None if min_time_bound_string is None else datetime.fromisoformat(min_time_bound_string[:-1])
        return Transaction(
            hash=tx['hash'],
            date_time=datetime.fromisoformat(tx['created_at'][:-1]),
            fee=int(tx['fee_charged']),
            operation_count=tx['operation_count'],
            source_account=tx['source_account'],
            succeeded=tx['successful'],
            sequence_number=tx['source_account_sequence'],
            transaction_envelope=tx['envelope_xdr'],
            ledger_nr=tx['ledger'],
            min_time_bound=min_time_bound,
            max_time_bound=max_time_bound
        )

    def get_base_fee(self):
        return self._make_request(self.server.fetch_base_fee)

    def get_ledger_height(self):
        response = self._make_request(self.server.ledgers().limit(1).order().call)
        return response['_embedded']['records'][0]['sequence']

    def get_account_sequence(self, address):
        return int(self._make_request(self.server.accounts().account_id(address).call)["sequence"])

    def check_account_created(self, address) -> bool:
        try:
            self._make_request(self.server.load_account, address)
        except NotFoundError:
            return False
        return True
