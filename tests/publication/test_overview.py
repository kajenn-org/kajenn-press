"""publication_overview: one read of a site's channels, routes and builds."""

import pytest
from publication.support import built, candidate, services, site_fixture

from kajenn_press.domain import DomainError


def test_overview_lists_settings_routes_and_builds_of_one_site(tmp_path):
    editorial, publication = services(tmp_path)
    try:
        one = site_fixture(editorial, publication, "one")
        two = site_fixture(editorial, publication, "two")
        status = built(publication, candidate(publication, one))
        overview = publication.execute(
            "admin", "publication_overview", site_id=one["site"]["record_id"]
        )
        (channel,) = overview["channels"]
        assert channel["record_id"] == one["settings"]["record_id"]
        assert channel["generation"] == one["settings"]["generation"]
        assert channel["channel"] == "main" and channel["public_origin"] == "https://one.test"
        assert channel["primary_language"] == "it"
        assert channel["landing_variant"] == one["variants"]["it"]["record_id"]
        assert channel["channel_generation"] == 0 and channel["active_build"] is None
        (build,) = channel["builds"]
        assert build["build_id"] == status["record_id"] and build["state"] == "succeeded"
        english = overview["routes"][one["variants"]["en"]["record_id"]]
        assert english["path"] == "/en/about/" and english["title"] == "en title"
        assert english["record_id"] == one["routes"]["en"]["record_id"]
        # Records of the other site never appear.
        assert two["variants"]["it"]["record_id"] not in overview["routes"]
        publication.policy.grants["admin"]["*"].append("publish")
        publication.execute(
            "admin",
            "release_activate",
            key="activate",
            settings_id=one["settings"]["record_id"],
            build_id=status["record_id"],
            expected_generation=0,
        )
        (channel,) = publication.execute(
            "admin", "publication_overview", site_id=one["site"]["record_id"]
        )["channels"]
        assert channel["channel_generation"] == 1
        assert channel["active_build"] == status["record_id"]
    finally:
        publication.close()
        editorial.catalog.close()


def test_overview_requires_read_on_the_site(tmp_path):
    editorial, publication = services(tmp_path)
    try:
        one = site_fixture(editorial, publication, "one")
        publication.policy.grants["reader"] = {"site:other": ["read"]}
        with pytest.raises(DomainError, match="Missing read"):
            publication.execute("reader", "publication_overview", site_id=one["site"]["record_id"])
        with pytest.raises(DomainError) as missing:
            publication.execute("admin", "publication_overview", site_id="unknown")
        assert missing.value.code == "not_found"
    finally:
        publication.close()
        editorial.catalog.close()
