"""S3 versioning on the development endpoint, through Genro Storage (N3 Phase 1)."""

from genro_storage import StorageManager
from publication.storage_support import release_bucket, versioned_bucket, versioning_status


def mount(config):
    manager = StorageManager()
    manager.configure([{"name": "src", **config}])
    return manager


def test_versions_are_listed_read_and_restored_as_a_new_version():
    config = versioned_bucket()
    manager = mount(config)
    node = manager.node("src:site/source.zip")
    for index in range(3):
        node.write_bytes(f"save {index}".encode())

    versions = node.versions
    contents = [
        manager.node("src:site/source.zip", version=v["version_id"]).read_bytes() for v in versions
    ]
    node.write_bytes(contents[0])

    assert versioning_status(config["bucket"]) == "Enabled"
    assert contents == [b"save 0", b"save 1", b"save 2"]
    assert [v["is_latest"] for v in versions] == [False, False, True]
    assert node.version_count == 4
    assert node.read_bytes() == b"save 0"


def test_a_bucket_without_versioning_is_detected():
    assert versioning_status(release_bucket()["bucket"]) is None
