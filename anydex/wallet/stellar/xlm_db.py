from base64 import b64decode
from datetime import datetime
from typing import List

from sqlalchemy import Column, Integer, String, create_engine, Boolean, DateTime, ForeignKey, func, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from stellar_sdk import Keypair
from stellar_sdk.xdr.StellarXDR_pack import StellarXDRUnpacker

Base = declarative_base()


class Secret(Base):
    """
    Database definition for keys table.
    """
    __tablename__ = 'secrets'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    secret = Column(String)
    address = Column(String)  # address is same as public key


class Payment(Base):
    """
    Database definition for payments table.
    In stellar there are multiple types of operations and payment is one of them.
    This table will hold info about normal payments and about the create account operation.
    """
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    # payment_id = Column(Integer, unique=True)
    from_ = Column(String)
    to = Column(String)
    transaction_hash = Column(String, ForeignKey('transactions.hash'))  # tx this payment is a part of
    amount = Column(Integer)
    asset_type = Column(String)  # we might support more assets

    def __repr__(self):
        return f"xlm_db.Payment( {self.from_}, {self.to}, {self.asset_type}, {self.amount} )"

    # def __eq__(self, other):
    #     if not isinstance(other, Payment):
    #         raise NotImplementedError(f'cannot compare equality between{self} and {other}')
    #     return self.payment_id == other.payment_id


class Transaction(Base):
    """
    Database definition for transactions table.
    In stellar multiple operations can be a part of a transaction
    """
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    hash = Column(String, unique=True)
    date_time = Column(DateTime, default=datetime.utcnow())
    fee = Column(Integer)
    source_account = Column(String)
    operation_count = Column(Integer)
    succeeded = Column(Boolean, default=True)
    sequence_number = Column(Integer)
    transaction_envelope = Column(String)  # base64 encode xdr
    min_time_bound = Column(DateTime)  # unix time stamp
    max_time_bound = Column(DateTime)  # unix time stamp
    ledger_nr = Column(Integer)  # ledger is kinde of like a block
    is_pending = Column(Boolean, default=False)

    def __eq__(self, other):
        if not isinstance(other, Transaction):
            raise NotImplementedError(f'cannot compare equality between{self} and {other}')
        return self.hash == other.hash


def initialize_db(db_path):
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session


class StellarDb:
    """
    Wrapper around the stellar database.
    Provides methods to interact with the database.
    This can be used instead of manually interacting with the database with a session.
    """

    def __init__(self, db_path):
        """
        :param db_path: full path (including db file)
        """
        self.session = initialize_db(db_path)

    def get_wallet_secret(self, wallet_name):
        """
        Checks the database for a wallet with the given wallet_name.
        :param wallet_name: wallet_name to check
        :return: wallet secret if exists else None
        """
        secret = self.session.query(Secret).filter(Secret.name == wallet_name).first()
        if secret:
            return secret.secret
        return None

    def add_secret(self, wallet_name: str, secret: str, address: str):
        """
        Add a secret to the database with the given parameters.

        :param wallet_name: name of the wallet
        :param secret: secret (like private key) of the wallet
        :param address: address (public key) of the wallet
        """
        self.session.add(Secret(name=wallet_name, secret=secret, address=address))
        self.session.commit()

    def get_outgoing_amount(self, address):
        """
        Get the amount of lumens we are sending but is not yet confirmed.

        :return: amount of lumens we are sending
        """
        pending_outgoing = self.session.query(func.sum(Payment.amount)) \
            .join(Transaction,
                  Payment.transaction_hash == Transaction.hash).filter(
            Transaction.is_pending.is_(True)).filter(
            Payment.from_ == address).first()[0]

        return pending_outgoing if pending_outgoing else 0

    def update_db(self, transactions: List[Transaction]):
        """
        Update the transactions and payments table with the specified transactions.
        The payments are derived from the transaction envelope.
        """
        pending_txs = self.session.query(Transaction).filter(Transaction.is_pending.is_(True)).all()
        confirmed_txs = self.session.query(Transaction).filter(Transaction.is_pending.is_(False)).all()
        for transaction in transactions:
            if transaction in pending_txs:
                self._update_transaction(transaction)
            elif transaction not in confirmed_txs:
                self._insert_transaction(transaction)
        self.session.commit()

    def _update_transaction(self, transaction):
        """
        Update a pending transaction and it's corresponding payments
        :param transaction: transaction to update
        """
        self.session.query(Transaction).filter(Transaction.hash == transaction.hash).update({
            Transaction.is_pending: False,
            Transaction.succeeded: transaction.succeeded,
            Transaction.date_time: transaction.date_time
        })

    def _insert_transaction(self, transaction):
        """
        Insert a transactions into the database.
        Todo what about merge account
        The payments (payment and create account) will also be added from the transactions.

        :param transaction: transaction to insert
        """
        self.session.add(transaction)

        xdr_unpacker = StellarXDRUnpacker(b64decode(transaction.transaction_envelope))
        operations = xdr_unpacker.unpack_TransactionEnvelope().tx.operations

        for operation in operations:
            source_account = operation.sourceAccount
            # check if the operation has a source account
            if not source_account:
                source_account = transaction.source_account

            else:
                source_account = Keypair.from_raw_ed25519_public_key(source_account[0].ed25519).public_key
            body = operation.body
            # we only care about create account and payment for the time being
            payment = None
            if body.type == 0:  # create account
                create_account_op = body.createAccountOp
                payment = Payment(
                    amount=create_account_op.startingBalance,
                    asset_type="native",
                    transaction_hash=transaction.hash,
                    to=Keypair.from_raw_ed25519_public_key(create_account_op.destination.ed25519).public_key,
                    from_=source_account
                )
            elif body.type == 1:  # payment
                payment_op = body.paymentOp
                payment = Payment(amount=payment_op.amount,
                                  asset_type="native",
                                  transaction_hash=transaction.hash,
                                  to=Keypair.from_raw_ed25519_public_key(payment_op.destination.ed25519).public_key,
                                  from_=source_account)
            if payment:
                self.session.add(payment)

    def insert_transaction(self, transaction):
        """
        Wrapper around the _insert_transactions function.
        This method is intended to be used by users of this classes.
        The difference is that this method commits after inserting.

        :param transaction: Transaction to insert
        """
        self._insert_transaction(transaction)
        self.session.commit()

    def get_sequence_number(self, address):
        """
        Query the database for the sequence number of the specified address.

        :param: address: address for which to find the sequence number
        :return: sequence number if exists or None
        """
        latest_sent_payment_sequence = self.session.query(Transaction.sequence_number).filter(
            Transaction.source_account == address).filter(Transaction.succeeded.is_(True)).order_by(
            Transaction.sequence_number.desc()
        ).first()
        return latest_sent_payment_sequence[0] if latest_sent_payment_sequence else None

    def get_payments_and_transactions(self, address):
        """
        Return a list of tuples containing a payment and its corresponding transactions.
        This is done so that we can also get the fee datatime etc.

        The payments are only returned if the relate to the given address.

        Maybe we should create a specific class for this?


        :param: address: address to get the payments of
        :return: List of tuples of payments, transactions
        """
        payments = self.session.query(Payment, Transaction).join(Transaction,
                                                                 Payment.transaction_hash == Transaction.hash).filter(
            Transaction.succeeded.is_(True)).filter(
            or_(Payment.from_ == address, Payment.to == address)).all()

        return payments
