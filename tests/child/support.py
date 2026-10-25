"""Run an ASGI host through its Kajenn lifespan and query it as one public origin."""

import asyncio
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def running(app, base_url):
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    task = asyncio.create_task(
        app({"type": "lifespan", "asgi": {"version": "3.0"}}, incoming.get, outgoing.put)
    )
    await incoming.put({"type": "lifespan.startup"})
    started = await asyncio.wait_for(outgoing.get(), timeout=30)
    assert started["type"] == "lifespan.startup.complete", started
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=base_url
        ) as http:
            yield http
    finally:
        await incoming.put({"type": "lifespan.shutdown"})
        await asyncio.wait_for(outgoing.get(), timeout=30)
        await asyncio.wait_for(task, timeout=30)


def snapshot(response):
    return response.status_code, response.content, dict(response.headers)
