import logging

from anydex.core.payment import Payment
from anydex.core.timestamp import Timestamp
from anydex.core.transaction import Transaction
from anydex.core.transaction_repository import TransactionRepository


class TransactionManager(object):
    """Manager for retrieving and creating transactions"""

    def __init__(self, transaction_repository):
        """
        :type transaction_repository: TransactionRepository
        """
        super(TransactionManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Transaction manager initialized")

        self.transaction_repository = transaction_repository

    def find_by_id(self, transaction_id):
        """
        :param transaction_id: The transaction id to look for
        :type transaction_id: TransactionId
        :return: The transaction or null if it cannot be found
        :rtype: Transaction
        """
        return self.transaction_repository.find_by_id(transaction_id)

    def find_all(self):
        """
        :rtype: [Transaction]
        """
        return self.transaction_repository.find_all()
