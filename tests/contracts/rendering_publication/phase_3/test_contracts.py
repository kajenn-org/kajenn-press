"""Executable contracts: real activation, serving, recovery and installed application."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from publication.test_activation_recovery import (
    test_activation_process_crashes_and_idempotent_reopen as crash_recovery,
)
from publication.test_public_serving import serving_scenario
from publication.test_release_api import full_api_cycle
from publication.test_releases import (
    test_atomic_activation_race_and_stale_base as activation_race,
)
from publication.test_releases import (
    test_language_update_rollback_restart_and_policy as rollback_cycle,
)
from publication.test_releases import (
    test_rollback_compatibility_and_unselected_languages as compatibility,
)


def test_activation_is_one_conditional_catalog_transition(tmp_path):
    # wf:contract: Competing publishers using the same channel generation cannot both win; the losing publication changes no active pointer or receipt.
    # wf:contract: Activation commits the release pointer, activation record, receipt and audit/event references together.
    # wf:contract: A candidate derived from a stale active release cannot silently discard an intervening publication.
    activation_race(tmp_path)


def test_public_response_pins_one_release_and_its_assets(tmp_path):
    # wf:contract: An activation during request processing cannot mix the chosen page, route metadata or artifact bytes from different releases.
    # wf:contract: HTML references immutable release-qualified assets that remain valid after another release activates, subject to explicit retained-public eligibility.
    # wf:contract: Public responses implement GET/HEAD, correct MIME/status and no-sniff, with authoritative HTML pointer resolution rather than stale shared caching.
    asyncio.run(serving_scenario(tmp_path))


def test_publishing_one_language_preserves_other_published_revisions(tmp_path):
    # wf:contract: Publish a selected language update while preserving exact previously published revisions of other languages.
    # wf:contract: Newer unfinished drafts and never-published languages stay excluded; canonical/alternate/sitemap reflect only the resulting release selection.
    # wf:contract: The root redirect cannot target an unselected primary-language landing page.
    compatibility(tmp_path)


def test_rollback_reactivates_a_complete_release_without_rendering(tmp_path):
    # wf:contract: Rollback conditionally activates a retained complete compatible release and records a new activation without deleting later history.
    # wf:contract: No renderer is invoked and exact prior pages, routes and assets are restored after restart.
    # wf:contract: Stale generation, wrong site/channel or incompatible destination produces a structured failure without pointer changes.
    rollback_cycle(tmp_path / "rollback")
    compatibility(tmp_path / "compatibility")


def test_activation_rechecks_current_grants_and_review_policy(tmp_path):
    # wf:contract: Revoke publish or required resource-use permission after building; activation must fail under the coordinator with no partial transition.
    # wf:contract: A site configured to require review cannot activate without the supported revision-bound approval flow, which this macro does not implement.
    # wf:contract: An authorized publisher can activate directly when review is disabled; REST and MCP enforce the same policy for human and LLM clients.
    asyncio.run(full_api_cycle(tmp_path))


def test_public_gateway_rejects_private_and_ambiguous_requests(tmp_path):
    # wf:contract: Unpublished candidates, drafts and ungranted previews cannot be fetched through public paths, hashes or alternate host headers.
    # wf:contract: Host/path resolution cannot route public aliases to administration; traversal and ambiguous encodings fail before object access.
    # wf:contract: Unknown public routes return 404, and only manifest-authorized assets of eligible published releases are served.
    asyncio.run(serving_scenario(tmp_path))


def test_activation_crash_recovery_and_retry_have_one_observable_result(tmp_path):
    # wf:contract: Force process interruption around activation publication boundaries, reopen and observe either the complete old release or the complete new release.
    # wf:contract: When the new pointer is visible its receipt/audit/event state is committed too; same-key retry returns the original outcome without duplicate activation.
    # wf:contract: Different input with the same key conflicts, and a revoked actor cannot use retries to regain authority.
    crash_recovery(tmp_path)


def test_installed_full_cycle_preserves_static_content_and_backend_contracts(
    tmp_path,
):
    # wf:contract: Run the installed application through build, private preview, activation, language-only update and whole-release rollback on real local storage.
    # wf:contract: Exercise actual REST/MCP and HTTP/browser consumers, with essential public text and SEO correct when browser JavaScript is disabled.
    # wf:contract: Preserve IDs, exact history, source bytes and storage refs through restart without Asqueel, SQL or an external database; earlier contracts stay green.
    python = os.environ.get("KAJENN_APP_PYTHON", sys.executable)
    tests = Path(__file__).resolve().parents[3]
    code = """import asyncio, importlib.util, sys
from pathlib import Path
import kajenn_public_site
assert 'site-packages' in kajenn_public_site.__file__, 'Use KAJENN_APP_PYTHON with a noneditable installation'
assert all(importlib.util.find_spec(name) is None for name in ('gramlot','markdown_it','nh3','sqlalchemy','asqueel'))
sys.path.insert(0, sys.argv[1])
from publication.test_release_api import full_api_cycle
asyncio.run(full_api_cycle(Path(sys.argv[2])))
print('Installed full REST/MCP/HTTP cycle: OK; no renderer or SQL dependencies in parent')
"""
    result = subprocess.run(
        [python, "-I", "-c", code, str(tests), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Installed full REST/MCP/HTTP cycle: OK" in result.stdout
