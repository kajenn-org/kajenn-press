"""Site sources on S3: one zip per site, every deliberate save an S3 version (d-publish-unit).

The zip holds one entry, `site.json`, the same envelope as the working copy (N3-D2). The
bucket must have S3 versioning enabled; the store refuses one that has not. Restoring a
version writes it as the new current object, so S3 keeps it as a new version and history
is never rewritten.
"""

import io
import json
import zipfile

import s3fs
from genro_storage import StorageManager

from ..catalog.errors import IntegrityError
from ..catalog.filesystem import encode
from ..domain import DomainError
from .storage import site_envelope, site_from_envelope

MOUNT = "sources"
ENTRY = "site.json"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def pack(site):
    """Deterministic zip bytes of a site."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(ENTRY, date_time=FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, encode(site_envelope(site)))
    return stream.getvalue()


def unpack(raw):
    """The site in zip bytes; anything but one intact `site.json` fails closed."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.namelist() != [ENTRY]:
                raise IntegrityError("A site zip holds exactly one site.json")
            envelope = json.loads(archive.read(ENTRY))
    except (zipfile.BadZipFile, ValueError) as exc:
        raise IntegrityError("Site zip is not readable") from exc
    return site_from_envelope(envelope)


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
        filesystem = s3fs.S3FileSystem(
            key=self.config["access_key"],
            secret=self.config["secret_key"],
            client_kwargs={"endpoint_url": self.config["endpoint_url"]},
            skip_instance_cache=True,
        )
        state = filesystem.call_s3("get_bucket_versioning", Bucket=self.config["bucket"])
        if state.get("Status") != "Enabled":
            raise DomainError("unavailable", "S3 versioning is not enabled on the source bucket")

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

    def load_into(self, site_id, working_copy, version_id=None):
        """Fill the local working copy from the store."""
        site = self.open(site_id, version_id)
        working_copy.save(site)
        return site

    def save_from(self, working_copy):
        """Save the local working copy to the store as a new version."""
        return self.save(working_copy.load())
