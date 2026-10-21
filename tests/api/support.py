"""Drive the real Kajenn lifecycle and both authenticated ASGI transports."""

import asyncio
from contextlib import asynccontextmanager

import httpx
from services.scenarios import ADMIN

from kajenn_public_site.application import create_server

AUTH = {
    "bearer": {
        "admin": {"token": "test-admin-token", "tags": "editor"},
        "writer": {"token": "test-writer-token", "tags": "editor"},
        "outsider": {"token": "test-outsider-token", "tags": "editor"},
    }
}


@asynccontextmanager
async def client(root, grants=None, token="test-admin-token"):
    server = create_server(root, auth=AUTH, grants=grants or ADMIN)
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    task = asyncio.create_task(
        server({"type": "lifespan", "asgi": {"version": "3.0"}}, incoming.get, outgoing.put)
    )
    await incoming.put({"type": "lifespan.startup"})
    started = await asyncio.wait_for(outgoing.get(), timeout=10)
    assert started["type"] == "lifespan.startup.complete", started
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server),
            base_url="http://local",
            headers={"Authorization": "Bearer " + token} if token else {},
        ) as http:
            yield http, server
    finally:
        await incoming.put({"type": "lifespan.shutdown"})
        assert (await asyncio.wait_for(outgoing.get(), timeout=10))[
            "type"
        ] == "lifespan.shutdown.complete"
        await asyncio.wait_for(task, timeout=10)


async def call(http, channel, operation, **arguments):
    if channel == "rest":
        response = await http.post("/" + operation, json=arguments)
        return response.status_code, response.json()
    response = await http.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": operation, "arguments": arguments},
        },
    )
    body = response.json()
    return response.status_code, body.get("result", {}).get("structuredContent", body)


async def record(http, channel, operation, **arguments):
    status, body = await call(http, channel, operation, **arguments)
    assert status == 200 and body.get("ok"), body
    return body["result"]["records"][0]


async def seed_http(http, channel="rest"):
    from services.scenarios import BLOCKS, DECLARATIONS

    site = await record(
        http, channel, "site_create", key="site", name="First", languages=["it", "en"]
    )
    other = await record(http, channel, "site_create", key="other", name="Second", languages=["it"])
    template = await record(
        http,
        channel,
        "resource_save",
        key="template",
        scope="library",
        kind="template",
        name="page",
        source="source only",
        engine="gramlot",
        blocks=DECLARATIONS,
    )
    content = await record(
        http, channel, "content_create", key="content", site_id=site["record_id"], title="Article"
    )
    variant = await record(
        http,
        channel,
        "variant_create",
        key="variant",
        content_id=content["record_id"],
        language="it",
        template_revision=template["revision_id"],
        blocks=BLOCKS,
    )
    return site, other, template, content, variant
