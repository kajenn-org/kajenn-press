"""Resolvers a page may use at render time, reaching data through named connections.

A page Bag names a connection; its configuration (address, credentials) comes from the
deployment of the server that renders, never from the Bag (d-resolver-config). A value
enters the page as text; with `html=True` it is HTML filtered like a content
(d-resolver-output).
"""

from typing import ClassVar

from genro_bag.resolver import BagResolver

from .contract import RenderProblem


class ConnectionResolver(BagResolver):
    """Base class: subclasses implement `fetch(config)` and return text."""

    class_kwargs: ClassVar[dict] = {
        "cache_time": 600,
        "read_only": False,
        "as_bag": False,
        "connection": None,
        "html": False,
    }

    def bind(self, connections):
        name = self._kw["connection"]
        if name not in connections:
            raise RenderProblem(
                "missing_connection", "The page names a connection this server lacks", name=name
            )
        self._config = connections[name]

    def load(self):
        value = self.fetch(self._config)
        if not self._kw["html"]:
            return value
        from .preparation import prepare_blocks

        prepared, _diagnostics = prepare_blocks(
            {"value": {"format": "html", "source": value}},
            {"value": {"format": "html", "required": False}},
            self._kw["connection"],
        )
        return prepared["value"]

    def fetch(self, config):
        raise NotImplementedError


class ConfigValueResolver(ConnectionResolver):
    """The value of one key of the connection configuration."""

    class_kwargs: ClassVar[dict] = {**ConnectionResolver.class_kwargs, "key": None}

    def fetch(self, config):
        return config[self._kw["key"]]
