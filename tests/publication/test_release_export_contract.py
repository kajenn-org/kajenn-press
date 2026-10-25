"""Plan-owned behavior contracts; implement only the copied test bodies."""

import asyncio
import json
import os
import tempfile
import threading
import time

import pytest
from api.support import call, client
from genro_storage.backends.local import LocalStorage
from publication.release_support import activate, initial_release, updated_release
from publication.storage_support import bucket_objects, filesystem, release_bucket
from publication.support import CONFIG, services
from publication.test_release_api import RELEASE_GRANTS

from kajenn_press.publication.export import ReleaseStorage


def exporting_publisher(root, storage):
    editorial, pub = services(root, release_storage=storage)
    editorial.policy.grants["admin"]["*"].append("publish")
    return editorial, pub


def three_releases(editorial, pub):
    """Activate, update, then roll back to the first build: channel generations 1, 2, 3."""
    fixture, _selected, first, activated = initial_release(editorial, pub)
    _candidate, second, _it, _en = updated_release(editorial, pub, fixture, first)
    updated = activate(pub, fixture, second, generation=1, key="activate-second")
    rolled = activate(
        pub, fixture, first, generation=2, key="rollback-first", operation="release_rollback"
    )
    return fixture, first, second, [activated, updated, rolled]


def public_artifacts(pub, build_id):
    snapshot = pub.catalog.read()
    job = pub.record(snapshot, build_id, "publication_job")
    manifest = pub.sealed_manifest(job)
    return job, {
        item["sha256"]: pub.artifact(job, "public", path)[0]
        for path, item in manifest["artifacts"]["public"].items()
    }


def test_export_follows_activation_and_rollback(tmp_path):
    # wf:contract: After a committed activation or rollback the installation writes the release
    # wf:contract: files, then the manifest, then the active pointer to the configured mount.
    # wf:contract: The pointer names site, channel, build, manifest digest and catalog channel
    # wf:contract: generation, and matches the catalog after each step.
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    try:
        fixture, first, second, results = three_releases(editorial, pub)
        expected = [(first, 1), (second, 2), (first, 3)]
        for result, (job, generation) in zip(results, expected):
            assert result["export"]["state"] == "exported"
            pointer = result["export"]["pointer"]
            assert pointer["settings_id"] == fixture["settings"]["record_id"]
            assert pointer["site_id"] == fixture["site"]["record_id"]
            assert pointer["build_id"] == job["record_id"]
            assert pointer["channel_generation"] == generation
            assert pointer["manifest_digest"] == job["attributes"]["manifest_digest"]
        channel = pub.execute(
            "admin", "channel_read", settings_id=fixture["settings"]["record_id"]
        )
        assert channel["export"]["state"] == "exported"
        assert channel["export"]["pointer"] == results[-1]["export"]["pointer"]
        objects = bucket_objects(storage)
        pointer = results[-1]["export"]["pointer"]
        assert pointer["history"] == [
            first["attributes"]["manifest_digest"],
            second["attributes"]["manifest_digest"],
        ]
        for build in (first, second):
            _job, artifacts = public_artifacts(pub, build["record_id"])
            assert f"manifests/{build['attributes']['manifest_digest']}.json" in objects
            assert all("objects/" + sha in objects for sha in artifacts)
    finally:
        pub.close()
        editorial.catalog.close()


def test_exported_release_is_byte_identical_and_immutable(tmp_path):
    # wf:contract: Every exported file equals the catalog artifact and its manifest digest.
    # wf:contract: Re-export never rewrites an immutable file; only the pointer is rewritten.
    # wf:contract: Drafts, previews and credentials never appear in release storage.
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    try:
        fixture, first, second, _results = three_releases(editorial, pub)
        objects = bucket_objects(storage)
        expected = {}
        for build in (first, second):
            job, artifacts = public_artifacts(pub, build["record_id"])
            manifest_path = f"manifests/{build['attributes']['manifest_digest']}.json"
            assert objects[manifest_path] == pub.catalog.read_payload(job["id"], "manifest")
            expected.update({"objects/" + sha: raw for sha, raw in artifacts.items()})
            expected[manifest_path] = objects[manifest_path]
        expected[f"pointers/{fixture['settings']['record_id']}.json"] = objects[
            f"pointers/{fixture['settings']['record_id']}.json"
        ]
        assert objects == expected
        fs = filesystem()
        immutable = [key for key in objects if not key.startswith("pointers/")]
        before = {key: fs.info(storage["bucket"] + "/" + key)["LastModified"] for key in immutable}
        time.sleep(1.1)
        exported = pub.execute(
            "admin", "release_export", settings_id=fixture["settings"]["record_id"]
        )
        assert exported["state"] == "exported"
        fs.invalidate_cache()
        after = {key: fs.info(storage["bucket"] + "/" + key)["LastModified"] for key in immutable}
        assert after == before
        secrets = [
            storage["secret_key"].encode(),
            storage["access_key"].encode(),
            CONFIG["preview_secret"],
            b"/preview/",
        ]
        assert not any(secret in raw for raw in objects.values() for secret in secrets)
    finally:
        pub.close()
        editorial.catalog.close()


def non_atomic_write(self, path, data):
    """Truncate, then write in chunks: the local backend before genro-storage 0.8.4 (#83)."""
    target = self._resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as stream:
        for start in range(0, len(data), 4096):
            stream.write(data[start : start + 4096])
            stream.flush()


def test_pointer_replacement_is_never_observed_partially(tmp_path, monkeypatch):
    # wf:contract: A concurrent reader of the configured backend observes either the old or the
    # wf:contract: new complete pointer during replacement.
    # wf:contract: A backend failing exclusive create, read-back digest or this check is refused
    # wf:contract: at startup with a clear error.
    local = {"protocol": "local", "base_path": tempfile.mkdtemp()}
    with monkeypatch.context() as patched:
        patched.setattr(LocalStorage, "write_bytes", non_atomic_write)
        with pytest.raises(ValueError, match="partially replaced"):
            ReleaseStorage(None, local)
    # genro-storage >= 0.8.4 replaces local files atomically: the same mount qualifies.
    ReleaseStorage(None, local)
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    reader_storage = ReleaseStorage(None, storage)
    seen, invalid, stop = [], [], threading.Event()
    try:
        fixture, _selected, first, _activated = initial_release(editorial, pub)
        settings_id = fixture["settings"]["record_id"]

        def reader():
            while not stop.is_set():
                try:
                    pointer = reader_storage.read_pointer(settings_id)
                except Exception as exc:  # noqa: BLE001 — every failure is recorded
                    invalid.append(repr(exc))
                    continue
                seen.append((pointer["channel_generation"], pointer["build_id"]))

        thread = threading.Thread(target=reader)
        thread.start()
        try:
            _candidate, second, _it, _en = updated_release(editorial, pub, fixture, first)
            generation = 1
            for index in range(6):
                job = second if index % 2 == 0 else first
                operation = "release_activate" if index == 0 else "release_rollback"
                activate(pub, fixture, job, generation, key=f"swap-{index}", operation=operation)
                generation += 1
        finally:
            stop.set()
            thread.join()
        assert not invalid
        builds = {first["record_id"], second["record_id"]}
        assert seen and all(build in builds for _generation, build in seen)
        assert [g for g, _b in seen] == sorted(g for g, _b in seen)
    finally:
        pub.close()
        editorial.catalog.close()


def test_export_failure_keeps_activation_and_is_retriable(tmp_path, monkeypatch):
    # wf:contract: An export failure leaves the catalog activation committed and reports the
    # wf:contract: export as pending on channel reads.
    # wf:contract: The release_export operation, through REST and MCP with current grants,
    # wf:contract: completes it idempotently.
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    try:
        monkeypatch.setattr(
            pub.release_storage, "export", lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
        )
        fixture, _selected, first, activated = initial_release(editorial, pub)
        assert activated["attributes"]["active_build"] == first["record_id"]
        assert activated["export"]["state"] == "pending"
        settings_id = fixture["settings"]["record_id"]
        channel = pub.execute("admin", "channel_read", settings_id=settings_id)
        assert channel["generation"] == 1 and channel["export"]["state"] == "pending"
    finally:
        pub.close()
        editorial.catalog.close()
    config = {
        **CONFIG,
        "render_python": os.environ["KAJENN_RENDER_PYTHON"],
        "release_storage": storage,
    }

    async def retry():
        async with client(tmp_path, grants=RELEASE_GRANTS, publication=config) as (http, _s):
            status, rest = await call(http, "rest", "release_export", settings_id=settings_id)
            assert status == 200 and rest["ok"], rest
            status, mcp = await call(http, "mcp", "release_export", settings_id=settings_id)
            assert status == 200 and mcp["ok"], mcp
            assert rest["result"] == mcp["result"]
            assert rest["result"]["pointer"]["build_id"] == first["record_id"]
            status, read = await call(http, "rest", "channel_read", settings_id=settings_id)
            assert read["result"]["export"]["state"] == "exported"
        async with client(
            tmp_path, grants=RELEASE_GRANTS, publication=config, token="test-outsider-token"
        ) as (http, _s):
            _status, denied = await call(http, "rest", "release_export", settings_id=settings_id)
            assert not denied.get("ok")

    asyncio.run(retry())
    pointer = json.loads(bucket_objects(storage)[f"pointers/{settings_id}.json"])
    assert pointer["channel_generation"] == 1
