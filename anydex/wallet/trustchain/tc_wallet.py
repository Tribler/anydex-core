from asyncio import Future
from base64 import b64encode
from binascii import hexlify, unhexlify

from ipv8.attestation.trustchain.listener import BlockListener
from ipv8.keyvault.crypto import ECCrypto
from ipv8.peer import Peer
from ipv8.util import succeed

from anydex.util.asyncio import add_default_callback
from anydex.wallet.bandwidth_block import TriblerBandwidthBlock
from anydex.wallet.wallet import InsufficientFunds, Wallet

MEGA_DIV = 1024.0 * 1024.0
MIN_TRANSACTION_SIZE = 1024 * 1024


class TrustchainWallet(Wallet, BlockListener):
    """
    This class is responsible for handling your wallet of Tribler tokens.
    """
    MONITOR_DELAY = 1
    BLOCK_CLASS = TriblerBandwidthBlock

    def __init__(self, trustchain):
        super(TrustchainWallet, self).__init__()

        self.trustchain = trustchain
        self.trustchain.add_listener(self, [b'tribler_bandwidth'])
        self.created = True
        self.unlocked = True
        self.check_negative_balance = False
        self.transaction_history = []

    def should_sign(self, block):
        """
        Return whether we should sign a given block. For the TrustChain, we only sign a block when we receive bytes.
        In our current design, only the person that should pay bytes to others initiates a signing request.
        This is true when considering payouts in the tunnels and when buying bytes on the market.
        """
        return block.transaction[b"down"] >= MIN_TRANSACTION_SIZE

    def received_block(self, block):
        pass

    def get_name(self):
        return 'Tokens (MB)'

    def get_identifier(self):
        return 'MB'

    def create_wallet(self, *args, **kwargs):
        raise RuntimeError("You cannot create a Tribler Token wallet")

    def get_bandwidth_tokens(self, peer=None):
        """
        Get the bandwidth tokens for another peer.
        Currently this is just the difference in the amount of MBs exchanged with them.

        :param peer: the peer we interacted with
        :type peer: Peer
        :return: the amount of bandwidth tokens for this peer
        :rtype: int
        """
        if peer is None:
            peer = self.trustchain.my_peer

        block = self.trustchain.persistence.get_latest(peer.public_key.key_to_bin(), block_type=b'tribler_bandwidth')
        if block:
            return block.transaction[b'total_up'] - block.transaction[b'total_down']

        return 0

    def get_balance(self):
        return succeed({
            'available': int(self.get_bandwidth_tokens() / MEGA_DIV),
            'pending': 0,
            'currency': self.get_identifier(),
            'precision': self.precision()
        })

    async def transfer(self, quantity, peer):
        balance = await self.get_balance()
        if self.check_negative_balance and balance['available'] < quantity:
            raise InsufficientFunds()
        return await self.create_transfer_block(peer, quantity)

    async def create_transfer_block(self, peer, quantity):
        transaction = {b"up": 0, b"down": int(quantity * MEGA_DIV)}

        add_default_callback(self.trustchain.sign_block(peer, peer.public_key.key_to_bin(),
                                                        block_type=b'tribler_bandwidth', transaction=transaction))

        latest_block = self.trustchain.persistence.get_latest(self.trustchain.my_peer.public_key.key_to_bin(),
                                                              block_type=b'tribler_bandwidth')
        txid = "%s.%s.%d.%d" % (hexlify(latest_block.public_key).decode('utf-8'),
                                latest_block.sequence_number, 0, int(quantity * MEGA_DIV))

        self.transaction_history.append({
            'id': txid,
            'outgoing': True,
            'from': self.get_address(),
            'to': b64encode(peer.public_key.key_to_bin()),
            'amount': quantity,
            'fee_amount': 0.0,
            'currency': self.get_identifier(),
            'timestamp': '',
            'description': ''
        })

        return txid

    def monitor_transaction(self, payment_id):
        """
        Monitor an incoming transaction with a specific id.
        """
        pub_key, sequence_number = payment_id.split('.')[:2]
        pub_key = unhexlify(pub_key)
        sequence_number = int(sequence_number)

        block = self.trustchain.persistence.get(pub_key, sequence_number)

        monitor_future = Future()

        def check_has_block():
            self._logger.info("Checking for block with id %s and num %d", hexlify(pub_key), sequence_number)
            db_block = self.trustchain.persistence.get(pub_key, sequence_number)
            if db_block:
                monitor_future.set_result(db_block)
                monitor_task.cancel()

        if block:
            return succeed(block)

        monitor_task = self.register_task("poll_%s" % payment_id, check_has_block, interval=self.MONITOR_DELAY)
        return monitor_future

    def get_address(self):
        return succeed(b64encode(self.trustchain.my_peer.public_key.key_to_bin()).decode('utf-8'))

    def get_transactions(self):
        return succeed(self.transaction_history)

    def min_unit(self):
        return 1

    def get_num_unique_interactors(self, public_key):
        """
        Returns the number of people you interacted with (either helped or that have helped you)
        :param public_key: The public key of the member of which we want the information
        :return: A tuple of unique number of interactors that helped you and that you have helped respectively
        """
        peers_you_helped = set()
        peers_helped_you = set()
        for block in self.trustchain.persistence.get_latest_blocks(public_key, limit=-1,
                                                                   block_types=[b'tribler_bandwidth']):
            if int(block.transaction[b"up"]) > 0:
                peers_you_helped.add(block.link_public_key)
            if int(block.transaction[b"down"]) > 0:
                peers_helped_you.add(block.link_public_key)
        return len(peers_you_helped), len(peers_helped_you)

    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local trustchain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.trustchain.my_peer.public_key.key_to_bin()

        latest_block = self.trustchain.persistence.get_latest(public_key)
        latest_bw_block = self.trustchain.persistence.get_latest(public_key, block_type=b'tribler_bandwidth')
        statistics = dict()
        statistics["id"] = hexlify(public_key).decode('utf-8')
        interacts = self.get_num_unique_interactors(public_key)
        statistics["peers_that_pk_helped"] = interacts[0] if interacts[0] is not None else 0
        statistics["peers_that_helped_pk"] = interacts[1] if interacts[1] is not None else 0
        if latest_block:
            statistics["total_blocks"] = latest_block.sequence_number
        else:
            statistics["total_blocks"] = 0

        if latest_bw_block:
            statistics["total_up"] = latest_block.transaction[b"total_up"]
            statistics["total_down"] = latest_block.transaction[b"total_down"]
        else:
            statistics["total_up"] = 0
            statistics["total_down"] = 0
        return statistics

    def bootstrap_new_identity(self, amount):
        """
        One-way payment channel.
        Create a new temporary identity, and transfer funds to the new identity.
        A different party can then take the result and do a transfer from the temporary identity to itself
        """

        # Create new identity for the temporary identity
        crypto = ECCrypto()
        tmp_peer = Peer(crypto.generate_key(u"curve25519"))

        # Create the transaction specification
        transaction = {
            'up': 0,
            'down': amount,
            'type': b'tribler_bandwidth'
        }

        # Create the two half blocks that form the transaction
        local_half_block = TriblerBandwidthBlock.create(b'tribler_bandwidth', transaction, self.trustchain.persistence,
                                                        self.trustchain.my_peer.public_key.key_to_bin(),
                                                        link_pk=tmp_peer.public_key.key_to_bin())
        local_half_block.sign(self.trustchain.my_peer.key)
        tmp_half_block = TriblerBandwidthBlock.create(b'tribler_bandwidth', transaction, self.trustchain.persistence,
                                                      tmp_peer.public_key.key_to_bin(),
                                                      link=local_half_block,
                                                      link_pk=self.trustchain.my_peer.public_key.key_to_bin())
        tmp_half_block.sign(tmp_peer.key)

        self.trustchain.persistence.add_block(local_half_block)
        self.trustchain.persistence.add_block(tmp_half_block)

        # Create the bootstrapped identity format
        block = {'block_hash': b64encode(tmp_half_block.hash),
                 'sequence_number': tmp_half_block.sequence_number}

        result = {'private_key': b64encode(tmp_peer.key.key_to_bin()),
                  'transaction': {'up': amount, 'down': 0}, 'block': block}
        return result

    def precision(self):
        return 0
