"""Single-owner, thread-serialized local catalog with one publication boundary."""

import fcntl
import json
import os
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from threading import RLock
from uuid import uuid4

from ..objects import ObjectRef, ObjectStore
from .errors import CommitUncertain, Conflict, IntegrityError, OwnershipError
from .filesystem import (
    contained_file,
    digest,
    encode,
    private_directory,
    publish_json,
    qualify_filesystem,
    read_json,
    sync_directory,
)


@dataclass(frozen=True)
class Change:
    """Trusted service input; scope is immutable once a record exists.

    None/0 creates an internally identified record. Updates require its current
    record generation. Payload values are exact bytes or previously committed refs.
    Data is opaque JSON here; editorial validation belongs to the shared services.
    """

    scope: str
    record_id: str | None = None
    expected_generation: int = 0
    data: dict = field(default_factory=dict)
    payloads: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Snapshot:
    """Detached, generation-pinned metadata; mutating it cannot change the catalog."""

    generation: int
    records: dict
    revisions: dict
    receipts: dict
    audit: list
    events: list


class LocalCatalog:
    """A private persistence backend; service code supplies authorization per commit.

    Use as a context manager. A failed IO publication poisons the coordinator:
    close and reopen, inspect recovery/receipt, then retry the same command key.
    """

    def __init__(self, root):
        self.root = private_directory(root)
        self._mutex = RLock()
        self._pid = os.getpid()
        self._closed = True
        self._failed = False
        self._authorizing = False
        lock = contained_file(self.root, "owner.lock")
        self._lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self._lock_fd)
            raise OwnershipError("Another coordinator owns this catalog") from exc
        self._closed = False
        try:
            self.manifests = private_directory(self.root / "manifests")
            self.intents = private_directory(self.root / "intents")
            self.staging = private_directory(self.root / "staging")
            qualify_filesystem(self.root, self.staging)
            self.objects = ObjectStore(self.root / "payloads")
            if not contained_file(self.root, "current.json").exists():
                if any(self.intents.iterdir()):
                    raise IntegrityError("Missing current reference in a used catalog")
                initial = {
                    "schema": 1,
                    "generation": 0,
                    "parent": None,
                    "records": {},
                    "revisions": {},
                    "receipts": {},
                    "audit": [],
                    "events": [],
                }
                ref = self._store_manifest(initial)
                publish_json(self.root, "current.json", ref, self.staging)
            _, verified = self._load_current()
            while verified["parent"] is not None:
                verified = self._load_manifest(verified["parent"])
            # A process may have died immediately after replacing current.json.
            # All its dependencies were flushed first; finish directory durability.
            sync_directory(self.root)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        with self._mutex:
            if self._authorizing:
                raise OwnershipError("Cannot close during authorization")
            if not self._closed:
                # A forked child must never unlock the parent's inherited flock.
                if os.getpid() == self._pid:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                self._closed = True

    def _ensure_open(self):
        if self._closed or os.getpid() != self._pid:
            raise OwnershipError("Coordinator is closed or belongs to another process")
        if self._failed:
            raise CommitUncertain("Reopen the coordinator and reconcile before retrying")

    def _store_manifest(self, value):
        name = uuid4().hex + ".json"
        publish_json(self.manifests, name, value, self.staging)
        return {
            "schema": 1,
            "name": name,
            "generation": value["generation"],
            "sha256": digest(encode(value)),
        }

    def _load_manifest(self, ref):
        try:
            if (
                set(ref) != {"schema", "name", "generation", "sha256"}
                or type(ref["schema"]) is not int
                or ref["schema"] != 1
                or type(ref["generation"]) is not int
                or ref["generation"] < 0
                or re.fullmatch(r"[0-9a-f]{32}\.json", ref["name"]) is None
                or re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]) is None
            ):
                raise ValueError("Invalid generation reference")
            manifest, raw = read_json(self.manifests, ref["name"])
            if digest(raw) != ref["sha256"]:
                raise ValueError("Manifest checksum mismatch")
            self._validate_manifest(manifest, ref["generation"])
            return manifest
        except (TypeError, KeyError, ValueError, FileNotFoundError) as exc:
            raise IntegrityError("Invalid committed manifest/reference") from exc

    def _validate_manifest(self, manifest, generation):
        if (
            set(manifest)
            != {
                "schema",
                "generation",
                "parent",
                "records",
                "revisions",
                "receipts",
                "audit",
                "events",
            }
            or type(manifest["schema"]) is not int
            or manifest["schema"] != 1
            or type(manifest["generation"]) is not int
            or manifest["generation"] != generation
        ):
            raise IntegrityError("Unsupported catalog schema or generation")
        for key in ("records", "revisions", "receipts"):
            if not isinstance(manifest[key], dict):
                raise IntegrityError("Invalid catalog collection")
        if not isinstance(manifest["audit"], list) or not isinstance(manifest["events"], list):
            raise IntegrityError("Invalid event collections")
        parent = manifest["parent"]
        if (generation == 0 and parent is not None) or (
            generation > 0
            and (not isinstance(parent, dict) or parent.get("generation") != generation - 1)
        ):
            raise IntegrityError("Invalid generation ancestry")
        revisions = manifest["revisions"]
        for record_id, head in manifest["records"].items():
            revision = revisions[head["revision_id"]]
            if (
                set(head) != {"revision_id", "generation", "scope"}
                or re.fullmatch(r"[0-9a-f]{32}", record_id) is None
                or revision["record_id"] != record_id
                or type(head["generation"]) is not int
                or head["generation"] < 1
                or revision["generation"] != head["generation"]
                or revision["scope"] != head["scope"]
            ):
                raise IntegrityError("Broken record head")
            members = [r for r in revisions.values() if r["record_id"] == record_id]
            if len(members) != head["generation"] or {r["generation"] for r in members} != set(
                range(1, head["generation"] + 1)
            ):
                raise IntegrityError("Incomplete or forked record history")
        for revision_id, revision in revisions.items():
            if (
                set(revision)
                != {"id", "record_id", "scope", "generation", "data", "payloads", "previous"}
                or revision["id"] != revision_id
                or re.fullmatch(r"[0-9a-f]{32}", revision_id) is None
                or type(revision["generation"]) is not int
                or revision["generation"] < 1
                or revision["record_id"] not in manifest["records"]
                or not isinstance(revision["scope"], str)
                or not revision["scope"]
                or revision["scope"] != manifest["records"][revision["record_id"]]["scope"]
                or not isinstance(revision["data"], dict)
                or not isinstance(revision["payloads"], dict)
            ):
                raise IntegrityError("Invalid revision identity/schema")
            previous = revision["previous"]
            if previous is not None:
                old = revisions[previous]
                if (
                    old["record_id"] != revision["record_id"]
                    or old["generation"] != revision["generation"] - 1
                    or old["scope"] != revision["scope"]
                ):
                    raise IntegrityError("Broken revision history")
            elif revision["generation"] != 1:
                raise IntegrityError("Missing preceding revision")
            for name, ref in revision["payloads"].items():
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name) is None:
                    raise IntegrityError("Invalid payload name")
                self.objects.read(ref)
        audits = {event["id"]: event for event in manifest["audit"]}
        events = {event["id"]: event for event in manifest["events"]}
        if not (
            len(manifest["receipts"])
            == len(manifest["audit"])
            == len(audits)
            == len(manifest["events"])
            == len(events)
            == generation
        ):
            raise IntegrityError("Incomplete or duplicate receipt/event history")
        observed_revisions, observed_generations, operations = set(), set(), set()
        for token, receipt in manifest["receipts"].items():
            if (
                set(receipt)
                != {
                    "token",
                    "operation_id",
                    "request_hash",
                    "principal",
                    "scope",
                    "key",
                    "generation",
                    "results",
                    "audit_id",
                    "event_id",
                }
                or receipt["token"] != token
                or any(
                    not isinstance(receipt[k], str) or not receipt[k]
                    for k in ("principal", "scope", "key")
                )
                or digest(encode([receipt["principal"], receipt["scope"], receipt["key"]])) != token
                or type(receipt["generation"]) is not int
                or not 1 <= receipt["generation"] <= generation
                or re.fullmatch(r"[0-9a-f]{64}", receipt["request_hash"]) is None
                or any(
                    re.fullmatch(r"[0-9a-f]{32}", receipt[k]) is None
                    for k in ("operation_id", "audit_id", "event_id")
                )
                or not isinstance(receipt["results"], list)
                or not receipt["results"]
            ):
                raise IntegrityError("Invalid operation receipt")
            observed_generations.add(receipt["generation"])
            operations.add(receipt["operation_id"])
            if audits[receipt["audit_id"]] != {
                "id": receipt["audit_id"],
                "operation_id": receipt["operation_id"],
                "principal": receipt["principal"],
                "generation": receipt["generation"],
            } or events[receipt["event_id"]] != {
                "id": receipt["event_id"],
                "operation_id": receipt["operation_id"],
                "type": "catalog.committed",
                "generation": receipt["generation"],
            }:
                raise IntegrityError("Broken receipt/event association")
            for result in receipt["results"]:
                revision = revisions[result["revision_id"]]
                if (
                    result
                    != {
                        "record_id": revision["record_id"],
                        "revision_id": revision["id"],
                        "scope": revision["scope"],
                        "generation": revision["generation"],
                    }
                    or revision["id"] in observed_revisions
                ):
                    raise IntegrityError("Receipt result differs from its exact revision")
                observed_revisions.add(revision["id"])
        if (
            observed_generations != set(range(1, generation + 1))
            or len(operations) != generation
            or observed_revisions != set(revisions)
        ):
            raise IntegrityError("Incomplete committed operation history")

    def _load_current(self):
        ref, _ = read_json(self.root, "current.json")
        return ref, self._load_manifest(ref)

    def read(self, generation=None):
        with self._mutex:
            self._ensure_open()
            ref, manifest = self._load_current()
            if generation is not None:
                if type(generation) is not int or generation < 0 or generation > ref["generation"]:
                    raise ValueError("Unknown generation")
                while manifest["generation"] > generation:
                    manifest = self._load_manifest(manifest["parent"])
            return Snapshot(
                **{
                    key: manifest[key]
                    for key in ("generation", "records", "revisions", "receipts", "audit", "events")
                }
            )

    def read_payload(self, revision_id, name, generation=None):
        snapshot = self.read(generation)
        return self.objects.read(snapshot.revisions[revision_id]["payloads"][name])

    def receipt(self, principal, scope, key):
        token = digest(encode([principal, scope, key]))
        return self.read().receipts.get(token)

    def commit(self, *, principal, scope, key, changes, authorize):
        """Commit all changes, or none; authorization executes under the writer lock.

        `authorize(principal, snapshot, changes)` must raise PermissionError on
        denial. It is trusted application code, never supplied by an HTTP client.
        Reads likewise require service-level authorization in the next phase.
        """
        with self._mutex:
            self._ensure_open()
            if self._authorizing:
                raise OwnershipError("Cannot commit during authorization")
            changes = deepcopy(list(changes))
            command, request_hash = self._command(principal, scope, key, changes)
            token = digest(encode([principal, scope, key]))
            parent, manifest = self._load_current()
            self._authorizing = True
            try:
                authorize(principal, self.read(), deepcopy(changes))
            finally:
                self._authorizing = False
            existing = manifest["receipts"].get(token)
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise Conflict("Idempotency key reused with different command data")
                return existing
            self._check_changes(manifest, changes)
            operation_id = uuid4().hex
            prepared = []
            results = []
            for change in changes:
                record_id = change.record_id or uuid4().hex
                revision_id = uuid4().hex
                refs = {}
                for name, value in change.payloads.items():
                    if isinstance(value, bytes):
                        ref = self.objects.reference(value)
                        prepared.append((ref, value))
                    else:
                        ref = asdict(value)
                    refs[name] = ref
                revision = {
                    "id": revision_id,
                    "record_id": record_id,
                    "scope": change.scope,
                    "generation": change.expected_generation + 1,
                    "data": change.data,
                    "payloads": refs,
                    "previous": manifest["records"].get(record_id, {}).get("revision_id"),
                }
                manifest["revisions"][revision_id] = revision
                head = {
                    "revision_id": revision_id,
                    "generation": revision["generation"],
                    "scope": change.scope,
                }
                manifest["records"][record_id] = head
                results.append({"record_id": record_id, **head})
            manifest["generation"] += 1
            manifest["parent"] = parent
            receipt = {
                "token": token,
                "operation_id": operation_id,
                "request_hash": request_hash,
                "principal": principal,
                "scope": scope,
                "key": key,
                "generation": manifest["generation"],
                "results": results,
                "audit_id": uuid4().hex,
                "event_id": uuid4().hex,
            }
            manifest["receipts"][token] = receipt
            manifest["audit"].append(
                {
                    "id": receipt["audit_id"],
                    "operation_id": operation_id,
                    "principal": principal,
                    "generation": manifest["generation"],
                }
            )
            manifest["events"].append(
                {
                    "id": receipt["event_id"],
                    "operation_id": operation_id,
                    "type": "catalog.committed",
                    "generation": manifest["generation"],
                }
            )
            intent = {
                "schema": 1,
                "operation_id": operation_id,
                "token": token,
                "request_hash": request_hash,
                "base": parent,
                "command": command,
                "principal": principal,
                "scope": scope,
                "key": key,
                "prepared": [ref for ref, _ in prepared],
            }
            try:
                publish_json(self.intents, operation_id + ".json", intent, self.staging)
                for ref, value in prepared:
                    self.objects.prepare(ObjectRef(**ref), value)
                next_ref = self._store_manifest(manifest)
                publish_json(self.root, "current.json", next_ref, self.staging)
            except BaseException as exc:
                self._failed = True
                if not isinstance(exc, Exception):
                    raise
                raise CommitUncertain(
                    "Publication interrupted; reopen and inspect receipt/recovery"
                ) from exc
            return deepcopy(receipt)

    def _command(self, principal, scope, key, changes):
        if any(not isinstance(value, str) or not value for value in (principal, scope, key)):
            raise ValueError("Principal, command scope and idempotency key are required")
        if not changes:
            raise ValueError("An empty changeset is not a command")
        command = []
        for change in changes:
            if (
                not isinstance(change, Change)
                or not isinstance(change.scope, str)
                or not change.scope
                or type(change.expected_generation) is not int
                or change.expected_generation < 0
                or not isinstance(change.data, dict)
                or not isinstance(change.payloads, dict)
            ):
                raise ValueError("Invalid changeset")
            payloads = {}
            for name, value in change.payloads.items():
                if (
                    not isinstance(name, str)
                    or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name) is None
                ):
                    raise ValueError("Invalid logical payload name")
                if isinstance(value, bytes):
                    payloads[name] = {"sha256": digest(value), "size": len(value)}
                elif isinstance(value, ObjectRef):
                    payloads[name] = asdict(value)
                else:
                    raise TypeError("Payload must be exact bytes or an immutable ObjectRef")
            command.append(
                {
                    "scope": change.scope,
                    "record_id": change.record_id,
                    "expected_generation": change.expected_generation,
                    "data": change.data,
                    "payloads": payloads,
                }
            )
        # Round-trip rejects non-string metadata keys rather than coercing them.
        raw = encode(command)
        if json.loads(raw) != command:
            raise ValueError("Metadata must contain only JSON values with string keys")
        return command, digest(raw)

    def _check_changes(self, manifest, changes):
        seen = set()
        committed_refs = {
            encode(ref)
            for rev in manifest["revisions"].values()
            for ref in rev["payloads"].values()
        }
        for change in changes:
            if change.record_id is None:
                if change.expected_generation != 0:
                    raise Conflict("A new record must use generation zero")
            else:
                if (
                    not isinstance(change.record_id, str)
                    or re.fullmatch(r"[0-9a-f]{32}", change.record_id) is None
                ):
                    raise ValueError("Invalid record ID")
                if change.record_id in seen:
                    raise ValueError("A changeset cannot update one record twice")
                seen.add(change.record_id)
                head = manifest["records"].get(change.record_id)
                if (
                    head is None
                    or head["generation"] != change.expected_generation
                    or head["scope"] != change.scope
                ):
                    raise Conflict(f"Stale generation or scope: {change.record_id}")
            for value in change.payloads.values():
                if isinstance(value, ObjectRef) and encode(asdict(value)) not in committed_refs:
                    raise IntegrityError("Cannot adopt an uncommitted payload reference")

    def recover(self):
        """Report preparations; never publish, retry effects or delete data implicitly."""
        with self._mutex:
            snapshot = self.read()
            committed_ops = {r["operation_id"] for r in snapshot.receipts.values()}
            committed_refs = {
                ref["key"]
                for rev in snapshot.revisions.values()
                for ref in rev["payloads"].values()
            }
            report = []
            for path in sorted(self.intents.iterdir()):
                intent, _ = read_json(self.intents, path.name)
                try:
                    if (
                        set(intent)
                        != {
                            "schema",
                            "operation_id",
                            "token",
                            "request_hash",
                            "base",
                            "command",
                            "prepared",
                            "principal",
                            "scope",
                            "key",
                        }
                        or type(intent["schema"]) is not int
                        or intent["schema"] != 1
                        or re.fullmatch(r"[0-9a-f]{32}", intent["operation_id"]) is None
                        or intent["operation_id"] + ".json" != path.name
                        or digest(encode(intent["command"])) != intent["request_hash"]
                        or any(
                            not isinstance(intent[k], str) or not intent[k]
                            for k in ("principal", "scope", "key")
                        )
                        or digest(encode([intent["principal"], intent["scope"], intent["key"]]))
                        != intent["token"]
                        or not isinstance(intent["command"], list)
                        or not intent["command"]
                        or not isinstance(intent["prepared"], list)
                    ):
                        raise ValueError("Invalid intent schema")
                    self._load_manifest(intent["base"])
                    for ref in intent["prepared"]:
                        ObjectRef(**ref)
                    receipt = snapshot.receipts.get(intent["token"])
                    if (
                        receipt is not None
                        and receipt["operation_id"] == intent["operation_id"]
                        and (
                            receipt["request_hash"] != intent["request_hash"]
                            or receipt["generation"] != intent["base"]["generation"] + 1
                        )
                    ):
                        raise ValueError("Intent disagrees with committed receipt")
                except (TypeError, KeyError, ValueError) as exc:
                    raise IntegrityError("Invalid preparation intent") from exc
                objects = []
                for ref in intent["prepared"]:
                    try:
                        self.objects.read(ref)
                        state = "committed" if ref["key"] in committed_refs else "prepared"
                    except FileNotFoundError:
                        state = "missing"
                    except IntegrityError:
                        state = "incomplete"
                    objects.append({"reference": ref, "state": state})
                report.append(
                    {
                        "operation_id": intent["operation_id"],
                        "token": intent["token"],
                        "state": "committed"
                        if intent["operation_id"] in committed_ops
                        else "prepared",
                        "payloads": objects,
                    }
                )
            return {
                "generation": snapshot.generation,
                "operations": report,
                "staging": sorted(p.name for p in self.staging.iterdir()),
            }
