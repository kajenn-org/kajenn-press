import base64
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from uuid import UUID

import pytest
from services.scenarios import BLOCKS, create_service, record, seed

from kajenn_public_site.domain import DomainError


def test_named_sources_restart_and_exact_template_selection(tmp_path):
    service = create_service(tmp_path)
    try:
        _site, _other, template, _content, variant = seed(service)
        assert variant["sources"]["block.intro"]["text"] == BLOCKS["intro"]["source"]
        assert variant["sources"]["block.body"]["text"] == BLOCKS["body"]["source"]
        assert service.execute("admin", "readiness", record_id=variant["record_id"])["ready"]
        record(
            service,
            "resource_save",
            key="template-v2",
            scope="library",
            kind="template",
            name="page",
            source="new source",
            engine="htmlbuilder",
            blocks={"new": {"format": "html", "required": True}},
            record_id=template["record_id"],
            expected_generation=1,
        )
        assert service.execute("admin", "readiness", record_id=variant["record_id"])["ready"]
        assert (
            service.execute("admin", "dependencies", record_id=variant["record_id"])[
                "dependencies"
            ][0]["revision_id"]
            == template["revision_id"]
        )
    finally:
        service.catalog.close()
    service = create_service(tmp_path)
    try:
        assert service.execute("admin", "record_read", record_id=variant["record_id"]) == variant
        assert len(service.execute("admin", "sites_list")) == 2
    finally:
        service.catalog.close()


def test_incomplete_validation_unknown_blocks_and_language_uniqueness(tmp_path):
    service = create_service(tmp_path)
    try:
        site, _, template, content, variant = seed(service)
        incomplete = record(
            service,
            "draft_save",
            key="empty",
            variant_id=variant["record_id"],
            expected_generation=1,
            template_revision=template["revision_id"],
            blocks={},
        )
        report = service.execute("admin", "readiness", record_id=incomplete["record_id"])
        assert report["diagnostics"] == [
            {
                "code": "required_block_missing",
                "resource_id": variant["record_id"],
                "block": "intro",
                "message": "Required block is missing or empty",
            }
        ]
        with pytest.raises(DomainError) as error:
            record(
                service,
                "draft_save",
                key="bad",
                variant_id=variant["record_id"],
                expected_generation=2,
                template_revision=template["revision_id"],
                blocks={"intro": {"format": "markdown", "source": "wrong"}},
            )
        assert error.value.code == "invalid_block" and error.value.block == "intro"
        with pytest.raises(DomainError, match="already exists"):
            record(
                service,
                "variant_create",
                key="duplicate",
                content_id=content["record_id"],
                language="it",
                template_revision=template["revision_id"],
            )
        with pytest.raises(DomainError, match="remove a language"):
            record(
                service,
                "site_configure",
                key="remove",
                site_id=site["record_id"],
                expected_generation=1,
                name="First site",
                languages=["en"],
            )
    finally:
        service.catalog.close()


def test_revision_checkpoint_compare_restore_and_idempotency(tmp_path, monkeypatch):
    # Make UUID order oppose generation order in the serialized catalog.
    identifiers = count((1 << 128) - 1, -1)
    monkeypatch.setattr(
        "kajenn_public_site.catalog.local.uuid4", lambda: UUID(int=next(identifiers))
    )
    service = create_service(tmp_path)
    try:
        _, _, template, _, variant = seed(service)
        changed = record(
            service,
            "draft_save",
            key="save",
            variant_id=variant["record_id"],
            expected_generation=1,
            template_revision=template["revision_id"],
            blocks={"intro": {"format": "html", "source": "updated"}},
        )
        checkpoint = record(
            service,
            "revision_checkpoint",
            key="checkpoint",
            record_id=variant["record_id"],
            expected_generation=2,
            message="Reviewed",
        )
        assert checkpoint["payloads"] == changed["payloads"]
        diff = service.execute(
            "admin",
            "revision_compare",
            record_id=variant["record_id"],
            left_revision=variant["revision_id"],
            right_revision=changed["revision_id"],
        )
        assert diff["sources"]["block.intro"]["changed"]
        restored = record(
            service,
            "revision_restore",
            key="restore",
            record_id=variant["record_id"],
            expected_generation=3,
            source_revision=variant["revision_id"],
        )
        assert restored["sources"] == variant["sources"]
        assert restored["attributes"]["restored_from"] == variant["revision_id"]
        history = service.execute("admin", "revision_history", record_id=variant["record_id"])
        assert [revision["generation"] for revision in history] == [1, 2, 3, 4]
        assert [revision["revision_id"] for revision in history] == [
            revision["revision_id"] for revision in (variant, changed, checkpoint, restored)
        ]
        # Retry a derived command after additional edits: original checkpoint remains exact.
        retry = record(
            service,
            "revision_checkpoint",
            key="checkpoint",
            record_id=variant["record_id"],
            expected_generation=2,
            message="Reviewed",
        )
        assert retry == checkpoint
        with pytest.raises(DomainError, match="different input"):
            record(
                service,
                "revision_checkpoint",
                key="checkpoint",
                record_id=variant["record_id"],
                expected_generation=2,
                message="Different",
            )
        with pytest.raises(DomainError) as conflict:
            record(
                service,
                "draft_save",
                key="stale",
                variant_id=variant["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks=BLOCKS,
            )
        assert (
            conflict.value.code == "conflict" and conflict.value.resource_id == variant["record_id"]
        )
    finally:
        service.catalog.close()
    service = create_service(tmp_path)
    try:
        assert service.execute(
            "admin", "revision_history", record_id=variant["record_id"]
        ) == history
    finally:
        service.catalog.close()


def test_scoped_grants_copy_and_media(tmp_path):
    service = create_service(tmp_path)
    try:
        site, other, template, _, _variant = seed(service)
        scope = "site:" + site["record_id"]
        service.policy.grants["writer"] = {
            scope: ["read", "write", "use"],
            "library": ["read", "use"],
        }
        copied = service.execute(
            "writer",
            "resource_copy",
            key="copy",
            source_revision=template["revision_id"],
            site_id=site["record_id"],
            name="local",
        )["records"][0]
        assert copied["record_id"] != template["record_id"]
        assert copied["attributes"]["copied_from"] == template["revision_id"]
        with pytest.raises(DomainError) as denied:
            service.execute(
                "writer",
                "resource_save",
                scope="library",
                kind="css",
                name="x",
                source="x",
                key="denied",
            )
        assert denied.value.code == "forbidden"
        with pytest.raises(DomainError):
            service.execute("writer", "record_read", record_id=other["record_id"])
        media = record(
            service,
            "media_save",
            scope=scope,
            name="bytes.bin",
            data_base64=base64.b64encode(b"\x00\xffbinary").decode(),
            mime_type="application/octet-stream",
            key="media",
        )
        assert base64.b64decode(media["sources"]["binary"]["base64"]) == b"\x00\xffbinary"
        assert media["attributes"]["mime_verified"] is False
        service.policy.grants["writer"] = {}
        with pytest.raises(DomainError):
            service.execute(
                "writer",
                "resource_copy",
                key="copy",
                source_revision=template["revision_id"],
                site_id=site["record_id"],
                name="local",
            )
    finally:
        service.catalog.close()


def test_concurrent_variant_creation_has_one_shared_head(tmp_path):
    from kajenn_public_site.services.editorial import EditorialService

    service = create_service(tmp_path)
    try:
        _, _, template, content, _ = seed(service)
        second = EditorialService(service.catalog, service.policy)

        def create(pair):
            owner, key = pair
            try:
                return record(
                    owner,
                    "variant_create",
                    key=key,
                    content_id=content["record_id"],
                    language="en",
                    template_revision=template["revision_id"],
                )
            except DomainError as exc:
                assert exc.code == "conflict"
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, [(service, "one"), (second, "two")]))
        assert sum(result is not None for result in results) == 1
    finally:
        service.catalog.close()


def test_copy_edits_preserve_provenance_and_original_dependencies(tmp_path):
    service = create_service(tmp_path)
    try:
        site, _, template, _, _ = seed(service)
        scope = "site:" + site["record_id"]
        copied = record(
            service,
            "resource_copy",
            key="copy",
            source_revision=template["revision_id"],
            site_id=site["record_id"],
            name="local",
        )
        changed = record(
            service,
            "resource_save",
            key="copy-edit",
            scope=scope,
            kind="template",
            name="local",
            source="changed independently",
            engine="gramlot",
            blocks=template["attributes"]["blocks"],
            record_id=copied["record_id"],
            expected_generation=1,
        )
        assert changed["attributes"]["copied_from"] == template["revision_id"]
        assert service.execute("admin", "record_read", record_id=template["record_id"]) == template
        assert (
            service.execute(
                "admin",
                "record_read",
                record_id=copied["record_id"],
                revision_id=copied["revision_id"],
            )
            == copied
        )
    finally:
        service.catalog.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"record_id": "", "expected_generation": 0},
        {"record_id": None, "expected_generation": 2},
        {"record_id": "../escape", "expected_generation": 1},
        {"record_id": None, "expected_generation": True},
        {"dependencies": [["not-an-id"]]},
    ],
)
def test_invalid_source_command_never_changes_catalog(tmp_path, kwargs):
    service = create_service(tmp_path)
    try:
        before = service.catalog.read()
        with pytest.raises(DomainError):
            record(
                service,
                "resource_save",
                key="bad",
                scope="library",
                kind="css",
                name="test.css",
                source="x",
                **kwargs,
            )
        assert service.catalog.read() == before
    finally:
        service.catalog.close()
