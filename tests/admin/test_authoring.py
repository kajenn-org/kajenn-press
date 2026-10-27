"""First usable template/content path, real persistence and the isolated renderer."""

import asyncio
import os
import re

import pytest

pytest.importorskip("gramlot", reason="Requires optional admin profile")
from api.support import call, record
from publication.support import CONFIG

from admin.support import admin_client, login, rpc
from kajenn_press.admin.pages.author import BLOCKS, TEMPLATE


def test_create_reopen_render_retry_and_revoke(tmp_path):
    async def check():
        grants = {"admin": {"*": ["read", "write", "use", "create_site", "build"]}}
        async with admin_client(
            tmp_path, grants, {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
        ) as (http, server):
            await login(http)
            site = await record(
                http, "rest", "site_create", key="site", name="Authoring", languages=["en"]
            )
            response = await http.get("/admin/author")
            page = re.search(r'"pageId":"([a-f0-9]+)"', response.text)[1]
            initial = await rpc(http, page, "editor", "source", site=site["record_id"])
            assert "htmlEditor" in initial["value"] and "codeMirror" in initial["value"]

            async def command(operation, **arguments):
                reply = await rpc(http, page, "command", operation=operation, arguments=arguments)
                assert reply["value"]["ok"], reply
                return reply["value"]["result"]

            args = {
                "scope": "site:" + site["record_id"],
                "kind": "template",
                "name": "First template",
                "source": TEMPLATE,
                "engine": "gramlot",
                "blocks": BLOCKS,
                "key": "template",
            }
            template = (await command("resource_save", **args))["records"][0]
            assert (await command("resource_save", **args))["records"][0] == template
            reuse = await rpc(
                http,
                page,
                "editor",
                "source",
                site=site["record_id"],
                template_id=template["record_id"],
            )
            assert "First template" in reuse["value"] and "htmlEditor" in reuse["value"]
            content = (
                await command(
                    "content_create", site_id=site["record_id"], title="My first page", key="page"
                )
            )["records"][0]
            raw = "<p>Hello <strong>Gramlot</strong>!</p>\r\n<!-- retained -->"
            variant = (
                await command(
                    "variant_create",
                    content_id=content["record_id"],
                    language="en",
                    template_revision=template["revision_id"],
                    blocks={"body": {"format": "html", "source": raw}},
                    key="variant",
                )
            )["records"][0]
            assert variant["sources"]["block.body"]["text"] == raw
            reopened = await rpc(
                http, page, "editor", "source", site=site["record_id"], variant=variant["record_id"]
            )
            assert "retained" in reopened["value"] and "htmlEditor" in reopened["value"]
            rendered = await command(
                "render_draft",
                variant_id=variant["record_id"],
                revision_id=variant["revision_id"],
                blocks={},
                resources={},
            )
            assert rendered["status"] == "succeeded", rendered
            assert (
                "<strong>Gramlot</strong>" in rendered["html"]
                and "My first page" in rendered["html"]
            )
            invalid = await rpc(
                http,
                page,
                "command",
                operation="render_draft",
                arguments={
                    "variant_id": variant["record_id"],
                    "revision_id": variant["revision_id"],
                    "resource_urls": {},
                },
            )
            assert invalid["value"]["error"]["code"] == "invalid_input"
            refused_get = await http.get(
                "/render_preview",
                params={"variant_id": variant["record_id"], "revision_id": variant["revision_id"]},
            )
            assert refused_get.status_code == 405
            # The MCP route uses the exact same authorization and worker.
            http.headers["Authorization"] = "Bearer test-admin-token"
            mcp = (
                await call(
                    http,
                    "mcp",
                    "render_preview",
                    variant_id=variant["record_id"],
                    revision_id=variant["revision_id"],
                )
            )[1]
            assert mcp["result"]["html"] == rendered["html"]
            http.headers.pop("Authorization")
            updated = (
                await command(
                    "draft_save",
                    variant_id=variant["record_id"],
                    expected_generation=variant["generation"],
                    template_revision=template["revision_id"],
                    blocks={"body": {"format": "html", "source": "<p>New revision</p>"}},
                    key="edit",
                )
            )["records"][0]
            stale = await rpc(
                http,
                page,
                "command",
                operation="draft_save",
                arguments={
                    "variant_id": variant["record_id"],
                    "expected_generation": variant["generation"],
                    "template_revision": template["revision_id"],
                    "blocks": {"body": {"format": "html", "source": "overwrite"}},
                    "key": "stale",
                },
            )
            assert stale["value"]["error"]["code"] == "conflict"
            assert (
                await command(
                    "render_draft",
                    variant_id=variant["record_id"],
                    revision_id=variant["revision_id"],
                    blocks={},
                    resources={},
                )
            )["html"] == rendered["html"]
            server.applications["press"].service.policy.grants["admin"] = {"*": ["read"]}
            denied = await rpc(
                http,
                page,
                "command",
                operation="render_draft",
                arguments={
                    "variant_id": variant["record_id"],
                    "revision_id": updated["revision_id"],
                    "blocks": {},
                    "resources": {},
                },
            )
            assert denied["value"]["error"]["code"] == "forbidden"
            denied = await rpc(
                http,
                page,
                "command",
                operation="resource_save",
                arguments={**args, "key": "denied"},
            )
            assert denied["value"]["error"]["code"] == "forbidden"

    asyncio.run(check())


STYLED = """def build(source, data):
    page = source.html(lang="^language")
    head = page.head()
    for asset in data.get_item("resources").values():
        if asset.get_item("kind") == "css":
            head.link(rel="stylesheet", href=asset.get_item("url"))
    page.body().main("^blocks.body")
"""


def test_draft_render_follows_unsaved_sources_with_inline_resources(tmp_path):
    async def check():
        grants = {"admin": {"*": ["read", "write", "use", "create_site", "build"]}}
        async with admin_client(
            tmp_path, grants, {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
        ) as (http, _server):
            await login(http)
            http.headers["Authorization"] = "Bearer test-admin-token"
            site = await record(
                http, "rest", "site_create", key="site", name="Drafts", languages=["en"]
            )
            scope = "site:" + site["record_id"]
            css = await record(
                http,
                "rest",
                "resource_save",
                key="css",
                scope=scope,
                kind="css",
                name="Styles",
                source="main { color: #123; }",
            )
            template = await record(
                http,
                "rest",
                "resource_save",
                key="template",
                scope=scope,
                kind="template",
                name="Styled",
                source=STYLED,
                engine="gramlot",
                blocks=BLOCKS,
                dependencies=[css["revision_id"]],
            )
            content = await record(
                http, "rest", "content_create", key="page", site_id=site["record_id"], title="Page"
            )
            variant = await record(
                http,
                "rest",
                "variant_create",
                key="variant",
                content_id=content["record_id"],
                language="en",
                template_revision=template["revision_id"],
                blocks={"body": {"format": "html", "source": "<p>Saved</p>"}},
            )
            arguments = {
                "variant_id": variant["record_id"],
                "revision_id": variant["revision_id"],
                "blocks": {"body": "<p>Live</p>"},
                "resources": {template["revision_id"]: STYLED.replace("main(", "article(")},
            }
            for channel in ("rest", "mcp"):
                status, reply = await call(http, channel, "render_draft", **arguments)
                result = reply["result"]
                assert result["status"] == "succeeded", (status, reply)
                assert "<article><p>Live</p></article>" in result["html"]
                assert "data:text/css;base64," in result["html"]
            refused_get = await http.get(
                "/render_draft",
                params={"variant_id": variant["record_id"], "revision_id": variant["revision_id"]},
            )
            assert refused_get.status_code == 405
            # Nothing was saved: the stored variant still renders its saved block.
            saved = (
                await call(
                    http,
                    "rest",
                    "render_preview",
                    variant_id=variant["record_id"],
                    revision_id=variant["revision_id"],
                )
            )[1]["result"]
            assert "<main><p>Saved</p></main>" in saved["html"]

    asyncio.run(check())
