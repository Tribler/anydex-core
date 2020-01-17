from aiohttp import WSMsgType, web

from anydex.restapi.base_market_endpoint import BaseMarketEndpoint


class AnyDexWebsocketProtocol(BaseMarketEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('/ws', self.handle_websockets)])

    async def handle_websockets(self, request):
        print("WebSocket connection open")

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                else:
                    await ws.send_str(msg.data + '/answer')
            elif msg.type == WSMsgType.ERROR:
                print('WebSocket connection closed with exception %s' % ws.exception())

        print('WebSocket connection closed')
        return ws
