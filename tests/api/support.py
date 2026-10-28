"""Drive the real Kajenn lifecycle and both authenticated ASGI transports."""

import asyncio
from contextlib import asynccontextmanager

import httpx

from kajenn_press.application import create_server

AUTH = {
    "bearer": {
        "admin": {"token": "test-admin-token", "tags": "editor"},
        "writer": {"token": "test-writer-token", "tags": "editor"},
        "outsider": {"token": "test-outsider-token", "tags": "editor"},
    }
}


ADMIN = {"admin": {"*": ["read", "write", "use", "create_site"]}}


@asynccontextmanager
async def client(root, grants=None, token="test-admin-token", sites=None):
    server = create_server(root, auth=AUTH, grants=grants or ADMIN, sites=sites)
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    task = asyncio.create_task(
        server({"type": "lifespan", "asgi": {"version": "3.0"}}, incoming.get, outgoing.put)
    )
    await incoming.put({"type": "lifespan.startup"})
    started = await asyncio.wait_for(outgoing.get(), timeout=30)
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
        assert (await asyncio.wait_for(outgoing.get(), timeout=30))[
            "type"
        ] == "lifespan.shutdown.complete"
        await asyncio.wait_for(task, timeout=30)


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
