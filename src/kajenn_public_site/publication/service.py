"""Shared authenticated publication commands over the existing catalog coordinator."""

import inspect
import json
from copy import deepcopy
from threading import RLock
from urllib.parse import urlsplit
from uuid import uuid4

from genro_storage.exceptions import StorageError

from ..catalog.errors import Conflict
from ..catalog.filesystem import digest, encode
from ..catalog.local import Change
from ..domain import DomainError
from ..rendering.contract import RenderProblem
from ..rendering.inputs import RenderInputs
from .export import ReleaseStorage
from .grants import PreviewGrants
from .jobs import BuildJobs
from .releases import RELEASE_MUTATIONS, RELEASE_READS, Releases
from .routes import localized_path, origin, route_map
from .serving import PublicServing

# Export writes release storage, never the catalog: no key, receipt or catalog commit.
EXPORTS = {"release_export"}
READS = {"candidate_read", "build_status"} | RELEASE_READS | EXPORTS
OPERATIONS = (
    {
        "publication_settings_save",
        "publication_route_save",
        "candidate_create",
        "candidate_read",
        "build_start",
        "build_retry",
        "build_status",
        "preview_grant_create",
        "preview_grant_revoke",
    }
    | RELEASE_READS
    | RELEASE_MUTATIONS
    | EXPORTS
)


class PublicationService(BuildJobs, PreviewGrants, Releases, PublicServing):
    def __init__(
        self,
        catalog,
        policy,
        worker,
        *,
        management_origin,
        preview_origin,
        preview_secret,
        preview_max_age=3600,
        public_origins=None,
        release_storage=None,
    ):
        self.catalog, self.policy, self.worker = catalog, policy, worker
        self.management_origin, self.preview_origin = (
            origin(management_origin),
            origin(preview_origin),
        )
        if urlsplit(self.management_origin).hostname == urlsplit(self.preview_origin).hostname:
            raise ValueError(
                "Preview must use a separate hostname to isolate host-only credentials"
            )
        if not isinstance(preview_secret, bytes) or len(preview_secret) < 32:
            raise ValueError("A persistent private preview key of at least 32 bytes is required")
        if type(preview_max_age) is not int or preview_max_age < 1:
            raise ValueError("Preview lifetime limit must be positive")
        self.preview_max_age = preview_max_age
        self.preview_secret = preview_secret
        self.public_origins = {}
        if public_origins is not None and not isinstance(public_origins, dict):
            raise ValueError("Public bindings must map explicit origins to settings IDs")
        for configured, settings_id in (public_origins or {}).items():
            binding = origin(configured)
            if (
                binding in self.public_origins
                or urlsplit(binding).hostname
                in {
                    urlsplit(self.management_origin).hostname,
                    urlsplit(self.preview_origin).hostname,
                }
                or not isinstance(settings_id, str)
            ):
                raise ValueError("Duplicate/unsafe public host binding")
            self.record(catalog.read(), settings_id, "publication_settings")
            self.public_origins[binding] = settings_id
        self.inputs = RenderInputs(catalog, policy)
        self.release_storage = (
            None if release_storage is None else ReleaseStorage(self, release_storage)
        )
        self._lock = RLock()
        self._closed = False
        self.start_jobs()

    def record(self, snapshot, record_id, kind=None):
        try:
            revision = snapshot.revisions[snapshot.records[record_id]["revision_id"]]
            if kind and revision["data"]["kind"] != kind:
                raise KeyError(record_id)
            return revision
        except (KeyError, TypeError) as exc:
            raise DomainError("not_found", "Record not found", resource_id=record_id) from exc

    def find(self, snapshot, kind, **attributes):
        matches = [
            snapshot.revisions[h["revision_id"]]
            for h in snapshot.records.values()
            if snapshot.revisions[h["revision_id"]]["data"].get("kind") == kind
            and all(
                snapshot.revisions[h["revision_id"]]["data"]["attributes"].get(k) == v
                for k, v in attributes.items()
            )
        ]
        if len(matches) > 1:
            raise DomainError("conflict", "Duplicate publication identity")
        return matches[0] if matches else None

    def _authorize(self, snapshot, identity, operation, arguments):
        if operation == "publication_settings_save":
            site_id = self.record(snapshot, arguments["site_id"], "site")["record_id"]
        elif operation == "publication_route_save":
            site_id = self.record(snapshot, arguments["variant_id"], "variant")["scope"][5:]
        else:
            key, kind = next(
                (k, v)
                for k, v in (
                    ("settings_id", "publication_settings"),
                    ("candidate_id", "publication_candidate"),
                    ("build_id", "publication_job"),
                    ("grant_id", "publication_grant"),
                )
                if k in arguments
            )
            site_id = self.record(snapshot, arguments[key], kind)["data"]["attributes"]["site_id"]
        permission = (
            "publish"
            if operation in RELEASE_READS | RELEASE_MUTATIONS | EXPORTS
            else "write"
            if operation.startswith("publication_")
            else "preview_grant"
            if operation.startswith("preview_")
            else "build"
        )
        self.policy.require(identity, "site:" + site_id, "read")
        self.policy.require(identity, "site:" + site_id, permission)
        return site_id

    def execute(self, identity, operation, **arguments):
        if operation not in OPERATIONS or not hasattr(self, "_" + operation):
            raise DomainError("invalid_operation", "Unknown publication operation")
        with self._lock:
            if self._closed:
                raise DomainError("unavailable", "Publication coordinator is closed")
            snapshot = self.catalog.read()
            handler = getattr(self, "_" + operation)
            try:
                bound = inspect.signature(handler).bind(snapshot, identity, **deepcopy(arguments))
                bound.apply_defaults()
                params = {
                    k: v for k, v in bound.arguments.items() if k not in {"snapshot", "identity"}
                }
                fingerprint = digest(encode([operation, params]))
            except (TypeError, ValueError) as exc:
                raise DomainError("invalid_input", str(exc)) from exc
            self._authorize(snapshot, identity, operation, params)
            if operation in READS:
                return handler(snapshot, identity, **params)
            key = params["key"]
            if not isinstance(key, str) or not key or len(key) > 256:
                raise DomainError(
                    "invalid_input", "A nonempty key of at most 256 characters is required"
                )
            prior = self.catalog.receipt(principal=identity, scope="publication", key=key)
            if prior:
                revision = snapshot.revisions[prior["results"][0]["revision_id"]]
                if revision["data"].get("command_hash") != fingerprint:
                    raise DomainError("conflict", "Idempotency key reused with different input")
                if operation in {"build_start", "build_retry"}:
                    self.authorize_candidate(
                        identity,
                        snapshot.revisions[revision["data"]["attributes"]["candidate_revision"]],
                    )
                    self._schedule(revision["record_id"])
                if operation in {"release_activate", "release_rollback"}:
                    self.authorize_release(
                        snapshot,
                        identity,
                        self.record(snapshot, params["settings_id"], "publication_settings"),
                        self.record(snapshot, params["build_id"], "publication_job"),
                    )
                    if self.release_storage is not None:
                        result = self._result(snapshot, identity, revision)
                        result["export"] = self.export_status(snapshot, params["settings_id"])
                        return result
                return self._result(snapshot, identity, revision)
            change = handler(snapshot, identity, **params)
            changes = change if isinstance(change, list) else [change]
            for item in changes:
                item.data["command_hash"] = fingerprint

            def authorize(principal, current, changes):
                self._authorize(current, principal, operation, params)
                # Revalidate catalog-dependent identity/selection under the writer lock.
                handler(current, principal, **params)

            try:
                receipt = self.catalog.commit(
                    principal=identity,
                    scope="publication",
                    key=key,
                    changes=changes,
                    authorize=authorize,
                )
            except Conflict as exc:
                raise DomainError("conflict", str(exc)) from exc
            current = self.catalog.read()
            revision = current.revisions[receipt["results"][0]["revision_id"]]
            if operation in {"build_start", "build_retry"}:
                self._schedule(revision["record_id"])
            result = self._result(current, identity, revision)
            if (
                operation in {"release_activate", "release_rollback"}
                and self.release_storage is not None
            ):
                # The activation is committed; an export failure only leaves it pending.
                result["export"] = self.export_after_commit(current, params["settings_id"])
            return result

    def export_after_commit(self, snapshot, settings_id):
        try:
            return {"state": "exported", "pointer": self.release_storage.export(snapshot, settings_id)}
        except (OSError, StorageError, DomainError) as exc:
            return {"state": "pending", "error": getattr(exc, "code", type(exc).__name__)}

    def export_status(self, snapshot, settings_id):
        try:
            return self.release_storage.status(snapshot, settings_id)
        except (OSError, StorageError, DomainError) as exc:
            return {"state": "unavailable", "error": getattr(exc, "code", type(exc).__name__)}

    def _release_export(self, snapshot, identity, settings_id):
        if self.release_storage is None:
            raise DomainError("unavailable", "Release storage is not configured")
        try:
            pointer = self.release_storage.export(snapshot, settings_id)
        except (OSError, StorageError) as exc:
            raise DomainError("export_failed", "Release storage write failed") from exc
        return {"state": "exported", "pointer": pointer}

    def _result(self, snapshot, identity, revision):
        if revision["data"]["kind"] == "publication_candidate":
            self.authorize_candidate(identity, revision)
        result = {
            "record_id": revision["record_id"],
            "revision_id": revision["id"],
            "generation": revision["generation"],
            "kind": revision["data"]["kind"],
            "attributes": deepcopy(revision["data"]["attributes"]),
        }

        if revision["data"]["kind"] == "publication_grant":
            current = self.record(snapshot, revision["record_id"], "publication_grant")
            if not current["data"]["attributes"]["revoked"]:
                result["url"] = self.grant_link(current)
        if revision["data"]["kind"] == "publication_channel" and revision["data"]["attributes"].get(
            "activation_token"
        ):
            activation = self.find(
                snapshot,
                "publication_activation",
                token=revision["data"]["attributes"]["activation_token"],
            )
            result["activation"] = self._result(snapshot, identity, activation)
        return result

    def change(self, kind, attrs, payloads=None, record_id=None, expected_generation=0):
        if (
            type(expected_generation) is not int
            or expected_generation < 0
            or bool(record_id) != bool(expected_generation)
        ):
            raise DomainError(
                "invalid_input", "Creation needs generation 0; updates need an exact generation"
            )
        return Change(
            "publication:" + attrs["site_id"],
            record_id,
            expected_generation,
            {"schema": 1, "kind": kind, "attributes": attrs},
            payloads or {},
        )

    def _publication_settings_save(
        self,
        snapshot,
        identity,
        site_id,
        channel,
        public_origin,
        primary_language,
        landing_variant,
        key,
        record_id=None,
        expected_generation=0,
    ):
        site = self.record(snapshot, site_id, "site")
        landing = self.record(snapshot, landing_variant, "variant")
        public_origin = origin(public_origin)
        if (
            urlsplit(public_origin).hostname
            in {urlsplit(self.management_origin).hostname, urlsplit(self.preview_origin).hostname}
            or primary_language not in site["data"]["attributes"]["languages"]
            or landing["scope"] != "site:" + site_id
            or landing["data"]["attributes"]["language"] != primary_language
            or not isinstance(channel, str)
            or not channel
            or len(channel) > 64
            or not all(c.isalnum() or c in "-_" for c in channel)
        ):
            raise DomainError(
                "invalid_settings", "Invalid channel, origin or primary landing variant"
            )
        existing = self.find(snapshot, "publication_settings", site_id=site_id, channel=channel)
        if existing and existing["record_id"] != record_id:
            raise DomainError("conflict", "Channel settings already exist")
        if record_id:
            old = self.record(snapshot, record_id, "publication_settings")["data"]["attributes"]
            if old["site_id"] != site_id or old["channel"] != channel:
                raise DomainError("invalid_settings", "Settings site and channel are immutable")
        return self.change(
            "publication_settings",
            {
                "site_id": site_id,
                "channel": channel,
                "public_origin": public_origin,
                "primary_language": primary_language,
                "landing_variant": landing_variant,
            },
            record_id=record_id,
            expected_generation=expected_generation,
        )

    def _publication_route_save(
        self,
        snapshot,
        identity,
        variant_id,
        path,
        title,
        description,
        key,
        record_id=None,
        expected_generation=0,
    ):
        variant = self.record(snapshot, variant_id, "variant")
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title) > 512
            or not isinstance(description, str)
            or len(description) > 4096
        ):
            raise DomainError("invalid_input", "Route title and description must be bounded text")
        route = localized_path(variant["data"]["attributes"]["language"], path)
        existing = self.find(snapshot, "publication_route", variant_id=variant_id)
        if existing and existing["record_id"] != record_id:
            raise DomainError("conflict", "Variant route already exists")
        if (
            record_id
            and self.record(snapshot, record_id, "publication_route")["data"]["attributes"][
                "variant_id"
            ]
            != variant_id
        ):
            raise DomainError("invalid_input", "Route variant is immutable")
        return self.change(
            "publication_route",
            {
                "site_id": variant["scope"][5:],
                "variant_id": variant_id,
                "path": route,
                "title": title,
                "description": description,
            },
            record_id=record_id,
            expected_generation=expected_generation,
        )

    def candidate_data(self, candidate):
        return json.loads(self.catalog.read_payload(candidate["id"], "inputs"))

    def authorize_candidate(self, identity, candidate, *, permission="build"):
        from ..rendering.contract import RenderInput

        for entry in self.candidate_data(candidate)["entries"].values():
            self.inputs.authorize(
                identity, RenderInput(encode(entry["input"])), permission=permission
            )

    def _candidate_create(
        self, snapshot, identity, settings_id, variant_revisions, key, base_build_id=None
    ):
        settings = self.record(snapshot, settings_id, "publication_settings")
        attrs = settings["data"]["attributes"]
        if (
            not isinstance(variant_revisions, list)
            or not variant_revisions
            or len(variant_revisions) > 100
            or not all(isinstance(r, str) for r in variant_revisions)
            or len(set(variant_revisions)) != len(variant_revisions)
        ):
            raise DomainError("invalid_input", "Select 1–100 unique exact variant revisions")
        channel = self.find(snapshot, "publication_channel", settings_id=settings_id)
        base_generation = channel["generation"] if channel else 0
        active = channel["data"]["attributes"].get("active_build") if channel else None
        try:
            profile = self.worker.profile()
        except RenderProblem as exc:
            raise DomainError(
                "render_profile_unavailable",
                "Qualified renderer profile unavailable",
                details=[exc.diagnostic],
            ) from exc
        entries = {}
        if base_build_id:
            base = self.record(snapshot, base_build_id, "publication_job")
            if (
                base["data"]["attributes"].get("state") != "succeeded"
                or active != base_build_id
                or channel["data"]["attributes"].get("active_revision") != base["id"]
                or base["data"]["attributes"]["site_id"] != attrs["site_id"]
            ):
                raise DomainError(
                    "invalid_base", "Carry-forward requires the specified active sealed build"
                )
            prior = self.record(
                snapshot, base["data"]["attributes"]["candidate_id"], "publication_candidate"
            )
            prior_data = self.candidate_data(prior)
            if prior_data["settings_id"] != settings_id or prior_data["profile"] != profile:
                raise DomainError(
                    "incompatible_base", "Base uses another channel or renderer profile"
                )
            self.authorize_candidate(identity, prior)
            entries = prior_data["entries"]
        for revision_id in variant_revisions:
            revision = snapshot.revisions.get(revision_id)
            if (
                not revision
                or revision["data"]["kind"] != "variant"
                or revision["scope"] != "site:" + attrs["site_id"]
            ):
                raise DomainError("invalid_variant", "Expected an exact variant from this site")
            variant_id = revision["record_id"]
            route = self.find(snapshot, "publication_route", variant_id=variant_id)
            if route is None:
                raise DomainError(
                    "missing_route", "Configure the variant route", resource_id=variant_id
                )
            value = self.inputs.freeze(
                identity,
                variant_id,
                profile,
                revision_id=revision_id,
                generation=snapshot.generation,
            ).unpack()
            value["data"]["page"]["title"] = route["data"]["attributes"]["title"]
            entries[variant_id] = {
                "variant_revision": revision_id,
                "route_revision": route["id"],
                "route": route["data"]["attributes"],
                "input": value,
                "content_id": revision["data"]["attributes"]["content_id"],
                "language": revision["data"]["attributes"]["language"],
            }
        routes, landing = route_map(entries, attrs)
        release_key = uuid4().hex
        # Candidate namespace is fixed before jobs exist; retries never change asset URLs.
        for entry in entries.values():
            for resource in entry["input"]["data"]["resources"].values():
                resource["url"] = (
                    f"/_releases/{release_key}/assets/" + resource["url"].rsplit("/", 1)[-1]
                )
        frozen = {
            "schema": 1,
            "catalog_generation": snapshot.generation,
            "settings_id": settings_id,
            "settings_revision": settings["id"],
            "settings": attrs,
            "profile": profile,
            "release_key": release_key,
            "entries": entries,
            "routes": routes,
            "landing": landing,
            "base_build_id": base_build_id,
            "base_channel_generation": base_generation,
            "base_active_build": active,
        }
        raw = encode(frozen)
        if len(raw) > 48 * 1024 * 1024:
            raise DomainError("input_limit", "Candidate exceeds 48 MiB")
        return self.change(
            "publication_candidate",
            {
                "site_id": attrs["site_id"],
                "settings_id": settings_id,
                "settings_revision": settings["id"],
                "input_digest": digest(raw),
                "release_key": release_key,
                "base_channel_generation": base_generation,
                "base_active_build": active,
                "base_build_id": base_build_id,
            },
            {"inputs": raw},
        )

    def _candidate_read(self, snapshot, identity, candidate_id):
        candidate = self.record(snapshot, candidate_id, "publication_candidate")
        result = self._result(snapshot, identity, candidate)
        result["selection"] = {
            k: {n: v for n, v in entry.items() if n != "input"}
            for k, entry in self.candidate_data(candidate)["entries"].items()
        }
        return result
