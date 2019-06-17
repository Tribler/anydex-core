from __future__ import absolute_import

import logging

from ipv8.REST.rest_manager import RESTRequest
from ipv8.taskmanager import TaskManager

from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.web import server

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

    def start(self, port=8090):
        """
        Starts the HTTP API with the listen port as specified in the session configuration.
        """
        self.port = port
        self.root_endpoint = RootEndpoint(self.session)
        site = server.Site(resource=self.root_endpoint)
        site.requestFactory = RESTRequest
        self.site = reactor.listenTCP(port, site, interface="127.0.0.1")

    def stop(self):
        """
        Stop the HTTP API and return a deferred that fires when the server has shut down.
        """
        return maybeDeferred(self.site.stopListening)
