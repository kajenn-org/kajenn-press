"""The Kajenn server application that serves published sites (N4 Phase 5)."""

import asyncio
import base64
import os
import sys
import time
from pathlib import Path

import pytest
from child.support import running
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.rendering.resolvers import ConfigValueResolver
from kajenn_press.site.private import sign
from kajenn_press.site.publish import Publisher
from kajenn_press.site.published import unpack_page
from kajenn_press.site.render import page_request, published_asset_name
from kajenn_press.site.service import SiteService
from kajenn_press.site.serving import create_site_server
from kajenn_press.site.store import SourceStore

ORIGIN = "http://site.localhost"
EXAMPLE = Path(__file__).parents[2] / "examples" / "kajenn_press_site"
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
SECRET = b"private-link-secret-for-tests-only"
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
        publisher=Publisher(releases, worker, {"site": {"headline": "at publish"}}, SECRET),
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
    run(
        service,
        "page_seo_set",
        site_id=site,
        key="address",
        page_id=pages["Home"],
        fields={"origin": ORIGIN},
    )
    run(service, "publish", site_id=site, key="p", selected=list(pages.values()))
    return site, pages


def server(setup, site, tmp_path, connections=None, cache_seconds=0.2):
    """A site server on the release bucket; `site` is bound through its root origin."""
    _service, releases, worker = setup
    return create_site_server(
        release_storage=releases,
        cache_root=tmp_path / "cache",
        cache_seconds=cache_seconds,
        worker=worker,
        connections=connections or {},
        private_secret=SECRET,
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


def test_publish_replaces_an_index_of_an_earlier_schema(setup):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    node = service.publisher.node(service.publisher.index_path(site))
    node.write_bytes(node.read_bytes().replace(b'"schema":3', b'"schema":2'))

    plan = run(service, "publish_plan", site_id=site)
    assert {item["state"] for item in plan} == {"new"}
    run(service, "publish", site_id=site, key="again", selected=list(pages.values()))
    assert set(service.publisher.index(site)["pages"]) == set(pages.values())


def test_the_example_site_has_no_seo_problem_and_serves_its_seo(setup, tmp_path):
    service, _releases, _worker = setup
    sys.path.insert(0, str(EXAMPLE))
    try:
        from publish import publish
    finally:
        sys.path.remove(str(EXAMPLE))
    site = publish(lambda operation, **arguments: run(service, operation, **arguments), ORIGIN)

    assert run(service, "seo_check", site_id=site) == []
    home, features, sitemap = get(server(setup, site, tmp_path), "/", "/features/", "/sitemap.xml")
    assert '<link rel="canonical" href="http://site.localhost/">' in home.text
    assert '<meta name="description" content="Kajenn Press builds a website' in home.text
    assert '<meta property="og:site_name" content="Kajenn Press">' in features.text
    assert f"<loc>{ORIGIN}/get-started/</loc>" in sitemap.text


def test_an_address_set_later_is_served_without_restart_and_moves(setup, tmp_path):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    app = server(setup, site, tmp_path)
    other = "http://new.localhost"

    async def scenario():
        async with running(app, ORIGIN) as http:
            before = (await http.get("/")).status_code
            await asyncio.to_thread(
                run,
                service,
                "page_seo_set",
                site_id=site,
                key="move",
                page_id=pages["Home"],
                fields={"origin": other},
            )
            await asyncio.to_thread(run, service, "publish", site_id=site, key="again", selected=[])
            await asyncio.sleep(0.3)
            old = (await http.get("/")).status_code
            new = (await http.get("/", headers={"host": "new.localhost"})).status_code
        return before, old, new

    assert asyncio.run(scenario()) == (200, 404, 200)
    assert service.publisher.bindings() == {
        other: {"site_id": site, "state": "public", "server": "default", "redirect": None}
    }


def test_two_sites_cannot_share_an_address(setup):
    service, _releases, _worker = setup
    first, _pages = publish_site(service)
    second = run(service, "site_new", key="second", name="T")["site_id"]
    template = run(
        service,
        "template_add",
        site_id=second,
        key="t2",
        name="L",
        engine="gramlot",
        python_source=LAYOUT,
    )["template_id"]
    page = run(service, "page_add", site_id=second, key="p2", name="Home", template_id=template)[
        "page_id"
    ]
    run(
        service,
        "page_seo_set",
        site_id=second,
        key="a2",
        page_id=page,
        fields={"origin": ORIGIN},
    )
    with pytest.raises(DomainError, match="address of another site"):
        run(service, "publish", site_id=second, key="pub2", selected=[page])
    assert service.publisher.binding(first)[0] == ORIGIN
    assert service.publisher.binding(second) == (None, None)


def test_a_private_site_is_seen_only_through_its_private_link(setup, tmp_path):
    service, _releases, _worker = setup
    site, _pages = publish_site(service)
    run(service, "site_visibility_set", site_id=site, key="private", state="private")
    link = run(service, "private_link", site_id=site, hours=8)["url"]
    assert link.startswith(ORIGIN + "/_private/")
    token = link.removeprefix(ORIGIN + "/_private/")
    forged = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    app = server(setup, site, tmp_path)

    async def scenario():
        async with running(app, ORIGIN) as http:
            hidden = (await http.get("/")).status_code
            refused = (await http.get("/_private/" + forged)).status_code
            entry = await http.get(link.removeprefix(ORIGIN))
            cookie = entry.headers["set-cookie"]
            seen = await http.get("/about/", headers={"cookie": "kpress_private=" + token})
            return hidden, refused, entry, cookie, seen

    hidden, refused, entry, cookie, seen = asyncio.run(scenario())
    assert (hidden, refused) == (404, 404)
    assert entry.status_code == 303 and entry.headers["location"] == "/"
    assert cookie.startswith("kpress_private=" + token)
    assert "HttpOnly" in cookie and "Secure" not in cookie
    assert seen.status_code == 200 and "<p>About</p>" in seen.text
    assert "no-store" in seen.headers["cache-control"]
    assert "set-cookie" not in seen.headers

    run(service, "site_visibility_set", site_id=site, key="public", state="public")
    (public,) = get(server(setup, site, tmp_path), "/")
    assert public.status_code == 200 and "set-cookie" not in public.headers


def test_the_private_link_opens_a_site_in_maintenance_and_expires(setup, tmp_path):
    service, _releases, _worker = setup
    site, _pages = publish_site(service)
    run(service, "maintenance_set", site_id=site, key="m", on=True)
    token = run(service, "private_link", site_id=site)["url"].rsplit("/", 1)[1]
    other_site = sign(SECRET, "another-site", time.time() + 3600)
    expired = sign(SECRET, site, time.time() - 1)
    app = server(setup, site, tmp_path)

    async def scenario():
        async with running(app, ORIGIN) as http:
            statuses = []
            for value in (None, token, other_site, expired):
                headers = {"cookie": "kpress_private=" + value} if value else {}
                statuses.append((await http.get("/", headers=headers)).status_code)
            return statuses

    assert asyncio.run(scenario()) == [503, 200, 503, 503]
    with pytest.raises(DomainError, match="8 hours or 7 days"):
        run(service, "private_link", site_id=site, hours=3)


def test_publication_state_follows_publish_visibility_and_maintenance(setup):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    state = run(service, "publication_state", site_id=site)
    assert state["address"] == ORIGIN and state["state"] == "public"
    assert state["published"] and not state["maintenance"] and state["changed"] == 0
    assert state["next_address"] is None and state["address_problem"] is None

    run(service, "maintenance_set", site_id=site, key="m", on=True)
    run(service, "site_visibility_set", site_id=site, key="v", state="private")
    run(
        service,
        "page_seo_set",
        site_id=site,
        key="d",
        page_id=pages["About"],
        fields={"description": "About text"},
    )
    state = run(service, "publication_state", site_id=site)
    assert state["maintenance"] and state["state"] == "private" and state["changed"] == 1

    run(
        service,
        "page_seo_set",
        site_id=site,
        key="o",
        page_id=pages["Home"],
        fields={"origin": "http://moved.localhost"},
    )
    assert run(service, "publication_state", site_id=site)["next_address"] == (
        "http://moved.localhost"
    )
    run(
        service,
        "page_seo_set",
        site_id=site,
        key="bad",
        page_id=pages["Home"],
        fields={"origin": "http://example.org"},
    )
    state = run(service, "publication_state", site_id=site)
    assert state["next_address"] is None and "HTTPS" in state["address_problem"]


def test_a_two_language_site_is_published_and_served_in_both(setup, tmp_path):
    service, _releases, _worker = setup
    site, pages = publish_site(service)
    read = run(service, "site_read", site_id=site)
    home_content = next(c["id"] for c in read["contents"] if c["name"] == "Home")
    run(service, "site_languages_set", site_id=site, key="lang-l", languages=["en", "it"])
    run(
        service,
        "content_translate",
        site_id=site,
        key="lang-t1",
        content_id=home_content,
        language="it",
        text="<p>Casa</p>",
    )
    run(
        service,
        "copies_update",
        site_id=site,
        key="lang-u1",
        original_id=home_content,
        selected=[
            [p["page_id"], p["path"]]
            for p in run(service, "copies_update_plan", site_id=site, original_id=home_content)
        ],
    )
    plan = run(service, "publish_plan", site_id=site)
    assert {(p["entry"], p["state"]) for p in plan} == {
        (pages["Home"], "changed"),
        (pages["About"], "changed"),
        (pages["Home"] + ".it", "new"),
        (pages["About"] + ".it", "new"),
    }
    run(service, "publish", site_id=site, key="lang-p", selected=list(pages.values()))

    home, italian, about_it, prefixed, sitemap = get(
        server(setup, site, tmp_path), "/", "/it/", "/it/about/", "/en/about/", "/sitemap.xml"
    )
    assert '<html lang="en"' in home.text and "<p>Home</p>" in home.text
    assert '<html lang="it"' in italian.text and "<p>Casa</p>" in italian.text
    assert "<p>About</p>" in about_it.text  # no Italian yet: the main text
    assert "kpress_fallback" not in about_it.text
    assert '<link rel="alternate" hreflang="it" href="http://site.localhost/it/">' in home.text
    assert (
        '<link rel="alternate" hreflang="x-default" href="http://site.localhost/">' in italian.text
    )
    assert prefixed.status_code == 301 and prefixed.headers["location"] == "/about/"
    for path in ("/", "/about/", "/it/", "/it/about/"):
        assert f"<loc>{ORIGIN}{path}</loc>" in sitemap.text

    run(
        service,
        "content_translate",
        site_id=site,
        key="lang-t2",
        content_id=home_content,
        language="it",
        text="<p>La casa</p>",
    )
    run(
        service,
        "copies_update",
        site_id=site,
        key="lang-u2",
        original_id=home_content,
        selected=[
            [p["page_id"], p["path"]]
            for p in run(service, "copies_update_plan", site_id=site, original_id=home_content)
        ],
    )
    changed = {
        p["entry"] for p in run(service, "publish_plan", site_id=site) if p["state"] != "unchanged"
    }
    assert changed == {pages["Home"] + ".it"}
    # The pages read the `site` connection: the preview gets it here, as Publish does.
    request = page_request(
        service.working_copy(site).load(),
        pages["About"],
        {"site": {"headline": "x"}},
        language="it",
    )
    preview = setup[2].render_page(request)
    assert preview["status"] == "succeeded", preview["diagnostics"]
    assert "kpress_fallback" in preview["html"]


def test_each_server_serves_its_sites_the_alias_redirects_and_a_site_moves(setup, tmp_path):
    service, releases, worker = setup
    service.policy = AccessPolicy(
        {"anna": {"*": ["read", "write", "create_site", "build", "publish", "servers"]}}
    )
    service.execute(
        "anna",
        "server_add",
        key="web-2",
        name="web-2",
        ipv4=["157.90.1.21"],
        ipv6=[],
        agent_url="https://web-2.example",
    )
    site, _pages = publish_site(service)
    run(service, "site_server_set", site_id=site, key="move", server="web-2", alias=True)
    assert service.publisher.bindings() == {
        ORIGIN: {"site_id": site, "state": "public", "server": "web-2", "redirect": None},
        "http://www.site.localhost": {
            "site_id": site,
            "state": "public",
            "server": "web-2",
            "redirect": ORIGIN,
        },
    }

    def serve(server):
        return create_site_server(
            release_storage=releases,
            cache_root=tmp_path / server,
            cache_seconds=0.2,
            worker=worker,
            private_secret=SECRET,
            server=server,
        )

    (default_home,) = get(serve("default"), "/")
    (moved_home,) = get(serve("web-2"), "/about/")
    assert default_home.status_code == 404 and moved_home.status_code == 200

    async def alias():
        async with running(serve("web-2"), "http://www.site.localhost") as http:
            return await http.get("/about/")

    redirected = asyncio.run(alias())
    assert redirected.status_code == 301
    assert redirected.headers["location"] == ORIGIN + "/about/"
    with pytest.raises(DomainError, match="serves 1 sites"):
        service.execute("anna", "server_remove", key="rm", name="web-2")
    with pytest.raises(DomainError, match="No server"):
        run(service, "site_server_set", site_id=site, key="bad", server="web-9")


def test_caddy_may_ask_which_names_are_bound(setup, tmp_path):
    service, _releases, _worker = setup
    site, _pages = publish_site(service)
    bound, unknown = get(
        server(setup, site, tmp_path),
        "/_kpress/ask?domain=site.localhost",
        "/_kpress/ask?domain=other.example",
    )
    assert (bound.status_code, unknown.status_code) == (200, 404)
