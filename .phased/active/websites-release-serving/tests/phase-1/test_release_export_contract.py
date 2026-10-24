"""Plan-owned behavior contracts; implement only the copied test bodies."""

import pytest


def test_export_follows_activation_and_rollback():
    # wf:contract: After a committed activation or rollback the installation writes the release
    # wf:contract: files, then the manifest, then the active pointer to the configured mount.
    # wf:contract: The pointer names site, channel, build, manifest digest and catalog channel
    # wf:contract: generation, and matches the catalog after each step.
    pytest.fail("phase 1 pending")


def test_exported_release_is_byte_identical_and_immutable():
    # wf:contract: Every exported file equals the catalog artifact and its manifest digest.
    # wf:contract: Re-export never rewrites an immutable file; only the pointer is rewritten.
    # wf:contract: Drafts, previews and credentials never appear in release storage.
    pytest.fail("phase 1 pending")


def test_pointer_replacement_is_never_observed_partially():
    # wf:contract: A concurrent reader of the configured backend observes either the old or the
    # wf:contract: new complete pointer during replacement.
    # wf:contract: A backend failing exclusive create, read-back digest or this check is refused
    # wf:contract: at startup with a clear error.
    pytest.fail("phase 1 pending")


def test_export_failure_keeps_activation_and_is_retriable():
    # wf:contract: An export failure leaves the catalog activation committed and reports the
    # wf:contract: export as pending on channel reads.
    # wf:contract: The release_export operation, through REST and MCP with current grants,
    # wf:contract: completes it idempotently.
    pytest.fail("phase 1 pending")
