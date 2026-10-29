"""Publish a site page by page to a versioned release bucket (d-publish-select, N4-D2).

Page objects are written first, each as a new S3 version; the site index is written last
and pins the version of every page that is online, so readers never see half a
publication. A page that fails to render is reported and keeps its previous version.
`bindings.json` gives each site its address, the public origin of its root page, and
its state, public or private; site servers read it like an index (N7-D2, N7-D3).
"""

import json

from genro_storage import StorageManager

from ..catalog.errors import IntegrityError
from ..domain import DomainError
from ..publication.routes import origin
from .languages import language_url, site_languages
from .private import PREFIX, private_token
from .published import (
    SCHEMA,
    STATES,
    PublishedPage,
    index_schema,
    make_bindings,
    make_index,
    pack_page,
    page_fingerprint,
    read_bindings,
    read_index,
    unpack_page,
)
from .render import page_assets, page_request, social_image_file
from .seo import effective_seo, indexable, root_page_id, seo_check
from .store import require_versioning

MOUNT = "releases"
BINDINGS_PATH = "bindings.json"
DEFAULT_REFRESH = 600


def entry_name(page_id, language, main):
    """The index entry of a page in a language: the page id for the main language."""
    return page_id if language == main else f"{page_id}.{language}"


def refresh_seconds(site, page_id):
    """Seconds a page's rendering stays valid: the shortest resolver cache, 0 if none."""
    times = [
        node.resolver.cache_time
        for node in site.page(page_id).bag.get_item("data").nodes
        if node.resolver is not None
    ]
    if not times:
        return 0
    return min(time if time > 0 else DEFAULT_REFRESH for time in times)


class Publisher:
    def __init__(self, config, worker, connections=None, private_secret=None):
        self.config = dict(config)
        self.private_secret = private_secret
        require_versioning(self.config, "release")
        self.storage = StorageManager()
        self.storage.configure([{"name": MOUNT, **self.config}])
        self.worker = worker
        self.connections = connections or {}

    def node(self, path, version_id=None):
        full = f"{MOUNT}:{path}"
        return (
            self.storage.node(full, version=version_id) if version_id else self.storage.node(full)
        )

    def index_path(self, site_id):
        return f"sites/{site_id}/index.json"

    def page_path(self, site_id, entry):
        """The object of an index entry: `<page id>` or `<page id>.<language>` (N9-D5)."""
        return f"sites/{site_id}/pages/{entry}.zip"

    def index(self, site_id, version_id=None):
        """The site index online, or None before the first Publish.

        A current index of an earlier schema (before N6 or N9) also reads as None: the next
        Publish writes every selected page and a new index.
        """
        node = self.node(self.index_path(site_id), version_id)
        if not node.exists():
            return None
        raw = node.read_bytes()
        schema = index_schema(raw)
        if version_id is None and isinstance(schema, int) and schema < SCHEMA:
            return None
        return read_index(raw)

    def plan(self, site):
        """Each page in each language with its state against the index online; changes
        are selected. `entry` is what Publish selects: the page id for the main language,
        `<page id>.<language>` for the others."""
        index = self.index(site.site_id) or {"pages": {}}
        online = index["pages"]
        problems = seo_check(site)
        languages = site_languages(site)
        plan, known = [], set()
        for node in site.section("pages").nodes:
            page_id = node.label
            check = site.page_check(page_id)
            warnings = [f"empty slot {name}" for name in check["empty_slots"]]
            warnings += [f"unplaced content {key}" for key in check["unplaced"]]
            warnings += [p["message"] for p in problems if p["page_id"] == page_id]
            for language in languages:
                entry_id = entry_name(page_id, language, languages[0])
                known.add(entry_id)
                entry = online.get(entry_id)
                state = (
                    "new"
                    if entry is None
                    else "unchanged"
                    if entry["fingerprint"] == page_fingerprint(site, page_id, language)
                    else "changed"
                )
                plan.append(
                    {
                        "page_id": page_id,
                        "entry": entry_id,
                        "language": language,
                        "name": node.attr["name"],
                        "url": language_url(site, page_id, language),
                        "state": state,
                        "selected": state != "unchanged",
                        "warnings": warnings if language == languages[0] else [],
                    }
                )
        for entry_id, entry in online.items():
            if entry_id not in known:
                plan.append(
                    {
                        "page_id": entry_id.partition(".")[0],
                        "entry": entry_id,
                        "language": entry["language"],
                        "name": None,
                        "url": entry["url"],
                        "state": "removed",
                        "selected": True,
                        "warnings": [],
                    }
                )
        return plan

    def bindings(self):
        """Public origin -> {"site_id", "state"} of every bound site (N7-D2)."""
        node = self.node(BINDINGS_PATH)
        return read_bindings(node.read_bytes()) if node.exists() else {}

    def binding(self, site_id):
        """(origin, entry) of a site, or (None, None) when it has no address."""
        for public_origin, entry in self.bindings().items():
            if entry["site_id"] == site_id:
                return public_origin, entry
        return None, None

    def site_address(self, site):
        """The site's address: the public origin of its root page (N7-D3), or None."""
        root = root_page_id(site)
        value = effective_seo(site, root)["origin"] if root is not None else ""
        # `origin` refuses http outside loopback hosts with a DomainError of its own.
        return origin(value) if value else None

    def check_address(self, site_id, public_origin):
        if public_origin is None:
            return
        entry = self.bindings().get(public_origin)
        if entry is not None and entry["site_id"] != site_id:
            raise DomainError("conflict", f"{public_origin} is the address of another site")

    def bind(self, site_id, public_origin, state=None):
        """Give a site its address (or none); the state is kept unless given."""
        self.check_address(site_id, public_origin)
        bindings = self.bindings()
        _previous, entry = self.binding(site_id)
        bindings = {o: e for o, e in bindings.items() if e["site_id"] != site_id}
        if public_origin is not None:
            kept = entry["state"] if entry is not None else "public"
            bindings[public_origin] = {"site_id": site_id, "state": state or kept}
        try:
            raw = make_bindings(bindings)
        except IntegrityError as exc:
            raise DomainError("conflict", str(exc)) from exc
        self.node(BINDINGS_PATH).write_bytes(raw)

    def state(self, site):
        """What the Published site tab shows: address, state, last Publish, pending changes."""
        address, entry = self.binding(site.site_id)
        try:
            wanted, problem = self.site_address(site), None
        except DomainError as exc:
            wanted, problem = None, str(exc)
        index = self.index(site.site_id)
        node = self.node(self.index_path(site.site_id))
        last = node.versions[-1] if index is not None else None
        return {
            "address": address,
            "next_address": wanted if wanted != address else None,
            "address_problem": problem,
            "state": entry["state"] if entry is not None else None,
            "maintenance": bool(index and index["maintenance"]),
            "published": index is not None,
            "last_publish": str(last["last_modified"]) if last else None,
            "index_version": last["version_id"] if last else None,
            "changed": sum(1 for item in self.plan(site) if item["state"] != "unchanged"),
        }

    def set_visibility(self, site, state):
        """Make a site public or private at its address; possible before the first Publish."""
        if state not in STATES:
            raise DomainError("invalid_input", "A site is public or private")
        address = self.site_address(site)
        if address is None:
            raise DomainError("invalid_input", "Give the root page a public origin first")
        self.bind(site.site_id, address, state)
        return {"address": address, "state": state}

    def private_link(self, site_id, hours):
        """A link that shows the real site while private or in maintenance (N7-D4)."""
        if self.private_secret is None:
            raise DomainError("unavailable", "Private links are not configured")
        address, _entry = self.binding(site_id)
        if address is None:
            raise DomainError("invalid_input", "The site has no address yet")
        try:
            token, expires = private_token(self.private_secret, site_id, hours)
        except ValueError as exc:
            raise DomainError("invalid_input", str(exc)) from exc
        return {"url": address + PREFIX + token, "expires": expires}

    def publish(self, site, source_version, selected):
        """Write the selected pages, then the index and the address; returns what happened."""
        address = self.site_address(site)
        self.check_address(site.site_id, address)
        index = self.index(site.site_id) or {"pages": {}, "maintenance": False}
        pages = dict(index["pages"])
        published, failed = [], []
        for entry_id, page_id, language in self.selected_entries(site, pages, selected):
            if language is None:
                pages.pop(entry_id)
                published.append({"page_id": page_id, "entry": entry_id, "state": "removed"})
                continue
            request = page_request(
                site, page_id, self.connections, published=True, language=language
            )
            result = self.worker.render_page(request)
            if result["status"] != "succeeded":
                failed.append(
                    {"page_id": page_id, "entry": entry_id, "diagnostics": result["diagnostics"]}
                )
                continue
            assets = {name: data for _url, name, data in page_assets(site, page_id, True).values()}
            image = social_image_file(site, page_id)
            if image is not None:
                assets[image[0]] = image[1]
            url = language_url(site, page_id, language)
            fingerprint = page_fingerprint(site, page_id, language)
            refresh = refresh_seconds(site, page_id)
            stored = {k: v for k, v in request.items() if k != "connections"}
            seen = indexable(effective_seo(site, page_id, language=language))
            raw = pack_page(
                PublishedPage(
                    page_id,
                    url,
                    fingerprint,
                    site.node("pages", page_id).value.to_tytx(transport="json"),
                    result["html"],
                    assets,
                    seen,
                    language,
                    json.dumps(stored, sort_keys=True) if refresh else None,
                    refresh,
                )
            )
            node = self.node(self.page_path(site.site_id, entry_id))
            node.write_bytes(raw)
            pages[entry_id] = {
                "url": url,
                "key": self.page_path(site.site_id, entry_id),
                "version_id": node.versions[-1]["version_id"],
                "fingerprint": fingerprint,
                "assets": sorted(assets),
                "refresh": refresh,
                "indexable": seen,
                "language": language,
            }
            published.append({"page_id": page_id, "entry": entry_id, "state": "published"})
        try:
            raw_index = make_index(
                site.site_id, source_version, pages, site.redirects(), index["maintenance"]
            )
        except IntegrityError as exc:
            raise DomainError("conflict", str(exc)) from exc
        node = self.node(self.index_path(site.site_id))
        node.write_bytes(raw_index)
        self.bind(site.site_id, address)
        return {
            "published": published,
            "failed": failed,
            "index_version": node.versions[-1]["version_id"],
        }

    def selected_entries(self, site, online, selected):
        """(entry, page id, language) for each selection; language None removes the entry.

        A page id selects every language of the page; `<page id>.<language>` one language.
        """
        languages = site_languages(site)
        found = []
        for item in selected:
            page_id, _, language = item.partition(".")
            if site.section("pages").get_node(page_id) is None or (
                language and language not in languages
            ):
                gone = [
                    e for e in online if e == item or (not language and e.partition(".")[0] == item)
                ]
                if not gone:
                    raise DomainError("not_found", f"No page {item}", resource_id=item)
                found += [(entry, page_id, None) for entry in gone]
                continue
            for code in [language] if language else languages:
                found.append((entry_name(page_id, code, languages[0]), page_id, code))
        return found

    def page_versions(self, site_id, page_id):
        """Versions of a page object, oldest first, with the one online marked."""
        node = self.node(self.page_path(site_id, page_id))
        if not node.exists():
            raise DomainError("not_found", f"Page {page_id} was never published")
        index = self.index(site_id) or {"pages": {}}
        current = index["pages"].get(page_id, {}).get("version_id")
        return [
            {
                "version_id": v["version_id"],
                "last_modified": str(v["last_modified"]),
                "size": v["size"],
                "online": v["version_id"] == current,
            }
            for v in node.versions
        ]

    def page_rollback(self, site_id, page_id, version_id):
        """Put an earlier version of a page online: a new index pinning it.

        `page_id` is an index entry: the page id (main language) or `<page id>.<language>`.
        """
        index = self.index(site_id)
        if index is None:
            raise DomainError("not_found", f"Site {site_id} was never published")
        key = self.page_path(site_id, page_id)
        if version_id not in {v["version_id"] for v in self.page_versions(site_id, page_id)}:
            raise DomainError("not_found", f"No version {version_id} of page {page_id}")
        earlier = unpack_page(self.node(key, version_id).read_bytes())
        if earlier.page_id != page_id.partition(".")[0]:
            raise IntegrityError("Page object holds another page")
        pages = {
            **index["pages"],
            page_id: {
                "url": earlier.url,
                "key": key,
                "version_id": version_id,
                "fingerprint": earlier.fingerprint,
                "assets": sorted(earlier.assets),
                "refresh": earlier.refresh,
                "indexable": earlier.indexable,
                "language": earlier.language,
            },
        }
        try:
            raw = make_index(
                site_id, index["source_version"], pages, index["redirects"], index["maintenance"]
            )
        except IntegrityError as exc:
            raise DomainError("conflict", str(exc)) from exc
        node = self.node(self.index_path(site_id))
        node.write_bytes(raw)
        return {
            "page_id": page_id,
            "version_id": version_id,
            "url": earlier.url,
            "index_version": node.versions[-1]["version_id"],
        }

    def set_maintenance(self, site_id, on):
        """A new index with the maintenance flag set or cleared; pages stay as they are."""
        index = self.index(site_id)
        if index is None:
            raise DomainError("not_found", f"Site {site_id} was never published")
        raw = make_index(
            site_id, index["source_version"], index["pages"], index["redirects"], bool(on)
        )
        node = self.node(self.index_path(site_id))
        node.write_bytes(raw)
        return {"maintenance": bool(on), "index_version": node.versions[-1]["version_id"]}
