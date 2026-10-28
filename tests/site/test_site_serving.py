"""The Kajenn server application that serves published sites (N4 Phase 5)."""

import asyncio
import base64
import os

import pytest
from child.support import running
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.rendering.resolvers import ConfigValueResolver
from kajenn_press.site.publish import Publisher
from kajenn_press.site.published import unpack_page
from kajenn_press.site.render import published_asset_name
from kajenn_press.site.service import SiteService
from kajenn_press.site.serving import create_site_server
from kajenn_press.site.store import SourceStore

ORIGIN = "http://site.localhost"
LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.img(src="^assets.logo.url", alt="")
    body.div("^news", node_label="news")
    body.div(node_label="body", kpress_slot="body")
"""
PNG = b"\x89PNG\r\n\x1a\nlogo"
GRANTS = {"anna": {"*": ["read", "write", "create_site", "build", "publish"]}}


@pytest.fixture
def setup(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    releases = versioned_bucket()
    service = SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy(GRANTS),
        worker=worker,
        publisher=Publisher(releases, worker, {"site": {"headline": "at publish"}}),
    )
    return service, releases, worker


def run(service, operation, **arguments):
    return service.execute("anna", operation, **arguments)


def publish_site(service, refresh=None):
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
    pages = {}
    for name in ("Home", "About"):
        page = run(service, "page_add", site_id=site, key=name, name=name, template_id=template)[
            "page_id"
        ]
        run(service, "page_asset_add", site_id=site, key="a" + name, page_id=page, asset_id=logo)
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
        pages[name] = page
    copy = service.working_copy(site)
    edited = copy.load()
    for page in pages.values():
        edited.page(page).bag.get_item("data").set_item(
            "news",
            None,
            resolver=ConfigValueResolver(
                connection="site", key="headline", cache_time=refresh or 0
            ),
        )
    copy.save(edited)
    run(service, "publish", site_id=site, key="p", selected=list(pages.values()))
    return site, pages


def server(setup, site, tmp_path, connections=None, cache_seconds=0.2):
    _service, releases, worker = setup
    return create_site_server(
        bindings={ORIGIN: site},
        release_storage=releases,
        cache_root=tmp_path / "cache",
        cache_seconds=cache_seconds,
        worker=worker,
        connections=connections or {},
    )


def get(app, *paths, method="GET"):
    async def scenario():
        async with running(app, ORIGIN) as http:
            return [await http.request(method, path) for path in paths]

    return asyncio.run(scenario())


def test_pages_assets_sitemap_and_robots(setup, tmp_path):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    entry = service.publisher.index(site)["pages"][pages["Home"]]
    rendered = unpack_page(service.publisher.node(entry["key"], entry["version_id"]).read_bytes())
    asset = published_asset_name(PNG, "image/png")

    home, about, image, sitemap, robots, head = get(
        server(setup, site, tmp_path),
        "/",
        "/about/",
        f"/_assets/{asset}",
        "/sitemap.xml",
        "/robots.txt",
    ) + get(server(setup, site, tmp_path), "/", method="HEAD")

    assert home.status_code == 200 and home.text == rendered.html
    assert home.headers["content-type"].startswith("text/html")
    assert "<p>About</p>" in about.text
    assert image.content == PNG and "immutable" in image.headers["cache-control"]
    assert image.headers["content-type"] == "image/png"
    assert f"<loc>{ORIGIN}/</loc>" in sitemap.text and f"<loc>{ORIGIN}/about/</loc>" in sitemap.text
    assert robots.text == f"User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n"
    assert head.status_code == 200 and head.content == b""


def test_redirects_missing_slash_and_404(setup, tmp_path):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    run(service, "page_url_set", site_id=site, key="u", page_id=pages["About"], url="/team/")
    run(service, "publish", site_id=site, key="p2", selected=[pages["About"]])

    old, slash, missing, post = get(
        server(setup, site, tmp_path), "/about/", "/team", "/nope/"
    ) + get(server(setup, site, tmp_path), "/", method="POST")

    assert (old.status_code, old.headers["location"]) == (301, "/team/")
    assert (slash.status_code, slash.headers["location"]) == (301, "/team/")
    assert missing.status_code == 404
    assert post.status_code == 405

    run(service, "page_url_set", site_id=site, key="u2", page_id=pages["About"], url="/404/")
    run(service, "publish", site_id=site, key="p3", selected=[pages["About"]])
    (custom,) = get(server(setup, site, tmp_path), "/nope/")
    assert custom.status_code == 404 and "<p>About</p>" in custom.text


def test_a_new_index_is_followed_within_the_cache_interval(setup, tmp_path):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    app = server(setup, site, tmp_path, cache_seconds=0.5)

    async def scenario():
        async with running(app, ORIGIN) as http:
            before = (await http.get("/about/")).status_code
            run(
                service, "page_url_set", site_id=site, key="u", page_id=pages["About"], url="/team/"
            )
            run(service, "publish", site_id=site, key="p2", selected=[pages["About"]])
            await asyncio.sleep(0.6)
            return before, (await http.get("/team/")).status_code

    assert asyncio.run(scenario()) == (200, 200)


def test_resolver_pages_refresh_after_their_cache_time_and_survive_a_restart(setup, tmp_path):
    service, _releases, _worker = setup
    site, _pages = publish_site(service, refresh=1)
    connections = {"site": {"headline": "first"}}
    app = server(setup, site, tmp_path, connections=connections)

    async def scenario():
        async with running(app, ORIGIN) as http:
            first = (await http.get("/")).text
            connections["site"]["headline"] = "second"
            cached = (await http.get("/")).text
            await asyncio.sleep(1.1)
            return first, cached, (await http.get("/")).text

    first, cached, refreshed = asyncio.run(scenario())
    assert "<div>first</div>" in first and "<div>first</div>" in cached
    assert "<div>second</div>" in refreshed
    (restarted,) = get(
        server(setup, site, tmp_path, connections={"site": {"headline": "third"}}), "/"
    )
    assert "<div>second</div>" in restarted.text


def test_an_unknown_host_is_not_found(setup, tmp_path):
    service, _releases, _worker = setup
    site, _pages = publish_site(service)

    async def scenario():
        async with running(server(setup, site, tmp_path), "http://other.localhost") as http:
            return (await http.get("/")).status_code

    assert asyncio.run(scenario()) == 404


def test_maintenance_answers_503_and_clears(setup, tmp_path):
    service, _releases, _worker = setup
    site, _pages = publish_site(service)
    run(service, "maintenance_set", site_id=site, key="m1", on=True)
    (down,) = get(server(setup, site, tmp_path), "/")
    run(service, "maintenance_set", site_id=site, key="m2", on=False)
    (up,) = get(server(setup, site, tmp_path), "/")
    assert (down.status_code, down.headers["retry-after"]) == (503, "300")
    assert up.status_code == 200


def test_noindex_pages_leave_the_sitemap_and_a_noindex_root_closes_the_site(setup, tmp_path):
    service, _releases, _worker = setup
    site, pages = publish_site(service)

    def seo(key, page, robots):
        run(
            service,
            "page_seo_set",
            site_id=site,
            key=key,
            page_id=pages[page],
            fields={"robots": robots},
        )
        run(service, "publish", site_id=site, key="p" + key, selected=list(pages.values()))
        return get(server(setup, site, tmp_path), "/about/", "/sitemap.xml", "/robots.txt")

    about, sitemap, robots = seo("seo1", "About", "noindex, follow")
    assert about.status_code == 200
    assert '<meta name="robots" content="noindex, follow">' in about.text
    assert f"<loc>{ORIGIN}/</loc>" in sitemap.text and "/about/" not in sitemap.text
    assert robots.text.startswith("User-agent: *\nAllow: /")

    _about, sitemap, robots = seo("seo2", "Home", "noindex, nofollow")
    assert "<url>" not in sitemap.text
    assert robots.text == "User-agent: *\nDisallow: /\n"


def test_publish_replaces_an_index_written_before_n6(setup):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    node = service.publisher.node(service.publisher.index_path(site))
    node.write_bytes(node.read_bytes().replace(b'"schema":2', b'"schema":1'))

    plan = run(service, "publish_plan", site_id=site)
    assert {item["state"] for item in plan} == {"new"}
    run(service, "publish", site_id=site, key="again", selected=list(pages.values()))
    assert set(service.publisher.index(site)["pages"]) == set(pages.values())
