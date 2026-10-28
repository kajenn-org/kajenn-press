"""Site sources on S3: one zip per site, every deliberate save an S3 version (d-publish-unit).

The zip holds one entry, `site.json`, the same envelope as the working copy (N3-D2). The
bucket must have S3 versioning enabled; the store refuses one that has not. Restoring a
version writes it as the new current object, so S3 keeps it as a new version and history
is never rewritten.
"""

import s3fs
from genro_storage import StorageManager

from ..catalog.errors import IntegrityError
from ..domain import DomainError
from .storage import pack, unpack

MOUNT = "sources"


def require_versioning(config, role):
    """Refuse an S3 bucket whose versioning is not enabled (genro-storage does not ask)."""
    if config.get("protocol") != "s3":
        raise DomainError("unavailable", f"The {role} bucket must be S3 with versioning")
    filesystem = s3fs.S3FileSystem(
        key=config["access_key"],
        secret=config["secret_key"],
        client_kwargs={"endpoint_url": config["endpoint_url"]},
        skip_instance_cache=True,
    )
    state = filesystem.call_s3("get_bucket_versioning", Bucket=config["bucket"])
    if state.get("Status") != "Enabled":
        raise DomainError("unavailable", f"S3 versioning is not enabled on the {role} bucket")


class SourceStore:
    """One versioned S3 bucket of site sources, written only by the manager."""

    def __init__(self, config):
        if config.get("protocol") != "s3":
            raise DomainError("unavailable", "Site sources need an S3 bucket with versioning")
        self.config = dict(config)
        self.storage = StorageManager()
        self.storage.configure([{"name": MOUNT, **self.config}])
        self.qualify()

    def qualify(self):
        require_versioning(self.config, "source")

    def node(self, site_id, version_id=None):
        path = f"{MOUNT}:sites/{site_id}/source.zip"
        return (
            self.storage.node(path, version=version_id) if version_id else self.storage.node(path)
        )

    def save(self, site):
        """Write the site as a new version; returns its version id."""
        node = self.node(site.site_id)
        node.write_bytes(pack(site))
        return node.versions[-1]["version_id"]

    def versions(self, site_id):
        """Versions of a site source, oldest first: id, date, size, latest flag."""
        node = self.node(site_id)
        if not node.exists():
            raise DomainError("not_found", f"No source for site {site_id}", resource_id=site_id)
        return [
            {key: version[key] for key in ("version_id", "last_modified", "size", "is_latest")}
            for version in node.versions
        ]

    def open(self, site_id, version_id=None):
        node = self.node(site_id, version_id)
        if not node.exists():
            raise DomainError("not_found", f"No source for site {site_id}", resource_id=site_id)
        site = unpack(node.read_bytes())
        if site.site_id != site_id:
            raise IntegrityError("Site source holds another site")
        return site

    def restore(self, site_id, version_id):
        """Make an older version current again, as a new version; returns its id.

        The audit log is not rolled back: the restored site keeps the current log.
        """
        current = self.open(site_id)
        restored = self.open(site_id, version_id)
        restored.bag.set_item("audit", current.audit)
        return self.save(restored)

    def export(self, site_id, version_id=None):
        """Zip bytes of a saved version: a complete site in one file."""
        self.open(site_id, version_id)
        return self.node(site_id, version_id).read_bytes()

    def starter_node(self, starter_id):
        return self.storage.node(f"{MOUNT}:library/starters/{starter_id}.zip")

    def starter_save(self, starter_id, site):
        """Keep a site in the Library as a starting site."""
        self.starter_node(starter_id).write_bytes(pack(site))

    def starters(self):
        """Starting sites in the Library: id and name."""
        folder = self.storage.node(f"{MOUNT}:library/starters")
        if not folder.exists():
            return []
        return [
            {"starter_id": node.stem, "name": unpack(node.read_bytes()).name}
            for node in sorted(folder.children(), key=lambda n: n.basename)
            if node.suffix == ".zip"
        ]

    def starter_open(self, starter_id):
        node = self.starter_node(starter_id)
        if not node.exists():
            raise DomainError("not_found", f"No starting site {starter_id}")
        return unpack(node.read_bytes())

    def load_into(self, site_id, working_copy, version_id=None):
        """Fill the local working copy from the store."""
        site = self.open(site_id, version_id)
        working_copy.save(site)
        return site

    def save_from(self, working_copy):
        """Save the local working copy to the store as a new version."""
        return self.save(working_copy.load())
