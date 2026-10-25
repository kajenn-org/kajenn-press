# Phase 3 — websites registry and Deployments view

## Delivered

- `src/kajenn_public_site/publication/deployments.py`: registry records `deployment_child`; operations `child_save`, `child_read`, `child_list`, `child_channels`; `deployment()` puts the catalog release beside the pointer read back from storage, with a state.
- `src/kajenn_public_site/publication/service.py`: operation sets, authorization (publish to save, read to read; list filtered per site).
- `src/kajenn_public_site/application.py`: REST and MCP routes for the four operations.
- `src/kajenn_public_site/admin/pages/deployments.py`, `index.py` (tree node and tab), `host.py` (registry reads allowed), `index.css` (table, badges, comparison).

## Verification

- Phase contracts copied verbatim to `tests/admin/test_websites_registry_contract.py`: 2 passed in the admin environment (UI register, REST and MCP update/read/list, idempotent retry, stale-generation conflict, writer denied to save but allowed to list, outsider sees nothing, receipts with audit IDs; view shows Up to date, a tampered pointer shows "Storage differs from catalog" without being corrected, re-export resolves it).
- Real browser, kajenn.org catalog, RustFS bucket `kajenn-org-releases`, viewport 1400x900:
  - Registered `kajenn-org` from the form: state "Not in storage" (release `d0eb6f5a` activated before storage existed). Screenshot `mockups/phase-3-not-in-storage.jpg`.
  - Re-export: "Up to date", catalog and storage `d0eb6f5a` generation 3. Screenshot `mockups/phase-3-up-to-date.jpg`.
  - Pointer rewritten in storage to build `94c3ae65` generation 2: "Storage differs from catalog", detail note shown. Screenshots `mockups/phase-3-mismatch.jpg`, `mockups/phase-3-mismatch-detail.jpg`.
  - "Re-export to storage": back to "Up to date". Screenshot `mockups/phase-3-resolved.jpg`.
- Compared with the approved mockup: same tree node, table columns, badges, side-by-side comparison, note, Re-export and Register form. The register form takes no public origin input: it comes from the chosen channel.
- After the qualification fix: full base suite 109 passed, 4 skipped (186 s); admin suite in `kajenn-org-site-data/admin-env` 13 passed, 1 failed — the known Gramlot 0.3.9 wheel hash check (qualified prerelease lost from /tmp, recorded in Phase 1 `> Review:`).
- `ruff check src tests examples`: passed.
