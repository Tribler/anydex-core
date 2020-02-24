from ipv8.messaging.payload import Payload

from anydex.core.assetamount import AssetAmount
from anydex.core.assetpair import AssetPair
from anydex.core.bloomfilter import BloomFilter
from anydex.core.message import TraderId
from anydex.core.order import OrderId, OrderNumber
from anydex.core.timeout import Timeout
from anydex.core.timestamp import Timestamp


class MessagePayload(Payload):
    """
    Payload for a generic message in the market community.
    """

    format_list = ['varlenI', 'Q']

    def __init__(self, trader_id, timestamp):
        super(MessagePayload, self).__init__()
        self.trader_id = trader_id
        self.timestamp = timestamp

    def to_pack_list(self):
        data = [('varlenI', bytes(self.trader_id)),
                ('Q', int(self.timestamp))]

        return data


class InfoPayload(MessagePayload):
    """
    Payload for an info message in the market community.
    """

    format_list = MessagePayload.format_list + ['?']

    def __init__(self, trader_id, timestamp, is_matchmaker):
        super(InfoPayload, self).__init__(trader_id, timestamp)
        self.is_matchmaker = is_matchmaker

    def to_pack_list(self):
        data = super(InfoPayload, self).to_pack_list()
        data.append(('?', self.is_matchmaker))
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, is_matchmaker):
        return InfoPayload(TraderId(trader_id), timestamp, is_matchmaker)


class CancelOrderPayload(MessagePayload):
    """
    Payload with cancellation of an order in the market.
    """

    format_list = MessagePayload.format_list + ['I']

    def __init__(self, trader_id, timestamp, order_number):
        super(CancelOrderPayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number

    def to_pack_list(self):
        data = super(CancelOrderPayload, self).to_pack_list()
        data += [('I', int(self.order_number))]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number):
        return CancelOrderPayload(TraderId(trader_id), timestamp, OrderNumber(order_number))


class OrderPayload(MessagePayload):
    """
    Payload for a message with an offer in the market community.
    """

    format_list = MessagePayload.format_list + ['I', 'Q', 'varlenI', 'Q', 'varlenI', 'I', 'Q', '?']

    def __init__(self, trader_id, timestamp, order_number, assets, timeout, traded, is_ask):
        super(OrderPayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number
        self.assets = assets
        self.timeout = timeout
        self.traded = traded
        self.is_ask = is_ask

    def to_pack_list(self):
        data = super(OrderPayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('Q', self.assets.first.amount),
                 ('varlenI', self.assets.first.asset_id.encode('utf-8')),
                 ('Q', self.assets.second.amount),
                 ('varlenI', self.assets.second.asset_id.encode('utf-8')),
                 ('I', int(self.timeout)),
                 ('Q', self.traded),
                 ('?', self.is_ask)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, asset1_amount, asset1_type, asset2_amount,
                         asset2_type, timeout, traded, is_ask):
        return OrderPayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                            AssetPair(AssetAmount(asset1_amount, asset1_type.decode()),
                                      AssetAmount(asset2_amount, asset2_type.decode())),
                            Timeout(timeout), traded, is_ask)


class MatchPayload(OrderPayload):
    """
    Payload for a match in the market community.
    """

    format_list = OrderPayload.format_list + ['I', 'varlenI', 'varlenI']

    def __init__(self, trader_id, timestamp, order_number, assets, timeout, traded, is_ask, recipient_order_number,
                 match_trader_id, matchmaker_trader_id):
        super(MatchPayload, self).__init__(trader_id, timestamp, order_number, assets, timeout, traded, is_ask)
        self.recipient_order_number = recipient_order_number
        self.match_trader_id = match_trader_id
        self.matchmaker_trader_id = matchmaker_trader_id

    def to_pack_list(self):
        data = super(MatchPayload, self).to_pack_list()
        data += [('I', int(self.recipient_order_number)),
                 ('varlenI', bytes(self.match_trader_id)),
                 ('varlenI', bytes(self.matchmaker_trader_id))]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, asset1_amount, asset1_type, asset2_amount,
                         asset2_type, timeout, traded, is_ask, recipient_order_number,
                         match_trader_id, matchmaker_trader_id):
        return MatchPayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                            AssetPair(AssetAmount(asset1_amount, asset1_type.decode('utf-8')),
                                      AssetAmount(asset2_amount, asset2_type.decode('utf-8'))),
                            Timeout(timeout), traded, is_ask, OrderNumber(recipient_order_number),
                            TraderId(match_trader_id), TraderId(matchmaker_trader_id))


class DeclineMatchPayload(MessagePayload):
    """
    Payload for a declined match in the market community.
    """

    format_list = MessagePayload.format_list + ['I', 'varlenI', 'I', 'I']

    def __init__(self, trader_id, timestamp, order_number, other_order_id, decline_reason):
        super(DeclineMatchPayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number
        self.other_order_id = other_order_id
        self.decline_reason = decline_reason

    def to_pack_list(self):
        data = super(DeclineMatchPayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('varlenI', bytes(self.other_order_id.trader_id)),
                 ('I', int(self.other_order_id.order_number)),
                 ('I', self.decline_reason)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, other_trader_id, other_order_number, decline_reason):
        return DeclineMatchPayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                                   OrderId(TraderId(other_trader_id), OrderNumber(other_order_number)), decline_reason)


class TradePayload(MessagePayload):
    """
    Payload that contains a trade in the market community.
    """

    format_list = MessagePayload.format_list + ['I', 'varlenI', 'I', 'I', 'Q', 'varlenI', 'Q', 'varlenI']

    def __init__(self, trader_id, timestamp, order_number, recipient_order_id, proposal_id, assets):
        super(TradePayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.assets = assets

    def to_pack_list(self):
        data = super(TradePayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('varlenI', bytes(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('Q', self.assets.first.amount),
                 ('varlenI', self.assets.first.asset_id.encode('utf-8')),
                 ('Q', self.assets.second.amount),
                 ('varlenI', self.assets.second.asset_id.encode('utf-8'))]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, recipient_trader_id, recipient_order_number,
                         proposal_id, asset1_amount, asset1_type, asset2_amount, asset2_type):
        return TradePayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                            OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)), proposal_id,
                            AssetPair(AssetAmount(asset1_amount, asset1_type.decode('utf-8')),
                                      AssetAmount(asset2_amount, asset2_type.decode('utf-8'))))


class CompletedTradePayload(TradePayload):
    """
    Payload that contains information on a completed trade.
    """

    format_list = TradePayload.format_list + ['varlenI']

    def __init__(self, trader_id, timestamp, order_number, recipient_order_id, proposal_id, assets, trade_id):
        super(CompletedTradePayload, self).__init__(trader_id, timestamp, order_number, recipient_order_id, proposal_id, assets)
        self.trade_id = trade_id

    def to_pack_list(self):
        data = super(CompletedTradePayload, self).to_pack_list()
        data += [('varlenI', self.trade_id)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, recipient_trader_id, recipient_order_number,
                         proposal_id, asset1_amount, asset1_type, asset2_amount, asset2_type, trade_id):
        return CompletedTradePayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                            OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)), proposal_id,
                            AssetPair(AssetAmount(asset1_amount, asset1_type.decode()),
                                      AssetAmount(asset2_amount, asset2_type.decode())), trade_id)


class DeclineTradePayload(MessagePayload):

    format_list = MessagePayload.format_list + ['I', 'varlenI', 'I', 'I', 'I']

    def __init__(self, trader_id, timestamp, order_number, recipient_order_id, proposal_id, decline_reason):
        super(DeclineTradePayload, self).__init__(trader_id, timestamp)
        self.order_number = order_number
        self.recipient_order_id = recipient_order_id
        self.proposal_id = proposal_id
        self.decline_reason = decline_reason

    def to_pack_list(self):
        data = super(DeclineTradePayload, self).to_pack_list()
        data += [('I', int(self.order_number)),
                 ('varlenI', bytes(self.recipient_order_id.trader_id)),
                 ('I', int(self.recipient_order_id.order_number)),
                 ('I', self.proposal_id),
                 ('I', self.decline_reason)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, order_number, recipient_trader_id,
                         recipient_order_number, proposal_id, decline_reason):
        return DeclineTradePayload(TraderId(trader_id), Timestamp(timestamp), OrderNumber(order_number),
                                   OrderId(TraderId(recipient_trader_id), OrderNumber(recipient_order_number)),
                                   proposal_id, decline_reason)


class OrderbookSyncPayload(MessagePayload):
    """
    Payload for synchronization of orders in the market community.
    """

    format_list = MessagePayload.format_list + ['B', 'c', 'varlenI']

    def __init__(self, trader_id, timestamp, bloomfilter):
        super(OrderbookSyncPayload, self).__init__(trader_id, timestamp)
        self.bloomfilter = bloomfilter

    def to_pack_list(self):
        data = super(OrderbookSyncPayload, self).to_pack_list()
        data += [('B', self.bloomfilter.functions),
                 ('c', self.bloomfilter.prefix),
                 ('varlenI', self.bloomfilter.bytes)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, bf_functions, bf_prefix, bf_bytes):
        bloomfilter = BloomFilter(bf_bytes, bf_functions, prefix=bf_prefix)
        return OrderbookSyncPayload(TraderId(trader_id), timestamp, bloomfilter)


class PingPongPayload(MessagePayload):
    """
    Payload for a ping and pong message in the market community.
    """

    format_list = MessagePayload.format_list + ['I']

    def __init__(self, trader_id, timestamp, identifier):
        super(PingPongPayload, self).__init__(trader_id, timestamp)
        self.identifier = identifier

    def to_pack_list(self):
        data = super(PingPongPayload, self).to_pack_list()
        data += [('I', self.identifier)]
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, identifier):
        return PingPongPayload(TraderId(trader_id), timestamp, identifier)


class PublicKeyPayload(MessagePayload):
    """
    Payload for a request/response message to fetch the public key from another peer.
    """

    format_list = MessagePayload.format_list + ['I']

    def __init__(self, trader_id, timestamp, identifier):
        super(PublicKeyPayload, self).__init__(trader_id, timestamp)
        self.identifier = identifier

    def to_pack_list(self):
        data = super(PublicKeyPayload, self).to_pack_list()
        data.append(('I', self.identifier))
        return data

    @classmethod
    def from_unpack_list(cls, trader_id, timestamp, identifier):
        return PublicKeyPayload(TraderId(trader_id), timestamp, identifier)
