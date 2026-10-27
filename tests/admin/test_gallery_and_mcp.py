"""User-requested gallery shell, site creation and LLM-facing MCP commands."""

import asyncio

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from api.support import call, record
from genro_bag import Bag
from services.scenarios import BLOCKS, DECLARATIONS

from admin.support import admin_client, login, rpc


def test_new_site_uses_shared_authority_and_mcp_creates_content(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            main = await rpc(http, page, "main", "source")
            assert "New site" in main["value"] and "navigationSelection" in main["value"]
            created = await rpc(
                http, page, "create_site", name="Da interfaccia", languages="it,en", key="ui-site"
            )
            repeated = await rpc(
                http, page, "create_site", name="Da interfaccia", languages="it,en", key="ui-site"
            )
            assert created["value"] == repeated["value"] and created["value"]["ok"]
            session_cookies = http.cookies
            http.cookies = {}
            management_origin = http.headers.pop("Origin")
            http.headers["Authorization"] = "Bearer test-admin-token"
            site = await record(
                http, "mcp", "site_create", key="llm-site", name="Da LLM", languages=["it", "en"]
            )
            template = await record(
                http,
                "mcp",
                "resource_save",
                key="llm-template",
                scope="library",
                kind="template",
                name="Pagina LLM",
                source="source only",
                engine="gramlot",
                blocks=DECLARATIONS,
            )
            content = await record(
                http,
                "mcp",
                "content_create",
                key="llm-content",
                site_id=site["record_id"],
                title="Creato tramite MCP",
            )
            variant = await record(
                http,
                "mcp",
                "variant_create",
                key="llm-variant",
                content_id=content["record_id"],
                language="it",
                template_revision=template["revision_id"],
                blocks=BLOCKS,
            )
            assert variant["attributes"]["content_id"] == content["record_id"]
            assert not http.cookies.get("session_id") or http.cookies.get(
                "session_id"
            ) != session_cookies.get("session_id")
            http.cookies = session_cookies
            http.headers["Origin"] = management_origin
            http.headers.pop("Authorization")
            ui = await rpc(
                http,
                page,
                "read",
                operation="record_read",
                arguments={"record_id": variant["record_id"]},
            )
            rest = (await call(http, "rest", "record_read", record_id=variant["record_id"]))[1]
            assert ui["value"] == rest["result"] == variant
            service = server.applications["press"].service
            service.policy.grants["admin"] = {"*": ["read"]}
            caps = (await call(http, "mcp", "scope_capabilities", scope="installation"))[1]
            assert caps["result"]["permissions"] == []
            assert not (
                await rpc(http, page, "create_site", name="Denied", languages="it", key="deny")
            )["value"]["ok"]
            _, denied = await call(
                http,
                "mcp",
                "content_create",
                key="deny-content",
                site_id=site["record_id"],
                title="Denied",
            )
            assert denied["error"]["code"] == "forbidden"

    asyncio.run(scenario())


def test_iframe_urls_are_derived_from_authorized_scope(tmp_path):
    from api.support import seed_http

    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            page = await login(http)
            site, _other, _template, content, _variant = await seed_http(http)

            nav = await rpc(http, page, "navigation_for_site", site=site["record_id"])
            navigation = nav["value"]
            # The core serializes Bags inside the RPC envelope, preserving all attributes.
            assert isinstance(navigation, Bag)
            selection = Bag()
            selection.set_item(
                "chosen",
                None,
                site=site["record_id"],
                section="page",
                record=content["record_id"],
                url="https://evil.test",
            )
            from genro_tytx import to_tytx

            payload = to_tytx(
                {
                    "id": "panel",
                    "pageId": page,
                    "name": "index_panel",
                    "contentType": "source",
                    "params": {"selection": selection},
                }
            )
            response = await http.post(
                "/admin/gramlot/rpc", content=payload, headers={"Content-Type": "application/json"}
            )
            source = response.json()["value"]
            expected = "page?site=" + site["record_id"] + "&content=" + content["record_id"]
            assert "evil.test" not in source and expected in source
            for path in ("home", "library", "resource", "page"):
                response = await http.get("/admin/" + path)
                assert response.status_code == 200
                assert "frame-ancestors 'self'" in response.headers["content-security-policy"]

    asyncio.run(scenario())
