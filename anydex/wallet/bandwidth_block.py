from ipv8.attestation.trustchain.block import EMPTY_SIG, GENESIS_HASH, GENESIS_SEQ, TrustChainBlock, \
    ValidationResult
from ipv8.messaging.deprecated.encoding import encode


class TriblerBandwidthBlock(TrustChainBlock):
    """
    Container for bandwidth block information
    """

    @classmethod
    def create(cls, block_type, transaction, database, public_key, link=None, link_pk=None, additional_info=None):
        """
        Create an empty next block.
        :param block_type: the type of the block to be created
        :param transaction: the transaction to use in this block
        :param database: the database to use as information source
        :param public_key: the public key to use for this block
        :param link: optionally create the block as a linked block to this block
        :param link_pk: the public key of the counterparty in this transaction
        :param additional_info: additional information, which has a higher priority than the
               transaction when link exists
        :return: A newly created block
        """
        latest_bw_block = database.get_latest(public_key, block_type=b'tribler_bandwidth')
        latest_block = database.get_latest(public_key)
        ret = cls()
        if link:
            ret.type = link.type
            ret.transaction[b"up"] = link.transaction[b"down"] if b"down" in link.transaction else 0
            ret.transaction[b"down"] = link.transaction[b"up"] if b"up" in link.transaction else 0
            ret.link_public_key = link.public_key
            ret.link_sequence_number = link.sequence_number
        else:
            ret.type = block_type
            ret.transaction[b"up"] = transaction[b"up"] if b"up" in transaction else 0
            ret.transaction[b"down"] = transaction[b"down"] if b"down" in transaction else 0
            ret.link_public_key = link_pk

        if latest_bw_block:
            ret.transaction[b"total_up"] = latest_bw_block.transaction[b"total_up"] + ret.transaction[b"up"]
            ret.transaction[b"total_down"] = latest_bw_block.transaction[b"total_down"] + ret.transaction[b"down"]
        else:
            ret.transaction[b"total_up"] = ret.transaction[b"up"]
            ret.transaction[b"total_down"] = ret.transaction[b"down"]

        if latest_block:
            ret.sequence_number = latest_block.sequence_number + 1
            ret.previous_hash = latest_block.hash

        ret._transaction = encode(ret.transaction)
        ret.public_key = public_key
        ret.signature = EMPTY_SIG
        ret.hash = ret.calculate_hash()

        return ret

    def validate_transaction(self, database):
        """
        Validates this transaction
        :param database: the database to check against
        :return: A tuple consisting of a ValidationResult and a list of user string errors
        """
        result = [ValidationResult.valid]
        errors = []

        def err(reason):
            result[0] = ValidationResult.invalid
            errors.append(reason)

        if self.transaction[b"up"] < 0:
            err("Up field is negative")
        if self.transaction[b"down"] < 0:
            err("Down field is negative")
        if self.transaction[b"down"] == 0 and self.transaction[b"up"] == 0:
            # In this case the block doesn't modify any counters, these block are without purpose and are thus invalid.
            err("Up and down are zero")
        if self.transaction[b"total_up"] < 0:
            err("Total up field is negative")
        if self.transaction[b"total_down"] < 0:
            err("Total down field is negative")

        blk = database.get(self.public_key, self.sequence_number)
        link = database.get_linked(self)
        prev_blk = database.get_block_before(self, block_type=b'tribler_bandwidth')
        next_blk = database.get_block_after(self, block_type=b'tribler_bandwidth')

        is_genesis = self.sequence_number == GENESIS_SEQ or self.previous_hash == GENESIS_HASH
        if is_genesis:
            if self.transaction[b"total_up"] != self.transaction[b"up"]:
                err("Genesis block invalid total_up and/or up")
            if self.transaction[b"total_down"] != self.transaction[b"down"]:
                err("Genesis block invalid total_down and/or down")

        if blk:
            if blk.transaction[b"up"] != self.transaction[b"up"]:
                err("Up does not match known block")
            if blk.transaction[b"down"] != self.transaction[b"down"]:
                err("Down does not match known block")
            if blk.transaction[b"total_up"] != self.transaction[b"total_up"]:
                err("Total up does not match known block")
            if blk.transaction[b"total_down"] != self.transaction[b"total_down"]:
                err("Total down does not match known block")

        if link:
            if self.transaction[b"up"] != link.transaction[b"down"]:
                err("Up/down mismatch on linked block")
            if self.transaction[b"down"] != link.transaction[b"up"]:
                err("Down/up mismatch on linked block")

        if prev_blk:
            if prev_blk.transaction[b"total_up"] + self.transaction[b"up"] > self.transaction[b"total_up"]:
                err("Total up is lower than expected compared to the preceding block")
            if prev_blk.transaction[b"total_down"] + self.transaction[b"down"] > self.transaction[b"total_down"]:
                err("Total down is lower than expected compared to the preceding block")

        if next_blk:
            if self.transaction[b"total_up"] + next_blk.transaction[b"up"] > next_blk.transaction[b"total_up"]:
                err("Total up is higher than expected compared to the next block")
                # In this case we could say there is fraud too, since the counters are too high. Also anyone that
                # counter signed any such counters should be suspected since they apparently failed to validate or put
                # their signature on it regardless of validation status. But it is not immediately clear where this
                # error occurred, it might be lower on the chain than self. So it is hard to create a fraud proof here
            if self.transaction[b"total_down"] + next_blk.transaction[b"down"] > next_blk.transaction[b"total_down"]:
                err("Total down is higher than expected compared to the next block")
                # See previous comment

        return result[0], errors
