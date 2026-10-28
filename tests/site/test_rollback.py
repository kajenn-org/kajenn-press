"""Page and site rollback (N4 Phase 4)."""

import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.publish import Publisher
from kajenn_press.site.published import unpack_page
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    doc.body().div(node_label="body", kpress_slot="body")
"""
GRANTS = {"anna": {"*": ["read", "write", "create_site", "build", "publish"]}}


@pytest.fixture
def service(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    return SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy(GRANTS),
        worker=worker,
        publisher=Publisher(versioned_bucket(), worker),
    )


def run(service, operation, **arguments):
    return service.execute("anna", operation, **arguments)


def html_online(service, site, page):
    entry = service.publisher.index(site)["pages"][page]
    return unpack_page(service.publisher.node(entry["key"], entry["version_id"]).read_bytes()).html


def published_site(service):
    site = run(service, "site_new", key="n", name="S")["site_id"]
    template = run(
        service,
        "template_add",
        site_id=site,
        key="t",
        name="L",
        engine="gramlot",
        python_source=LAYOUT,
    )["template_id"]
    pages = {}
    for name in ("Home", "About"):
        page = run(service, "page_add", site_id=site, key=name, name=name, template_id=template)[
            "page_id"
        ]
        content = run(
            service,
            "content_add",
            site_id=site,
            key="c" + name,
            name=name,
            format="html",
            text=f"<p>{name} v1</p>",
        )["content_id"]
        run(
            service,
            "slot_assign",
            site_id=site,
            key="s" + name,
            page_id=page,
            slot="body",
            content_id=content,
        )
        pages[name] = page
    first = run(service, "publish", site_id=site, key="p1", selected=list(pages.values()))
    return site, pages, first


def edit_and_publish(service, site, pages, version, key):
    for name, page in pages.items():
        content = run(
            service,
            "content_add",
            site_id=site,
            key=f"{key}{name}",
            name=name,
            format="html",
            text=f"<p>{name} {version}</p>",
        )["content_id"]
        run(
            service,
            "slot_assign",
            site_id=site,
            key=f"{key}s{name}",
            page_id=page,
            slot="body",
            content_id=content,
        )
    return run(service, "publish", site_id=site, key=key, selected=list(pages.values()))


def test_a_page_rollback_changes_only_that_page(service):
    site, pages, _first = published_site(service)
    edit_and_publish(service, site, pages, "v2", "p2")
    versions = run(service, "page_versions", site_id=site, page_id=pages["Home"])
    assert [v["online"] for v in versions] == [False, True]

    run(
        service,
        "page_rollback",
        site_id=site,
        key="r",
        page_id=pages["Home"],
        version_id=versions[0]["version_id"],
    )

    assert "<p>Home v1</p>" in html_online(service, site, pages["Home"])
    assert "<p>About v2</p>" in html_online(service, site, pages["About"])
    assert [
        v["online"] for v in run(service, "page_versions", site_id=site, page_id=pages["Home"])
    ] == [True, False]


def test_a_site_rollback_serves_the_pages_of_the_chosen_source(service):
    site, pages, first = published_site(service)
    edit_and_publish(service, site, pages, "v2", "p2")

    result = run(
        service, "site_rollback", site_id=site, key="sr", version_id=first["source_version"]
    )

    assert result["failed"] == []
    assert "<p>Home v1</p>" in html_online(service, site, pages["Home"])
    assert "<p>About v1</p>" in html_online(service, site, pages["About"])
    operations = [n.attr["operation"] for n in service.working_copy(site).load().audit.nodes]
    assert operations[-1] == "site_rollback"


def test_rollback_to_an_unknown_version_is_refused(service):
    site, pages, _first = published_site(service)
    with pytest.raises(DomainError, match="No version"):
        run(
            service,
            "page_rollback",
            site_id=site,
            key="x",
            page_id=pages["Home"],
            version_id="missing",
        )
    with pytest.raises(DomainError, match="never published"):
        run(service, "page_versions", site_id=site, page_id="0" * 32)
