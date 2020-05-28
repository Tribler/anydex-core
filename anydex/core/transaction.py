import logging
from binascii import hexlify, unhexlify

from ipv8.database import database_blob

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.timestamp import Timestamp
from anydex.core.wallet_address import WalletAddress


class TransactionId(object):
    """Immutable class for representing the id of a transaction."""

    def __init__(self, transaction_id):
        """
        :param transaction_id: String representing the transaction id
        :type transaction_id: bytes
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TransactionId, self).__init__()

        transaction_id = transaction_id if isinstance(transaction_id, bytes) else bytes(transaction_id)

        if len(transaction_id) != 32:
            raise ValueError("Transaction ID must be 32 bytes")

        self.transaction_id = transaction_id  # type: bytes

    def __str__(self):
        return "%s" % self.transaction_id

    def __bytes__(self):  # type: () -> bytes
        return self.transaction_id

    def as_hex(self):
        return hexlify(bytes(self)).decode('utf-8')

    def __eq__(self, other):
        return self.transaction_id == other.transaction_id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.transaction_id)


class Transaction(object):
    """Class for representing a transaction between two nodes"""

    def __init__(self, transaction_id, assets, order_id, partner_order_id, timestamp):
        """
        :param transaction_id: An transaction id to identify the order
        :param assets: The asset pair to exchange
        :param order_id: The id of your order for this transaction
        :param partner_order_id: The id of the order of the other party
        :param timestamp: A timestamp when the transaction was created
        :type transaction_id: TransactionId
        :type assets: AssetPair
        :type order_id: OrderId
        :type partner_order_id: OrderId
        :type timestamp: Timestamp
        """
        super(Transaction, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._transaction_id = transaction_id
        self._assets = assets
        self._transferred_assets = AssetPair(AssetAmount(0, assets.first.asset_id),
                                             AssetAmount(0, assets.second.asset_id))
        self._order_id = order_id
        self._partner_order_id = partner_order_id
        self._timestamp = timestamp

        self.sent_wallet_info = False
        self.received_wallet_info = False
        self.incoming_address = None
        self.outgoing_address = None
        self.partner_incoming_address = None
        self.partner_outgoing_address = None
        self.trading_peer = None

        self._payments = []
        self._current_payment = 0

    @classmethod
    def from_database(cls, data, payments):
        """
        Create a Transaction object based on information in the database.
        """
        (trader_id, transaction_id, order_number, partner_trader_id, partner_order_number,
         asset1_amount, asset1_type, asset1_transferred, asset2_amount, asset2_type, asset2_transferred,
         transaction_timestamp, sent_wallet_info, received_wallet_info, incoming_address, outgoing_address,
         partner_incoming_address, partner_outgoing_address) = data

        transaction_id = TransactionId(bytes(transaction_id))
        transaction = cls(transaction_id,
                          AssetPair(AssetAmount(asset1_amount, asset1_type.decode()),
                                    AssetAmount(asset2_amount, asset2_type.decode())),
                          OrderId(TraderId(bytes(trader_id)), OrderNumber(order_number)),
                          OrderId(TraderId(bytes(partner_trader_id)), OrderNumber(partner_order_number)),
                          Timestamp(transaction_timestamp))

        transaction._transferred_assets = AssetPair(AssetAmount(asset1_transferred, asset1_type.decode()),
                                                    AssetAmount(asset2_transferred, asset2_type.decode()))
        transaction.sent_wallet_info = sent_wallet_info
        transaction.received_wallet_info = received_wallet_info
        transaction.incoming_address = WalletAddress(str(incoming_address))
        transaction.outgoing_address = WalletAddress(str(outgoing_address))
        transaction.partner_incoming_address = WalletAddress(str(partner_incoming_address))
        transaction.partner_outgoing_address = WalletAddress(str(partner_outgoing_address))
        transaction._payments = payments

        return transaction

    def to_database(self):
        """
        Returns a database representation of a Transaction object.
        :rtype: tuple
        """
        return (database_blob(bytes(self.order_id.trader_id)), database_blob(bytes(self.transaction_id)),
                int(self.order_id.order_number),
                database_blob(bytes(self.partner_order_id.trader_id)), int(self.partner_order_id.order_number),
                self.assets.first.amount, str(self.assets.first.asset_id), self.transferred_assets.first.amount,
                self.assets.second.amount, str(self.assets.second.asset_id),
                self.transferred_assets.second.amount, int(self.timestamp), self.sent_wallet_info,
                self.received_wallet_info, str(self.incoming_address), str(self.outgoing_address),
                str(self.partner_incoming_address), str(self.partner_outgoing_address))

    @classmethod
    def from_accepted_trade(cls, accepted_trade, transaction_id):
        """
        Create a transaction from an *outgoing* accepted trade
        :param accepted_trade: The accepted trade to create the transaction for
        :param transaction_id: The transaction id to use for this transaction
        :type accepted_trade: AcceptedTrade
        :type transaction_id: TransactionId
        :return: The created transaction
        :rtype: Transaction
        """
        return cls(transaction_id, accepted_trade.assets, accepted_trade.recipient_order_id,
                   accepted_trade.order_id, Timestamp.now())

    @classmethod
    def from_tx_init_block(cls, tx_init_block):
        """
        Create a transaction from an incoming tx_init block.
        :param tx_init_block: The tx_init block containing the transaction information
        :return: The created transaction
        :rtype: Transaction
        """
        tx_dict = tx_init_block.transaction["tx"]
        order_id = OrderId(TraderId(unhexlify(tx_dict["partner_trader_id"])),
                           OrderNumber(tx_dict["partner_order_number"]))
        partner_order_id = OrderId(TraderId(unhexlify(tx_dict["trader_id"])),
                                   OrderNumber(tx_dict["order_number"]))
        return cls(TransactionId(tx_init_block.hash), AssetPair.from_dictionary(tx_dict["assets"]),
                   order_id, partner_order_id, Timestamp.now())

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def assets(self):
        """
        :rtype: AssetPair
        """
        return self._assets

    @property
    def transferred_assets(self):
        """
        :rtype: AssetPair
        """
        return self._transferred_assets

    @property
    def order_id(self):
        """
        Return the id of your order
        :rtype: OrderId
        """
        return self._order_id

    @property
    def partner_order_id(self):
        """
        :rtype: OrderId
        """
        return self._partner_order_id

    @property
    def payments(self):
        """
        :rtype: [Payment]
        """
        return self._payments

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp

    @property
    def status(self):
        """
        Return the status of this transaction, can be one of these: "pending", "completed".
        :rtype: str
        """
        return "completed" if self.is_payment_complete() else "pending"

    def add_payment(self, payment):
        """
        Add a completed payment to this transaction and update its state.
        """
        self._logger.debug("Adding transferred assets %s to transaction %s",
                           payment.transferred_assets, self.transaction_id.as_hex())
        if payment.transferred_assets.asset_id == self.transferred_assets.first.asset_id:
            self.transferred_assets.first += payment.transferred_assets
        else:
            self.transferred_assets.second += payment.transferred_assets
        self._payments.append(payment)

    def next_payment(self, order_is_ask):
        """
        Return the assets that this user has to send to the counterparty as a next step.
        :param order_is_ask: Whether the order is an ask or not.
        :return: An AssetAmount object, indicating how much we should send to the counterparty.
        """
        assets_to_transfer = self.assets.first if order_is_ask else self.assets.second
        self._logger.debug("Returning %s for the next payment (no incremental payments)", assets_to_transfer)
        return assets_to_transfer

    def is_payment_complete(self):
        return self.transferred_assets.first >= self.assets.first and \
               self.transferred_assets.second >= self.assets.second

    def to_block_dictionary(self):
        """
        Return a dictionary with a representation of this transaction (to add to a tx_done block).
        """
        return {
            "trader_id": self.order_id.trader_id.as_hex(),
            "order_number": int(self.order_id.order_number),
            "partner_trader_id": self.partner_order_id.trader_id.as_hex(),
            "partner_order_number": int(self.partner_order_id.order_number),
            "transaction_id": self.transaction_id.as_hex(),
            "assets": self.assets.to_dictionary(),
            "transferred": self.transferred_assets.to_dictionary(),
            "timestamp": int(self.timestamp),
        }
