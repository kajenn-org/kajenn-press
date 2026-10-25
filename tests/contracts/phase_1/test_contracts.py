"""Plan-time contract skeletons; intentionally pending implementation."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from catalog.support import baseline, commit, crash_changes, worker, workspace
from genro_storage import StorageNode

from kajenn_press.catalog.errors import Conflict, UnsupportedProfile
from kajenn_press.catalog.local import Change, LocalCatalog
from kajenn_press.objects import ObjectStore


def test_committed_catalog_survives_restart():
    # wf:contract: A successfully committed catalog generation remains readable after coordinator restart.
    # wf:contract: Stable IDs, generations and exact payload references are preserved.
    with workspace() as root:
        receipt = baseline(root)
        assert worker(root, "read").returncode == 0
        with LocalCatalog(root) as c:
            assert c.read().generation == receipt["generation"] == 1
            head = receipt["results"][0]
            assert c.read().records[head["record_id"]]["revision_id"] == head["revision_id"]
            assert c.read_payload(head["revision_id"], "body") == b"old\r\n"
            before = c.read().revisions
        with LocalCatalog(root) as c:
            assert c.read().revisions == before


def test_historical_payload_is_immutable():
    # wf:contract: Saving a new revision preserves the exact bytes and digest of every previously committed revision.
    # wf:contract: Local history uses explicit immutable snapshots and does not require S3 versioning.
    with workspace() as root:
        first = baseline(root)["results"][0]
        with LocalCatalog(root) as c:
            original = c.read().revisions[first["revision_id"]]
            second = commit(
                c, "save", Change("site:one", first["record_id"], 1, payloads={"body": b"new\n"})
            )["results"][0]
            assert c.read().revisions[first["revision_id"]] == original
            assert c.read(1).records[first["record_id"]]["revision_id"] == first["revision_id"]
            assert c.read_payload(first["revision_id"], "body") == b"old\r\n"
            assert c.read_payload(second["revision_id"], "body") == b"new\n"
            assert (
                original["payloads"]["body"]["sha256"]
                != c.read().revisions[second["revision_id"]]["payloads"]["body"]["sha256"]
            )


def test_stale_generation_does_not_overwrite():
    # wf:contract: Two mutations using the same expected generation cannot both advance the same head.
    # wf:contract: The rejected mutation leaves the winning state unchanged and reports a conflict.
    with workspace() as root:
        first = baseline(root)["results"][0]
        with LocalCatalog(root) as c:

            def update(key):
                try:
                    return commit(
                        c,
                        key,
                        Change("site:one", first["record_id"], 1, payloads={"body": key.encode()}),
                    )
                except Conflict:
                    return None

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(update, ["left", "right"]))
            assert sum(result is not None for result in results) == 1
            winner = next(result for result in results if result is not None)
            before = c.read()
            with pytest.raises(Conflict):
                commit(c, "stale", Change("site:one", first["record_id"], 1))
            assert c.read() == before
            assert (
                before.records[first["record_id"]]["revision_id"]
                == winner["results"][0]["revision_id"]
            )


def test_duplicate_coordinator_is_rejected():
    # wf:contract: A second coordinator cannot acquire write ownership of the same local catalog while the first owns it.
    # wf:contract: After the first process terminates, ownership can be reacquired without discarding committed data.
    with workspace() as root:
        baseline(root)
        env = dict(os.environ)
        project = Path(__file__).resolve().parents[3]
        env["PYTHONPATH"] = os.pathsep.join([str(project / "src"), str(project / "tests")])
        process = subprocess.Popen(
            [sys.executable, str(project / "tests/catalog/worker.py"), str(root), "hold", ""],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdout.readline().strip() == "owned"
            assert worker(root, "probe").returncode == 23
            process.kill()
            process.wait(timeout=10)
            with LocalCatalog(root) as c:
                assert c.read().generation == 1
                assert c.receipt("admin", "installation", "baseline") is not None
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)


def test_idempotent_retry_survives_restart():
    # wf:contract: Repeating a completed command with the same principal, scope, key and payload after restart returns its original result.
    # wf:contract: The retry does not create a second revision, audit event or domain event.
    with workspace() as root:
        first = baseline(root)
        with LocalCatalog(root) as c:
            before = c.read()
            retry = commit(
                c,
                "baseline",
                Change("site:one", data={"title": "First"}, payloads={"body": b"old\r\n"}),
            )
            assert retry == first
            assert c.read() == before
            assert len(before.revisions) == len(before.audit) == len(before.events) == 1


def test_idempotency_key_payload_mismatch_is_rejected():
    # wf:contract: Reusing an idempotency key with different command data returns a conflict without changing committed state.
    with workspace() as root:
        baseline(root)
        with LocalCatalog(root) as c:
            before = c.read()
            with pytest.raises(Conflict, match="Idempotency"):
                commit(c, "baseline", Change("site:one", payloads={"body": b"different"}))
            assert c.read() == before


def test_interrupted_commit_has_one_visible_generation():
    # wf:contract: Inject process termination at payload preparation, manifest preparation and current-reference publication boundaries.
    # wf:contract: After restart readers observe one complete valid generation, never a mixture or a reference to an incomplete payload.
    # wf:contract: The recovery path determines whether the command committed before retrying effects.
    for stage in (
        "intent",
        "payload_partial",
        "payload_complete",
        "manifest",
        "head_before",
        "head_replaced",
        "head_durable",
    ):
        with workspace() as root:
            baseline(root)
            result = worker(root, "crash", stage)
            assert result.returncode == 86, (stage, result.stderr)
            with LocalCatalog(root) as c:
                committed = stage in ("head_replaced", "head_durable")
                before = c.read()
                assert before.generation == (2 if committed else 1)
                assert len(before.records) == (2 if committed else 1)
                assert len(before.revisions) == (3 if committed else 1)
                assert c.read(1).generation == 1
                receipt = c.receipt("admin", "installation", "crash")
                assert (receipt is not None) == committed
                report = c.recover()
                assert sum(op["state"] == "committed" for op in report["operations"]) == (
                    2 if committed else 1
                )
                retry = commit(c, "crash", *crash_changes(c))
                if committed:
                    assert retry == receipt
                    assert c.read() == before
                assert c.read().generation == 2
                assert len(c.read().audit) == len(c.read().events) == 2
                for revision in c.read().revisions.values():
                    for name in revision["payloads"]:
                        assert isinstance(c.read_payload(revision["id"], name), bytes)


def test_uncommitted_payload_is_not_visible():
    # wf:contract: A payload written before a failed catalog commit is not exposed as a committed revision or public artifact.
    # wf:contract: The recovery report distinguishes unreferenced prepared data from committed dependencies.
    with workspace() as root:
        baseline(root)
        result = worker(root, "crash", "payload_complete")
        assert result.returncode == 86, result.stderr
        with LocalCatalog(root) as c:
            report = c.recover()
            prepared = next(op for op in report["operations"] if op["state"] == "prepared")
            assert [item["state"] for item in prepared["payloads"]] == ["prepared", "missing"]
            committed_refs = {
                ref["key"]
                for rev in c.read().revisions.values()
                for ref in rev["payloads"].values()
            }
            assert all(
                item["reference"]["key"] not in committed_refs for item in prepared["payloads"]
            )
            with pytest.raises(KeyError):
                c.read_payload(prepared["payloads"][0]["reference"]["key"], "body")
            assert c.read().generation == 1
            assert not (root / "public").exists()


def test_coordinated_changes_commit_together():
    # wf:contract: A changeset touching site and generic-library records finalizes all referenced changes and its receipt together.
    # wf:contract: A stale base for any member prevents advancement of all members.
    with workspace() as root:
        with LocalCatalog(root) as c:
            first = commit(c, "create", Change("site:one"), Change("library"))
            a, b = first["results"]
            updated = commit(
                c,
                "both",
                Change("site:one", a["record_id"], 1, {"value": 2}),
                Change("library", b["record_id"], 1, {"value": 2}),
            )
            assert c.receipt("admin", "installation", "both") == updated
            assert [result["generation"] for result in updated["results"]] == [2, 2]
            before = c.read()
            with pytest.raises(Conflict):
                commit(
                    c,
                    "stale-member",
                    Change("site:one", a["record_id"], 2, {"value": 3}),
                    Change("library", b["record_id"], 1, {"value": 3}),
                )
            assert c.read() == before
        with LocalCatalog(root) as c:
            assert c.read() == before


def test_payload_access_uses_public_storage_api():
    # wf:contract: Content payloads are accessed through public Genro Storage interfaces.
    # wf:contract: Catalog commit does not rely on StorageNode.move_to being an atomic rename or on private backend paths.
    # wf:contract: The local profile verifies the actual exclusive-create and durability primitives used; unavailable required primitives produce a clear unsupported-profile error.
    with workspace() as root, pytest.MonkeyPatch.context() as patch:
        modes = []
        original = StorageNode.open

        def tracked(node, mode="r", *args, **kwargs):
            modes.append(mode)
            return original(node, mode, *args, **kwargs)

        def forbidden(*args, **kwargs):
            raise AssertionError("move_to is not an atomic commit primitive")

        patch.setattr(StorageNode, "open", tracked)
        patch.setattr(StorageNode, "move_to", forbidden)
        baseline(root)
        assert "xb" in modes and "rb" in modes

        # Qualify the actual runtime, then prove unavailable primitives fail closed.
        def no_flush(stream):
            raise OSError("unsupported durable flush")

        patch.setattr("kajenn_press.objects.sync_file", no_flush)
        with pytest.raises(UnsupportedProfile, match="durable flush"):
            ObjectStore(root / "unsupported")
        source = Path(__file__).resolve().parents[3] / "src/kajenn_press"
        for path in source.rglob("*.py"):
            assert "._backend" not in path.read_text()
            assert ".move_to(" not in path.read_text()
