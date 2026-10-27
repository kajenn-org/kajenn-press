"""Plan-owned behavior contracts; implement only the copied test bodies."""

import pytest


def test_child_registry_uses_catalog_rules_and_shared_transports():
    # wf:contract: Registry records for children are created, updated, read and listed through
    # wf:contract: UI, REST and MCP with the same grants, generations, receipts and audit as other
    # wf:contract: catalog records.
    pytest.fail("phase 3 pending")


def test_deployment_view_reads_back_storage_and_shows_mismatches():
    # wf:contract: The deployment view shows for each child its bound site, the active catalog
    # wf:contract: release, the exported release and the release read back from storage.
    # wf:contract: A mismatch is shown, never corrected silently; re-export resolves it.
    pytest.fail("phase 3 pending")
