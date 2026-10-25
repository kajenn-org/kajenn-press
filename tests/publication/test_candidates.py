import pytest
from publication.support import candidate, services, site_fixture

from kajenn_press.domain import DomainError


def test_candidate_snapshot_and_editorial_separation(tmp_path):
    editorial, publication = services(tmp_path)
    try:
        fixture = site_fixture(editorial, publication)
        created = candidate(publication, fixture)
        assert candidate(publication, fixture) == created
        info = publication.execute("admin", "candidate_read", candidate_id=created["record_id"])
        assert {e["route"]["path"] for e in info["selection"].values()} == {"/it/", "/en/about/"}
        listed = editorial.execute(
            "admin", "records_list", scope="site:" + fixture["site"]["record_id"]
        )
        assert all(not row["kind"].startswith("publication_") for row in listed)
        for op in ("record_read", "revision_history"):
            with pytest.raises(DomainError, match="not found"):
                editorial.execute("admin", op, record_id=created["record_id"])
    finally:
        publication.close()
        editorial.catalog.close()
