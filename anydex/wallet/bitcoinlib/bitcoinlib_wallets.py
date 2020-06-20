import os
import time

from binascii import hexlify
from configparser import ConfigParser

from bitcoinlib.wallets import wallet_exists, HDWallet, WalletError, DbTransaction, DbTransactionInput
from bitcoinlib.transactions import Transaction
from ipv8.util import fail, succeed

from anydex.wallet.wallet import InsufficientFunds, Wallet


class UnsupportedNetwork(Exception):
    """
    Used for throwing exceptions when a wallet is initialised with an invalid network
    """
    def __init__(self, network):
        super(UnsupportedNetwork, self).__init__(f'Network {network} is not supported.')


SUPPORTED_NETWORKS = ['bitcoin', 'litecoin', 'dash', 'testnet', 'litecoin_testnet', 'dash_testnet']


class BitcoinlibWallet(Wallet):
    """
    Superclass used for the implementation of bitcoinlib wallets.
    """

    def __init__(self, wallet_dir, testnet, network, currency):
        if network not in SUPPORTED_NETWORKS:
            raise UnsupportedNetwork(network)

        super(BitcoinlibWallet, self).__init__()

        self.network = network
        self.wallet_name = f'tribler_{self.network}'
        self.testnet = testnet
        self.unlocked = True

        self.currency = currency
        self.wallet_dir = wallet_dir
        self.min_confirmations = 0
        self.wallet = None
        self.db_path = os.path.join(wallet_dir, 'wallets.sqlite')

        if wallet_exists(self.wallet_name, db_uri=self.db_path):
            self.wallet = HDWallet(self.wallet_name, db_uri=self.db_path)
            self.created = True

        self.lib_init()

    def cfg_init(self):
        """
        Adjusts the bitcoinlib configuration for the creation of a wallet.
        """
        config = ConfigParser()

        config['locations'] = {}
        locations = config['locations']
        locations['data_dir'] = self.wallet_dir.__str__()
        # locations['database_dir'] = 'database'
        # locations['default_databasefile'] = 'bitcoinlib.sqlite'
        # locations['default_databasefile_cache'] = 'bitcoinlib_cache.sqlite'
        locations['log_file'] = self.network + '_log.log'

        config['common'] = {}
        common = config['common']
        # common['allow_database_threads'] = 'True'
        # common['timeout_requests'] = '5'
        # common['default_language'] = 'english'
        common['default_network'] = self.network
        # common['default_witness_type'] = ''
        # common['service_caching_enabled'] = 'True'

        config['logs'] = {}
        logs = config['logs']
        logs['enable_bitcoinlib_logging'] = 'False'
        logs['loglevel'] = 'INFO'

        return config

    def lib_init(self):
        """
        Initializes bitcoinlib by creating a configuration file and
        setting the environmental variable.
        """
        cfg_name = 'bcl_config.ini'

        config = self.cfg_init()
        with open(cfg_name, 'w') as configfile:
            config.write(configfile)

        os.environ['BCL_CONFIG_FILE'] = os.path.abspath(cfg_name)

    def get_identifier(self):
        return self.currency

    def get_name(self):
        return self.network

    def create_wallet(self):
        if self.created:
            return fail(RuntimeError(f"{self.network} wallet with name {self.wallet_name} already exists."))

        self._logger.info("Creating wallet in %s", self.wallet_dir)
        try:
            self.wallet = HDWallet.create(self.wallet_name, network=self.network, db_uri=self.db_path)
            self.wallet.new_key('tribler_payments')
            self.wallet.new_key('tribler_change', change=1)
            self.created = True
        except WalletError as exc:
            self._logger.error("Cannot create %s wallet!", self.network)
            return fail(exc)
        return succeed(None)

    def get_balance(self):
        if not self.created:
            return succeed({
                "available": 0,
                "pending": 0,
                "currency": self.currency,
                "precision": self.precision()
            })

        self.wallet.utxos_update(networks=self.network)

        return succeed({
            "available": self.wallet.balance(network=self.network),
            "pending": 0,
            "currency": self.currency,
            "precision": self.precision()
        })

    async def transfer(self, amount, address):
        balance = await self.get_balance()

        if balance['available'] >= int(amount):
            self._logger.info("Creating %s payment with amount %d to address %s",
                              self.network, int(amount), address)
            tx = self.wallet.send_to(address, int(amount))
            return str(tx.hash)
        raise InsufficientFunds("Insufficient funds")

    def get_address(self):
        if not self.created:
            return succeed('')
        return succeed(self.wallet.keys(name='tribler_payments', is_active=False)[-1].address)

    def get_transactions(self):
        if not self.created:
            return succeed([])

        # Update all transactions
        self.wallet.transactions_update(network=self.network)

        # TODO: 'Access to a protected member _session of a class'
        txs = self.wallet._session.query(DbTransaction.raw, DbTransaction.confirmations,
                                         DbTransaction.date, DbTransaction.fee) \
            .filter(DbTransaction.wallet_id == self.wallet.wallet_id) \
            .all()
        transactions = []

        for db_result in txs:
            transaction = Transaction.import_raw(db_result[0], network=self.network)
            transaction.confirmations = db_result[1]
            transaction.date = db_result[2]
            transaction.fee = db_result[3]
            transactions.append(transaction)

        # Sort them based on locktime
        transactions.sort(key=lambda tx: tx.locktime, reverse=True)

        my_keys = [key.address for key in self.wallet.keys(network=self.network, is_active=False)]

        transactions_list = []
        for transaction in transactions:
            value = 0
            input_addresses = []
            output_addresses = []
            for tx_input in transaction.inputs:
                input_addresses.append(tx_input.address)
                if tx_input.address in my_keys:
                    # At this point, we do not have the value of the input so we should do a database query for it
                    db_res = self.wallet._session.query(DbTransactionInput.value).filter(
                        hexlify(tx_input.prev_hash) == DbTransactionInput.prev_hash,
                        tx_input.output_n_int == DbTransactionInput.output_n).all()
                    if db_res:
                        value -= db_res[0][0]  # TODO: db_res[0][0] not an int, but hash string (value/fee expected?)

            for tx_output in transaction.outputs:
                output_addresses.append(tx_output.address)
                if tx_output.address in my_keys:
                    value += tx_output.value

            transactions_list.append({
                'id': transaction.hash,
                'outgoing': value < 0,
                'from': ','.join(input_addresses),
                'to': ','.join(output_addresses),
                'amount': abs(value),
                'fee_amount': transaction.fee,
                'currency': self.currency,
                'timestamp': time.mktime(transaction.date.timetuple()),
                'description': f'Confirmations: {transaction.confirmations}'
            })

        return succeed(transactions_list)

    def min_unit(self):
        return 100000  # For LTC, BTC and DASH, the minimum trade should be 100.000 basic units (Satoshi, duffs)

    def precision(self):
        return 8       # The precision for LTC, BTC and DASH is the same.

    def is_testnet(self):
        return self.testnet


class BitcoinWallet(BitcoinlibWallet):
    """
    This class is responsible for handling your bitcoin wallet.
    """
    def __init__(self, wallet_dir):
        super(BitcoinWallet, self)\
            .__init__(wallet_dir=wallet_dir,
                      testnet=False,
                      network='bitcoin',
                      currency='BTC')


class LitecoinWallet(BitcoinlibWallet):
    """
    This class is responsible for handling your litecoin wallet.
    """
    def __init__(self, wallet_dir):
        super(LitecoinWallet, self) \
            .__init__(wallet_dir=wallet_dir,
                      testnet=False,
                      network='litecoin',
                      currency='LTC')


class DashWallet(BitcoinlibWallet):
    """
    This class is responsible for handling your dash wallet.
    """
    def __init__(self, wallet_dir):
        super(DashWallet, self) \
            .__init__(wallet_dir=wallet_dir,
                      testnet=False,
                      network='dash',
                      currency='DASH')


class BitcoinTestnetWallet(BitcoinlibWallet):
    """
    This class is responsible for handling your bitcoin testnet wallet.
    """
    def __init__(self, wallet_dir):
        super(BitcoinTestnetWallet, self)\
            .__init__(wallet_dir=wallet_dir,
                      testnet=True,
                      network='testnet',
                      currency='TBTC')


class LitecoinTestnetWallet(BitcoinlibWallet):
    """
    This class is responsible for handling your litecoin testnet wallet.
    """
    def __init__(self, wallet_dir):
        super(LitecoinTestnetWallet, self) \
            .__init__(wallet_dir=wallet_dir,
                      testnet=True,
                      network='litecoin_testnet',
                      currency='XLT')


class DashTestnetWallet(BitcoinlibWallet):
    """
    This class is responsible for handling your dash testnet wallet.
    """
    def __init__(self, wallet_dir):
        super(DashTestnetWallet, self) \
            .__init__(wallet_dir=wallet_dir,
                      testnet=True,
                      network='dash_testnet',
                      currency='TDASH')
