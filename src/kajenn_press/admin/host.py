"""Public Gramlot adapter, trusted request context and management-origin boundary."""

import asyncio
import json
from contextvars import ContextVar
from importlib.resources import files
from pathlib import Path

from genro_routes import route
from gramlot_py_server.kajenn import Application
from kajenn.config.templates import ShortcutConfiguration
from kajenn.response import Response

from ..domain import DomainError
from ..publication.routes import origin

CURRENT_REQUEST = ContextVar("public_site_admin_request")
LOGO_URL = "/assets/branding/kajenn-press-256.png"
# Pages live below the administration mount, so they reference assets relatively.
LOGO_SRC = LOGO_URL.removeprefix("/")
READ_OPERATIONS = frozenset(
    {
        "sites_list",
        "records_index",
        "revision_index",
        "scope_capabilities",
        "record_read",
        "child_list",
        "child_channels",
        "publication_overview",
    }
)


async def execute_read(operation, **arguments):
    if operation not in READ_OPERATIONS:
        raise DomainError("invalid_operation", "Unsupported administration read")
    return await execute_service(operation, arguments)


async def execute_site_create(**arguments):
    return await execute_service("site_create", arguments)


async def execute_service(operation, arguments):
    request = CURRENT_REQUEST.get()
    avatar = request.avatar()
    if avatar is None or "editor" not in avatar.tags:
        raise DomainError("unauthenticated", "Sign in to continue")
    application = request.server.applications["press"]
    result = await asyncio.to_thread(application._execute, request, operation, arguments)
    if not result["ok"]:
        error = result["error"]
        raise DomainError(error["code"], error["message"])
    return result["result"]


class AdminConfiguration(ShortcutConfiguration):
    def applications_section(self, cfg):
        apps = cfg.applications(default=self.default_code)
        for app_class, params in self.app_entries:
            node = apps.application(**params, app_class=app_class)
            if issubclass(app_class, AdminApplication):
                node.request(body="raw")


class AdminApplication(Application):
    def __init__(self, **kwargs):
        core = files("gramlot")
        collections, assets = [], {}
        for name in ("layout", "tree", "inputs", "editors"):
            collections.append(
                {
                    "grammar": json.loads(core.joinpath(f"collections/{name}.json").read_text()),
                    "module": f"/assets/{name}.js",
                }
            )
        resources = core.joinpath("resources/components")
        # Serve only the shipped collection files, including lazy engine chunks.
        for resource in resources.rglob("*"):
            if resource.is_file() and resource.suffix in {".js", ".css", ".woff2"}:
                relative = resource.relative_to(resources).as_posix()
                assets[f"/assets/{relative}"] = {
                    "file": resource,
                    "type": {".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2"}[
                        resource.suffix
                    ],
                }
        assets[LOGO_URL] = {
            "file": Path(__file__).parent / "branding" / "kajenn-press-256.png",
            "type": "image/png",
        }
        super().__init__(
            Path(__file__).parent / "pages",
            collections=collections,
            assets=assets,
            content_security_policy=(
                "default-src 'self'; script-src 'self' 'unsafe-eval' 'nonce-{nonce}'; "
                "style-src 'self' 'unsafe-inline' data:; img-src 'self' data:; "
                "connect-src 'self'; frame-src 'self' about:; object-src 'none'; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
            ),
            **kwargs,
        )

    @route(media_type="text/html")
    async def index(self, *segments, _request, body_raw=None, **query):
        token = CURRENT_REQUEST.set(_request)
        try:
            return await super().index(*segments, _request=_request, body_raw=body_raw, **query)
        finally:
            CURRENT_REQUEST.reset(token)


class ManagementGuard:
    """Origin checks for browser sessions without constraining bearer API clients."""

    def __init__(self, server, management_origin):
        self.server = server
        self.origin = origin(management_origin)

    @property
    def applications(self):
        return self.server.applications

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.server(scope, receive, send)
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        headers = {}
        for name, value in scope["headers"]:
            headers.setdefault(name.lower(), []).append(value.decode("latin-1"))
        hosts, origins = headers.get(b"host", []), headers.get(b"origin", [])
        valid_host = len(hosts) == 1 and scope["scheme"] + "://" + hosts[0] == self.origin
        if not valid_host:
            response = Response("Not found", status_code=404)
        elif scope["path"] in {"/_server/login", "/_server/logout"} and scope["method"] != "POST":
            response = Response("POST required", status_code=405)
        elif scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            authorization = headers.get(b"authorization", [])
            bearer = len(authorization) == 1 and authorization[0].startswith("Bearer ")
            if origins != [self.origin] and (origins or not bearer):
                response = Response("Same-origin request required", status_code=403)
            else:
                if not origins and bearer:
                    # API requests cannot fall back to browser session credentials.
                    scope = {
                        **scope,
                        "headers": [(k, v) for k, v in scope["headers"] if k.lower() != b"cookie"],
                    }
                return await self.server(scope, receive, send)
        else:
            return await self.server(scope, receive, send)
        response.set_header("cache-control", "no-store")
        await response(scope, receive, send)
