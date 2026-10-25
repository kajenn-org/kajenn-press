from concurrent.futures import ThreadPoolExecutor

import pytest
from publication.release_support import activate, initial_release, publisher, updated_release
from publication.support import built, candidate, site_fixture
from services.scenarios import record

from kajenn_press.domain import DomainError


def test_atomic_activation_race_and_stale_base(tmp_path):
    editorial, pub = publisher(tmp_path)
    try:
        fixture = site_fixture(editorial, pub)
        first = built(pub, candidate(pub, fixture))
        second = built(pub, candidate(pub, fixture, key="second"), key="second-build")
        before = pub.catalog.read()

        def compete(job, key):
            try:
                return activate(pub, fixture, job, key=key)
            except DomainError as exc:
                return exc

        with ThreadPoolExecutor(2) as executor:
            results = list(executor.map(compete, (first, second), ("race-a", "race-b")))
        winners = [r for r in results if isinstance(r, dict)]
        assert len(winners) == 1
        assert [r.code for r in results if isinstance(r, DomainError)] == ["conflict"]
        current = pub.catalog.read()
        assert current.generation == before.generation + 1
        assert len(current.records) == len(before.records) + 2
        assert len(current.receipts) == len(before.receipts) + 1
        winner = winners[0]
        receipt = next(
            r for r in current.receipts.values() if r["generation"] == current.generation
        )
        assert {r["revision_id"] for r in receipt["results"]} == {
            winner["revision_id"],
            winner["activation"]["revision_id"],
        }
        assert any(a["id"] == receipt["audit_id"] for a in current.audit)
        assert any(a["id"] == receipt["event_id"] for a in current.events)
        losing_job = second if winner["attributes"]["active_build"] == first["record_id"] else first
        with pytest.raises(DomainError) as stale:
            activate(pub, fixture, losing_job, generation=1, key="stale-base")
        assert stale.value.code == "stale_base"
        assert pub.catalog.read().generation == current.generation
    finally:
        pub.close()
        editorial.catalog.close()


def test_language_update_rollback_restart_and_policy(tmp_path):
    editorial, pub = publisher(tmp_path)
    try:
        fixture, _, original, first = initial_release(editorial, pub)
        selected, updated, italian, english = updated_release(editorial, pub, fixture, original)
        value = pub.candidate_data(pub.catalog.read().revisions[selected["revision_id"]])
        assert value["entries"][italian["record_id"]]["variant_revision"] == italian["revision_id"]
        assert (
            value["entries"][english["record_id"]]["variant_revision"]
            == fixture["variants"]["en"]["revision_id"]
        )
        second = activate(pub, fixture, updated, generation=first["generation"], key="update")
        assert (
            activate(pub, fixture, updated, generation=first["generation"], key="update") == second
        )
        pub.close()
        editorial.catalog.close()
        editorial, pub = publisher(tmp_path)
        pub.worker.python = str(tmp_path / "no-renderer")
        restored = activate(
            pub,
            fixture,
            original,
            generation=second["generation"],
            key="rollback",
            operation="release_rollback",
        )
        assert restored["attributes"]["active_revision"] == original["revision_id"]
        assert restored["activation"]["attributes"]["action"] == "rollback"
        history = pub.execute(
            "admin", "release_history", settings_id=fixture["settings"]["record_id"]
        )
        assert [row["attributes"]["build_id"] for row in history] == [
            original["record_id"],
            updated["record_id"],
            original["record_id"],
        ]
        snapshot = pub.catalog.read()
        for permission in ("publish", "use"):
            editorial.policy.grants["admin"]["*"].remove(permission)
            with pytest.raises(DomainError) as denied:
                activate(
                    pub,
                    fixture,
                    original,
                    generation=second["generation"],
                    key="rollback",
                    operation="release_rollback",
                )
            assert denied.value.code == "forbidden"
            editorial.policy.grants["admin"]["*"].append(permission)
        site = fixture["site"]
        record(
            editorial,
            "site_configure",
            site_id=site["record_id"],
            expected_generation=site["generation"],
            key="review",
            name="one",
            languages=["it", "en"],
            review_required=True,
        )
        with pytest.raises(DomainError) as review:
            activate(
                pub,
                fixture,
                updated,
                generation=restored["generation"],
                key="blocked",
                operation="release_rollback",
            )
        assert review.value.code == "review_required"
        assert pub.catalog.read().generation == snapshot.generation + 1
    finally:
        pub.close()
        editorial.catalog.close()


def test_rollback_compatibility_and_unselected_languages(tmp_path):
    editorial, pub = publisher(tmp_path)
    try:
        fixture, _, first, channel = initial_release(editorial, pub)
        site = fixture["site"]
        record(
            editorial,
            "site_configure",
            site_id=site["record_id"],
            expected_generation=1,
            key="french",
            name="one",
            languages=["it", "en", "fr"],
        )
        record(
            editorial,
            "variant_create",
            content_id=fixture["content"]["record_id"],
            language="fr",
            template_revision=fixture["template"]["revision_id"],
            key="fr-variant",
            blocks={"body": {"format": "markdown", "source": "NEVER PUBLISHED"}},
        )
        _, updated, _, _ = updated_release(editorial, pub, fixture, first)
        manifest = pub.sealed_manifest(pub.catalog.read().revisions[updated["revision_id"]])
        assert set(manifest["routes"]) == {"/it/", "/en/about/"}
        second = activate(pub, fixture, updated, generation=channel["generation"], key="update")
        unpublished = built(
            pub, candidate(pub, fixture, key="unpublished"), key="unpublished-build"
        )
        before = pub.catalog.read().generation
        with pytest.raises(DomainError) as hidden:
            activate(
                pub,
                fixture,
                unpublished,
                generation=second["generation"],
                key="hidden",
                operation="release_rollback",
            )
        assert hidden.value.code == "not_published"
        assert pub.catalog.read().generation == before
        other = site_fixture(editorial, pub, prefix="other")
        for settings_id in (
            other["settings"]["record_id"],
            pub.execute(
                "admin",
                "publication_settings_save",
                site_id=site["record_id"],
                channel="other",
                public_origin="https://one.test",
                primary_language="it",
                landing_variant=fixture["variants"]["it"]["record_id"],
                key="other-channel",
            )["record_id"],
        ):
            with pytest.raises(DomainError) as wrong:
                pub.execute(
                    "admin",
                    "release_rollback",
                    settings_id=settings_id,
                    build_id=first["record_id"],
                    expected_generation=0,
                    key=settings_id,
                )
            assert wrong.value.code == "incompatible_release"
        settings = fixture["settings"]
        pub.public_origins = {"https://one.test": settings["record_id"]}
        previous_html = pub.public_response("https://one.test", "/it/", "GET").body
        pub.execute(
            "admin",
            "publication_settings_save",
            record_id=settings["record_id"],
            expected_generation=settings["generation"],
            site_id=site["record_id"],
            channel="main",
            public_origin="https://changed.test",
            primary_language="it",
            landing_variant=fixture["variants"]["it"]["record_id"],
            key="changed-destination",
        )
        before = pub.catalog.read().generation
        with pytest.raises(DomainError) as destination:
            activate(
                pub,
                fixture,
                first,
                generation=second["generation"],
                key="incompatible",
                operation="release_rollback",
            )
        assert destination.value.code == "incompatible_release"
        assert pub.catalog.read().generation == before
        changed = built(
            pub, candidate(pub, fixture, key="changed-origin"), key="changed-origin-build"
        )
        before = pub.catalog.read().generation
        with pytest.raises(DomainError) as binding:
            activate(
                pub, fixture, changed, generation=second["generation"], key="changed-activation"
            )
        assert binding.value.code == "incompatible_release"
        assert pub.catalog.read().generation == before
        assert pub.catalog.receipt("admin", "publication", "changed-activation") is None
        assert pub.public_response("https://one.test", "/it/", "GET").body == previous_html
        pub.public_origins = {"https://changed.test": settings["record_id"]}
        migrated = activate(
            pub, fixture, changed, generation=second["generation"], key="changed-activation"
        )
        assert migrated["generation"] == second["generation"] + 1
        assert pub.public_response("https://changed.test", "/it/", "GET").status_code == 200
        pub.public_origins = {"https://one.test": settings["record_id"]}
        before = pub.catalog.read().generation
        for operation, generation, key in (
            ("release_activate", second["generation"], "changed-activation"),
            ("release_rollback", migrated["generation"], "wrong-binding-rollback"),
        ):
            with pytest.raises(DomainError) as binding:
                activate(pub, fixture, changed, generation=generation, key=key, operation=operation)
            assert binding.value.code == "incompatible_release"
            assert pub.catalog.read().generation == before
    finally:
        pub.close()
        editorial.catalog.close()
