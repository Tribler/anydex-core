from sqlalchemy import Column, Integer, String, create_engine, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class DatabaseSeed(Base):
    """
    Database definition for seeds.
    """
    __tablename__ = "seeds"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)
    seed = Column(String(81), unique=True)


class DatabaseTransaction(Base):
    """
    Database definition for transactions.
    """
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    seed = Column(String(81))
    address = Column(String(81))
    value = Column(Integer)
    hash = Column(String(81), unique=True)
    msg_sig = Column(String(2187))
    current_index = Column(Integer)
    timestamp = Column(Integer)
    is_confirmed = Column(Boolean, default=False)
    bundle_hash = Column(String(81))


class DatabaseBundle(Base):
    """
    Database definition for bundles.
    """
    __tablename__ = "bundles"
    id = Column(Integer, primary_key=True)
    hash = Column(String(81), unique=True)
    tail_transaction_hash = Column(String(81), unique=True)
    count = Column(Integer)
    is_confirmed = Column(Boolean, default=False)


class DatabaseAddress(Base):
    """
    Database definition for addresses.
    """
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    address = Column(String(81), unique=True)
    seed = Column(String(81))
    is_spent = Column(Boolean, default=False)


def initialize_db(db_path):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session
