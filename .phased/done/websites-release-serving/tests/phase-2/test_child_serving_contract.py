"""Plan-owned behavior contracts; implement only the copied test bodies."""

import pytest


def test_child_serves_the_active_release_without_catalog_or_renderers():
    # wf:contract: The child serves the release named by the storage pointer for its configured
    # wf:contract: host and imports neither the catalog, Gramlot nor the render worker.
    # wf:contract: It serves only files listed in a manifest whose digest it validated.
    pytest.fail("phase 2 pending")


def test_child_responses_match_in_process_public_serving():
    # wf:contract: For every route, asset, sitemap, root redirect and a missing path, the child
    # wf:contract: returns the same body, status code and public headers as in-process serving
    # wf:contract: of the same release.
    pytest.fail("phase 2 pending")


def test_child_follows_activation_and_rollback_within_cache_interval():
    # wf:contract: A new activation or a rollback becomes visible in the child within the
    # wf:contract: configured cache interval.
    # wf:contract: A missing or invalid pointer or manifest yields 503 unless a validated release
    # wf:contract: is already loaded, which keeps being served.
    pytest.fail("phase 2 pending")
