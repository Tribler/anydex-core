
class WalletAddress:
    """Used for having a validated instance of a wallet address that we can easily check if it still valid."""

    def __init__(self, wallet_address):
        """
        :param wallet_address: String representation of a wallet address
        :type wallet_address: str
        :raises TypeError: Thrown when the type of wallet_address is invalid
        """
        if not isinstance(wallet_address, str):
            raise TypeError(f"Wallet address must be a string, found {type(wallet_address)} instead")

        self._wallet_address = wallet_address

    def __eq__(self, other):
        return str(other) == self._wallet_address

    @property
    def address(self):
        return self._wallet_address

    def __str__(self):
        return self._wallet_address
