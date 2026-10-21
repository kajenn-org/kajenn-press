from concurrent.futures import ThreadPoolExecutor

import pytest

from catalog.support import commit
from kajenn_public_site.catalog.errors import Conflict, IntegrityError, OwnershipError
from kajenn_public_site.catalog.local import Change, LocalCatalog


def test_atomic_changes_history_and_reopen(tmp_path):
    with LocalCatalog(tmp_path) as c:
        first = commit(
            c, "create", Change("site:one", data={"name": "test"}, payloads={"body": b"old"})
        )
        head = first["results"][0]
        second = commit(
            c, "update", Change("site:one", head["record_id"], 1, payloads={"body": b"new"})
        )
        assert c.read(1).records[head["record_id"]]["generation"] == 1
        assert c.read_payload(head["revision_id"], "body") == b"old"
        assert c.read_payload(second["results"][0]["revision_id"], "body") == b"new"
        assert c.recover()["operations"][0]["state"] == "committed"
    with LocalCatalog(tmp_path) as c:
        assert c.read().generation == 2
        assert c.receipt("admin", "installation", "create") == first
        assert (
            commit(
                c, "create", Change("site:one", data={"name": "test"}, payloads={"body": b"old"})
            )
            == first
        )


def test_thread_conflict_and_authorization(tmp_path):
    with LocalCatalog(tmp_path) as c:
        head = commit(c, "create", Change("site:one"))["results"][0]

        def update(i):
            try:
                return commit(c, str(i), Change("site:one", head["record_id"], 1, {"value": i}))
            except Conflict:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(update, range(8)))
        assert sum(result is not None for result in results) == 1
        assert c.read().generation == 2
        before = c.read()

        def deny(principal, snapshot, changes):
            assert snapshot == before
            raise PermissionError("No site grant")

        with pytest.raises(PermissionError):
            c.commit(
                principal="admin",
                scope="installation",
                key="denied",
                changes=[Change("site:one")],
                authorize=deny,
            )
        assert c.read() == before
        # Revocation also applies to replaying a completed operation receipt.
        with pytest.raises(PermissionError):
            c.commit(
                principal="admin",
                scope="installation",
                key="create",
                changes=[Change("site:one")],
                authorize=deny,
            )


def test_coordinator_lifecycle_and_detached_reads(tmp_path):
    with LocalCatalog(tmp_path) as c:
        with pytest.raises(OwnershipError):
            LocalCatalog(tmp_path)
        head = commit(c, "create", Change("library"))["results"][0]
        snapshot = c.read()
        snapshot.records.clear()
        assert head["record_id"] in c.read().records
    with pytest.raises(OwnershipError):
        c.read()


def test_committed_corruption_fails_closed(tmp_path):
    with LocalCatalog(tmp_path) as c:
        head = commit(c, "create", Change("library", payloads={"body": b"data"}))["results"][0]
        ref = c.read().revisions[head["revision_id"]]["payloads"]["body"]
    (tmp_path / "payloads" / (ref["key"] + ".blob")).write_bytes(b"xxxx")
    with pytest.raises(IntegrityError):
        LocalCatalog(tmp_path)


@pytest.mark.parametrize("operation", ["commit", "close"])
def test_authorization_cannot_mutate_or_release_ownership(tmp_path, operation):
    with LocalCatalog(tmp_path) as c:
        before = c.read()

        def reentrant(principal, snapshot, changes):
            assert c.read() == before
            if operation == "commit":
                commit(c, "nested", Change("library"))
            else:
                c.close()

        with pytest.raises(OwnershipError, match="during authorization"):
            c.commit(
                principal="admin",
                scope="installation",
                key="outer",
                changes=[Change("library")],
                authorize=reentrant,
            )
        assert c.read() == before
        with pytest.raises(OwnershipError):
            LocalCatalog(tmp_path)
        assert commit(c, "later", Change("library"))["generation"] == 1


@pytest.mark.parametrize("damage", ["schema", "receipt", "history", "head", "missing_payload"])
def test_manifest_schema_and_references_fail_closed(tmp_path, damage):
    import json

    from kajenn_public_site.catalog.filesystem import digest, encode

    with LocalCatalog(tmp_path) as c:
        first = commit(c, "create", Change("library", payloads={"body": b"data"}))["results"][0]
    current = json.loads((tmp_path / "current.json").read_bytes())
    path = tmp_path / "manifests" / current["name"]
    manifest = json.loads(path.read_bytes())
    if damage == "schema":
        manifest["schema"] = True
    elif damage == "receipt":
        next(iter(manifest["receipts"].values()))["results"][0]["record_id"] = "0" * 32
    elif damage == "history":
        manifest["revisions"][first["revision_id"]]["previous"] = "0" * 32
    elif damage == "head":
        manifest["records"][first["record_id"]]["generation"] = 7
    else:
        ref = manifest["revisions"][first["revision_id"]]["payloads"]["body"]
        (tmp_path / "payloads" / (ref["key"] + ".blob")).unlink()
    path.write_bytes(encode(manifest))
    current["sha256"] = digest(encode(manifest))
    (tmp_path / "current.json").write_bytes(encode(current))
    with pytest.raises(IntegrityError):
        LocalCatalog(tmp_path)


def test_invalid_intent_is_reported_as_integrity_failure(tmp_path):
    from kajenn_public_site.catalog.filesystem import encode

    with LocalCatalog(tmp_path) as c:
        commit(c, "create", Change("library"))
        path = next(c.intents.iterdir())
        path.write_bytes(encode({"schema": 1}))
        with pytest.raises(IntegrityError, match="intent"):
            c.recover()


def test_catalog_symlink_and_path_containment(tmp_path):
    from kajenn_public_site.catalog.filesystem import contained_file

    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "catalog"
    root.mkdir()
    (root / "manifests").symlink_to(outside, target_is_directory=True)
    with pytest.raises(IntegrityError, match="Symlink"):
        LocalCatalog(root)
    assert list(outside.iterdir()) == []
    with pytest.raises(IntegrityError):
        contained_file(root, "../outside")
    with pytest.raises(IntegrityError):
        contained_file(root, str(outside))


def test_committed_reference_reuse_and_reject_orphan(tmp_path):
    from kajenn_public_site.objects import ObjectRef

    with LocalCatalog(tmp_path) as c:
        original = commit(c, "original", Change("library", payloads={"source": b"exact"}))[
            "results"
        ][0]
        ref = ObjectRef(**c.read().revisions[original["revision_id"]]["payloads"]["source"])
        copied = commit(c, "copy", Change("site:one", payloads={"source": ref}))["results"][0]
        assert copied["record_id"] != original["record_id"]
        assert c.read_payload(copied["revision_id"], "source") == b"exact"
        orphan = ObjectRef(**c.objects.reference(b"orphan"))
        c.objects.prepare(orphan, b"orphan")
        before = c.read()
        with pytest.raises(IntegrityError, match="uncommitted"):
            commit(c, "adopt", Change("site:one", payloads={"source": orphan}))
        assert c.read() == before


def test_independent_records_and_receipt_scopes(tmp_path):
    from catalog.support import allow

    with LocalCatalog(tmp_path) as c:
        created = commit(c, "create", Change("site:one"), Change("site:two"))
        a, b = created["results"]
        commit(c, "one", Change("site:one", a["record_id"], 1))
        # Another record may still be saved with generation 1 after the global head advances.
        commit(c, "two", Change("site:two", b["record_id"], 1))
        other_scope = c.commit(
            principal="admin",
            scope="different",
            key="create",
            changes=[Change("library")],
            authorize=allow,
        )
        assert other_scope != created
        assert c.receipt("admin", "installation", "create") == created
        assert c.receipt("admin", "different", "create") == other_scope
        assert c.receipt("other", "installation", "create") is None


def test_io_error_requires_reopen_and_receipt_reconciliation(
    tmp_path, monkeypatch
):
    from kajenn_public_site.catalog import local
    from kajenn_public_site.catalog.errors import CommitUncertain

    original = local.publish_json

    def lost_ack(root, name, value, staging):
        original(root, name, value, staging)
        if name == "current.json":
            raise OSError("Simulated response uncertainty after durable publication")

    with LocalCatalog(tmp_path) as c, monkeypatch.context() as patch:
        patch.setattr(local, "publish_json", lost_ack)
        with pytest.raises(CommitUncertain):
            commit(c, "save", Change("library"))
        with pytest.raises(CommitUncertain, match="Reopen"):
            commit(c, "another", Change("library"))
    with LocalCatalog(tmp_path) as c:
        receipt = c.receipt("admin", "installation", "save")
        assert receipt is not None
        assert commit(c, "save", Change("library")) == receipt
        assert c.read().generation == 1


def test_configured_parent_alias_is_resolved_but_root_link_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    with LocalCatalog(alias / "new") as c:
        assert c.root == actual / "new"
        assert commit(c, "save", Change("library"))["generation"] == 1
    with pytest.raises(IntegrityError, match="Symlink"):
        LocalCatalog(alias)
