"""Plan-owned behavior contracts; implement only the copied test bodies."""

import asyncio
import json
import os
import subprocess
import sys
import time

from api.support import AUTH
from child.support import running, snapshot
from publication.release_support import activate, initial_release, updated_release
from publication.storage_support import filesystem, release_bucket
from publication.support import CONFIG
from publication.test_release_api import RELEASE_GRANTS
from publication.test_release_export_contract import exporting_publisher

from kajenn_press.application import create_server
from kajenn_press.child import create_static_site_server

PUBLIC = "https://one.test"


def published(root):
    """One activated release exported to a fresh bucket; the catalog is closed afterwards."""
    storage = release_bucket()
    editorial, pub = exporting_publisher(root, storage)
    try:
        fixture, _selected, job, activated = initial_release(editorial, pub)
        assert activated["export"]["state"] == "exported"
        manifest = pub.sealed_manifest(pub.record(pub.catalog.read(), job["record_id"]))
    finally:
        pub.close()
        editorial.catalog.close()
    return storage, fixture["settings"]["record_id"], manifest


def test_child_serves_the_active_release_without_catalog_or_renderers(tmp_path):
    # wf:contract: The child serves the release named by the storage pointer for its configured
    # wf:contract: host and imports neither the catalog, Gramlot nor the render worker.
    # wf:contract: It serves only files listed in a manifest whose digest it validated.
    storage, settings_id, manifest = published(tmp_path)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, kajenn_press.child; "
                "assert not [m for m in sys.modules if m.startswith(('gramlot', "
                "'kajenn_press.catalog', 'kajenn_press.rendering', "
                "'kajenn_press.services', 'kajenn_press.publication.service'))]"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert probe.returncode == 0, probe.stderr
    fs = filesystem()
    # A stored object that no manifest lists is never served.
    fs.pipe(storage["bucket"] + "/objects/" + "0" * 64, b"stray")

    async def check():
        child = create_static_site_server(
            bindings={PUBLIC: settings_id}, release_storage=storage
        )
        async with running(child, PUBLIC) as http:
            for path in manifest["artifacts"]["public"]:
                assert (await http.get(path)).status_code == 200, path
            assert (await http.get("/" + "0" * 64)).status_code == 404
            health = await http.get("/_health/health", headers={"host": "health.test"})
            assert health.json() == {"ok": True}
        pointer = json.loads(fs.cat_file(f"{storage['bucket']}/pointers/{settings_id}.json"))
        manifest_key = f"{storage['bucket']}/manifests/{pointer['manifest_digest']}.json"
        fs.pipe(manifest_key, bytes(fs.cat_file(manifest_key)) + b" ")
        tampered = create_static_site_server(
            bindings={PUBLIC: settings_id}, release_storage=storage
        )
        async with running(tampered, PUBLIC) as http:
            assert (await http.get("/it/")).status_code == 503

    asyncio.run(check())


def test_child_responses_match_in_process_public_serving(tmp_path):
    # wf:contract: For every route, asset, sitemap, root redirect and a missing path, the child
    # wf:contract: returns the same body, status code and public headers as in-process serving
    # wf:contract: of the same release.
    storage, settings_id, manifest = published(tmp_path)
    config = {
        **CONFIG,
        "render_python": os.environ["KAJENN_RENDER_PYTHON"],
        "public_origins": {PUBLIC: settings_id},
        "release_storage": storage,
    }
    paths = [*manifest["artifacts"]["public"], *manifest["redirects"], "/en/missing/"]
    assert "/sitemap.xml" in paths and "/" in paths

    async def compare():
        installation = create_server(
            tmp_path, auth=AUTH, grants=RELEASE_GRANTS, publication=config
        )
        child = create_static_site_server(
            bindings={PUBLIC: settings_id}, release_storage=storage
        )
        async with running(installation, PUBLIC) as inside, running(child, PUBLIC) as outside:
            for path in paths:
                for method in ("GET", "HEAD", "POST"):
                    expected = snapshot(await inside.request(method, path))
                    assert snapshot(await outside.request(method, path)) == expected, (
                        method,
                        path,
                    )

    asyncio.run(compare())


def test_child_follows_activation_and_rollback_within_cache_interval(tmp_path):
    # wf:contract: A new activation or a rollback becomes visible in the child within the
    # wf:contract: configured cache interval.
    # wf:contract: A missing or invalid pointer or manifest yields 503 unless a validated release
    # wf:contract: is already loaded, which keeps being served.
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    try:
        fixture, _selected, first, _activated = initial_release(editorial, pub)
        settings_id = fixture["settings"]["record_id"]
        _candidate, second, _it, _en = updated_release(editorial, pub, fixture, first)

        async def follow():
            child = create_static_site_server(
                bindings={PUBLIC: settings_id}, release_storage=storage, cache_seconds=1
            )
            async with running(child, PUBLIC) as http:
                before = (await http.get("/it/")).text
                await asyncio.to_thread(
                    activate, pub, fixture, second, 1, "activate-second"
                )
                changed = await within(http, lambda body: body != before, 3)
                await asyncio.to_thread(
                    activate, pub, fixture, first, 2, "rollback-first", "release_rollback"
                )
                assert await within(http, lambda body: body == before, 3)
                assert changed
                fs = filesystem()
                fs.pipe(storage["bucket"] + f"/pointers/{settings_id}.json", b"not json")
                await asyncio.sleep(1.2)
                kept = await http.get("/it/")
                assert kept.status_code == 200 and kept.text == before
            unbound = create_static_site_server(
                bindings={PUBLIC: "missing-settings"}, release_storage=storage
            )
            async with running(unbound, PUBLIC) as http:
                assert (await http.get("/it/")).status_code == 503

        asyncio.run(follow())
    finally:
        pub.close()
        editorial.catalog.close()


async def within(http, accept, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        response = await http.get("/it/")
        if response.status_code == 200 and accept(response.text):
            return True
        await asyncio.sleep(0.2)
    return False
