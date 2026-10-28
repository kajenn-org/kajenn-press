"""Site sources as versioned zips on S3 (N3 Phase 2)."""

import io
import zipfile

import pytest
from publication.storage_support import release_bucket, versioned_bucket
from site_support import template_source

from kajenn_press.catalog.errors import IntegrityError
from kajenn_press.domain import DomainError
from kajenn_press.site.model import Site
from kajenn_press.site.storage import WorkingCopy
from kajenn_press.site.store import SourceStore, pack, unpack


def sample_site():
    site = Site.create("Kajenn Press")
    template = site.add_template("Landing", "gramlot", template_source("hero", "body"))
    page = site.add_page("Home", template)
    site.assign_content(page, "hero", site.add_content("Hero", "html", "<p>Hello</p>"))
    site.add_page_asset(page, site.add_asset("logo", "media", b"\x89PNG\x00\xff", "image/png"))
    return site


def tytx(site):
    return site.bag.to_tytx(transport="json")


def test_pack_is_deterministic_and_unpack_restores_the_site():
    site = sample_site()
    assert pack(site) == pack(site)
    assert tytx(unpack(pack(site))) == tytx(site)


@pytest.mark.parametrize(
    "raw",
    [
        b"not a zip",
        b"",
    ],
)
def test_unreadable_zip_fails_closed(raw):
    with pytest.raises(IntegrityError):
        unpack(raw)


def test_a_zip_with_other_entries_fails_closed():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("site.json", "{}")
        archive.writestr("extra.txt", "x")
    with pytest.raises(IntegrityError, match="exactly one"):
        unpack(stream.getvalue())


def test_three_saves_give_three_versions_and_restore_adds_a_fourth():
    store = SourceStore(versioned_bucket())
    site = sample_site()
    saved = []
    for title in ("v1", "v2", "v3"):
        site.bag.get_node("info").attr["name"] = title
        saved.append(store.save(site))

    versions = store.versions(site.site_id)
    assert [v["version_id"] for v in versions] == saved
    assert [store.open(site.site_id, v).name for v in saved] == ["v1", "v2", "v3"]

    restored = store.restore(site.site_id, saved[0])

    assert store.open(site.site_id).name == "v1"
    assert [v["version_id"] for v in store.versions(site.site_id)] == [*saved, restored]
    assert store.versions(site.site_id)[-1]["is_latest"] is True


def test_working_copy_is_filled_from_and_saved_to_the_store(tmp_path):
    store = SourceStore(versioned_bucket())
    site = sample_site()
    store.save(site)
    copy = WorkingCopy(tmp_path / "w")

    store.load_into(site.site_id, copy)
    edited = copy.load()
    edited.add_content("Later", "html", "<p>later</p>")
    copy.save(edited)
    store.save_from(copy)

    assert len(store.versions(site.site_id)) == 2
    assert tytx(store.open(site.site_id)) == tytx(edited)


def test_a_corrupted_object_fails_closed():
    config = versioned_bucket()
    store = SourceStore(config)
    site = sample_site()
    store.save(site)
    store.node(site.site_id).write_bytes(b"corrupted")
    with pytest.raises(IntegrityError):
        store.open(site.site_id)


def test_an_unversioned_bucket_is_refused():
    with pytest.raises(DomainError, match="versioning is not enabled"):
        SourceStore(release_bucket())


def test_a_local_mount_is_refused(tmp_path):
    with pytest.raises(DomainError, match="S3 bucket"):
        SourceStore({"protocol": "local", "base_path": str(tmp_path)})


def test_a_missing_site_is_not_found():
    store = SourceStore(versioned_bucket())
    with pytest.raises(DomainError, match="No source"):
        store.versions("0" * 32)
