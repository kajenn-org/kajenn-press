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

## Phase 3

- Owner approved the Deployments mockup (`mockups/phase-3.html`) on 2026-10-24: an installation-wide tree node beside "Shared across sites", a table of children with catalog and storage releases, a detail card with both side by side, Re-export, and a Register child form.
- Registry operations live in `publication/deployments.py` (`Deployments` mixin of `PublicationService`): `child_save` (permission `publish`), `child_read`, `child_list` (permission `read`, list filtered per site). A child's public origin must equal its channel settings' origin, because the child answers only for the origin its pointer names; its channel is immutable after creation.
- Added beyond the planned four operations: `child_channels`, a read listing the channel settings a child can be registered for. The registration form needs them, and publication records are not readable through generic editorial access.
- "Exported release" and "release read back from storage" are the same value: Phase 1 records no export in the catalog, and the view reads the pointer back from storage at every load. States: `up_to_date`, `storage_differs`, `not_exported`, `nothing_to_serve`, `storage_unconfigured`.
- Browser verification ran against the real kajenn.org catalog with release storage in RustFS bucket `kajenn-org-releases`. The owner authorized the agent to sign in with the disposable loopback credentials (demo / demo) after two sign-ins landed outside the controlled tab. The native channel `<select>` inside the workspace iframe did not respond to synthetic keys; the channel was chosen by setting its value and dispatching `change`, the event a pointer choice produces.
- Defect found during Phase 3 in the Phase 1 qualification: a fixed run of 40 replacements let the concurrent reader miss every replacement window, so the `local` backend was accepted in 10 of 40 runs (and once in the full suite). The qualification now replaces for at least 0.5 s and until the reader completed 200 reads, within a 20 s budget, refusing the backend if the budget elapses. Measured afterwards: `local` refused in 150 of 150 runs; RustFS accepted in 5 of 5 runs, about 2.4 s each. `docs/14-release-storage.md` updated.

## Phase 4

- Owner decision (2026-10-25): adopt genro-storage 0.8.4, released 2026-10-24 with atomic local writes (genro-org/genro-storage#83 closed). Verified before adopting: the issue reproducer gives 0 invalid reads of 843, and the qualification accepts `local` in 20 of 20 runs. `pyproject.toml` requires `genro-storage>=0.8.4,<0.9` (and the `release-s3` extra the same); every local environment was upgraded.
- Consequence approved by the owner: the body of `test_pointer_replacement_is_never_observed_partially` no longer uses `local` as the refused example; it patches `LocalStorage.write_bytes` with a truncate-then-chunked write (the 0.8.1 behaviour) and checks the refusal, then checks that the real `local` mount qualifies. The contract lines are unchanged. Phase 5 (shared volume) is unblocked by the same release.
- RustFS IAM verified before the design: a user with the `readonly` policy reads objects and is refused writes and deletes (`mc`, RustFS 1.0.3).
- Credentials are generated by a one-shot service into three volumes, one per consumer (RustFS root, websites, child); the child mounts only its own, so it never holds read-write credentials. The generator is `credentials.py`: a file named `secrets.py` shadowed the standard `secrets` module it imports.
- Hosts inside the composition: the builder calls websites at `http://websites:8875` with `Host: 127.0.0.1:8875`, the management origin, because the installation routes management requests by host.
- The builder `channel_read` result for a channel never activated carries no `attributes`; `examples/kajenn_org/build.py` handles it.
- The Docker contract tests run only with `KAJENN_DOCKER=1`, remove the composition's volumes, and pass storage credentials to `mc` through the environment, never in command arguments.
- Contract coverage: the Phase 4 `Decisions:` and `Done:` fields and the second contract skeleton's two `wf:contract:` lines differ from the plan commit because of the owner's RustFS decision of 2026-10-24 (shared volume → RustFS bucket, read-only volume → read-only credentials), recorded under Phase 1 and committed with it.
- New functions in `deploy/docker/` and `examples/kajenn_org/build.py` were written without `wf:phase-4:new` markers; the naming review lists them explicitly.

## Rename to kajenn-press (2026-10-25, between Phase 4 and Phase 5)

- Owner decision: the project is named `kajenn-press`. Package `kajenn_public_site` → `kajenn_press`, distribution and MCP name `kajenn-public-site` → `kajenn-press`, `PublicSiteApplication` → `PressApplication`, Kajenn application code `public_site` → `press`. Historical records keep the old name: evidence files, notes, the design prompt, the qualified admin freeze. The GitHub repository and the local folder are not renamed yet.
- The render profile records third-party versions only, so builds frozen before the rename stay compatible.
- Checks after the rename: ruff passed; Node 4 passed; base suite 109 passed, 7 skipped; admin 13 passed plus the known Gramlot wheel hash failure; Docker 3 passed. The Docker secret check now searches every tracked file for generated credentials instead of listing file extensions under `deploy/`, which flagged the Dockerfiles once they were tracked.

## Phase 5

- The Phase 4 entrypoints had the S3 storage written in code; they now read `RELEASE_STORAGE` (`s3` default, `local` for `/releases`). Product code is unchanged between the two compositions; the switch is the override file `compose.volume.yaml` plus that variable.
- The override disables `rustfs` and `storage-init` through a profile (`s3`) and replaces the websites dependencies with `depends_on: !override`; `!reset` would empty them, ignoring the new entries. A one-shot `releases-init` gives the volume to uid 10002 (websites) with mode 755; the child (uid 10003) mounts it read-only.
- Qualification record: websites started on the local mount, which happens only after `ReleaseStorage.qualify` accepted it (genro-storage 0.8.4); a refused mount stops the installation at startup.
- `update_and_rollback()` was extracted from the Phase 4 Docker test so that both compositions run the same cycle.
- Contract coverage: the Phase 5 fields and contract skeleton (renamed to `test_local_volume_configuration_contract.py`) differ from the plan commit by the owner's RustFS decision of 2026-10-24 (MinIO → shared volume once genro-storage#83 is fixed), recorded under Phase 1; the release fixing #83 (0.8.4) was adopted under Phase 4.
