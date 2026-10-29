"""The registry of servers that serve published sites (N7b, d-server-registry).

A server is a host running the Kajenn site server image and an agent. The registry is
`servers.json` in the source bucket: name, public IPv4 and IPv6 addresses, and the URL
of the server's agent. Agent tokens are secret files of the manager, never written here.
"""

import ipaddress
import json
import re
from urllib.parse import urlsplit

from ..domain import DomainError
from .store import MOUNT

SCHEMA = 1
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
PATH = "servers.json"


def checked_addresses(values, version):
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise DomainError("invalid_input", f"IPv{version} addresses are a list of strings")
    found = []
    for value in values:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise DomainError("invalid_input", f"{value} is not an IP address") from exc
        if address.version != version:
            raise DomainError("invalid_input", f"{value} is not an IPv{version} address")
        found.append(str(address))
    return found


def checked_agent_url(value):
    parts = urlsplit(value) if isinstance(value, str) else None
    loopback = parts is not None and parts.hostname in ("127.0.0.1", "localhost", "::1")
    if (
        parts is None
        or not parts.hostname
        or parts.scheme not in ("https", "http")
        or (parts.scheme == "http" and not loopback)
        or parts.query
        or parts.fragment
    ):
        raise DomainError("invalid_input", "The agent URL is https (http only on loopback)")
    return value.rstrip("/")


class ServerRegistry:
    """`servers.json` in the source bucket, read and written by the manager only."""

    def __init__(self, source_store):
        self.storage = source_store.storage

    def node(self):
        return self.storage.node(f"{MOUNT}:{PATH}")

    def servers(self):
        node = self.node()
        if not node.exists():
            return {}
        document = json.loads(node.read_bytes())
        if not isinstance(document, dict) or document.get("schema") != SCHEMA:
            raise DomainError("conflict", "The server registry has an unknown schema")
        return document["servers"]

    def write(self, servers):
        raw = json.dumps({"schema": SCHEMA, "servers": servers}, sort_keys=True)
        self.node().write_bytes(raw.encode("utf-8"))

    def add(self, name, ipv4, ipv6, agent_url):
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise DomainError("invalid_input", "A server name is lower case: letters, digits, -")
        servers = self.servers()
        if name in servers:
            raise DomainError("conflict", f"A server named {name} exists", resource_id=name)
        entry = {
            "ipv4": checked_addresses(ipv4, 4),
            "ipv6": checked_addresses(ipv6, 6),
            "agent_url": checked_agent_url(agent_url),
        }
        if not entry["ipv4"] and not entry["ipv6"]:
            raise DomainError("invalid_input", "A server needs at least one address")
        servers[name] = entry
        self.write(servers)
        return {"name": name, **entry}

    def get(self, name):
        servers = self.servers()
        if name not in servers:
            raise DomainError("not_found", f"No server {name}", resource_id=name)
        return servers[name]

    def remove(self, name, bound_sites):
        """Remove a server that serves no site; `bound_sites` are the sites bound to it."""
        self.get(name)
        if bound_sites:
            raise DomainError(
                "conflict", f"Server {name} serves {len(bound_sites)} sites: move them first"
            )
        servers = self.servers()
        del servers[name]
        self.write(servers)
