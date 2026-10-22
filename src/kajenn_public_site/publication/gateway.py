"""Explicit origin dispatch and per-request access checks around Kajenn."""

import asyncio
import hashlib
import re
from http.cookies import CookieError, SimpleCookie
from urllib.parse import quote

from kajenn.response import Response

from ..catalog.errors import CatalogError
from ..domain import DomainError
from .routes import origin, request_path
from .serving import PUBLIC_HEADERS

PRIVATE_HEADERS = {
    "cache-control": "no-store, private",
    "x-robots-tag": "noindex, nofollow, noarchive",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "cross-origin-resource-policy": "same-origin",
}
ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
BOOTSTRAP = """<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Anteprima privata</title></head><body><p id="status">Apertura anteprima…</p><script>
const token = location.hash.slice(1);
history.replaceState(null, '', location.pathname);
fetch(location.pathname.replace('/open/', '/access/'), {
  method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'text/plain'}, body: token
}).then(async response => {
  if (!response.ok) throw new Error('Accesso scaduto o revocato');
  location.replace(await response.text());
}).catch(() => {document.getElementById('status').textContent = 'Anteprima non disponibile: link scaduto o revocato.';});
</script></body></html>"""


class PreviewGateway:
    def __init__(self, server, management_origin, preview_origin):
        self.server = server
        self.management_origin, self.preview_origin = (
            origin(management_origin),
            origin(preview_origin),
        )
        if self.management_origin == self.preview_origin:
            raise ValueError("Preview must use another origin")

    @property
    def applications(self):
        return self.server.applications

    @property
    def publication(self):
        return self.applications["public_site"].publication

    def binding(self, scope):
        hosts = [v.decode("ascii") for k, v in scope["headers"] if k.lower() == b"host"]
        if len(hosts) != 1 or "/" in hosts[0] or "@" in hosts[0]:
            raise DomainError("invalid_origin", "Unknown host binding")
        return origin(scope["scheme"] + "://" + hosts[0])

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.server(scope, receive, send)
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        try:
            binding = self.binding(scope)
        except (DomainError, UnicodeError, ValueError):
            binding = None
        if binding == self.management_origin:
            # Deployment must keep management credentials host-only. Preview never
            # calls the management application, even with a supplied bearer header.
            return await self.server(scope, receive, send)
        response = Response("Not found", status_code=404, headers=PRIVATE_HEADERS)
        if binding == self.preview_origin and self.publication is not None:
            try:
                path = request_path(scope.get("raw_path", scope["path"].encode()))
                body = b""
                if scope["method"] == "POST" and path.startswith("/access/"):
                    while True:
                        event = await asyncio.wait_for(receive(), timeout=5)
                        if event["type"] != "http.request":
                            raise DomainError("forbidden", "Disconnected")
                        body += event.get("body", b"")
                        if len(body) > 128:
                            raise DomainError("forbidden", "Invalid credential")
                        if not event.get("more_body"):
                            break
                response = await asyncio.to_thread(self.preview_response, scope, path, body)
            except (DomainError, UnicodeError, ValueError, TimeoutError, CookieError):
                response = Response("Preview unavailable", status_code=404, headers=PRIVATE_HEADERS)
        if self.publication is not None and binding in self.publication.public_origins:
            try:
                path = request_path(scope.get("raw_path", scope["path"].encode()))
                response = await asyncio.to_thread(
                    self.publication.public_response, binding, path, scope["method"]
                )
            except DomainError:
                response = Response("Not found", status_code=404, headers=PUBLIC_HEADERS)
            except CatalogError:
                response = Response("Release unavailable", status_code=503, headers=PUBLIC_HEADERS)
        if scope["method"] == "HEAD":
            response.body = b""
        await response(scope, receive, send)

    def preview_response(self, scope, path, body):
        headers = dict(scope["headers"])
        method = scope["method"]
        parts = path.strip("/").split("/")
        if (
            len(parts) == 2
            and parts[0] == "open"
            and ID.fullmatch(parts[1])
            and method in {"GET", "HEAD"}
        ):
            response = Response(BOOTSTRAP, media_type="text/html", headers=PRIVATE_HEADERS)
            script = BOOTSTRAP.split("<script>", 1)[1].split("</script>", 1)[0]
            import base64

            script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
            response.set_header(
                "content-security-policy",
                "default-src 'none'; script-src 'sha256-"
                + script_hash
                + "'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
            )
            return response
        if len(parts) == 2 and parts[0] == "access" and ID.fullmatch(parts[1]) and method == "POST":
            # Fragment-to-body exchange accepts only the configured origin and a
            # simple bounded token. No secret goes into redirects or query logs.
            if headers.get(b"origin", b"").decode() != self.preview_origin:
                raise DomainError("forbidden", "Cross-origin exchange denied")
            grant, job = self.publication.preview_access(parts[1], body.decode("ascii"))
            build_id = job["record_id"]
            target = "/preview/" + build_id + "/"
            response = Response(target, media_type="text/plain", headers=PRIVATE_HEADERS)
            response.set_cookie(
                "preview_" + build_id,
                grant["record_id"] + "." + body.decode(),
                path=target,
                secure=self.preview_origin.startswith("https:"),
                httponly=True,
                samesite="strict",
            )
            return response
        if (
            len(parts) >= 2
            and parts[0] == "preview"
            and ID.fullmatch(parts[1])
            and method in {"GET", "HEAD"}
        ):
            build_id = parts[1]
            cookies = SimpleCookie()
            cookies.load(headers.get(b"cookie", b"").decode("ascii"))
            cookie = cookies.get("preview_" + build_id)
            if cookie is None or "." not in cookie.value:
                raise DomainError("forbidden", "Missing preview access")
            grant_id, token = cookie.value.split(".", 1)
            _, job = self.publication.preview_access(grant_id, token, build_id)
            prefix = "/preview/" + build_id
            route = path[len(prefix) :]
            manifest = self.publication.sealed_manifest(job)
            if route in manifest["redirects"]:
                response = Response(status_code=307, headers=PRIVATE_HEADERS)
                response.set_header(
                    "location", prefix + quote(manifest["redirects"][route], safe="/")
                )
                return response
            raw, mime = self.publication.artifact(job, "preview", route)
            response = Response(raw, media_type=mime, headers=PRIVATE_HEADERS)
            response.set_header(
                "content-security-policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
            return response
        raise DomainError("not_found", "Preview route not found")
