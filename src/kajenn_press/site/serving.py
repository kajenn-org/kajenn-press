"""A Kajenn server application that serves published sites from their site index (N4).

It binds public origins to site ids, reads each site index from the release bucket at
most every `cache_seconds`, and answers page URLs with the HTML of the page version the
index pins, assets by content address, redirects with 301, `sitemap.xml`, `robots.txt`
and the 404 page. Pages whose Data uses resolvers are rendered again by the worker with
this server's named connections and kept in a local filesystem cache for their refresh
time (d-rerender-cache). It needs read-only release credentials only.
"""

import asyncio
import json
import mimetypes
import os
import threading
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from xml.sax.saxutils import escape

from genro_routes import route
from genro_storage import StorageManager
from genro_storage.exceptions import StorageError
from kajenn import AsgiServer, BaseApplication, RoutedApplication
from kajenn.response import Response

from ..catalog.errors import IntegrityError
from ..catalog.filesystem import private_directory, sync_directory, sync_file
from ..domain import DomainError
from ..publication.routes import origin, request_path
from .published import read_index, unpack_page
from .seo import NOT_FOUND_URL, ROOT_URL

MOUNT = "releases"
HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}
PAGE_HEADERS = {
    **HEADERS,
    "cache-control": "no-cache",
    "content-security-policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self' https:; "
        "object-src 'none'; base-uri 'none'"
    ),
}
ASSET_HEADERS = {**HEADERS, "cache-control": "public, max-age=31536000, immutable"}


class SiteReader:
    """The index of one site, reread at most every `cache_seconds`, and its page objects."""

    def __init__(self, storage, site_id, cache_seconds):
        self.storage, self.site_id, self.cache_seconds = storage, site_id, cache_seconds
        self.loaded, self.loaded_at = None, None
        self.pages = {}

    def read(self, path, version_id=None, attempts=5):
        full = f"{MOUNT}:{path}"
        for _ in range(attempts):
            try:
                node = (
                    self.storage.node(full, version=version_id)
                    if version_id
                    else self.storage.node(full)
                )
                return node.read_bytes()
            except OSError:
                # S3-compatible stores abort a read when the object is replaced meanwhile.
                time.sleep(0.05)
        raise DomainError("unavailable", "Release storage is unreadable")

    def index(self):
        if self.loaded is not None and time.monotonic() - self.loaded_at < self.cache_seconds:
            return self.loaded
        try:
            index = read_index(self.read(f"sites/{self.site_id}/index.json"))
            if index["site_id"] != self.site_id:
                raise IntegrityError("Index belongs to another site")
            self.loaded = index
        except (DomainError, IntegrityError, StorageError, OSError):
            # An index validated earlier keeps being served; nothing validated means 503.
            if self.loaded is None:
                raise DomainError("unavailable", "No valid site index in storage") from None
        self.loaded_at = time.monotonic()
        return self.loaded

    def page(self, entry):
        """The published page an index entry pins, kept in memory by key and version."""
        cached = (entry["key"], entry["version_id"])
        if cached not in self.pages:
            published = unpack_page(self.read(entry["key"], entry["version_id"]))
            self.pages = {k: v for k, v in self.pages.items() if k[0] != entry["key"]}
            self.pages[cached] = published
        return self.pages[cached]


class RenderCache:
    """Pages rendered again by the worker, one file per page version, kept on local disk."""

    def __init__(self, root, worker, connections):
        self.root = private_directory(root)
        self.worker, self.connections = worker, connections
        self.locks, self.mutex = {}, threading.Lock()

    def html(self, site_id, page_id, version_id, published, refresh):
        folder = private_directory(self.root / site_id / page_id)
        path = folder / f"{version_id}.html"
        if path.exists() and time.time() - path.stat().st_mtime < refresh:
            return path.read_text("utf-8")
        with self.mutex:
            lock = self.locks.setdefault((site_id, page_id), threading.Lock())
        with lock:
            if path.exists() and time.time() - path.stat().st_mtime < refresh:
                return path.read_text("utf-8")
            result = self.worker.render_page(
                {**json.loads(published.request), "connections": self.connections}
            )
            if result["status"] != "succeeded":
                # The last good rendering, or the one made at Publish, stays online.
                return path.read_text("utf-8") if path.exists() else published.html
            self.write(folder, path, result["html"])
            return result["html"]

    def write(self, folder, path, html):
        temporary = folder / f".{uuid4().hex}.tmp"
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(html)
            sync_file(stream)
        os.replace(temporary, path)
        for other in folder.glob("*.html"):
            if other != path:
                other.unlink()
        sync_directory(folder)


class SiteServerApplication(BaseApplication):
    """Kajenn application on the site root: answers every public path of the bound sites."""

    mount = ""

    def __init__(
        self,
        bindings,
        release_storage,
        cache_root,
        cache_seconds=5,
        worker=None,
        connections=None,
        **kwargs,
    ):
        storage = StorageManager()
        storage.configure([{"name": MOUNT, **release_storage}])
        self.readers = {
            origin(public_origin): SiteReader(storage, site_id, cache_seconds)
            for public_origin, site_id in bindings.items()
        }
        self.renders = RenderCache(cache_root, worker, connections or {}) if worker else None
        super().__init__(**kwargs)

    def binding(self, scope):
        hosts = [v.decode("ascii") for k, v in scope["headers"] if k.lower() == b"host"]
        if len(hosts) != 1 or "/" in hosts[0] or "@" in hosts[0]:
            raise DomainError("not_found", "Unknown host binding")
        return origin(scope["scheme"] + "://" + hosts[0])

    def respond(self, binding, path, method):
        if method not in ("GET", "HEAD"):
            return Response(
                "Method not allowed", status_code=405, headers={**HEADERS, "allow": "GET, HEAD"}
            )
        reader = self.readers.get(binding)
        if reader is None:
            raise DomainError("not_found", "Unknown site")
        index = reader.index()
        if index["maintenance"]:
            return Response(
                "Site under maintenance",
                status_code=503,
                headers={**HEADERS, "cache-control": "no-store", "retry-after": "300"},
            )
        if path == "/robots.txt":
            text = robots(binding, index)
            return Response(text, media_type="text/plain", headers=PAGE_HEADERS)
        if path == "/sitemap.xml":
            return Response(
                sitemap(binding, index), media_type="application/xml", headers=PAGE_HEADERS
            )
        if path in index["redirects"]:
            location = quote(index["redirects"][path], safe="/")
            return Response(status_code=301, headers={**HEADERS, "location": location})
        if path.startswith("/_assets/"):
            return self.asset(reader, index, path.removeprefix("/_assets/"))
        pages = {entry["url"]: page_id for page_id, entry in index["pages"].items()}
        if path not in pages and path + "/" in pages:
            return Response(
                status_code=301, headers={**HEADERS, "location": quote(path + "/", safe="/")}
            )
        if path in pages:
            return self.page(reader, index, pages[path], 200)
        if NOT_FOUND_URL in pages:
            return self.page(reader, index, pages[NOT_FOUND_URL], 404)
        raise DomainError("not_found", "No page at this URL")

    def page(self, reader, index, page_id, status):
        entry = index["pages"][page_id]
        published = reader.page(entry)
        html = published.html
        if entry["refresh"] and self.renders is not None:
            html = self.renders.html(
                index["site_id"], page_id, entry["version_id"], published, entry["refresh"]
            )
        return Response(
            html, status_code=status, media_type="text/html; charset=utf-8", headers=PAGE_HEADERS
        )

    def asset(self, reader, index, name):
        for entry in index["pages"].values():
            if name in entry["assets"]:
                data = reader.page(entry).assets[name]
                media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
                return Response(data, media_type=media_type, headers=ASSET_HEADERS)
        raise DomainError("not_found", "No such asset")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        try:
            binding = self.binding(scope)
            path = request_path(scope.get("raw_path", scope["path"].encode()))
            response = await asyncio.to_thread(self.respond, binding, path, scope["method"])
        except (DomainError, IntegrityError, UnicodeError, ValueError) as exc:
            response = (
                Response(
                    "Site unavailable",
                    status_code=503,
                    headers={**HEADERS, "cache-control": "no-store"},
                )
                if getattr(exc, "code", None) == "unavailable"
                else Response(
                    "Not found", status_code=404, headers={**HEADERS, "cache-control": "no-store"}
                )
            )
        if scope["method"] == "HEAD":
            response.body = b""
        await response(scope, receive, send)


def robots(binding, index):
    """Closed to robots when the root page is not indexable, else open with the sitemap."""
    root = [entry for entry in index["pages"].values() if entry["url"] == ROOT_URL]
    if root and not root[0]["indexable"]:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\nSitemap: {binding}/sitemap.xml\n"


def sitemap(binding, index):
    urls = sorted(entry["url"] for entry in index["pages"].values() if entry["indexable"])
    body = "".join(
        f"<url><loc>{escape(binding + quote(url, safe='/'))}</loc></url>" for url in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    )


class SiteServerHealth(RoutedApplication):
    @route()
    def health(self) -> dict:
        return {"ok": True}


def create_site_server(
    *, bindings, release_storage, cache_root, cache_seconds=5, worker=None, connections=None
):
    """A Kajenn server whose root application serves `{public origin: site id}`."""
    return AsgiServer(
        # Public pages carry no session: no cookie on any response.
        middleware={"session": False},
        applications=[
            (SiteServerHealth, {"code": "health", "mount": "_health"}),
            (
                SiteServerApplication,
                {
                    "code": "site",
                    "bindings": bindings,
                    "release_storage": release_storage,
                    "cache_root": str(Path(cache_root)),
                    "cache_seconds": cache_seconds,
                    "worker": worker,
                    "connections": connections,
                },
            ),
        ],
    )
