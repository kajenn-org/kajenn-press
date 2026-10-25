"""Registry of children serving a channel from release storage, and what each one gets."""

from ..domain import DomainError
from .export import MOUNT
from .routes import origin

DEPLOYMENT_READS = {"child_read", "child_list", "child_channels"}
DEPLOYMENT_MUTATIONS = {"child_save"}


class Deployments:
    def _child_save(
        self,
        snapshot,
        identity,
        settings_id,
        name,
        public_origin,
        serving_address,
        key,
        mount=MOUNT,
        record_id=None,
        expected_generation=0,
    ):
        settings = self.record(snapshot, settings_id, "publication_settings")
        attrs = settings["data"]["attributes"]
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 64
            or not all(c.isalnum() or c in "-_." for c in name)
        ):
            raise DomainError("invalid_input", "A child name of letters, digits, '-', '_' or '.'")
        if mount != MOUNT:
            raise DomainError("invalid_input", "This installation exports to one mount only")
        if origin(public_origin) != attrs["public_origin"]:
            # The child answers only for the origin its pointer names.
            raise DomainError("invalid_input", "Public origin differs from the channel settings")
        for other in self.children(snapshot):
            if other["record_id"] != record_id and other["data"]["attributes"]["name"] == name:
                raise DomainError("conflict", "Child name already registered")
        if record_id:
            old = self.record(snapshot, record_id, "deployment_child")["data"]["attributes"]
            if old["settings_id"] != settings_id:
                raise DomainError("invalid_input", "A child's channel is immutable")
        return self.change(
            "deployment_child",
            {
                "site_id": attrs["site_id"],
                "settings_id": settings_id,
                "name": name,
                "public_origin": attrs["public_origin"],
                "mount": mount,
                "serving_address": origin(serving_address),
            },
            record_id=record_id,
            expected_generation=expected_generation,
        )

    def _child_read(self, snapshot, identity, record_id):
        child = self.record(snapshot, record_id, "deployment_child")
        return {**self._result(snapshot, identity, child), "deployment": self.deployment(snapshot, child)}

    def _child_list(self, snapshot, identity):
        return [
            {**self._result(snapshot, identity, child), "deployment": self.deployment(snapshot, child)}
            for child in self.children(snapshot)
            if self.policy.allows(identity, "site:" + child["data"]["attributes"]["site_id"], "read")
        ]

    def _child_channels(self, snapshot, identity):
        """Channels a child can be registered for: settings of sites the caller can read."""
        return [
            {
                "settings_id": settings["record_id"],
                "site_id": settings["data"]["attributes"]["site_id"],
                "site_name": self.record(snapshot, settings["data"]["attributes"]["site_id"], "site")[
                    "data"
                ]["attributes"]["name"],
                "channel": settings["data"]["attributes"]["channel"],
                "public_origin": settings["data"]["attributes"]["public_origin"],
            }
            for h in snapshot.records.values()
            if (settings := snapshot.revisions[h["revision_id"]])["data"].get("kind")
            == "publication_settings"
            and self.policy.allows(
                identity, "site:" + settings["data"]["attributes"]["site_id"], "read"
            )
        ]

    def children(self, snapshot):
        return sorted(
            (
                snapshot.revisions[h["revision_id"]]
                for h in snapshot.records.values()
                if snapshot.revisions[h["revision_id"]]["data"].get("kind") == "deployment_child"
            ),
            key=lambda child: child["data"]["attributes"]["name"],
        )

    def deployment(self, snapshot, child):
        """Catalog release beside the release read back from storage; never corrected here."""
        settings_id = child["data"]["attributes"]["settings_id"]
        channel = self.find(snapshot, "publication_channel", settings_id=settings_id)
        active = channel["data"]["attributes"].get("active_build") if channel else None
        catalog = {"build_id": active, "channel_generation": channel["generation"] if channel else 0}
        if self.release_storage is None:
            return {"catalog": catalog, "storage": None, "state": "storage_unconfigured"}
        storage = self.export_status(snapshot, settings_id)
        pointer = storage["pointer"]
        if storage["state"] == "unavailable":
            state = "storage_unavailable"
        elif active is None and pointer is None:
            state = "nothing_to_serve"
        elif pointer is None:
            state = "not_exported"
        elif storage["state"] == "exported":
            state = "up_to_date"
        else:
            state = "storage_differs"
        return {"catalog": catalog, "storage": pointer, "state": state}
