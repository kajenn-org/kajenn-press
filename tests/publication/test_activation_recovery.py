import multiprocessing
import shutil

import pytest
from publication.crash_worker import interrupt_activation
from publication.release_support import initial_release, publisher, updated_release

from kajenn_public_site.domain import DomainError


def test_activation_process_crashes_and_idempotent_reopen(tmp_path):
    baseline = tmp_path / "baseline"
    editorial, pub = publisher(baseline)
    try:
        fixture, _, first, channel = initial_release(editorial, pub)
        _, second, _, _ = updated_release(editorial, pub, fixture, first)
        before = pub.catalog.read()
    finally:
        pub.close()
        editorial.catalog.close()
    ctx = multiprocessing.get_context("spawn")
    for stage in ("intent", "manifest", "head_before", "head_replaced", "head_durable"):
        root = tmp_path / stage
        shutil.copytree(baseline, root)
        process = ctx.Process(
            target=interrupt_activation,
            args=(
                str(root),
                fixture["settings"]["record_id"],
                second["record_id"],
                channel["generation"],
                stage,
            ),
        )
        process.start()
        process.join(30)
        assert process.exitcode == 86, stage
        editorial, pub = publisher(root)
        try:
            args = {
                "settings_id": fixture["settings"]["record_id"],
                "build_id": second["record_id"],
                "expected_generation": channel["generation"],
                "key": "crash-activate",
            }
            current = pub.catalog.read()
            visible = pub.execute("admin", "channel_read", settings_id=args["settings_id"])
            receipt = pub.catalog.receipt("admin", "publication", "crash-activate")
            if stage in {"head_replaced", "head_durable"}:
                assert visible["attributes"]["active_revision"] == second["revision_id"]
                assert receipt is not None and current.generation == before.generation + 1
                assert any(a["id"] == receipt["audit_id"] for a in current.audit)
                assert any(e["id"] == receipt["event_id"] for e in current.events)
                assert {r["revision_id"] for r in receipt["results"]} == {
                    visible["revision_id"],
                    visible["activation"]["revision_id"],
                }
            else:
                assert visible == channel and receipt is None
                assert current.generation == before.generation
            retried = pub.execute("admin", "release_activate", **args)
            assert retried["attributes"]["active_revision"] == second["revision_id"]
            final_generation = pub.catalog.read().generation
            assert pub.execute("admin", "release_activate", **args) == retried
            assert (
                len(pub.execute("admin", "release_history", settings_id=args["settings_id"])) == 2
            )
            assert pub.catalog.read().generation == final_generation
            with pytest.raises(DomainError) as changed:
                pub.execute("admin", "release_activate", **{**args, "build_id": first["record_id"]})
            assert changed.value.code == "conflict"
            pub.policy.grants["admin"]["*"].remove("publish")
            with pytest.raises(DomainError) as revoked:
                pub.execute("admin", "release_activate", **args)
            assert revoked.value.code == "forbidden"
            assert pub.catalog.read().generation == final_generation
        finally:
            pub.close()
            editorial.catalog.close()
