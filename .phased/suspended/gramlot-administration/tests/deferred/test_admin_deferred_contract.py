"""Contracts moved out of the gramlot-administration plan on 2026-10-23, kept verbatim for a later plan."""

import pytest


def test_conflict_resolution_preserves_base_local_and_current():
    # wf:contract: Concurrent saves expose base, unsaved local and current server versions without
    # wf:contract: overwriting or discarding any of them.
    # wf:contract: An explicitly resolved result saves conditionally against the newly read
    # wf:contract: generation and can itself report a new conflict.
    pytest.fail("phase 2 pending")


def test_revision_comparison_restore_and_local_comparison_use_shared_rules():
    # wf:contract: History and comparison show exact revisions; restore creates a new conditional
    # wf:contract: revision instead of rewriting history.
    # wf:contract: Any new application comparison needed for unsaved-local conflict handling is
    # wf:contract: authorized and exposed consistently through UI, REST and MCP.
    pytest.fail("phase 2 pending")


def test_variant_media_and_source_commit_atomically():
    # wf:contract: A variant saves named-block source and exact media revision references
    # wf:contract: atomically; a refused reference leaves no partial update.
    # wf:contract: Existing variants without media references remain readable and renderable;
    # wf:contract: site/library use permissions and revision scopes are checked.
    pytest.fail("phase 2 pending")


def test_media_picker_inserts_revision_reference_without_private_engines():
    # wf:contract: The catalog picker inserts an explicit image fragment and usage alt text at the
    # wf:contract: end of the selected named block in the canonical Data draft.
    # wf:contract: Insertion remains unsaved until Save, can be reverted, and does not use a
    # wf:contract: private editor engine or embed an uploaded image as a base64 HTML payload.
    pytest.fail("phase 2 pending")


def test_image_verification_preserves_valid_png_jpeg_webp_bytes():
    # wf:contract: The qualified image verifier recognizes actual PNG, JPEG and WebP data, checks
    # wf:contract: declared MIME, decoding completeness and bounded image/frame resources, and
    # wf:contract: rejects malformed, truncated, mismatched or unsupported payloads.
    # wf:contract: Accepted original bytes are preserved in stored sources and published artifacts;
    # wf:contract: unavailable WebP decoding is a qualification failure rather than silent
    # wf:contract: acceptance.
    pytest.fail("phase 2 pending")


def test_variant_media_closure_is_complete_and_old_releases_still_work():
    # wf:contract: Both renderers include the exact authorized per-variant media revisions in
    # wf:contract: candidate closure, artifact manifests and public serving with verified MIME
    # wf:contract: types.
    # wf:contract: Missing or undeclared media references fail clearly; existing PNG releases
    # wf:contract: remain verifiable and rollback-compatible.
    pytest.fail("phase 2 pending")
