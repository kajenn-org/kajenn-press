"""One editor at a time per site (d-editing-lock), kept in the manager's working directory.

A holder keeps a site while it acts; after `expiry` seconds without activity the site is
free. Another identity can take a held site only explicitly: the lock records whom it was
taken from, and the previous holder's next action is refused with that information. Help
me acts under the identity of the user who opened it, so it needs no lock of its own.
"""

import time
from threading import RLock

from ..catalog.filesystem import contained_file, private_directory, publish_json, read_json
from ..domain import DomainError

EXPIRY_SECONDS = 30 * 60


class EditingLock:
    def __init__(self, root, expiry=EXPIRY_SECONDS, clock=time.time):
        self.root = private_directory(root)
        self.staging = private_directory(self.root / "staging")
        self.expiry = expiry
        self.clock = clock
        self._mutex = RLock()

    def file_name(self, site_id):
        return f"{site_id}.lock.json"

    def state(self, site_id):
        """The lock record, or None when the site was never locked."""
        if not contained_file(self.root, self.file_name(site_id)).exists():
            return None
        return read_json(self.root, self.file_name(site_id))[0]

    def holder(self, site_id):
        """The current holder's identity, or None when the site is free or expired."""
        state = self.state(site_id)
        if state is None or state["holder"] is None:
            return None
        if self.clock() - state["last_activity"] > self.expiry:
            return None
        return state["holder"]

    def take(self, site_id, identity, force=False):
        """Hold the site; `force` takes it from another holder and records whom from."""
        with self._mutex:
            current = self.holder(site_id)
            if current not in (None, identity) and not force:
                raise DomainError(
                    "conflict", f"Site is being edited by {current}", details={"holder": current}
                )
            now = self.clock()
            taken_from = current if current not in (None, identity) else None
            self._write(
                site_id,
                {
                    "holder": identity,
                    "taken_at": now,
                    "last_activity": now,
                    "taken_from": taken_from,
                },
            )
            return {"holder": identity, "taken_from": taken_from}

    def require(self, site_id, identity):
        """Refuse an action by anyone but the current holder; refresh the holder's activity."""
        with self._mutex:
            state = self.state(site_id)
            current = self.holder(site_id)
            if current != identity:
                details = {"holder": current}
                if state is not None and current is not None and state["taken_from"] == identity:
                    details["taken_from_you_at"] = state["taken_at"]
                message = (
                    "Take the site before editing it"
                    if current is None
                    else f"Site is being edited by {current}"
                )
                raise DomainError("conflict", message, details=details)
            self._write(site_id, {**state, "last_activity": self.clock()})

    def release(self, site_id, identity):
        with self._mutex:
            if self.holder(site_id) == identity:
                state = self.state(site_id)
                self._write(site_id, {**state, "holder": None})

    def _write(self, site_id, state):
        publish_json(self.root, self.file_name(site_id), state, self.staging)
