"""Plan-owned behavior contracts; implement only the copied test bodies."""

import pytest


def test_composition_serves_kajenn_org_from_the_child():
    # wf:contract: From a clean checkout the composition builds kajenn.org in websites through
    # wf:contract: MCP, activates it, and the child serves it on kajenn.localhost.
    pytest.fail("phase 4 pending")


def test_child_container_cannot_write_release_storage():
    # wf:contract: The release volume is read-only in the child container; websites is its only
    # wf:contract: writer, and no credential is committed or written to the volume.
    pytest.fail("phase 4 pending")
