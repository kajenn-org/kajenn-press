# Context: feat/site-source
Parent: main
Mode: manual
Must not break: The existing tests keep passing; the current catalog, publication and administration keep working. N3 adds the site source beside them; nothing is removed until N4–N5 replace it.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-publish-unit, d-editing-lock, d-idempotency, d-audit in particular).
Must not break: Storage credentials never enter a Bag, a zip, a log or the repository. The source store is written only by the manager; children never receive credentials that can read sources.
Must not break: The Hetzner installation is changed only with the owner's go-ahead, and only after versioning is enabled on its bucket by the owner.
Must not break: Real tests against a real versioned S3 endpoint (RustFS in Docker on the Mac); mocks only for network faults.

## Objective

Keep each site's source as one zipped object on S3, versioned by S3, and expose the N2 site model through the common services on REST and MCP. The manager unpacks the source into the local working copy for editing and zips it again on each deliberate save; every save is an S3 version that can be listed and restored. One editor at a time holds a site. Mutations carry idempotency keys with receipts kept 24 hours; a minimal audit log travels in the site Bag. A complete site is exported and imported as one zip; starting sites are kept in the Library.

Entry: `xmldocs/proposal/redesign-inventory.xml` (sections "Catalog and services", "Upstream capabilities"), the N2 library `src/kajenn_press/site/` (main `16d28ee`).

Known facts (2026-10-27):
- genro-storage lists and reads S3 versions (`get_versions`, `open_version`) but has no restore; restoring means reading a version and writing it as the new current object, which S3 records as a new version.
- Versioning is not enabled on the Hetzner bucket `kpress-releases`.
- A RustFS 1.0.3 test container (`kajenn-press-test-rustfs`) runs on the Mac; the S3 tests read its credentials from the JSON file named by `KAJENN_RELEASE_S3` (`tests/publication/storage_support.py:1`). Without that file 11 existing tests fail.
- The RustFS composition creates buckets with `minio/mc`, which is no longer pullable; versioning can be enabled through the S3 API (`PutBucketVersioning`) without `mc`. Not yet tried.

## Owner decisions (2026-10-28)

- **N3-D1 · Where sources live.** (a) A separate bucket, `kpress-sources`, with credentials held only by the manager. (b) A `sources/` prefix in `kpress-releases`. Recommended: (a). Children hold read credentials for the release bucket; with (b) a child key could read sources, unless the provider scopes keys per prefix, which is not verified for Hetzner. Decided: (a).
- **N3-D2 · Zip layout.** (a) One entry, `site.json`, the same envelope as the working copy (TYTX JSON and SHA-256). (b) One entry per template, content and asset. Recommended: (a) now; (b) only if size becomes a problem, since binary assets travel in TYTX. Decided: (a).
- **N3-D3 · Lock storage.** (a) In the manager's local working directory, since one manager edits a site. (b) As an S3 object, for several managers. Recommended: (a). Decided: (a).
- **N3-D4 · Operation names.** Proposed at the Phase 5 gate.

## Decisions shared by all phases

- Each phase ends with its tests green (including the 11 S3 tests once Phase 1 provides the endpoint file), ruff clean on the changed files only (never `ruff format` over untouched files), one commit on `feat/site-source`.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Versioned S3 for development and tests
  > Done: `versioned_bucket` and `versioning_status` in `tests/publication/storage_support.py`; `tests/site/test_s3_versions.py` (2 tests). On RustFS 1.0.3 versioning is enabled through `PutBucketVersioning` (no `minio/mc`); through Genro Storage three writes give three versions, each readable by version id, and writing an old version as current makes it the fourth version. A bucket never versioned reports no `Status`. `deploy/docker/README.md` documents the three interpreters and the endpoint file of the full suite.
  > Suite with `KAJENN_RENDER_PYTHON`, `KAJENN_APP_PYTHON` (non-editable `.[release-s3]`) and `KAJENN_RELEASE_S3` (RustFS on 127.0.0.1:19100): 179 passed, 19 skipped, 0 failed. The 11 earlier failures were only missing environment.
  - Run: opus / high
  - Files: `tests/publication/storage_support.py` (versioned bucket helper), new `tests/site/test_s3_versions.py`, `deploy/docker/README.md` (how to start the test endpoint and write the `KAJENN_RELEASE_S3` file).
  - Details: enable versioning on a fresh RustFS bucket through `PutBucketVersioning`; with genro-storage write an object three times, list its versions, read each one, restore an old one by writing it as current; check that a bucket without versioning is detected by querying `GetBucketVersioning`.
  - Done: the version cycle passes on RustFS; the 11 existing S3 tests pass with the endpoint file; an unversioned bucket is reported.

- [x] **Phase 2**: Site source store
  > Done: `src/kajenn_press/site/store.py` (`pack`, `unpack`, `SourceStore` with `save`, `versions`, `open`, `restore`, `load_into`, `save_from`); `storage.py` now exposes `site_envelope`, `site_from_envelope`, `check_structure`, shared by the working copy and the zip; `tests/site/test_source_store.py` (10 tests). The zip is deterministic (one `site.json` entry, fixed date). The source of a site is `sites/<site id>/source.zip`; each save returns its S3 version id; restore writes an old version as current (a new version). The store accepts only `protocol: s3` and refuses a bucket whose versioning is not `Enabled` (checked with `GetBucketVersioning` through s3fs, since genro-storage does not query it); a corrupted object, a zip with other entries or a source of another site fail closed.
  > Suite: 189 passed, 19 skipped, 0 failed.
  - Run: opus / high
  - Files: new `src/kajenn_press/site/store.py`, `tests/site/`.
  - Details: pack a site into a zip (layout per N3-D2) and unpack it with integrity checks; a store on a Genro Storage S3 mount with one object per site; save writes a new version; list versions with date and size; open a version as a site; restore a version as the new current one; startup refuses a bucket without versioning; the working copy is filled from the store and saved back to it.
  - Done: three saves give three versions; restoring the first makes it current as a fourth version; a corrupted object fails closed; an unversioned bucket is refused.

- [x] **Phase 3**: Editing lock
  > Done: `src/kajenn_press/site/lock.py` (`EditingLock` with `take`, `require`, `release`, `holder`); `tests/site/test_editing_lock.py` (6 tests). One JSON record per site in the manager's directory, written with `publish_json`; expiry 30 minutes of inactivity by default, refreshed by every `require`. `take(force=True)` records `taken_from`; the previous holder's next `require` is refused with the new holder and the time it was taken. Help me acts under the user's identity, so it needs no lock of its own. The clock is a parameter, so expiry is tested with explicit time.
  - Run: opus / high
  - Files: new `src/kajenn_press/site/lock.py`, `tests/site/`.
  - Details: one holder per site (identity, taken at, last activity); expiry after 30 minutes of inactivity (configurable); an explicit take by another identity records the previous holder and warns it; save and every mutation check the holder; Help me acts under the holder's identity (d-editing-lock).
  - Done: a second identity cannot save; expiry frees the site; an explicit take works and is recorded; a stale holder's save is refused.

- [x] **Phase 4**: Receipts and audit
  > Done: `src/kajenn_press/site/receipts.py` (`Receipts.run`, `read`, `purge`); site section `audit` with `Site.audit` and `Site.record` (identity, operation, time, optional `via="help_me"`, details); `SourceStore.restore` keeps the current audit log instead of the restored one; `tests/site/test_receipts_and_audit.py` (7 tests). A receipt per (identity, key) holds the input fingerprint and the JSON result; a repeat returns the result, other input is a conflict, receipts older than 24 hours are ignored and purged.
  > Limit: the receipt is written after the mutation; a crash between the two lets the retry apply again. The site is saved to the store only on deliberate saves, so the window covers working-copy edits.
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `tests/site/`.
  - Details: every mutation carries a key; a repeated key with the same input returns the first result, with different input it is a conflict; receipts are kept 24 hours in the working directory (d-idempotency). The site Bag keeps an audit log of saves, restores, lock takes and Publish (later), with identity, time and operation; actions through Help me are recorded as such (d-audit).
  - Done: a retried mutation does not apply twice; an expired receipt is dropped; the audit log survives zip and restore.

- [x] **Phase 5**: Site operations on REST and MCP
  > Done: `src/kajenn_press/site/service.py` (`SiteService`, 21 operations: controls `site_new`, `site_open`, `site_close`, `site_save`, `site_restore`; reads `site_read`, `site_versions`, `copies_update_plan`, `template_switch_plan`, `page_check`, `page_render`; changes `template_add`, `content_add`, `content_save`, `asset_add`, `page_add`, `page_asset_add`, `slot_assign`, `copies_update`, `template_switch`, `unplaced_place`); 21 routes in `application.py`, `create_server(..., sites=...)` with `root`, `sources`, optional `connections` and `render_python`; `capabilities` lists them when configured, otherwise they answer `unavailable`. Changes need `write` on `site:<id>`, the editing lock and a key; they are recorded in the audit log; `site_new` needs `create_site`; `page_render` needs `build`. The holder reads the working copy, others the latest saved version. Names follow the owner's choice of 2026-10-28: no collision with the existing 44 operations. Tests: `tests/site/test_site_service.py` (7), `tests/api/test_site_operations.py` (2, real REST and MCP transports).
  > Note: `SourceStore` is imported where the site configuration is read, because s3fs belongs to the optional `release-s3` extra and an installation without site sources must start without it (same pattern as the administration import in `create_server`).
  > Suite: 211 passed, 19 skipped, 0 failed (headless interpreter reinstalled).
  - Run: opus / high
  - Files: new `src/kajenn_press/site/service.py`, `src/kajenn_press/application.py`, `tests/api/`, `tests/site/`.
  - Details: a service with the same entry pattern as `EditorialService.execute` (identity, binding, authorization through `AccessPolicy` on `site:<id>` and `library`), wrapping the N2 model, the store, the lock, receipts and audit: create a site, read the site and its trees, templates/contents/assets/pages, slot assignment, Update plan and apply, template switch, page check, render a page, save, versions and restore, lock take and release. The existing 44 operations stay.
  - Owner actions: approve the operation names at the gate.
  - Done: the operations are listed by `capabilities` and on `/mcp`; a full cycle over MCP creates a site, fills two pages, saves, restores and renders.

- [x] **Phase 6**: Export, import and starting sites
  > Done: operations `site_export` (a saved version as one zip in base64), `site_import` (a new site id, same content, the importer holds it), `starter_save` (latest saved version kept in the Library at `library/starters/<id>.zip`), `starters_list`, and `site_new(starter_id=...)`; `Site.reidentify`; `SourceStore.export`, `starter_save`, `starters`, `starter_open`; 4 routes (69 in total); `tests/site/test_export_import.py` (4 tests). Imported and started sites keep the audit log of their origin and add their own entry. `pack`/`unpack` moved from `store.py` to `storage.py`, so the service and the application import without s3fs (checked with s3fs import blocked).
  > Suite: 215 passed, 19 skipped, 0 failed.
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `tests/site/`.
  - Details: export the current source as one zip; import a zip as a new site (new site id, same content); starting sites kept as zips in the Library; a new site from a starting site.
  - Done: export then import gives a site with the same pages, contents and templates; a new site starts from a starting site.

- [ ] **Phase 7**: Deployment configuration
  - Run: opus / high
  - Files: `deploy/docker/compose.yaml`, `deploy/docker/compose.external-s3.yaml`, `deploy/docker/websites.py`, `deploy/docker/HETZNER.md`, `tests/docker/`.
  - Details: the manager receives the source store configuration (bucket per N3-D1, credentials from secrets); the RustFS profile creates and versions the source bucket without `minio/mc`; the Hetzner runbook adds enabling versioning and the source bucket.
  - Owner actions: enable versioning on the Hetzner buckets; create `kpress-sources` if N3-D1 (a); approve any command on the server.
  - Done: the Docker tests pass with the source store; the Mac composition saves and restores a site; the Hetzner steps are written and, with the owner's go-ahead, applied.

## Notes

- Restore uses read-and-write because genro-storage has no restore; the upstream item stays open and is not a blocker.
