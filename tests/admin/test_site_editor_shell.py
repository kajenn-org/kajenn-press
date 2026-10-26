"""Site editor shell: Kajenn Press identity, record navigation and one tab per object."""

import asyncio

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from api.support import record, seed_http

from admin.support import admin_client, login, open_page, rpc

LOGO = "assets/branding/kajenn-press-256.png"


def test_login_and_toolbar_show_the_kajenn_press_logo(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            anonymous = await open_page(http)
            view = await rpc(http, anonymous, "main", "source")
            assert LOGO in view["value"] and "Kajenn Press" in view["value"]
            # Root-relative /assets/ would miss the /admin/ mount.
            assert "/" + LOGO not in view["value"]
            assert "kajenn public site" not in view["value"]
            page = await login(http)
            shell = await rpc(http, page, "main", "source")
            assert LOGO in shell["value"] and "Kajenn Press" in shell["value"]
            logo = await http.get("/admin/" + LOGO)
            assert logo.status_code == 200
            assert logo.headers["content-type"].startswith("image/png")
            assert logo.content.startswith(b"\x89PNG")

    asyncio.run(scenario())


def test_navigation_lists_site_records_by_kind(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            page = await login(http)
            site, other, _template, content, variant = await seed_http(http)
            style = await record(
                http,
                "rest",
                "resource_save",
                key="site-style",
                scope="site:" + site["record_id"],
                kind="css",
                name="Site styles",
                source="body{color:#123}",
            )
            nav = (await rpc(http, page, "navigation_for_site", site=site["record_id"]))["value"]
            pages = nav.get_node("site.pages").value
            assert pages.get_node("new_page").attr["section"] == "new_page"
            entry = pages.get_node("r_" + content["record_id"])
            assert entry.attr["label"] == "Article"
            # Pages open their editor; the other kinds open the record view.
            assert entry.attr["url"] == (
                "page?site=" + site["record_id"] + "&content=" + content["record_id"]
            )
            # Language variants belong to their content and get no tree entry of their own.
            assert pages.get_node("r_" + variant["record_id"]) is None
            styles = nav.get_node("site.styles").value
            style_entry = styles.get_node("r_" + style["record_id"])
            assert style_entry.attr["label"] == "Site styles"
            assert style_entry.attr["url"].startswith("resource?site=")
            # The seeded template lives in the shared library, not in the site.
            assert len(nav.get_node("site.templates").value or []) == 0
            second = (await rpc(http, page, "navigation_for_site", site=other["record_id"]))[
                "value"
            ]
            assert second.get_node("site.pages").value.get_node("r_" + content["record_id"]) is None

    asyncio.run(scenario())


def test_csp_admits_data_stylesheets_for_the_draft_preview(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            response = await http.get("/admin/")
            policy = response.headers["content-security-policy"]
            assert "style-src 'self' 'unsafe-inline' data:;" in policy
            # Scripts stay restricted: data: is admitted for styles and images only.
            assert "data:" not in policy.split("script-src", 1)[1].split(";", 1)[0]

    asyncio.run(scenario())
