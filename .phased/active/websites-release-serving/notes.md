## Planning

- Created 2026-10-24 on branch `codex/websites-release-serving` from `codex/gramlot-administration` at `68d1042`. The previous plan is suspended in `.phased/suspended/gramlot-administration/`, not finalized.

## Phase 1

- Owner decision (2026-10-24), covering the changed `Files:` and `Done:` fields: after genro-org/genro-storage#83 (the `local` backend exposes partially rewritten files), release storage for development and tests is RustFS in Docker through the `s3` backend; the `local` backend is refused by the startup qualification until a fixed Genro Storage release passes it. `Files:` adds `pyproject.toml` for the optional `release-s3` extra. The owner also approved the matching changes to Phases 4 and 5 and to their contract skeletons (Phase 5 now uses the shared volume once #83 is fixed).
- On S3-compatible storage a read can fail with `OSError` (precondition) while the object is replaced; readers retry. No partial content was observed on RustFS 1.0.3.
- Write-once uses an existence check instead of exclusive create: on s3fs, `open("xb")` over an existing key raises a generic `OSError`, not `FileExistsError`. The installation is the only writer, so the check cannot race with another writer.
- `release_export` writes storage only: no idempotency key, receipt or catalog record. Repeating it yields the same pointer and rewrites no artifact. Export status is derived by reading the pointer back instead of storing it in the catalog, so a write that happened is never contradicted by a missing record.
- Production methods of this phase were written without `wf:phase-1:new` markers (only the four test helpers carry them); the naming review used an explicit list of the new callables. The `wf:phase-1:new` markers on `records_index`, `revision_index`, `scope_capabilities` and `render_preview` in `application.py` belong to the suspended gramlot-administration Phase 1 and are left for its own naming review.

## Phase 2

- Owner decisions (2026-10-24): the site is served by a Kajenn application, `StaticSiteServerApplication` (module `kajenn_public_site/child.py`), mounted on the site root (`mount = ""`) of the child server built by `create_static_site_server`; a second application, `StaticSiteHealth`, answers `/_health/health`. A first version named `ReleaseSiteServer` copied the `PreviewGateway` shape (an ASGI front before Kajenn routing); the owner expected an application whose purpose is serving the site, and Kajenn supports it: a `BaseApplication` implements the ASGI call and the root mount receives every unclaimed path (`kajenn/docs/concepts.md`, demux rule). The name was chosen by the owner after `ReleaseSite...` and `SitePublisher...` were discussed.
- The child server disables Kajenn sessions (`middleware={"session": False}`): with the session stage armed by default, every public response carried a `session_id` cookie, which the parity test caught.
- Parity is by construction: `method_response` and `release_response` were extracted from `PublicServing.public_response` into `publication/serving.py`; the installation and the child call the same function and differ only in where bytes are read. Existing serving, gateway and release tests pass unchanged after the extraction.
- With no valid release the child answers 503 (plan decision), while the installation answers 404 when a channel has no active release; parity is required for the same activated release, not for an empty channel.
- History assets (`/_releases/...`) are checked against the current pointer's public origin for the whole channel history: the pointer written in Phase 1 lists history digests without per-release origins. Equal to in-process behaviour unless a channel's public origin changes between releases.
