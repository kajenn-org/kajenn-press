"""Receipts of site mutations and the audit log (N3 Phase 4)."""

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import DomainError
from kajenn_press.site.model import Site
from kajenn_press.site.receipts import Receipts
from kajenn_press.site.store import SourceStore, pack, unpack


class Clock:
    def __init__(self):
        self.now = 2_000_000.0

    def __call__(self):
        return self.now


def test_a_retried_mutation_applies_once(tmp_path):
    receipts = Receipts(tmp_path / "r", clock=Clock())
    site = Site.create("S")

    def add():
        return site.add_content("Note", "html", "<p>x</p>")

    first = receipts.run("anna", "k1", "content_add", {"name": "Note"}, add)
    again = receipts.run("anna", "k1", "content_add", {"name": "Note"}, add)

    assert first == again
    assert len(site.section("contents")) == 1


def test_a_key_reused_with_other_input_is_a_conflict(tmp_path):
    receipts = Receipts(tmp_path / "r", clock=Clock())
    receipts.run("anna", "k1", "content_add", {"name": "A"}, lambda: "id-a")
    with pytest.raises(DomainError, match="different input"):
        receipts.run("anna", "k1", "content_add", {"name": "B"}, lambda: "id-b")


def test_keys_are_per_identity(tmp_path):
    receipts = Receipts(tmp_path / "r", clock=Clock())
    assert receipts.run("anna", "k1", "op", {}, lambda: "a") == "a"
    assert receipts.run("bruno", "k1", "op", {}, lambda: "b") == "b"


def test_expired_receipts_are_ignored_and_purged(tmp_path):
    clock = Clock()
    receipts = Receipts(tmp_path / "r", clock=clock)
    calls = []
    receipts.run("anna", "k1", "op", {}, lambda: calls.append(1) or len(calls))
    clock.now += 24 * 60 * 60 + 1

    assert receipts.run("anna", "k2", "op", {}, lambda: "fresh") == "fresh"
    assert receipts.purge() == 1
    assert receipts.run("anna", "k1", "op", {}, lambda: calls.append(1) or len(calls)) == 2


def test_invalid_keys_are_refused(tmp_path):
    receipts = Receipts(tmp_path / "r", clock=Clock())
    for key in ("", None, "x" * 257):
        with pytest.raises(DomainError, match="key"):
            receipts.run("anna", key, "op", {}, lambda: None)


def test_audit_entries_survive_the_zip():
    site = Site.create("S")
    site.record("anna", "save", "2026-10-28T10:00:00+00:00")
    site.record("anna", "content_add", "2026-10-28T10:01:00+00:00", via="help_me", name="Hero")

    entries = [n.attr for n in unpack(pack(site)).audit.nodes]

    assert entries == [
        {"identity": "anna", "operation": "save", "at": "2026-10-28T10:00:00+00:00"},
        {
            "identity": "anna",
            "operation": "content_add",
            "at": "2026-10-28T10:01:00+00:00",
            "name": "Hero",
            "via": "help_me",
        },
    ]


def test_restore_keeps_the_current_audit_log():
    store = SourceStore(versioned_bucket())
    site = Site.create("S")
    site.record("anna", "save", "t1")
    first = store.save(site)
    site.add_content("Later", "html", "<p>later</p>")
    site.record("anna", "save", "t2")
    store.save(site)

    store.restore(site.site_id, first)
    restored = store.open(site.site_id)

    assert len(restored.section("contents")) == 0
    assert [n.attr["at"] for n in restored.audit.nodes] == ["t1", "t2"]
