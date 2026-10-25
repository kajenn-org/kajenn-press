"""Immutable payloads using only public Genro Storage streams.

Directory fsync operates on the explicitly configured local root, never a
Storage backend's private path. Payload bytes only pass through StorageNode.open.
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from genro_storage import StorageManager

from .catalog.errors import IntegrityError, UnsupportedProfile
from .catalog.filesystem import contained_file, digest, private_directory, sync_directory, sync_file


@dataclass(frozen=True)
class ObjectRef:
    key: str
    sha256: str
    size: int
    schema: int = 1

    def __post_init__(self):
        if (
            type(self.schema) is not int
            or self.schema != 1
            or not isinstance(self.key, str)
            or re.fullmatch(r"[0-9a-f]{32}", self.key) is None
            or not isinstance(self.sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None
            or type(self.size) is not int
            or self.size < 0
        ):
            raise IntegrityError("Invalid payload reference")


class ObjectStore:
    """Trusted local backend, not an authorization or public file-serving API."""

    def __init__(self, root):
        self.root = private_directory(Path(root))
        self.storage = StorageManager()
        self.storage.configure(
            [{"name": "payloads", "protocol": "local", "base_path": str(self.root)}]
        )
        self.qualify()

    def qualify(self):
        ref = ObjectRef(uuid4().hex, digest(b"probe"), 5)
        try:
            self.prepare(ref, b"probe")
            try:
                with self.storage.node(f"payloads:{ref.key}.blob").open("xb"):
                    pass
            except FileExistsError:
                pass
            else:
                raise ValueError("Storage exclusive create did not reject an existing file")
            if self.read(ref) != b"probe":
                raise ValueError("Payload readback failed")
        except (OSError, ValueError, AttributeError, IntegrityError) as exc:
            raise UnsupportedProfile(
                "Local Storage needs exclusive streams, fileno and durable flush"
            ) from exc
        finally:
            # Remove only this disposable qualification object via the public API.
            node = self.storage.node(f"payloads:{ref.key}.blob")
            if node.exists:
                node.delete()
                sync_directory(self.root)

    def prepare(self, ref, data):
        if not isinstance(data, bytes) or len(data) != ref.size or digest(data) != ref.sha256:
            raise IntegrityError("Payload does not match its reference")
        contained_file(self.root, ref.key + ".blob")
        with self.storage.node(f"payloads:{ref.key}.blob").open("xb") as stream:
            stream.write(data)
            sync_file(stream)
        sync_directory(self.root)
        self.read(ref)

    def read(self, ref):
        if isinstance(ref, dict):
            try:
                ref = ObjectRef(**ref)
            except TypeError as exc:
                raise IntegrityError("Invalid payload reference schema") from exc
        contained_file(self.root, ref.key + ".blob")
        with self.storage.node(f"payloads:{ref.key}.blob").open("rb") as stream:
            data = stream.read()
        if len(data) != ref.size or digest(data) != ref.sha256:
            raise IntegrityError(f"Payload checksum mismatch: {ref.key}")
        return data

    def reference(self, data):
        return asdict(ObjectRef(uuid4().hex, digest(data), len(data)))
