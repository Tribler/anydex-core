import logging

from aiohttp import web

from ipv8.taskmanager import TaskManager

from anydex.restapi.root_endpoint import RootEndpoint


class RESTManager(TaskManager):
    """
    This class is responsible for managing the startup and closing of the HTTP API.
    """

    def __init__(self, session):
        super(RESTManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.site = None
        self.root_endpoint = None
        self.port = None

    async def start(self, port=8090):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self.port = port
        self.root_endpoint = RootEndpoint()
        self.root_endpoint.initialize(self.session)
        runner = web.AppRunner(self.root_endpoint.app, access_log=None)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', port)
        await self.site.start()

    async def stop(self):
        """
        Stop the HTTP API and return a deferred that fires when the server has shut down.
        """
        await self.site.stop()
