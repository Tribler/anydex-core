from datetime import datetime

from sqlalchemy import Column, Integer, String, LargeBinary, create_engine, DateTime, Boolean, func, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Key(Base):
    """
    Database definition for keys table.
    """
    __tablename__ = 'keys'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    # public_key = Column(String(32))
    private_key = Column(LargeBinary(32))
    address = Column(String(42))  # including "0x" address is 42 bytes long


class Transaction(Base):
    """
    Database definition for transactions
    """
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)

    block_number = Column(Integer)

    from_ = Column(String(42))
    gas = Column(Integer)
    gas_price = Column(Integer)
    hash = Column(String, unique=True)
    nonce = Column(Integer)

    to = Column(String(42))

    value = Column(Integer)
    date_time = Column(DateTime, default=datetime.utcnow())
    is_pending = Column(Boolean, default=False)
    token_identifier = Column(String)  # Used to differentiate between the different tokens.

    def __eq__(self, other):
        if not isinstance(other, Transaction):
            raise NotImplementedError(f'cannot compare equality between{self} and {other}')
        return self.hash == other.hash

    def __hash__(self):
        return hash(self.hash)


def initialize_db(db_path):
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session


class EthereumDb:
    """
    Wrapper around the Ethereum database.
    """

    def __init__(self, db_path):
        """
        :param db_path: full path (including db file)
        """
        self.session = initialize_db(db_path)

    def get_wallet_private_key(self, wallet_name):
        """
        Retrieve the private key of the wallet with the given name.

        :param wallet_name: name of wallet to find key of
        :return: private key if wallet exists else None
        """
        row = self.session.query(Key).filter(Key.name == wallet_name).first()
        return row.private_key if row else None

    def add_key(self, name, private_key, address):
        self.session.add(Key(name=name, private_key=private_key, address=address))
        self.session.commit()

    def update_database(self, transactions, token):
        """
        Update transactions in the database.
        Pending transactions that have been confirmed will be updated
        to have a block number and will no longer be pending.
        Other transactions that are not in the database will be added.

        :param token: token identifier, should be ETH for Ethereum
        :param transactions: list of transactions
        """
        # Use subquery instead??
        pending_transactions = self.session.query(Transaction).filter(Transaction.is_pending.is_(True)).all()
        confirmed_transactions = self.session.query(Transaction).filter(Transaction.is_pending.is_(False)).all()

        for transaction in transactions:
            if transaction in pending_transactions:
                # update transaction set is_pending = false where hash = ''
                self.session.query(Transaction).filter(Transaction.hash == transaction.hash).update({
                    Transaction.is_pending: False,
                    Transaction.block_number: transaction.block_number
                })
            elif transaction not in confirmed_transactions:
                transaction.token_identifier = token
                self.session.add(transaction)
        self.session.commit()

    def get_transaction_count(self, address):
        """
        Get the amount of transactions sent by this wallet
        """
        row = self.session.query(Transaction.nonce).filter(func.lower(Transaction.from_) == address.lower()).order_by(
            Transaction.nonce.desc()).first()
        if row:
            return row[0] + 1  # nonce + 1
        return 0

    def get_outgoing_amount(self, address, token):
        """
        Get the current amount of specified token that we are sending, but is still unconfirmed.

        :return: pending outgoing amount
        """
        outgoing = self.session.query(func.sum(Transaction.value)).filter(Transaction.is_pending.is_(True)).filter(
            func.lower(Transaction.from_) == address).filter(Transaction.token_identifier == token).first()[0]
        return outgoing if outgoing else 0

    def get_incoming_amount(self, address, token):
        """
        Get the current amount of specified token that is being sent to us, but is still unconfirmed.

        :return: pending incoming amount
        """
        incoming = self.session.query(func.sum(Transaction.value)).filter(Transaction.is_pending.is_(True)).filter(
            func.lower(Transaction.to) == address).filter(
            Transaction.token_identifier == token).first()[0]
        return incoming if incoming else 0

    def add(self, obj):
        """
        Wrapper around add method.
        This method also calls `session.commit`

        :param obj: a database object
        """
        self.session.add(obj)
        self.session.commit()

    def get_transactions(self, address, token):
        """
        Retrieve the transactions relating to the given address and token.

        :param address: address of ethereum wallet
        :param token: token identifier
        :return: List of transactions from db
        """
        transactions_db = self.session.query(Transaction).filter(
            or_(func.lower(Transaction.from_) == address.lower(),
                func.lower(Transaction.to) == address.lower()
                )).filter(Transaction.token_identifier == token).all()
        return transactions_db
