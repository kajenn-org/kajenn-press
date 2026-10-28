"""The unpacked working copy of a site: one durable file in a private local directory.

The file is canonical JSON holding the site Bag in TYTX JSON and its SHA-256. A missing,
malformed or altered file fails closed. N3 zips this copy and versions it on S3.
"""

from genro_bag import Bag, BagException

from ..catalog.errors import IntegrityError
from ..catalog.filesystem import digest, private_directory, publish_json, read_json
from .model import PAGE_SECTIONS, SECTIONS, Site

SITE_FILE = "site.json"
SCHEMA = 1


def site_envelope(site):
    """Canonical JSON value holding the site Bag in TYTX JSON and its SHA-256."""
    tytx = site.bag.to_tytx(transport="json")
    return {"schema": SCHEMA, "sha256": digest(tytx.encode("utf-8")), "site": tytx}


def site_from_envelope(envelope):
    """The site of an envelope; any mismatch fails closed with IntegrityError."""
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema", "sha256", "site"}
        or envelope["schema"] != SCHEMA
        or not isinstance(envelope["site"], str)
        or digest(envelope["site"].encode("utf-8")) != envelope["sha256"]
    ):
        raise IntegrityError("Site source failed its integrity check")
    try:
        bag = Bag.from_tytx(envelope["site"])
    except (BagException, TypeError, ValueError) as exc:
        raise IntegrityError("Site source is not a readable Bag") from exc
    check_structure(bag)
    return Site(bag)


def check_structure(bag):
    info = bag.get_node("info")
    if info is None or not {"site_id", "name"} <= set(info.attr):
        raise IntegrityError("Site source has no site identity")
    for section in SECTIONS:
        if not isinstance(bag.get_item(section), Bag):
            raise IntegrityError(f"Site source has no {section}")
    for page in bag.get_item("pages").values():
        if not isinstance(page, Bag) or any(
            page.get_node(section) is None for section in PAGE_SECTIONS
        ):
            raise IntegrityError("Site source has a malformed page")


class WorkingCopy:
    """Save and load one site in a private, application-owned directory."""

    def __init__(self, root):
        self.root = private_directory(root)
        self.staging = private_directory(self.root / "staging")

    def save(self, site):
        publish_json(self.root, SITE_FILE, site_envelope(site), self.staging)

    def load(self):
        envelope, _raw = read_json(self.root, SITE_FILE)
        return site_from_envelope(envelope)
