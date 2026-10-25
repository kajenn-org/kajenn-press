"""Real session/adapter fixtures; credentials belong only to these tests."""

import asyncio
import copy
from contextlib import asynccontextmanager

import httpx
from api.support import AUTH
from kajenn.auth.user_store import UserStore
from services.scenarios import ADMIN

from kajenn_press.application import create_server


class FixtureUsers(UserStore):
    def __init__(self, storage, **kwargs):
        self.records = {
            name: {
                "identity": name,
                "password_hash": self.hash_password("fixture-only"),
                "tags": ["editor"],
                "enabled": True,
            }
            for name in ("admin", "writer")
        }

    def load_all(self):
        return copy.deepcopy(list(self.records.values()))

    def get(self, identity):
        return copy.deepcopy(self.records.get(identity))

    def save(self, record):
        self.records[record["identity"]] = copy.deepcopy(record)

    def delete(self, identity):
        return self.records.pop(identity, None) is not None


@asynccontextmanager
async def admin_client(root, grants=None, publication=None):
    origin = publication["management_origin"] if publication else "https://admin.test"
    server = create_server(
        root,
        auth=AUTH,
        grants=grants or ADMIN,
        publication=publication,
        administration={"origin": origin, "users": {"store_class": FixtureUsers}},
    )
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    task = asyncio.create_task(
        server({"type": "lifespan", "asgi": {"version": "3.0"}}, incoming.get, outgoing.put)
    )
    await incoming.put({"type": "lifespan.startup"})
    assert (await asyncio.wait_for(outgoing.get(), 30))["type"] == "lifespan.startup.complete"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server), base_url=origin, headers={"Origin": origin}
        ) as http:
            yield http, server
    finally:
        await incoming.put({"type": "lifespan.shutdown"})
        assert (await asyncio.wait_for(outgoing.get(), 30))["type"] == "lifespan.shutdown.complete"
        await asyncio.wait_for(task, 30)


async def open_page(http):
    import re

    response = await http.get("/admin/")
    assert response.status_code == 200, response.text
    return re.search(r'"pageId":"([a-f0-9]+)"', response.text)[1]


async def rpc(http, page, method, content_type="data", **params):
    response = await http.post(
        "/admin/gramlot/rpc",
        json={
            "id": "test",
            "pageId": page,
            "name": method,
            "contentType": content_type,
            "params": params,
        },
    )
    assert response.status_code == 200, response.text
    from genro_tytx import from_tytx, to_tytx

    result = from_tytx(response.text)
    if content_type == "source" and "value" in result and not isinstance(result["value"], str):
        result["value"] = to_tytx(result["value"])
    return result


async def login(http, identity="admin"):
    page = await open_page(http)
    result = await rpc(http, page, "sign_in", username=identity, password="fixture-only")
    assert result.get("value") == "", result
    return page
