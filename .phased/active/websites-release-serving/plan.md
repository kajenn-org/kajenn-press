# Context: codex/websites-release-serving
Parent: main
Mode: manual
Must not break: Stable content IDs, exact source revisions, record generations, receipts and audit remain authoritative in the installation catalog; no storage copy becomes a second editable authority.
Must not break: Activation and rollback stay conditional on the channel generation in the catalog. The storage copy of the active pointer is written by one writer (the installation) after the catalog commit and never decides activation.
Must not break: Release artifacts stay immutable and content-addressed. An exported release is byte-identical to the catalog release and verifiable against its manifest digest. Drafts and private previews never reach release storage.
Must not break: UI, REST and MCP consume the same application rules; current grants are rechecked by common services. Editorial-only, admin and render installations stay independently installable; the static render profile changes only through explicit qualification.
Must not break: Filesystem/Genro Storage remains the only catalog backend; no Asqueel or database is introduced. Existing releases, rollback and in-process public serving keep working unchanged.

## Objective

Separate where a site is edited and built from where it is served. An installation (catalog with one or more sites and their shared library, served by the existing application) exports each activated release and its active pointer to a configurable Genro Storage mount. A lightweight child application serves the active release of a site from that mount, without catalog, Gramlot or render worker. The existing server becomes websites: administration, internal installation and a registry of children. A local Docker composition proves the cycle with kajenn.org: built in websites, served by a child on `kajenn.localhost`. The same composition with MinIO proves that changing the Genro Storage configuration changes the backend without code changes.

Owner decisions (2026-10-24): websites.genro.com is the target address of the manager; the unit managed by websites is the installation; installations inside websites and installations with their own deployment coexist; shared resources stay shared inside one installation and are copied with provenance across installations; release storage goes through Genro Storage, configured per deployment (Docker volume locally, S3 or similar when hosts differ). Production DNS, real deployment and the per-site management application of a deployed installation are outside this plan.

Main baseline: `3bfe65fcebd0f92e87ff7835e6feb1f9cce4a289`. This branch starts from `codex/gramlot-administration` at `68d1042`, whose plan is suspended in `.phased/suspended/gramlot-administration/` after its Phase 1 work.

## Decisions shared by all phases

- Release storage layout: one Genro Storage mount per deployment. Immutable files are written once with exclusive create under a content-addressed path; the manifest is written after its files; the active pointer per site channel is written last. A reader never needs a file that is not yet written.
- Pointer: a small JSON document (site, channel, build, manifest digest, catalog channel generation, export time). The catalog stays authoritative; the storage pointer is rewritten after every activation and rollback and on explicit re-export. Genro Storage 0.8.1 has no conditional writes: the single writer is the installation process that owns the catalog lock.
- Atomicity: a reader must see either the old or the new complete pointer. The local backend declares atomic writes but the project has not verified it; Phase 1 qualifies it with a concurrent reader test before any consumer relies on it. A backend that fails qualification is refused, not worked around.
- Child serving: the child rereads the pointer with a short cache (default 5 seconds) and serves only files listed in the manifest it validated. Public headers, 404 and redirect behavior match the current in-process public serving. Previews stay in websites.
- Configuration: mounts, host-to-site bindings and cache interval come from deployment configuration. No credentials in release storage, pointer or manifest.
- Naming: the child application name is decided in Phase 2 with the owner; `GramlotWebsiteApplication` remains reserved for the per-site management application, outside this plan.
- Scope: no DNS provisioning, TLS automation, production deployment, CDN configuration, Asqueel, multi-writer storage, cross-installation library copy or interactive public components.

## Work Plan

- [ ] **Phase 1**: Release export to a configurable Genro Storage mount
  - Run: opus / high
  - Pattern: `src/kajenn_public_site/objects.py:ObjectStore.qualify` (Genro Storage mount configuration and exclusive-create qualification); `src/kajenn_public_site/publication/releases.py:Releases._release_activate` (conditional activation the export follows).
  - Files: existing `src/kajenn_public_site/publication/releases.py`, `src/kajenn_public_site/publication/service.py`, `src/kajenn_public_site/application.py`, `docs/12-publication-rollback.md`; new `src/kajenn_public_site/publication/export.py`, tests under `tests/publication/`, `docs/14-release-storage.md`.
  - Decisions: Export runs after the catalog commit of activation and rollback, with the same idempotency key; an export failure leaves the catalog activation committed and reports the export as pending, retriable through a REST/MCP operation. Re-export of an already exported release writes no immutable file twice and rewrites only the pointer.
  - Details: Configure the export mount through `create_server(..., publication={..., "release_storage": ...})` using Genro Storage configuration. Write files, manifest and pointer in that order. Add a qualification of the configured backend at startup: exclusive create, read-back digest, and pointer replacement observed by a concurrent reader. Expose export status on channel reads and a `release_export` operation on REST and MCP.
  - Done: The plan's tests for this phase, copied into `tests/publication/`, pass. The full existing suite and lint pass. An activation, an update and a rollback produce matching pointers in a local mount; a concurrent reader never observes a partial pointer; a simulated export failure leaves the activation committed and a retry completes it.

- [ ] **Phase 2**: Lightweight child application serving from release storage
  - Run: opus / high
  - Pattern: `src/kajenn_public_site/publication/serving.py:PublicServing.public_response` (public paths, headers, 404, release assets); `src/kajenn_public_site/publication/gateway.py:PreviewGateway` (host binding before kajenn routing).
  - Files: new child module and its server factory under `src/kajenn_public_site/`, tests under `tests/child/`, `examples/child_serve.py`; existing `pyproject.toml` (no new mandatory dependency), `docs/14-release-storage.md`, `README.md`.
  - Decisions: The child imports neither the catalog nor Gramlot nor the render worker. It validates the manifest digest before serving and refuses files not listed in it. When the pointer or manifest is missing or invalid it answers 503 and keeps serving the last validated release only if it was already loaded.
  - Details: Host-to-site binding from configuration. Pointer reread on the cache interval. Same response headers and path rules as in-process public serving, verified by running the same requests against both. The child installation profile is documented separately from editorial, admin and render.
  - Done: The plan's tests for this phase, copied into `tests/child/`, pass. Lint and the full suite pass. The same release served in-process and by the child returns identical bodies, status codes and public headers for every route, asset, sitemap, root redirect and a missing path; activation and rollback become visible within the cache interval.

- [ ] **Phase 3**: websites registry and deployment view `ui`
  - Run: opus / high
  - Pattern: `src/kajenn_public_site/admin/pages/index.py:Page.navigation_bag` (Gallery tree and scope-bound tabs); `src/kajenn_public_site/services/editorial.py:EditorialService.execute` (shared authorized operation dispatch).
  - Files: existing `src/kajenn_public_site/admin/` pages and views, `src/kajenn_public_site/application.py`, `docs/13-amministrazione.md`; new registry service module and tests under `tests/admin/` and `tests/services/`.
  - Decisions: A child is a registry record with name, public origin, bound site, release storage mount name and declared serving address. The registry belongs to the installation catalog with the same generation, receipt and audit rules. websites reads the storage pointer back to show which release each child serves; it never writes child configuration files.
  - Details: Add registry create, update, read and list operations on REST and MCP. Add an admin view listing children with bound site, active catalog release, exported release, export status and the release read back from storage, with re-export. Mismatches are shown, not corrected silently.
  - Done: The plan's tests for this phase, copied into `tests/admin/`, pass. Lint and the full suite pass. A real browser shows a registered child, its exported release and a deliberate mismatch; re-export resolves it. Compare the view with its approved mockup.
  - Verify: now — The deployment view makes clear which release each child serves and whether it matches the catalog.

- [ ] **Phase 4**: Local Docker composition with a shared release volume
  - Run: opus / medium
  - Pattern: `examples/admin_demo.py:main` (loopback administration server composition); `/Users/gporcari/Sviluppo/kajenn/kajenn-org-site-data/tools/build_site.py:main` (kajenn.org built through MCP only; read-only reference outside the repository).
  - Files: new `deploy/docker/` with Dockerfiles for websites and child, `compose.yaml`, configuration files and a README; `examples/` script that builds kajenn.org through MCP inside the composition; `docs/14-release-storage.md`.
  - Decisions: Images install pinned published artifacts with recorded hashes; the render worker profile stays a separate environment inside the websites image. The release volume is mounted read-write in websites and read-only in the child. Local credentials are generated at startup and never committed.
  - Details: Compose websites (admin, internal installation, render worker) and one child bound to `kajenn.localhost`. Build kajenn.org through MCP, activate, and serve it from the child. Document start, stop, rebuild and reset of volumes.
  - Done: `docker compose up` from a clean checkout serves kajenn.org from the child; the child container has no write access to the release volume; an update and a rollback in websites become visible in the child within the cache interval. Record exact image digests and commands in the phase evidence.

- [ ] **Phase 5**: Same composition with MinIO as S3 release storage
  - Run: opus / medium
  - Pattern: Phase 4 composition; Genro Storage `s3` mount configuration in `genro_storage.storage_grammar.StorageGrammar.s3`.
  - Files: `deploy/docker/` compose override and configuration for MinIO; `docs/14-release-storage.md`.
  - Decisions: Only configuration changes between Phase 4 and Phase 5. If the S3 backend fails the Phase 1 qualification, the phase stops with a reproducible report for Genro Storage instead of adding a workaround.
  - Details: Add MinIO, configure the release storage mount as `s3` in websites and child, repeat the Phase 4 cycle.
  - Done: The Phase 4 cycle passes against MinIO with no code change; the startup qualification result for the S3 mount is recorded.

## Contract tests and execution

Plan-time skeletons live in `tests/phase-1/` through `tests/phase-5/` relative to this plan. They import only pytest and intentionally fail until implemented. Copy the current phase's file into the destination named in its Done line; keep test names and every `# wf:contract:` line verbatim.

Each phase starts only after its predecessors are closed. The `ui` phase first obtains approval of a rendered mockup under `mockups/phase-3.html`. Human operators perform login in a visible browser; never type or persist their credentials.

Commands at plan creation: `.venv/bin/python -m ruff check .phased/active/websites-release-serving/tests`; `.venv/bin/python -m pytest --collect-only -q .phased/active/websites-release-serving/tests`; plugin `next-phase.py --validate`.

## Planning evidence and dependency boundaries

- Genro Storage 0.8.1 (installed in `.venv`) exposes mounts `local`, `s3`, `gcs`, `azure`, `sftp`, `webdav` and others; `StorageNode.write` writes whole objects; exclusive create (`open("xb")`) is already qualified by `ObjectStore.qualify`. No conditional write parameter exists in `StorageNode.write`.
- Backend capability flags declare `atomic_operations` for `local` and for S3 PUT; the project has not verified either. Phase 1 qualifies them before use.
- Public serving today reads the active release from the catalog snapshot (`PublicServing.public_response`); host binding happens in `PreviewGateway` before kajenn routing.
- kajenn routes by first path segment, not by host (`kajenn/docs/concepts.md`, "The one demux rule").
- `kajenn-orchestra` (process pool) and `kajenn-hub` (instance links, design status) do not provide deployment, DNS or release distribution.
- kajenn.org was built on 2026-10-23/24 through MCP only with the existing application; its catalog and tools are in `/Users/gporcari/Sviluppo/kajenn/kajenn-org-site-data`. In a release build `page.title` is the route title (`publication/service.py`), while a saved-page render uses the content title.

## Notes

No implementation, sibling-repository change, external deployment, merge or push is authorized by saving this plan. The suspended plan keeps its contracts for a later macro.
