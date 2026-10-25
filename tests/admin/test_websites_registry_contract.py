"""Plan-owned behavior contracts; implement only the copied test bodies."""

import asyncio
import json
import os
import re

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from publication.release_support import initial_release
from publication.storage_support import filesystem, release_bucket
from publication.support import CONFIG
from publication.test_release_export_contract import exporting_publisher

from admin.support import admin_client, login, rpc
from kajenn_press.catalog.local import LocalCatalog

GRANTS = {
    "admin": {"*": ["read", "write", "use", "create_site", "build", "preview_grant", "publish"]},
    "writer": {"*": ["read", "use"]},
}


def published(root):
    storage = release_bucket()
    editorial, pub = exporting_publisher(root, storage)
    try:
        fixture, _selected, job, _activated = initial_release(editorial, pub)
    finally:
        pub.close()
        editorial.catalog.close()
    config = {
        **CONFIG,
        "render_python": os.environ["KAJENN_RENDER_PYTHON"],
        "release_storage": storage,
    }
    return storage, config, fixture["settings"]["record_id"], job["record_id"]


async def deployments_page(http):
    response = await http.get("/admin/deployments")
    assert response.status_code == 200, response.text
    return re.search(r'"pageId":"([a-f0-9]+)"', response.text)[1]


async def api(http, token, channel, operation, **arguments):
    headers = {"Authorization": "Bearer " + token}
    if channel == "rest":
        response = await http.post("/" + operation, json=arguments, headers=headers)
        return response.json()
    response = await http.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": operation, "arguments": arguments},
        },
        headers=headers,
    )
    return response.json()["result"]["structuredContent"]


def test_child_registry_uses_catalog_rules_and_shared_transports(tmp_path):
    # wf:contract: Registry records for children are created, updated, read and listed through
    # wf:contract: UI, REST and MCP with the same grants, generations, receipts and audit as other
    # wf:contract: catalog records.
    _storage, config, settings_id, _build = published(tmp_path)

    async def check():
        async with admin_client(tmp_path, grants=GRANTS, publication=config) as (http, _server):
            await login(http)
            page = await deployments_page(http)
            registered = await rpc(
                http,
                page,
                "register",
                settings_id=settings_id,
                name="one-child",
                serving_address="http://127.0.0.1:8876",
                key="ui-register",
            )
            assert registered["value"] == {"ok": True, "message": "Registered one-child."}
            listed = await api(http, "test-admin-token", "rest", "child_list")
            assert listed["ok"] and [c["attributes"]["name"] for c in listed["result"]] == [
                "one-child"
            ]
            child = listed["result"][0]
            assert child["generation"] == 1
            update = {
                "settings_id": settings_id,
                "name": "one-child",
                "public_origin": "https://one.test",
                "serving_address": "http://127.0.0.1:9876",
                "key": "mcp-update",
                "record_id": child["record_id"],
                "expected_generation": 1,
            }
            updated = await api(http, "test-admin-token", "mcp", "child_save", **update)
            assert updated["ok"] and updated["result"]["generation"] == 2, updated
            retried = await api(http, "test-admin-token", "rest", "child_save", **update)
            assert retried["result"]["revision_id"] == updated["result"]["revision_id"]
            stale = await api(
                http, "test-admin-token", "rest", "child_save", **{**update, "key": "stale"}
            )
            assert not stale["ok"] and stale["error"]["code"] == "conflict"
            read = await api(
                http, "test-admin-token", "mcp", "child_read", record_id=child["record_id"]
            )
            assert read["result"]["attributes"]["serving_address"] == "http://127.0.0.1:9876"
            denied = await api(
                http, "test-writer-token", "rest", "child_save", **{**update, "key": "writer"}
            )
            assert not denied["ok"]
            visible = await api(http, "test-writer-token", "mcp", "child_list")
            assert [c["record_id"] for c in visible["result"]] == [child["record_id"]]
            outsider = await api(http, "test-outsider-token", "rest", "child_list")
            assert outsider.get("result", []) == []

    asyncio.run(check())
    with LocalCatalog(tmp_path) as catalog:
        for principal, key in (("admin", "ui-register"), ("admin", "mcp-update")):
            receipt = catalog.receipt(principal=principal, scope="publication", key=key)
            assert receipt and receipt["audit_id"]


def test_deployment_view_reads_back_storage_and_shows_mismatches(tmp_path):
    # wf:contract: The deployment view shows for each child its bound site, the active catalog
    # wf:contract: release, the exported release and the release read back from storage.
    # wf:contract: A mismatch is shown, never corrected silently; re-export resolves it.
    storage, config, settings_id, build_id = published(tmp_path)
    pointer_key = f"{storage['bucket']}/pointers/{settings_id}.json"

    async def check():
        async with admin_client(tmp_path, grants=GRANTS, publication=config) as (http, _server):
            await login(http)
            page = await deployments_page(http)
            await rpc(
                http,
                page,
                "register",
                settings_id=settings_id,
                name="one-child",
                serving_address="http://127.0.0.1:8876",
                key="register",
            )
            view = (await rpc(http, page, "view", "source"))["value"]
            assert "one-child" in view and "one" in view and build_id[:8] in view
            assert "Up to date" in view
            fs = filesystem()
            stale = {**json.loads(fs.cat_file(pointer_key)), "build_id": "0" * 32}
            fs.pipe(pointer_key, json.dumps(stale).encode())
            view = (await rpc(http, page, "view", "source"))["value"]
            assert "Storage differs from catalog" in view and "00000000" in view
            assert json.loads(fs.cat_file(pointer_key))["build_id"] == "0" * 32
            message = await rpc(http, page, "reexport", settings_id=settings_id)
            assert message["value"] == f"Exported release {build_id[:8]} to storage."
            view = (await rpc(http, page, "view", "source"))["value"]
            assert "Up to date" in view and "Storage differs" not in view

    asyncio.run(check())
