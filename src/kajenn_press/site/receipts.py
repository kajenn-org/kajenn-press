"""Idempotency of site mutations (d-idempotency): receipts kept 24 hours by the manager.

A mutation carries a key chosen by the client. Repeating the key with the same input
returns the first result without applying the mutation again; reusing it with another
input is a conflict. Receipts older than the retention are dropped. A crash between the
mutation and its receipt makes the retry apply again: the receipt is written after the
mutation, not with it.
"""

import time
from threading import RLock

from ..catalog.filesystem import (
    contained_file,
    digest,
    encode,
    private_directory,
    publish_json,
    read_json,
    sync_directory,
)
from ..domain import DomainError

RETENTION_SECONDS = 24 * 60 * 60


class Receipts:
    def __init__(self, root, retention=RETENTION_SECONDS, clock=time.time):
        self.root = private_directory(root)
        self.staging = private_directory(self.root / "staging")
        self.retention = retention
        self.clock = clock
        self._mutex = RLock()

    def run(self, identity, key, operation, arguments, action):
        """Apply `action()` once per (identity, key); its result must be JSON."""
        if not isinstance(key, str) or not key or len(key) > 256:
            raise DomainError(
                "invalid_input", "A nonempty key of at most 256 characters is required"
            )
        fingerprint = digest(encode([operation, arguments]))
        name = digest(encode([identity, key])) + ".json"
        with self._mutex:
            receipt = self.read(name)
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise DomainError("conflict", "Idempotency key reused with different input")
                return receipt["result"]
            result = action()
            publish_json(
                self.root,
                name,
                {"fingerprint": fingerprint, "result": result, "at": self.clock()},
                self.staging,
            )
            return result

    def read(self, name):
        """A receipt still within the retention, or None."""
        path = contained_file(self.root, name)
        if not path.exists():
            return None
        receipt = read_json(self.root, name)[0]
        if self.clock() - receipt["at"] > self.retention:
            return None
        return receipt

    def purge(self):
        """Delete receipts older than the retention; returns how many were deleted."""
        deleted = 0
        with self._mutex:
            for path in self.root.glob("*.json"):
                if self.read(path.name) is None:
                    path.unlink()
                    deleted += 1
            if deleted:
                sync_directory(self.root)
        return deleted
