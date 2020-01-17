from asyncio import gather

from aiohttp import web

from ipv8.REST.base_endpoint import HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, Response

from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class WalletsEndpoint(BaseMarketEndpoint):
    """
    This class represents the root endpoint of the wallets resource.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_wallets),
                             web.put('/{wallet_id}', self.create_wallet),
                             web.get('/{wallet_id}/balance', self.get_wallet_balance),
                             web.get('/{wallet_id}/transactions', self.get_wallet_transactions),
                             web.post('/{wallet_id}/transfer', self.transfer_funds)])

    async def get_wallets(self, request):
        """
        .. http:get:: /wallets

        A GET request to this endpoint will return information about all available wallets in Tribler.
        This includes information about the address, a human-readable wallet name and the balance.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/wallets

            **Example response**:

            .. sourcecode:: javascript

                {
                    "wallets": [{
                        "created": True,
                        "name": "Bitcoin",
                        "unlocked": True,
                        "precision": 8,
                        "min_unit": 100000,
                        "address": "17AVS7n3zgBjPq1JT4uVmEXdcX3vgB2wAh",
                        "balance": {
                            "available": 0.000126,
                            "pending": 0.0,
                            "currency": "BTC"
                        }
                    }, ...]
                }
        """
        wallets = {}

        async def add_wallet(wallet_id, wallet):
            balance = await wallet.get_balance()
            wallets[wallet_id] = {
                'created': wallet.created,
                'unlocked': wallet.unlocked,
                'address': wallet.get_address(),
                'name': wallet.get_name(),
                'precision': wallet.precision(),
                'min_unit': wallet.min_unit(),
                'balance': balance
            }

        await gather(*[add_wallet(wid, w) for wid, w in self.get_market_community().wallets.items()])
        return Response({"wallets": wallets})

    async def create_wallet(self, request):
        """
        .. http:put:: /wallets/(string:wallet identifier)

        A request to this endpoint will create a new wallet.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/wallets/BTC

            **Example response**:

            .. sourcecode:: javascript

                {
                    "created": True
                }
        """
        identifier = request.match_info['wallet_id']
        if self.get_market_community().wallets[identifier].created:
            return Response({"error": "this wallet already exists"}, status=HTTP_BAD_REQUEST)

        try:
            await self.get_market_community().wallets[identifier].create_wallet()
        except Exception as e:
            return Response({"error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)
        return Response({"created": True})

    async def get_wallet_balance(self, request):
        """
        .. http:get:: /wallets/(string:wallet identifier)/balance

        A GET request to this endpoint will return balance information of a specific wallet.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/wallets/BTC/balance

            **Example response**:

            .. sourcecode:: javascript

                {
                    "balance": {
                        "available": 0.000126,
                        "pending": 0.0,
                        "currency": "BTC"
                    }
                }
        """
        identifier = request.match_info['wallet_id']
        balance = await self.get_market_community().wallets[identifier].get_balance()
        return Response({"balance": balance})

    async def get_wallet_transactions(self, request):
        """
        .. http:get:: /wallets/(string:wallet identifier)/transactions

        A GET request to this endpoint will return past transactions of a specific wallet.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/wallets/BTC/transactions

            **Example response**:

            .. sourcecode:: javascript

                {
                    "transactions": [{
                        "currency": "BTC",
                        "to": "17AVS7n3zgBjPq1JT4uVmEXdcX3vgB2wAh",
                        "outgoing": false,
                        "from": "",
                        "description": "",
                        "timestamp": "1489673696",
                        "fee_amount": 0.0,
                        "amount": 0.00395598,
                        "id": "6f6c40d034d69c5113ad8cb3710c172955f84787b9313ede1c39cac85eeaaffe"
                    }, ...]
                }
        """
        identifier = request.match_info['wallet_id']
        transactions = await self.get_market_community().wallets[identifier].get_transactions()
        return Response({"transactions": transactions})

    async def transfer_funds(self, request):
        """
        .. http:post:: /wallets/(string:wallet identifier)/transfer

        A POST request to this endpoint will transfer some units from a wallet to another address.

            **Example request**:

            .. sourcecode:: none

                curl -X POST http://localhost:8085/wallets/BTC/transfer
                --data "amount=0.3&destination=mpC1DDgSP4PKc5HxJzQ5w9q6CGLBEQuLsN"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "txid": "abcd"
                }
        """
        parameters = await request.post()

        identifier = request.match_info['wallet_id']
        if identifier != "BTC" and identifier != "TBTC":
            return Response({"error": "currently, currency transfers using the API "
                                      "is only supported for Bitcoin"}, status=HTTP_BAD_REQUEST)

        wallet = self.get_market_community().wallets[identifier]

        if not wallet.created:
            return Response({"error": "this wallet is not created"}, status=HTTP_BAD_REQUEST)

        if 'amount' not in parameters or 'destination' not in parameters:
            return Response({"error": "an amount and a destination address are required"}, status=HTTP_BAD_REQUEST)

        try:
            txid = await wallet.transfer(parameters['amount'], parameters['destination'])
        except Exception as e:
            return Response({"txid": "", "error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)
        return Response({"txid": txid})
