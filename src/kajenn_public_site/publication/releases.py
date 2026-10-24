"""Conditional channel transitions and immutable publication history."""

from uuid import uuid4

from ..domain import DomainError
from .artifacts import validate_references, verify_bundle

RELEASE_READS = {"channel_read", "release_read", "release_history"}
RELEASE_MUTATIONS = {"channel_create", "release_activate", "release_rollback"}


class Releases:
    def activations(self, snapshot, settings_id):
        return sorted(
            (
                snapshot.revisions[h["revision_id"]]
                for h in snapshot.records.values()
                if snapshot.revisions[h["revision_id"]]["data"].get("kind")
                == "publication_activation"
                and snapshot.revisions[h["revision_id"]]["data"]["attributes"]["settings_id"]
                == settings_id
            ),
            key=lambda revision: revision["data"]["attributes"]["channel_generation"],
        )

    def _channel_create(self, snapshot, identity, settings_id, key):
        settings = self.record(snapshot, settings_id, "publication_settings")
        if self.find(snapshot, "publication_channel", settings_id=settings_id):
            raise DomainError("conflict", "Channel already exists")
        return self.change(
            "publication_channel",
            {
                "site_id": settings["data"]["attributes"]["site_id"],
                "settings_id": settings_id,
                "active_build": None,
                "active_revision": None,
                "activation_token": None,
            },
        )

    def _channel_read(self, snapshot, identity, settings_id):
        channel = self.find(snapshot, "publication_channel", settings_id=settings_id)
        if channel is None:
            return {"settings_id": settings_id, "generation": 0, "active_build": None}
        result = self._result(snapshot, identity, channel)
        if self.release_storage is not None:
            result["export"] = self.export_status(snapshot, settings_id)
        return result

    def _release_read(self, snapshot, identity, build_id):
        job = self.record(snapshot, build_id, "publication_job")
        candidate = snapshot.revisions[job["data"]["attributes"]["candidate_revision"]]
        self.authorize_candidate(identity, candidate, permission="publish")
        manifest = self.sealed_manifest(job)
        return {**self._result(snapshot, identity, job), "manifest": manifest}

    def _release_history(self, snapshot, identity, settings_id):
        return [
            self._result(snapshot, identity, activation)
            for activation in self.activations(snapshot, settings_id)
        ]

    def authorize_release(self, snapshot, identity, settings, job):
        """No renderer calls: current policy plus exact bytes and destination compatibility."""
        attrs = settings["data"]["attributes"]
        site = self.record(snapshot, attrs["site_id"], "site")
        self.policy.require(identity, "site:" + attrs["site_id"], "publish")
        if site["data"]["attributes"].get("review_required"):
            raise DomainError("review_required", "Revision-bound approvals are not implemented")
        candidate = snapshot.revisions[job["data"]["attributes"]["candidate_revision"]]
        data = self.candidate_data(candidate)
        if (
            job["data"]["attributes"]["site_id"] != attrs["site_id"]
            or data["settings_id"] != settings["record_id"]
            or data["settings"] != attrs
        ):
            raise DomainError("incompatible_release", "Release targets different channel/settings")
        bindings = {
            origin
            for origin, settings_id in self.public_origins.items()
            if settings_id == settings["record_id"]
        }
        if bindings and data["settings"]["public_origin"] not in bindings:
            raise DomainError(
                "incompatible_release", "Release targets an unconfigured public origin"
            )
        self.authorize_candidate(identity, candidate, permission="publish")
        validate_references(data)
        manifest = self.sealed_manifest(job)
        if (
            manifest.get("schema") != 1
            or manifest["settings_id"] != data["settings_id"]
            or manifest["settings_revision"] != data["settings_revision"]
            or manifest["build_id"] != job["record_id"]
            or manifest["release_key"] != data["release_key"]
            or manifest["routes"] != data["routes"]
            or manifest["profile"] != data["profile"]
            or manifest["redirects"] != {"/": data["landing"]}
        ):
            raise DomainError("invalid_output", "Release manifest differs from frozen candidate")
        payloads = {
            item["payload"]: self.catalog.read_payload(job["id"], item["payload"])
            for context in manifest["artifacts"].values()
            for item in context.values()
        }
        verify_bundle(manifest, payloads)
        return data

    def _activation_changes(
        self, snapshot, identity, settings_id, build_id, expected_generation, action
    ):
        if type(expected_generation) is not int or expected_generation < 0:
            raise DomainError("invalid_input", "Expected a nonnegative channel generation")
        settings = self.record(snapshot, settings_id, "publication_settings")
        channel = self.find(snapshot, "publication_channel", settings_id=settings_id)
        generation = channel["generation"] if channel else 0
        if generation != expected_generation:
            raise DomainError("conflict", "Channel generation changed")
        current = channel["data"]["attributes"] if channel else {}
        job = self.record(snapshot, build_id, "publication_job")
        data = self.authorize_release(snapshot, identity, settings, job)
        if action == "activate":
            if data["base_channel_generation"] != generation or data[
                "base_active_build"
            ] != current.get("active_build"):
                raise DomainError("stale_base", "Candidate was built from another channel state")
        elif not any(
            a["data"]["attributes"]["build_revision"] == job["id"]
            for a in self.activations(snapshot, settings_id)
        ):
            raise DomainError("not_published", "Rollback requires a retained published release")
        token = uuid4().hex
        attrs = {
            "site_id": settings["data"]["attributes"]["site_id"],
            "settings_id": settings_id,
            "active_build": build_id,
            "active_revision": job["id"],
            "activation_token": token,
        }
        activation = {
            "site_id": attrs["site_id"],
            "settings_id": settings_id,
            "settings_revision": settings["id"],
            "build_id": build_id,
            "build_revision": job["id"],
            "candidate_revision": job["data"]["attributes"]["candidate_revision"],
            "from_build": current.get("active_build"),
            "from_revision": current.get("active_revision"),
            "channel_generation": generation + 1,
            "action": action,
            "actor": identity,
            "token": token,
        }
        return [
            self.change(
                "publication_channel",
                attrs,
                record_id=channel["record_id"] if channel else None,
                expected_generation=generation,
            ),
            self.change("publication_activation", activation),
        ]

    def _release_activate(
        self, snapshot, identity, settings_id, build_id, expected_generation, key
    ):
        return self._activation_changes(
            snapshot, identity, settings_id, build_id, expected_generation, "activate"
        )

    def _release_rollback(
        self, snapshot, identity, settings_id, build_id, expected_generation, key
    ):
        return self._activation_changes(
            snapshot, identity, settings_id, build_id, expected_generation, "rollback"
        )
