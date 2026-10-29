"""Published page objects and the site index (d-publish-unit, N4-D1, N4-D2).

A published page is one zip: `page.json` (the page Bag in TYTX JSON with its id, URL,
fingerprint and the SHA-256 of its HTML), `index.html` (the pre-rendered HTML) and
`assets/<sha256>.<ext>` (its asset bytes, addressed by content), and for a page whose
Data uses resolvers `request.json` (the worker request without connections), so the
serving server can render it again. The site index is
canonical JSON naming, for each page, its URL and the S3 version of its object that is
online; readers that follow the index always see a complete publication. `sitemap.xml`
and `robots.txt` are built by the serving server from the index and its own origin: the
sitemap lists the indexable pages; a root page that is not indexable closes the whole site
to robots.
"""

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass

from ..catalog.errors import IntegrityError
from ..catalog.filesystem import encode
from .seo import effective_seo
from .storage import FIXED_TIME

SCHEMA = 3
ASSET_NAME = re.compile(r"[0-9a-f]{64}\.[a-z0-9]{1,8}")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def language_bag(site, page_id, language):
    """The page Bag as one language sees it: only that language's translations and URL."""
    from .languages import main_language

    bag = site.node("pages", page_id).value.deepcopy()
    main = language == main_language(site)
    for copy in bag.get_item("translations").values():
        for code in [n.label for n in copy.nodes if main or n.label != language]:
            copy.pop(code)
    languages = bag.get_item("languages")
    for code in [n.label for n in languages.nodes if main or n.label != language]:
        languages.pop(code)
    return bag


def page_fingerprint(site, page_id, language=None):
    """What makes a page in a language change for Publish: name, URL, the page Bag as
    that language sees it, effective SEO, site texts and the site's languages.

    The effective SEO also follows the root defaults, so changing them changes every page
    that inherits them; a translation in one language leaves the others unchanged.
    """
    from .languages import language_url, main_language, site_languages
    from .render import page_texts

    language = language or main_language(site)
    node = site.node("pages", page_id)
    raw = encode(
        [
            node.attr["name"],
            language_url(site, page_id, language),
            language_bag(site, page_id, language).to_tytx(transport="json"),
            effective_seo(site, page_id, language=language),
            page_texts(site, language),
            site_languages(site),
        ]
    )
    return sha256(raw)


@dataclass(frozen=True)
class PublishedPage:
    page_id: str
    url: str
    fingerprint: str
    page: str
    html: str
    assets: dict
    indexable: bool
    language: str
    request: str | None = None
    refresh: int = 0


def pack_page(published):
    """Deterministic zip bytes of a published page."""
    entries = {
        "page.json": encode(
            {
                "schema": SCHEMA,
                "page_id": published.page_id,
                "url": published.url,
                "fingerprint": published.fingerprint,
                "html_sha256": sha256(published.html.encode("utf-8")),
                "page": published.page,
                "refresh": published.refresh,
                "indexable": published.indexable,
                "language": published.language,
            }
        ),
        "index.html": published.html.encode("utf-8"),
        **({"request.json": published.request.encode("utf-8")} if published.request else {}),
        **{f"assets/{name}": data for name, data in sorted(published.assets.items())},
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return stream.getvalue()


def unpack_page(raw):
    """The published page in zip bytes; any mismatch fails closed."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if names[:2] != ["page.json", "index.html"]:
                raise IntegrityError("A published page starts with page.json and index.html")
            meta = json.loads(archive.read("page.json"))
            html = archive.read("index.html").decode("utf-8")
            request = None
            rest = names[2:]
            if rest[:1] == ["request.json"]:
                request = archive.read("request.json").decode("utf-8")
                json.loads(request)
                rest = rest[1:]
            assets = {}
            for name in rest:
                asset = name.removeprefix("assets/")
                if name == asset or not ASSET_NAME.fullmatch(asset):
                    raise IntegrityError(f"Unexpected entry {name} in a published page")
                data = archive.read(name)
                if sha256(data) != asset.split(".")[0]:
                    raise IntegrityError(f"Asset {asset} does not match its content")
                assets[asset] = data
    except (zipfile.BadZipFile, UnicodeDecodeError, ValueError) as exc:
        raise IntegrityError("Published page is not readable") from exc
    if (
        not isinstance(meta, dict)
        or set(meta)
        != {
            "schema",
            "page_id",
            "url",
            "fingerprint",
            "html_sha256",
            "page",
            "refresh",
            "indexable",
            "language",
        }
        or meta["schema"] != SCHEMA
        or not isinstance(meta["indexable"], bool)
        or meta["html_sha256"] != sha256(html.encode("utf-8"))
    ):
        raise IntegrityError("Published page failed its integrity check")
    return PublishedPage(
        meta["page_id"],
        meta["url"],
        meta["fingerprint"],
        meta["page"],
        html,
        assets,
        meta["indexable"],
        meta["language"],
        request,
        meta["refresh"],
    )


def make_index(site_id, source_version, pages, redirects, maintenance=False):
    """Canonical JSON bytes of a site index.

    `pages` maps page ids to {"url", "key", "version_id", "fingerprint", "assets",
    "refresh"}: `assets` lists the content-addressed asset names the page object holds;
    `refresh` is how many seconds its rendering stays valid (0 for a static page);
    `indexable` is false for a `noindex` page, left out of `sitemap.xml`; `language` is
    the language of the object. The main language's entry is keyed by the page id, every
    other language's by `<page id>.<language>` (N9-D5).
    """
    urls = [entry["url"] for entry in pages.values()]
    if len(urls) != len(set(urls)):
        raise IntegrityError("Two published pages share a URL")
    return encode(
        {
            "schema": SCHEMA,
            "site_id": site_id,
            "source_version": source_version,
            "maintenance": bool(maintenance),
            "pages": pages,
            "redirects": redirects,
        }
    )


def index_schema(raw):
    """The schema number of index bytes, or None when they are not an index object."""
    try:
        index = json.loads(raw)
    except ValueError:
        return None
    return index.get("schema") if isinstance(index, dict) else None


def read_index(raw):
    """The site index in bytes, checked; any mismatch fails closed."""
    try:
        index = json.loads(raw)
    except ValueError as exc:
        raise IntegrityError("Site index is not JSON") from exc
    if (
        not isinstance(index, dict)
        or set(index)
        != {"schema", "site_id", "source_version", "maintenance", "pages", "redirects"}
        or index["schema"] != SCHEMA
        or not isinstance(index["pages"], dict)
        or not isinstance(index["redirects"], dict)
        or any(
            set(entry)
            != {
                "url",
                "key",
                "version_id",
                "fingerprint",
                "assets",
                "refresh",
                "indexable",
                "language",
            }
            for entry in index["pages"].values()
        )
        or len({e["url"] for e in index["pages"].values()}) != len(index["pages"])
    ):
        raise IntegrityError("Site index failed its integrity check")
    return index


BINDINGS_SCHEMA = 2
STATES = ("public", "private")
# The site server of an installation that registered none (N7b): the demo's and the tests'.
DEFAULT_SERVER = "default"
ENTRY = {"site_id", "state", "server", "redirect"}


def make_bindings(bindings):
    """Canonical JSON bytes of the bindings (N7-D2, d-www).

    Public origin -> {"site_id", "state", "server", "redirect"}: each site has one origin
    with `redirect` None, its address, and at most one alias whose `redirect` is that
    address.
    """
    addresses = {}
    for origin, entry in bindings.items():
        if set(entry) != ENTRY or entry["state"] not in STATES:
            raise IntegrityError("Bindings entries are site, state, server and redirect")
        if entry["redirect"] is None:
            if entry["site_id"] in addresses:
                raise IntegrityError("A site has one address")
            addresses[entry["site_id"]] = origin
    for origin, entry in bindings.items():
        if entry["redirect"] is not None and addresses.get(entry["site_id"]) != entry["redirect"]:
            raise IntegrityError(f"{origin} redirects to an origin that is not its site's address")
    return encode({"schema": BINDINGS_SCHEMA, "bindings": bindings})


def read_bindings(raw):
    """The bindings in bytes, checked; any mismatch fails closed.

    Bindings of schema 1 (before N7b) are read with the default server and no alias.
    """
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise IntegrityError("Bindings are not JSON") from exc
    if not isinstance(document, dict) or set(document) != {"schema", "bindings"}:
        raise IntegrityError("Bindings failed their integrity check")
    bindings = document["bindings"]
    if not isinstance(bindings, dict) or not all(isinstance(e, dict) for e in bindings.values()):
        raise IntegrityError("Bindings failed their integrity check")
    if document["schema"] == 1:
        bindings = {
            origin: {**entry, "server": DEFAULT_SERVER, "redirect": None}
            for origin, entry in bindings.items()
        }
    elif document["schema"] != BINDINGS_SCHEMA:
        raise IntegrityError("Bindings have an unknown schema")
    make_bindings(bindings)
    return bindings
