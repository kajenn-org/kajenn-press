"""The unpacked working copy of a site: one durable file in a private local directory.

The file is canonical JSON holding the site Bag in TYTX JSON and its SHA-256. A missing,
malformed or altered file fails closed. N3 zips this copy and versions it on S3.
"""

import io
import json
import zipfile

from genro_bag import Bag, BagException

from ..catalog.errors import IntegrityError
from ..catalog.filesystem import digest, encode, private_directory, publish_json, read_json
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
    add_missing_sections(bag)
    check_structure(bag)
    return Site(bag)


def add_missing_sections(bag):
    """Sources saved before N6 and N9 lack the sections those added: add them empty.

    Any other missing section is still refused by `check_structure`.
    """
    for section in ("texts", "translations"):
        if bag.get_node(section) is None:
            bag.set_item(section, Bag())
    pages = bag.get_item("pages")
    for page in pages.values() if isinstance(pages, Bag) else ():
        for section in ("seo", "translations", "languages"):
            if isinstance(page, Bag) and page.get_node(section) is None:
                page.set_item(section, Bag())


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
