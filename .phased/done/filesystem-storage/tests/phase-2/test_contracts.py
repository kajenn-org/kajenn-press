"""Plan-time contract skeletons; intentionally pending implementation."""

import pytest


def test_rest_and_mcp_share_domain_results():
    # wf:contract: Execute creation, draft save, exact revision read and conflicting save through both REST and MCP.
    # wf:contract: Both channels enforce the same application rules and expose equivalent IDs, generations and error codes.
    pytest.fail("phase-2 pending")

def test_authorization_is_shared_and_scoped():
    # wf:contract: A caller without the required site or generic-library grant cannot read or modify protected records through REST or MCP.
    # wf:contract: Payload role declarations cannot grant authority.
    pytest.fail("phase-2 pending")

def test_named_blocks_preserve_format_and_source():
    # wf:contract: A template declares named HTML and Markdown blocks and their required status.
    # wf:contract: Saving and reopening a draft preserves names, source formats and exact source text without converting the canonical source.
    pytest.fail("phase-2 pending")

def test_incomplete_draft_can_be_saved():
    # wf:contract: A draft missing a required template block can be saved and reopened.
    # wf:contract: Publication-readiness validation reports the missing block by name; an empty optional block is not a blocking error.
    pytest.fail("phase-2 pending")

def test_shared_draft_conflict_preserves_history():
    # wf:contract: Each content and language has one shared draft.
    # wf:contract: A stale edit is rejected without altering the accepted head or losing its preceding immutable revisions.
    pytest.fail("phase-2 pending")

def test_generic_resource_copy_is_independent():
    # wf:contract: Copying a selected generic resource revision into a site creates a new resource identity and revision history.
    # wf:contract: Subsequent changes to either resource do not alter the other; exact dependency references and provenance are retained.
    pytest.fail("phase-2 pending")

def test_languages_have_independent_draft_heads():
    # wf:contract: Saving one language variant does not modify another language draft head or its revisions.
    # wf:contract: Translation provenance does not create an implicit requirement to save other variants together.
    pytest.fail("phase-2 pending")

def test_filesystem_backend_has_no_asqueel_dependency():
    # wf:contract: The application starts and completes the site, draft, source and resource-copy scenarios without Asqueel or a PostgreSQL driver installed.
    # wf:contract: Restart preserves IDs, revisions, generations and storage references required by later rendering and a future catalog migration.
    pytest.fail("phase-2 pending")

def test_clients_can_discover_templates_and_read_sources():
    # wf:contract: REST and MCP expose template block declarations and exact readable source revisions for authorized clients.
    # wf:contract: Validation errors identify the relevant resource and block so an LLM can correct the input without browser automation.
    pytest.fail("phase-2 pending")
