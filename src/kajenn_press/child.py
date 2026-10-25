"""Public pages served from release storage, without catalog, Gramlot or render worker.

`StaticSiteServerApplication` is mounted on the site root of a Kajenn server: it
binds public origins to channel pointers written by an installation
(`publication/export.py`) and answers with the same rules as the installation's
own public serving (`publication/serving.py`).
"""

import asyncio
import hashlib
import json
import time

from genro_routes import route
from genro_storage import StorageManager
from genro_storage.exceptions import StorageError
from kajenn import AsgiServer, BaseApplication, RoutedApplication
from kajenn.response import Response

from .domain import DomainError
from .publication.routes import origin, request_path
from .publication.serving import PUBLIC_HEADERS, method_response, release_response

MOUNT = "releases"


class ReleaseReader:
    """The validated release of one channel, reread from storage at most every `cache_seconds`."""

    def __init__(self, storage, settings_id, cache_seconds):
        self.storage, self.settings_id, self.cache_seconds = storage, settings_id, cache_seconds
        self.loaded, self.loaded_at = None, None

    def read(self, path, attempts=5):
        # S3-compatible stores abort a read when the object is replaced meanwhile.
        for _ in range(attempts):
            try:
                return self.storage.node(f"{MOUNT}:{path}").read_bytes()
            except OSError:
                time.sleep(0.05)
        raise DomainError("unavailable", "Release storage is unreadable")

    def current(self):
        if self.loaded is not None and time.monotonic() - self.loaded_at < self.cache_seconds:
            return self.loaded
        try:
            self.loaded = self.load()
        except (DomainError, StorageError, OSError, ValueError, KeyError, TypeError):
            # A release validated earlier keeps being served; nothing validated means 503.
            if self.loaded is None:
                raise DomainError("unavailable", "No valid release in storage") from None
        self.loaded_at = time.monotonic()
        return self.loaded

    def load(self):
        pointer = json.loads(self.read(f"pointers/{self.settings_id}.json"))
        if pointer["schema"] != 1 or pointer["settings_id"] != self.settings_id:
            raise ValueError("Pointer belongs to another schema or channel")
        manifests = {}
        for manifest_digest in [*pointer["history"], pointer["manifest_digest"]]:
            raw = self.read(f"manifests/{manifest_digest}.json")
            if hashlib.sha256(raw).hexdigest() != manifest_digest:
                raise ValueError("Manifest digest differs")
            manifests[manifest_digest] = json.loads(raw)
        return pointer, manifests

    def artifact(self, item):
        raw = self.read("objects/" + item["sha256"])
        if hashlib.sha256(raw).hexdigest() != item["sha256"] or len(raw) != item["size"]:
            raise DomainError("unavailable", "Artifact integrity failure")
        return raw


class StaticSiteServerApplication(BaseApplication):
    """Kajenn application on the site root: answers every public path from release storage."""

    mount = ""

    def __init__(self, bindings, release_storage, cache_seconds=5, **kwargs):
        if not isinstance(release_storage, dict) or "name" in release_storage:
            raise ValueError("Release storage needs a Genro Storage mount without a name")
        storage = StorageManager()
        storage.configure([{"name": MOUNT, **release_storage}])
        self.readers = {
            origin(public_origin): ReleaseReader(storage, settings_id, cache_seconds)
            for public_origin, settings_id in bindings.items()
        }
        super().__init__(**kwargs)

    def binding(self, scope):
        hosts = [v.decode("ascii") for k, v in scope["headers"] if k.lower() == b"host"]
        if len(hosts) != 1 or "/" in hosts[0] or "@" in hosts[0]:
            raise DomainError("invalid_origin", "Unknown host binding")
        return origin(scope["scheme"] + "://" + hosts[0])

    def respond(self, binding, path, method):
        refused = method_response(method)
        if refused is not None:
            return refused
        if binding not in self.readers:
            raise DomainError("not_found", "Unknown site")
        pointer, manifests = self.readers[binding].current()
        if pointer["public_origin"] != binding:
            raise DomainError("not_found", "Release targets another origin")
        manifest = manifests[pointer["manifest_digest"]]
        if path.startswith("/_releases/"):
            # Assets of any release this channel activated stay reachable, newest first.
            manifest = next(
                (
                    manifests[d]
                    for d in reversed(pointer["history"])
                    if path in manifests[d]["artifacts"]["public"]
                ),
                None,
            )
            if manifest is None:
                raise DomainError("not_found", "Asset was never publicly eligible here")
        return release_response(manifest, path, self.readers[binding].artifact)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        try:
            binding = self.binding(scope)
            path = request_path(scope.get("raw_path", scope["path"].encode()))
            response = await asyncio.to_thread(self.respond, binding, path, scope["method"])
        except (DomainError, UnicodeError, ValueError) as exc:
            response = (
                Response("Release unavailable", status_code=503, headers=PUBLIC_HEADERS)
                if getattr(exc, "code", None) == "unavailable"
                else Response("Not found", status_code=404, headers=PUBLIC_HEADERS)
            )
        if scope["method"] == "HEAD":
            response.body = b""
        await response(scope, receive, send)


class StaticSiteHealth(RoutedApplication):
    @route()
    def health(self) -> dict:
        return {"ok": True}


def create_static_site_server(*, bindings, release_storage, cache_seconds=5):
    """A Kajenn server whose root application serves `{public origin: settings_id}`."""
    return AsgiServer(
        # Public static pages carry no session: no cookie on any response.
        middleware={"session": False},
        applications=[
            (StaticSiteHealth, {"code": "health", "mount": "_health"}),
            (
                StaticSiteServerApplication,
                {
                    "code": "site",
                    "bindings": bindings,
                    "release_storage": release_storage,
                    "cache_seconds": cache_seconds,
                },
            ),
        ]
    )
