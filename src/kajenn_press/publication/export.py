"""Activated releases copied to a Genro Storage mount for servers without the catalog.

The catalog stays authoritative. Storage receives immutable content-addressed
artifacts, the sealed manifests, then one pointer per channel written last.
"""

import json
import threading
import time
from uuid import uuid4

from genro_storage import StorageManager

from ..catalog.filesystem import digest
from ..domain import DomainError

MOUNT = "releases"
POINTER_SCHEMA = 1


class ReleaseStorage:
    def __init__(self, publication, config):
        if not isinstance(config, dict) or "protocol" not in config or "name" in config:
            raise ValueError("Release storage needs a Genro Storage mount without a name")
        self.publication = publication
        self.storage = StorageManager()
        self.storage.configure([{"name": MOUNT, **config}])
        self.qualify()

    def node(self, path):
        return self.storage.node(f"{MOUNT}:{path}")

    def qualify(self, size=262144, min_reads=200, min_seconds=0.5, budget=20.0):
        """Refuse a backend that loses bytes or exposes a partially replaced object.

        Replacements continue for at least `min_seconds` and until the reader has
        completed `min_reads` reads during them: a short or fixed run let the reader
        miss every replacement window.
        """
        probe = f"qualification/{uuid4().hex}"
        raw = uuid4().bytes * (size // 16)
        self.node(probe).write_bytes(raw)
        if digest(self.node(probe).read_bytes()) != digest(raw):
            raise ValueError("Release storage returned different bytes")
        versions = [json.dumps({"n": n, "pad": "x" * size}).encode() for n in range(2)]
        self.node(probe).write_bytes(versions[0])
        stop, partial, reads = threading.Event(), [], [0]

        def reader():
            while not stop.is_set():
                try:
                    body = self.node(probe).read_bytes()
                except OSError:
                    # S3-compatible stores abort a read when the object changes; retry.
                    continue
                reads[0] += 1
                if body not in versions:
                    partial.append(len(body))

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        started, writes = time.monotonic(), 0
        try:
            while not partial and (
                reads[0] < min_reads or time.monotonic() - started < min_seconds
            ):
                if time.monotonic() - started > budget:
                    raise ValueError("Release storage too slow to observe concurrent reads")
                writes += 1
                self.node(probe).write_bytes(versions[writes % 2])
        finally:
            stop.set()
            thread.join()
            self.node(probe).delete()
        if partial:
            raise ValueError(
                "Release storage exposes partially replaced objects to readers "
                f"({len(partial)} partial reads); see genro-org/genro-storage#83"
            )

    def write_once(self, path, raw):
        """Immutable objects are content-addressed: an existing one is never rewritten."""
        node = self.node(path)
        if not node.exists():
            node.write_bytes(raw)

    def pointer_path(self, settings_id):
        return f"pointers/{settings_id}.json"

    def read_pointer(self, settings_id, attempts=5):
        node = self.node(self.pointer_path(settings_id))
        for _ in range(attempts):
            try:
                if not node.exists():
                    return None
                return json.loads(node.read_bytes())
            except OSError:
                time.sleep(0.05)
        raise DomainError("unavailable", "Release storage pointer is unreadable")

    def export(self, snapshot, settings_id):
        service = self.publication
        channel = service.find(snapshot, "publication_channel", settings_id=settings_id)
        if channel is None or not channel["data"]["attributes"].get("active_revision"):
            raise DomainError("not_found", "No active release to export")
        active = snapshot.revisions[channel["data"]["attributes"]["active_revision"]]
        history = []
        for activation in service.activations(snapshot, settings_id):
            job = snapshot.revisions[activation["data"]["attributes"]["build_revision"]]
            if job["id"] not in [item["id"] for item in history]:
                history.append(job)
        manifests = []
        for job in history:
            manifest_digest = job["data"]["attributes"]["manifest_digest"]
            manifests.append(manifest_digest)
            if self.node(f"manifests/{manifest_digest}.json").exists():
                # A manifest is written after its objects: a stored one has all of them.
                continue
            raw = service.catalog.read_payload(job["id"], "manifest")
            if digest(raw) != manifest_digest:
                raise DomainError("invalid_output", "Sealed manifest digest differs")
            manifest = json.loads(raw)
            for item in manifest["artifacts"]["public"].values():
                body = service.catalog.read_payload(job["id"], item["payload"])
                if digest(body) != item["sha256"] or len(body) != item["size"]:
                    raise DomainError("invalid_output", "Artifact integrity failure")
                self.write_once("objects/" + item["sha256"], body)
            self.write_once(f"manifests/{manifest_digest}.json", raw)
        attrs = channel["data"]["attributes"]
        pointer = {
            "schema": POINTER_SCHEMA,
            "site_id": attrs["site_id"],
            "settings_id": settings_id,
            "public_origin": service.release_origin(snapshot, active),
            "build_id": attrs["active_build"],
            "manifest_digest": active["data"]["attributes"]["manifest_digest"],
            "channel_generation": channel["generation"],
            "history": manifests,
        }
        # Written last: a reader that sees this pointer finds every file it names.
        self.node(self.pointer_path(settings_id)).write_bytes(
            json.dumps(pointer, sort_keys=True).encode()
        )
        return pointer

    def status(self, snapshot, settings_id):
        channel = self.publication.find(snapshot, "publication_channel", settings_id=settings_id)
        pointer = self.read_pointer(settings_id)
        current = (
            channel is not None
            and pointer is not None
            and pointer["channel_generation"] == channel["generation"]
            and pointer["build_id"] == channel["data"]["attributes"]["active_build"]
        )
        return {"state": "exported" if current else "pending", "pointer": pointer}
