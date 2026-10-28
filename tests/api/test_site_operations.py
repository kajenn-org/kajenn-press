"""Site operations over the real REST and MCP transports (N3 Phase 5)."""

import asyncio
import os

from api.support import call, client
from publication.storage_support import versioned_bucket

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.div(node_label="hero", kpress_slot="hero")
    body.div(node_label="body", kpress_slot="body")
"""


async def result(http, channel, operation, **arguments):
    status, body = await call(http, channel, operation, **arguments)
    assert status == 200 and body.get("ok"), body
    return body["result"]


def test_full_cycle_over_mcp_and_discovery(tmp_path):
    sites = {
        "root": str(tmp_path / "sites"),
        "sources": versioned_bucket(),
        "render_python": os.environ["KAJENN_RENDER_PYTHON"],
    }

    async def scenario():
        grants = {"admin": {"*": ["read", "write", "use", "create_site", "build"]}}
        async with client(tmp_path / "catalog", grants=grants, sites=sites) as (http, _server):
            capabilities = await result(http, "mcp", "capabilities")
            assert {"site_new", "slot_assign", "page_render"} <= set(capabilities["operations"])
            tools = await http.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            names = {tool["name"] for tool in tools.json()["result"]["tools"]}
            assert {"site_new", "site_save", "site_restore", "template_switch"} <= names

            site = (await result(http, "mcp", "site_new", key="s", name="Demo"))["site_id"]
            template = (
                await result(
                    http,
                    "mcp",
                    "template_add",
                    site_id=site,
                    key="t",
                    name="Layout",
                    engine="gramlot",
                    python_source=LAYOUT,
                )
            )["template_id"]
            pages = []
            for name in ("Home", "About"):
                page = await result(
                    http,
                    "mcp",
                    "page_add",
                    site_id=site,
                    key=name,
                    name=name,
                    template_id=template,
                )
                pages.append(page["page_id"])
            hero = (
                await result(
                    http,
                    "mcp",
                    "content_add",
                    site_id=site,
                    key="c",
                    name="Hero",
                    format="markdown",
                    text="# Welcome",
                )
            )["content_id"]
            for page in pages:
                await result(
                    http,
                    "mcp",
                    "slot_assign",
                    site_id=site,
                    key="a" + page,
                    page_id=page,
                    slot="hero",
                    content_id=hero,
                )
            first = (await result(http, "mcp", "site_save", site_id=site))["version_id"]
            await result(
                http,
                "rest",
                "content_add",
                site_id=site,
                key="c2",
                name="Later",
                format="html",
                text="<p>later</p>",
            )
            await result(http, "mcp", "site_save", site_id=site)
            await result(http, "mcp", "site_restore", site_id=site, version_id=first)

            read = await result(http, "rest", "site_read", site_id=site)
            assert [c["name"] for c in read["contents"]] == ["Hero"]
            assert read["contents"][0]["uses"] == 2
            assert len(await result(http, "mcp", "site_versions", site_id=site)) == 4
            rendered = await result(http, "mcp", "page_render", site_id=site, page_id=pages[1])
            assert rendered["status"] == "succeeded", rendered
            assert "<h1>Welcome</h1>" in rendered["html"]

    asyncio.run(scenario())


def test_site_operations_without_configuration_are_unavailable(tmp_path):
    async def scenario():
        async with client(tmp_path) as (http, _server):
            status, body = await call(http, "rest", "site_new", key="s", name="Demo")
            assert status == 503 and body["error"]["code"] == "unavailable"

    asyncio.run(scenario())
