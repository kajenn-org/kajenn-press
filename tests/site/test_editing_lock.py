"""One editor at a time per site (N3 Phase 3)."""

import pytest
from publication.storage_support import versioned_bucket
from site_support import template_source

from kajenn_press.domain import DomainError
from kajenn_press.site.lock import EditingLock
from kajenn_press.site.model import Site
from kajenn_press.site.store import SourceStore

SITE = "a" * 32


class Clock:
    """Explicit time for expiry checks."""

    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def lock(tmp_path, clock):
    return EditingLock(tmp_path / "locks", expiry=1800, clock=clock)


def test_a_second_identity_cannot_take_or_act(tmp_path):
    editing = lock(tmp_path, Clock())
    assert editing.take(SITE, "anna") == {"holder": "anna", "taken_from": None}

    with pytest.raises(DomainError, match="edited by anna"):
        editing.take(SITE, "bruno")
    with pytest.raises(DomainError, match="edited by anna"):
        editing.require(SITE, "bruno")
    editing.require(SITE, "anna")


def test_acting_before_taking_is_refused(tmp_path):
    with pytest.raises(DomainError, match="Take the site"):
        lock(tmp_path, Clock()).require(SITE, "anna")


def test_inactivity_frees_the_site_and_activity_keeps_it(tmp_path):
    clock = Clock()
    editing = lock(tmp_path, clock)
    editing.take(SITE, "anna")
    clock.advance(1700)
    editing.require(SITE, "anna")
    clock.advance(1700)
    assert editing.holder(SITE) == "anna"
    clock.advance(200)

    assert editing.holder(SITE) is None
    assert editing.take(SITE, "bruno") == {"holder": "bruno", "taken_from": None}


def test_explicit_take_is_recorded_and_the_previous_holder_is_told(tmp_path):
    clock = Clock()
    editing = lock(tmp_path, clock)
    editing.take(SITE, "anna")
    clock.advance(60)

    assert editing.take(SITE, "bruno", force=True) == {"holder": "bruno", "taken_from": "anna"}
    with pytest.raises(DomainError) as refused:
        editing.require(SITE, "anna")

    assert refused.value.details == {"holder": "bruno", "taken_from_you_at": clock.now}


def test_release_frees_the_site_and_the_lock_survives_a_restart(tmp_path):
    clock = Clock()
    lock(tmp_path, clock).take(SITE, "anna")
    assert lock(tmp_path, clock).holder(SITE) == "anna"
    lock(tmp_path, clock).release(SITE, "bruno")
    assert lock(tmp_path, clock).holder(SITE) == "anna"
    lock(tmp_path, clock).release(SITE, "anna")
    assert lock(tmp_path, clock).holder(SITE) is None


def test_only_the_holder_saves_the_source(tmp_path):
    clock = Clock()
    editing = lock(tmp_path, clock)
    store = SourceStore(versioned_bucket())
    site = Site.create("S")
    site.add_template("T", "gramlot", template_source("body"))

    def save(identity):
        editing.require(site.site_id, identity)
        return store.save(site)

    editing.take(site.site_id, "anna")
    save("anna")
    editing.take(site.site_id, "bruno", force=True)
    with pytest.raises(DomainError):
        save("anna")
    save("bruno")
    assert len(store.versions(site.site_id)) == 2
