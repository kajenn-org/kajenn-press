"""The server agent: a Kajenn application the manager calls to serve a site's names (N7b).

It has four actions and no generic shell (d-server-agent): add, remove and read the
state of a site's names on the proxy installed on the server, and reload that proxy.
It answers only bearer tokens with the `manager` tag, from client addresses in its
allow-list; the network limit (firewall or tunnel) belongs to the server's installation.
"""

from typing import ClassVar

from genro_routes import route
from kajenn import AsgiServer, HTTPException, McpOpenApiApplication

from ..domain import DomainError

ERROR_STATUS = {"invalid_input": 422, "unavailable": 503, "forbidden": 403}


class AgentApplication(McpOpenApiApplication):
    openapi_info: ClassVar[dict] = {
        "title": "kajenn-press agent",
        "version": "0.1.0",
        "description": "Serve a site's names on this server's proxy",
    }
    mcp_name = "kajenn-press-agent"

    def __init__(self, driver, allowed, **kwargs):
        self.driver, self.allowed = driver, set(allowed)
        super().__init__(**kwargs)

    def _call(self, request, action, *arguments):
        if request is None or request.avatar() is None:
            raise HTTPException(401, "Authentication required")
        if request.scope["method"] != "POST":
            raise HTTPException(405, "Actions require POST")
        client = (request.scope.get("client") or ("",))[0]
        try:
            if client not in self.allowed:
                raise DomainError("forbidden", "This address may not call the agent")
            result = getattr(self.driver, action)(*arguments)
            return {"ok": True, "result": {"proxy": self.driver.name, **(result or {})}}
        except DomainError as exc:
            request.response.status_code = ERROR_STATUS.get(exc.code, 422)
            return {"ok": False, "error": exc.as_dict()}

    @route(channel_channels="rest", auth_rule="manager", openapi_method="post")
    def domain_add(self, names: list, _request=None) -> dict:
        """Serve these names (the address, and its alias) through the proxy, with TLS."""
        return self._call(_request, "add", names)

    @route(channel_channels="rest", auth_rule="manager", openapi_method="post")
    def domain_remove(self, names: list, _request=None) -> dict:
        """Stop serving these names."""
        return self._call(_request, "remove", names)

    @route(channel_channels="rest", auth_rule="manager", openapi_method="post")
    def domain_status(self, names: list, _request=None) -> dict:
        """Whether the names are configured and how their certificate is obtained."""
        return self._call(_request, "status", names)

    @route(channel_channels="rest", auth_rule="manager", openapi_method="post")
    def proxy_reload(self, _request=None) -> dict:
        """Reload the proxy's configuration."""
        return self._call(_request, "reload")


def create_agent_server(*, token, driver, allowed):
    """The agent's Kajenn server: one bearer token with the `manager` tag."""
    return AsgiServer(
        applications=[
            (AgentApplication, {"code": "agent", "mount": "", "driver": driver, "allowed": allowed})
        ],
        auth={"bearer": {"manager": {"token": token, "tags": "manager"}}},
        middleware={"session": False},
        credential_cache_ttl=0,
    )
