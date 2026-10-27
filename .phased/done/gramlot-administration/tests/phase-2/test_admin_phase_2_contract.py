"""Plan-owned behavior contracts; implement only the copied test bodies."""

import pytest


def test_template_data_lists_site_pages_for_navigation():
    # wf:contract: Both template engines receive the site's pages in Data with path, title and
    # wf:contract: language, in a deterministic order, from the same catalog generation.
    # wf:contract: A build takes the list from the candidate route map; a saved-page render takes
    # wf:contract: it from saved routes. Templates that ignore the list render unchanged and
    # wf:contract: existing releases stay verifiable.
    pytest.fail("phase 2 pending")


def test_pages_workspace_creates_pages_and_edits_routes():
    # wf:contract: The Pages workspace lists the selected site's content identities with their
    # wf:contract: language variants and creates a page with content, variant and exact template.
    # wf:contract: Route path, title and description are saved through the existing route
    # wf:contract: operation; collisions and invalid paths are refused with the service error.
    # wf:contract: Every new operation is available through REST and MCP with the same grants.
    pytest.fail("phase 2 pending")


def test_conflicting_save_is_refused_and_keeps_the_local_buffer():
    # wf:contract: A save against a stale record generation is refused with a conflict; the UI
    # wf:contract: reports it, keeps the whole local buffer dirty and never overwrites the newer
    # wf:contract: revision.
    pytest.fail("phase 2 pending")


def test_png_resource_upload_is_usable_by_templates():
    # wf:contract: A PNG uploaded through the UI becomes a site or library resource revision with
    # wf:contract: its original bytes; a template that declares it receives its exact URL in Data.
    # wf:contract: Payloads that fail the existing bounded PNG verification are refused before
    # wf:contract: they enter a build.
    pytest.fail("phase 2 pending")


def test_editor_views_share_source_and_enable_filtered_markdown_html():
    # wf:contract: Rich, Code and Quick preview use one canonical Data string; opening and
    # wf:contract: switching views without edits preserve the exact original source.
    # wf:contract: Markdown quick preview enables embedded HTML, filters executable content and
    # wf:contract: remains isolated without changing source or undo history merely by toggling
    # wf:contract: preview.
    pytest.fail("phase 2 pending")


def test_rich_edits_preserve_opaque_blocks_and_support_history():
    # wf:contract: Real browser input reaches Data through Jodit, ProseMirror and CodeMirror;
    # wf:contract: supported rich syntax may normalize only after an edit.
    # wf:contract: Unsupported Markdown blocks retain their source, initial undo restores the
    # wf:contract: original string, and independent documents do not share undo history.
    pytest.fail("phase 2 pending")


def test_editor_disposal_readonly_and_late_startup_are_safe():
    # wf:contract: Readonly and disabled editors reject user changes while accepting authorized
    # wf:contract: external Data replacement.
    # wf:contract: Switching or closing documents and disposing during lazy startup leaves no late
    # wf:contract: writes or live detached editor instance.
    pytest.fail("phase 2 pending")


def test_explicit_save_protects_dirty_buffers_and_inflight_typing():
    # wf:contract: No inactivity timer writes a revision; explicit Save writes the submitted
    # wf:contract: snapshot and dirty navigation requires an explicit decision.
    # wf:contract: Typing after submission remains dirty when that save succeeds; rejected or
    # wf:contract: uncertain saves preserve the entire current local buffer.
    pytest.fail("phase 2 pending")


def test_save_retry_is_idempotent_and_does_not_duplicate_revisions():
    # wf:contract: Retrying the same uncertain submitted snapshot with its original key returns one
    # wf:contract: durable outcome and creates at most one revision.
    # wf:contract: A changed snapshot is not submitted using an old uncertain operation key or an
    # wf:contract: unconfirmed generation.
    pytest.fail("phase 2 pending")


def test_named_block_contract_and_template_changes_are_explicit():
    # wf:contract: The editor derives block names, formats and required flags from the exact
    # wf:contract: referenced template revision.
    # wf:contract: An incomplete required block can be saved but fails readiness/build; template
    # wf:contract: changes never silently convert formats or discard unmatched source.
    pytest.fail("phase 2 pending")


def test_source_resources_copy_and_data_inspection_preserve_references():
    # wf:contract: Template engine selection, Python/CSS/JavaScript sources and exact resource
    # wf:contract: dependencies survive edit/save/reload and library-to-site copying with
    # wf:contract: provenance.
    # wf:contract: Data inspection does not create a second editable copy of derived values and
    # wf:contract: identifies their source records.
    pytest.fail("phase 2 pending")


def test_quick_preview_does_not_claim_build_equivalence():
    # wf:contract: The UI labels quick editor preview separately from build preview and surfaces
    # wf:contract: preparation diagnostics without rewriting the source.
    # wf:contract: A fixture whose quick preview and static sanitization differ demonstrates that
    # wf:contract: publication follows the qualified build output.
    pytest.fail("phase 2 pending")
