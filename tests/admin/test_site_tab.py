"""The site tab of the administration (N5): navigation, Visual editor and drawer."""

import asyncio
import os

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from publication.storage_support import versioned_bucket

from admin.support import admin_client, login, open_page, rpc

GRANTS = {"admin": {"*": ["read", "write", "use", "create_site", "build", "publish"]}}
LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.div(node_label="hero", kpress_slot="hero")
    body.div(node_label="body", kpress_slot="body")
"""


def sites_config(tmp_path):
    return {
        "root": str(tmp_path / "sites"),
        "sources": versioned_bucket(),
        "releases": versioned_bucket(),
        "render_python": os.environ["KAJENN_RENDER_PYTHON"],
    }


async def call(server, operation, **arguments):
    return server.applications["press"].sites.execute("admin", operation, **arguments)


def test_navigation_and_site_tab_show_sites_pages_slots_and_contents(tmp_path):
    async def scenario():
        async with admin_client(tmp_path / "c", grants=GRANTS, sites=sites_config(tmp_path)) as (
            http,
            server,
        ):
            site = (await call(server, "site_new", key="n", name="Demo site"))["site_id"]
            template = (
                await call(
                    server,
                    "template_add",
                    site_id=site,
                    key="t",
                    name="Layout",
                    engine="gramlot",
                    python_source=LAYOUT,
                )
            )["template_id"]
            page = (
                await call(
                    server, "page_add", site_id=site, key="p", name="Home", template_id=template
                )
            )["page_id"]
            content = (
                await call(
                    server,
                    "content_add",
                    site_id=site,
                    key="c",
                    name="Welcome",
                    format="html",
                    text="<p>Hi</p>",
                )
            )["content_id"]
            await call(
                server,
                "slot_assign",
                site_id=site,
                key="s",
                page_id=page,
                slot="hero",
                content_id=content,
            )

            shell_page = await login(http)
            shell = (await rpc(http, shell_page, "main", "source"))["value"]
            assert "Sites" in shell and "Library" in shell and "Demo site" in shell
            assert "Current site" not in shell

            tab = await open_page(http, "/admin/site?site=" + site)
            view = (await rpc(http, tab, "site_workspace", "source", site=site))["value"]
            for text in (
                "Visual editor",
                "SEO",
                "Published site",
                "Pages",
                "Contents",
                "Show slots",
                "CodeMirror",
                "Jodit",
            ):
                assert text in view, text
            assert "hero ← Welcome" in view and "body · empty" in view
            assert 'sandbox="allow-scripts"' in view or "allow-scripts" in view

            reply = await rpc(
                http,
                tab,
                "command",
                operation="page_render",
                arguments={"site_id": site, "page_id": page},
            )
            assert reply["value"]["ok"] is True
            assert "<p>Hi</p>" in reply["value"]["result"]["html"]
            refused = await rpc(http, tab, "command", operation="site_delete", arguments={})
            assert "error" in str(refused) or refused.get("value") is None

    asyncio.run(scenario())


def test_without_site_sources_the_catalog_navigation_stays(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            shell_page = await login(http)
            shell = (await rpc(http, shell_page, "main", "source"))["value"]
            assert "Current site" in shell

    asyncio.run(scenario())
