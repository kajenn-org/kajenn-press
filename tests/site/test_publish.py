"""Publish page by page to a versioned release bucket (N4 Phase 3)."""

import base64
import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.rendering.resolvers import ConfigValueResolver
from kajenn_press.site.publish import Publisher
from kajenn_press.site.published import unpack_page
from kajenn_press.site.render import published_asset_name
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.img(src="^assets.logo.url", alt="")
    body.div(node_label="body", kpress_slot="body")
"""
PNG = b"\x89PNG\r\n\x1a\nlogo"
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


def build_site(service):
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
    logo = run(
        service,
        "asset_add",
        site_id=site,
        key="a",
        name="logo",
        kind="media",
        data_base64=base64.b64encode(PNG).decode(),
        mime_type="image/png",
    )["asset_id"]
    pages = []
    for name in ("Home", "About"):
        page = run(service, "page_add", site_id=site, key=name, name=name, template_id=template)[
            "page_id"
        ]
        run(service, "page_asset_add", site_id=site, key="pa" + name, page_id=page, asset_id=logo)
        content = run(
            service,
            "content_add",
            site_id=site,
            key="c" + name,
            name=name,
            format="html",
            text=f"<p>{name}</p>",
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
        pages.append(page)
    return site, pages


def online(service, site):
    return service.publisher.index(site)["pages"]


def object_of(service, site, page_id):
    entry = online(service, site)[page_id]
    return unpack_page(service.publisher.node(entry["key"], entry["version_id"]).read_bytes())


def test_first_publish_puts_every_page_online_with_content_addressed_assets(service):
    site, pages = build_site(service)
    plan = run(service, "publish_plan", site_id=site)
    assert [(p["state"], p["selected"]) for p in plan] == [("new", True), ("new", True)]

    result = run(service, "publish", site_id=site, key="p1", selected=[p["page_id"] for p in plan])

    assert result["failed"] == [] and len(result["published"]) == 2
    index = service.publisher.index(site)
    assert index["source_version"] == result["source_version"]
    assert sorted(e["url"] for e in index["pages"].values()) == ["/", "/about/"]
    home = object_of(service, site, pages[0])
    asset = published_asset_name(PNG, "image/png")
    assert f'src="/_assets/{asset}"' in home.html and "<p>Home</p>" in home.html
    assert home.assets == {asset: PNG}
    assert [p["state"] for p in run(service, "publish_plan", site_id=site)] == ["unchanged"] * 2


def test_publishing_one_changed_page_leaves_the_other_untouched(service):
    site, pages = build_site(service)
    run(service, "publish", site_id=site, key="p1", selected=pages)
    before = online(service, site)
    run(service, "page_url_set", site_id=site, key="u", page_id=pages[0], url="/start/")
    run(service, "page_url_set", site_id=site, key="v", page_id=pages[1], url="/team/")

    plan = {p["page_id"]: p["state"] for p in run(service, "publish_plan", site_id=site)}
    assert plan == {pages[0]: "changed", pages[1]: "changed"}
    run(service, "publish", site_id=site, key="p2", selected=[pages[0]])

    after = online(service, site)
    assert after[pages[0]]["version_id"] != before[pages[0]]["version_id"]
    assert after[pages[1]] == before[pages[1]]
    assert after[pages[0]]["url"] == "/start/" and after[pages[1]]["url"] == "/about/"
    states = {p["page_id"]: p["state"] for p in run(service, "publish_plan", site_id=site)}
    assert states == {pages[0]: "unchanged", pages[1]: "changed"}


def test_a_page_that_fails_to_render_keeps_its_previous_version(service, tmp_path):
    site_id, pages = build_site(service)
    run(service, "publish", site_id=site_id, key="p1", selected=pages)
    before = online(service, site_id)
    site = service.working_copy(site_id).load()
    site.page(pages[1]).bag.get_item("data").set_item(
        "news", None, resolver=ConfigValueResolver(connection="missing", key="x")
    )
    site.set_page_url(pages[0], "/start/")

    result = service.publisher.publish(site, "sv", pages)

    assert [f["page_id"] for f in result["failed"]] == [pages[1]]
    assert result["failed"][0]["diagnostics"][0]["code"] == "missing_connection"
    after = online(service, site_id)
    assert after[pages[1]] == before[pages[1]]
    assert after[pages[0]]["url"] == "/start/"


def test_a_removed_page_leaves_the_index(service):
    site_id, pages = build_site(service)
    run(service, "publish", site_id=site_id, key="p1", selected=pages)
    site = service.working_copy(site_id).load()
    site.section("pages").pop(pages[1])

    plan = service.publisher.plan(site)
    assert [p["state"] for p in plan] == ["unchanged", "removed"]
    service.publisher.publish(site, "sv", [pages[1]])
    assert list(online(service, site_id)) == [pages[0]]


def test_publish_needs_the_lock_the_grant_and_a_release_bucket(service, tmp_path):
    site, pages = build_site(service)
    service.lock.release(site, "anna")
    with pytest.raises(DomainError, match="Take the site"):
        run(service, "publish", site_id=site, key="p", selected=pages)
    plain = SiteService(tmp_path / "x", service.store, AccessPolicy(GRANTS))
    with pytest.raises(DomainError, match="release bucket"):
        plain.execute("anna", "publish_plan", site_id=site)
    other = SiteService(
        tmp_path / "y",
        service.store,
        AccessPolicy({"bob": {"*": ["read"]}}),
        publisher=service.publisher,
    )
    with pytest.raises(DomainError, match="Missing publish"):
        other.execute("bob", "publish_plan", site_id=site)


def test_warnings_are_listed_but_do_not_block(service):
    site, _pages = build_site(service)
    template = run(service, "site_read", site_id=site)["templates"][0]["id"]
    extra = run(service, "page_add", site_id=site, key="e", name="Empty", template_id=template)
    logo = run(service, "site_read", site_id=site)["assets"][0]["id"]
    run(service, "page_asset_add", site_id=site, key="ea", page_id=extra["page_id"], asset_id=logo)
    plan = {p["page_id"]: p for p in run(service, "publish_plan", site_id=site)}
    assert plan[extra["page_id"]]["warnings"] == ["empty slot body"]
    result = run(service, "publish", site_id=site, key="p", selected=list(plan))
    assert result["failed"] == []
