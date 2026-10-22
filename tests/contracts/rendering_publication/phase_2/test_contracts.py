"""Executable plan contracts across the real catalog, workers and transports."""

import asyncio

from publication.scenarios import (
    frozen_contract,
    grant_contract,
    invalid_outputs_contract,
    route_contract,
)
from publication.test_gateway import preview_scenario
from publication.test_jobs import test_complete_build_and_integrity as complete_build
from publication.test_recovery import test_real_process_interruption_retry_and_fence as recovery


def test_routes_and_seo_share_a_versioned_language_map(tmp_path):
    # wf:contract: Versioned per-variant paths are independent of IDs, prefixed for every language and canonicalized consistently.
    # wf:contract: Reject normalized collisions, traversal, ambiguous encoding and reserved paths before build sealing.
    # wf:contract: Root redirect, canonical, reciprocal alternate links and sitemap use one frozen map with only selected variants and a valid primary landing page.
    route_contract(tmp_path)


def test_candidate_freezes_revisions_and_carried_publication_choices(tmp_path):
    # wf:contract: Create a candidate from one pinned catalog snapshot with exact settings, routes, variants, profiles and resource closure.
    # wf:contract: Later source or settings edits do not alter it; carrying forward languages uses a specified release, never their current draft heads.
    # wf:contract: Record the base release/channel generation so a future activation can detect an intervening publication.
    frozen_contract(tmp_path)


def test_only_complete_verified_artifact_sets_are_sealed(tmp_path):
    # wf:contract: Missing dependencies, cycles, cross-site refs, unresolved internal targets, invalid output paths and unsupported inline media fail the build.
    # wf:contract: An artifact manifest becomes complete only after every output byte set and reference is verified, including size, digest and serving type.
    # wf:contract: Failure or partial output is inspectable but cannot be advertised as a ready release or public artifact.
    invalid_outputs_contract(tmp_path / "invalid")
    complete_build(tmp_path / "complete")


def test_build_recovery_and_attempt_fencing_preserve_frozen_inputs(tmp_path):
    # wf:contract: Persist build intent and state; a real process interruption and reopen distinguish incomplete work from a completed sealed result.
    # wf:contract: Retry uses the same frozen candidate, and stale or duplicate attempt completion cannot overwrite the accepted result.
    # wf:contract: Worker shutdown and timeout do not allow writes after coordinator closure or a second owner; no build failure activates a release.
    recovery(tmp_path)


def test_preview_grant_opens_only_its_exact_release_context(tmp_path):
    # wf:contract: An authorized creator issues a temporary link usable without administration credentials for exactly one candidate/build.
    # wf:contract: All preview navigation and assets stay inside the authorized context; another site, candidate or ungranted object remains inaccessible.
    # wf:contract: Preview origin is separately configured from administration/public origins, with canonical metadata for the intended public target.
    asyncio.run(grant_contract(tmp_path))


def test_preview_expiry_and_revocation_cover_every_request_after_restart(
    tmp_path,
):
    # wf:contract: Expired or explicitly revoked grants deny both page and asset GET/HEAD requests, including with previously established browser access.
    # wf:contract: Revocation and grant scope survive restart; cached HTML, asset URLs or guessed hashes cannot bypass access checks.
    asyncio.run(grant_contract(tmp_path / "expiry"))
    asyncio.run(preview_scenario(tmp_path / "revocation"))


def test_preview_responses_do_not_expose_secrets_or_management_authority(
    tmp_path,
):
    # wf:contract: Preview pages and assets use no-store/noindex and restrictive referrer handling; grant secrets are absent from artifacts and recorded diagnostics.
    # wf:contract: Preview access cannot invoke management or publish operations and does not send administration credentials to the preview origin.
    # wf:contract: Unknown or forged host bindings and public-origin requests cannot obtain unpublished preview artifacts.
    asyncio.run(grant_contract(tmp_path / "secrets"))
    asyncio.run(preview_scenario(tmp_path / "hosts"))


def test_build_and_preview_management_share_authorized_rest_mcp_services(
    tmp_path,
):
    # wf:contract: Actual authenticated REST and MCP expose equivalent candidate, job/status and preview-grant results and structured errors.
    # wf:contract: Build and preview-grant permissions are explicit; read/write/use alone do not silently authorize those actions.
    # wf:contract: Idempotent retries do not duplicate builds or widen preview grants, and job/artifact records do not leak through ordinary editorial listings.
    asyncio.run(preview_scenario(tmp_path))
