import asyncio
import importlib.util

from api.support import call, client, record
from services.scenarios import BLOCKS, DECLARATIONS


def test_actual_rest_mcp_lifecycle_and_discovery_without_gramlot(tmp_path):
    async def scenario():
        async with client(tmp_path) as (http, _server):
            site = await record(
                http, "rest", "site_create", key="site", name="Site", languages=["it", "en"]
            )
            replay = await record(
                http, "mcp", "site_create", key="site", name="Site", languages=["it", "en"]
            )
            assert replay == site
            template = await record(
                http,
                "mcp",
                "resource_save",
                key="template",
                scope="library",
                kind="template",
                name="page",
                source="not executed",
                engine="gramlot",
                blocks=DECLARATIONS,
            )
            content = await record(
                http,
                "rest",
                "content_create",
                key="content",
                site_id=site["record_id"],
                title="Title",
            )
            variant = await record(
                http,
                "mcp",
                "variant_create",
                key="variant",
                content_id=content["record_id"],
                language="it",
                template_revision=template["revision_id"],
                blocks=BLOCKS,
            )
            left = await call(http, "rest", "record_read", record_id=variant["record_id"])
            right = await call(http, "mcp", "record_read", record_id=variant["record_id"])
            assert left == right
            checkpoint = await record(
                http,
                "rest",
                "revision_checkpoint",
                record_id=template["record_id"],
                expected_generation=1,
                key="template-checkpoint",
                message="History ordering",
            )
            for channel in ("rest", "mcp"):
                status, history = await call(
                    http, channel, "revision_history", record_id=template["record_id"]
                )
                assert status == 200
                assert history == {"ok": True, "result": [template, checkpoint]}
            schema = await http.get("/_meta/schema_json")
            assert schema.status_code == 200
            assert "/draft_save" in schema.json()["paths"]
            assert "_request" not in str(schema.json()["paths"]["/draft_save"])
            tools = (
                await http.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            ).json()["result"]["tools"]
            assert {"draft_save", "resource_save", "record_read", "readiness"} <= {
                t["name"] for t in tools
            }
        async with client(tmp_path) as (http, _server):
            _status, read = await call(http, "mcp", "record_read", record_id=variant["record_id"])
            assert read["result"] == variant
            for channel in ("rest", "mcp"):
                status, history = await call(
                    http, channel, "revision_history", record_id=template["record_id"]
                )
                assert status == 200
                assert history == {"ok": True, "result": [template, checkpoint]}

    asyncio.run(scenario())
    for module in ("gramlot", "asqueel", "psycopg", "psycopg2", "asyncpg", "sqlalchemy"):
        assert importlib.util.find_spec(module) is None


def test_authentication_and_post_only_mutations(tmp_path):
    async def scenario():
        async with client(tmp_path) as (http, server):
            response = await http.get(
                "/resource_save",
                params={"key": "no", "name": "x", "kind": "css", "scope": "library", "source": "x"},
            )
            assert response.status_code == 405
            before = server.applications["press"].service.catalog.read().generation
            http.headers.clear()
            assert (
                await http.post(
                    "/site_create", json={"key": "no", "name": "x", "languages": ["it"]}
                )
            ).status_code in (401, 403)
            http.headers["Authorization"] = "Bearer invalid"
            assert (await http.post("/sites_list", json={})).status_code == 401
            http.headers["Authorization"] = "Bearer test-outsider-token"
            status, body = await call(
                http, "rest", "site_create", key="denied", name="x", languages=["it"]
            )
            assert status == 403 and body["error"]["code"] == "forbidden"
            assert server.applications["press"].service.catalog.read().generation == before

    asyncio.run(scenario())


def test_duplicate_application_startup_fails_closed_and_releases_on_shutdown(
    tmp_path,
):
    from api.support import AUTH
    from services.scenarios import ADMIN

    from kajenn_press.application import create_server

    async def scenario():
        async with client(tmp_path) as (http, _server):
            duplicate = create_server(tmp_path, auth=AUTH, grants=ADMIN)
            incoming, outgoing = asyncio.Queue(), asyncio.Queue()
            task = asyncio.create_task(duplicate({"type": "lifespan"}, incoming.get, outgoing.put))
            await incoming.put({"type": "lifespan.startup"})
            assert (await asyncio.wait_for(outgoing.get(), timeout=5))[
                "type"
            ] == "lifespan.startup.failed"
            await asyncio.wait_for(task, timeout=5)
            assert (await call(http, "rest", "capabilities"))[1]["ok"]
        async with client(tmp_path) as (http, _server):
            assert (await call(http, "mcp", "capabilities"))[1]["ok"]

    asyncio.run(scenario())


def test_private_payloads_have_no_public_route(tmp_path):
    async def scenario():
        async with client(tmp_path) as (http, _server):
            source = await record(
                http,
                "rest",
                "resource_save",
                key="css",
                scope="library",
                kind="css",
                name="private.css",
                source="body {color:red}",
            )
            object_id = source["payloads"]["source"]["key"]
            http.headers.clear()
            for path in (f"/payloads/{object_id}.blob", "/current.json"):
                assert (await http.get(path)).status_code == 404
            tools = (
                await http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            ).json()
            assert not tools.get("result", {}).get("tools", [])

    asyncio.run(scenario())
