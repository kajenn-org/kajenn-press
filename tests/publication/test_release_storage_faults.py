"""Release storage faults reported as states, and exports that skip stored releases."""

from publication.storage_support import filesystem, release_bucket
from publication.test_release_export_contract import exporting_publisher, three_releases


def test_malformed_pointer_is_reported_not_raised(tmp_path):
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    try:
        fixture, *_rest = three_releases(editorial, pub)
        settings_id = fixture["settings"]["record_id"]
        child = {"data": {"attributes": {"settings_id": settings_id}}}
        pointer_key = storage["bucket"] + f"/pointers/{settings_id}.json"
        for body in (b"not json", b"[]", b'{"schema": 1}'):
            filesystem().pipe(pointer_key, body)
            channel = pub.execute("admin", "channel_read", settings_id=settings_id)
            assert channel["export"]["state"] == "unavailable", body
            assert channel["export"]["pointer"] is None
            deployment = pub.deployment(pub.catalog.read(), child)
            assert deployment["state"] == "storage_unavailable", body
            assert deployment["storage"] is None
    finally:
        pub.close()
        editorial.catalog.close()


def test_export_reads_only_releases_missing_from_storage(tmp_path, monkeypatch):
    storage = release_bucket()
    editorial, pub = exporting_publisher(tmp_path, storage)
    try:
        fixture, first, second, _results = three_releases(editorial, pub)
        settings_id = fixture["settings"]["record_id"]
        snapshot = pub.catalog.read()
        jobs = {
            revision_id
            for revision_id, revision in snapshot.revisions.items()
            if revision["data"].get("kind") == "publication_job"
        }
        reads = []
        read_payload = pub.catalog.read_payload

        def tracked(revision_id, name):
            # The pointer's public origin comes from the candidate, not from a build job.
            if revision_id in jobs:
                reads.append(revision_id)
            return read_payload(revision_id, name)

        monkeypatch.setattr(pub.catalog, "read_payload", tracked)
        pointer = pub.release_storage.export(pub.catalog.read(), settings_id)
        assert reads == [] and pointer["build_id"] == first["record_id"]
        job = pub.record(snapshot, second["record_id"], "publication_job")
        digest = job["data"]["attributes"]["manifest_digest"]
        filesystem().rm(storage["bucket"] + f"/manifests/{digest}.json")
        pub.release_storage.export(pub.catalog.read(), settings_id)
        assert reads and {snapshot.revisions[r]["record_id"] for r in reads} == {
            second["record_id"]
        }
        assert filesystem().exists(storage["bucket"] + f"/manifests/{digest}.json")
    finally:
        pub.close()
        editorial.catalog.close()
