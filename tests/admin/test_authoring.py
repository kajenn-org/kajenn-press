"""First usable template/content path, real persistence and the isolated renderer."""

import asyncio
import os
import re

import pytest

pytest.importorskip("gramlot", reason="Requires optional admin profile")
from api.support import call, record
from publication.support import CONFIG

from admin.support import admin_client, login, rpc
from kajenn_public_site.admin.pages.author import BLOCKS, TEMPLATE


def test_create_reopen_render_retry_and_revoke(tmp_path):  # wf:phase-1:new
    async def check():  # wf:phase-1:new
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

            async def command(operation, **arguments):  # wf:phase-1:new
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
                "render_preview",
                variant_id=variant["record_id"],
                revision_id=variant["revision_id"],
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
                operation="render_preview",
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
                    "render_preview",
                    variant_id=variant["record_id"],
                    revision_id=variant["revision_id"],
                )
            )["html"] == rendered["html"]
            server.applications["public_site"].service.policy.grants["admin"] = {"*": ["read"]}
            denied = await rpc(
                http,
                page,
                "command",
                operation="render_preview",
                arguments={
                    "variant_id": variant["record_id"],
                    "revision_id": updated["revision_id"],
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
