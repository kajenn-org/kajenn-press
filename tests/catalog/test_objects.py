from dataclasses import asdict

import pytest

from kajenn_press.catalog.errors import IntegrityError, UnsupportedProfile
from kajenn_press.objects import ObjectRef, ObjectStore


def test_public_storage_preserves_bytes_and_rejects_overwrite(tmp_path):
    store = ObjectStore(tmp_path / "payloads")
    data = b"\x00<html> exact\r\n\xff"
    ref = ObjectRef(**store.reference(data))
    store.prepare(ref, data)
    assert store.read(asdict(ref)) == data
    with pytest.raises(FileExistsError):
        store.prepare(ref, data)


def test_object_containment_and_corruption(tmp_path):
    store = ObjectStore(tmp_path / "payloads")
    ref = ObjectRef(**store.reference(b"source"))
    with pytest.raises(IntegrityError):
        ObjectRef("../escape", ref.sha256, ref.size)
    outside = tmp_path / "outside"
    outside.write_bytes(b"source")
    link = store.root / (ref.key + ".blob")
    link.symlink_to(outside)
    with pytest.raises(IntegrityError):
        store.read(ref)
    with pytest.raises(IntegrityError):
        store.prepare(ref, b"source")
    assert outside.read_bytes() == b"source"
    link.unlink()
    store.prepare(ref, b"source")
    link.write_bytes(b"broken")
    with pytest.raises(IntegrityError, match="checksum"):
        store.read(ref)


def test_unsupported_flush_fails_closed(tmp_path, monkeypatch):
    def unavailable(stream):
        raise OSError("no durable primitive")

    monkeypatch.setattr("kajenn_press.objects.sync_file", unavailable)
    with pytest.raises(UnsupportedProfile, match="durable flush"):
        ObjectStore(tmp_path)
