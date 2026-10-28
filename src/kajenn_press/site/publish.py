"""Publish a site page by page to a versioned release bucket (d-publish-select, N4-D2).

Page objects are written first, each as a new S3 version; the site index is written last
and pins the version of every page that is online, so readers never see half a
publication. A page that fails to render is reported and keeps its previous version.
"""

import json

from genro_storage import StorageManager

from ..catalog.errors import IntegrityError
from ..domain import DomainError
from .published import (
    PublishedPage,
    make_index,
    pack_page,
    page_fingerprint,
    read_index,
    unpack_page,
)
from .render import page_assets, page_request
from .store import require_versioning

MOUNT = "releases"
DEFAULT_REFRESH = 600


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
    def __init__(self, config, worker, connections=None):
        self.config = dict(config)
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

    def page_path(self, site_id, page_id):
        return f"sites/{site_id}/pages/{page_id}.zip"

    def index(self, site_id, version_id=None):
        """The site index online, or None before the first Publish."""
        node = self.node(self.index_path(site_id), version_id)
        if not node.exists():
            return None
        return read_index(node.read_bytes())

    def plan(self, site):
        """Each page with its state against the index online; changes are selected."""
        index = self.index(site.site_id) or {"pages": {}}
        online = index["pages"]
        plan = []
        for node in site.section("pages").nodes:
            page_id = node.label
            entry = online.get(page_id)
            state = (
                "new"
                if entry is None
                else "unchanged"
                if entry["fingerprint"] == page_fingerprint(site, page_id)
                else "changed"
            )
            check = site.page_check(page_id)
            warnings = [f"empty slot {name}" for name in check["empty_slots"]]
            warnings += [f"unplaced content {key}" for key in check["unplaced"]]
            plan.append(
                {
                    "page_id": page_id,
                    "name": node.attr["name"],
                    "url": node.attr["url"],
                    "state": state,
                    "selected": state != "unchanged",
                    "warnings": warnings,
                }
            )
        for page_id, entry in online.items():
            if site.section("pages").get_node(page_id) is None:
                plan.append(
                    {
                        "page_id": page_id,
                        "name": None,
                        "url": entry["url"],
                        "state": "removed",
                        "selected": True,
                        "warnings": [],
                    }
                )
        return plan

    def publish(self, site, source_version, selected):
        """Write the selected pages, then the index; returns what happened to each page."""
        index = self.index(site.site_id) or {"pages": {}, "maintenance": False}
        pages = dict(index["pages"])
        published, failed = [], []
        for page_id in selected:
            if site.section("pages").get_node(page_id) is None:
                if page_id not in pages:
                    raise DomainError("not_found", f"No page {page_id}", resource_id=page_id)
                pages.pop(page_id)
                published.append({"page_id": page_id, "state": "removed"})
                continue
            request = page_request(site, page_id, self.connections, published=True)
            result = self.worker.render_page(request)
            if result["status"] != "succeeded":
                failed.append({"page_id": page_id, "diagnostics": result["diagnostics"]})
                continue
            assets = {name: data for _url, name, data in page_assets(site, page_id, True).values()}
            url = site.node("pages", page_id).attr["url"]
            fingerprint = page_fingerprint(site, page_id)
            refresh = refresh_seconds(site, page_id)
            stored = {k: v for k, v in request.items() if k != "connections"}
            raw = pack_page(
                PublishedPage(
                    page_id,
                    url,
                    fingerprint,
                    site.node("pages", page_id).value.to_tytx(transport="json"),
                    result["html"],
                    assets,
                    json.dumps(stored, sort_keys=True) if refresh else None,
                    refresh,
                )
            )
            node = self.node(self.page_path(site.site_id, page_id))
            node.write_bytes(raw)
            pages[page_id] = {
                "url": url,
                "key": self.page_path(site.site_id, page_id),
                "version_id": node.versions[-1]["version_id"],
                "fingerprint": fingerprint,
                "assets": sorted(assets),
                "refresh": refresh,
            }
            published.append({"page_id": page_id, "state": "published"})
        try:
            raw_index = make_index(
                site.site_id, source_version, pages, site.redirects(), index["maintenance"]
            )
        except IntegrityError as exc:
            raise DomainError("conflict", str(exc)) from exc
        node = self.node(self.index_path(site.site_id))
        node.write_bytes(raw_index)
        return {
            "published": published,
            "failed": failed,
            "index_version": node.versions[-1]["version_id"],
        }

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
        """Put an earlier version of a page online: a new index pinning it."""
        index = self.index(site_id)
        if index is None:
            raise DomainError("not_found", f"Site {site_id} was never published")
        key = self.page_path(site_id, page_id)
        if version_id not in {v["version_id"] for v in self.page_versions(site_id, page_id)}:
            raise DomainError("not_found", f"No version {version_id} of page {page_id}")
        earlier = unpack_page(self.node(key, version_id).read_bytes())
        if earlier.page_id != page_id:
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
