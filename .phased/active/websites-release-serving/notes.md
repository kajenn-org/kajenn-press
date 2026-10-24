## Planning

- Created 2026-10-24 on branch `codex/websites-release-serving` from `codex/gramlot-administration` at `68d1042`. The previous plan is suspended in `.phased/suspended/gramlot-administration/`, not finalized.

## Phase 1

- Owner decision (2026-10-24), covering the changed `Files:` and `Done:` fields: after genro-org/genro-storage#83 (the `local` backend exposes partially rewritten files), release storage for development and tests is RustFS in Docker through the `s3` backend; the `local` backend is refused by the startup qualification until a fixed Genro Storage release passes it. `Files:` adds `pyproject.toml` for the optional `release-s3` extra. The owner also approved the matching changes to Phases 4 and 5 and to their contract skeletons (Phase 5 now uses the shared volume once #83 is fixed).
- On S3-compatible storage a read can fail with `OSError` (precondition) while the object is replaced; readers retry. No partial content was observed on RustFS 1.0.3.
- Write-once uses an existence check instead of exclusive create: on s3fs, `open("xb")` over an existing key raises a generic `OSError`, not `FileExistsError`. The installation is the only writer, so the check cannot race with another writer.
- `release_export` writes storage only: no idempotency key, receipt or catalog record. Repeating it yields the same pointer and rewrites no artifact. Export status is derived by reading the pointer back instead of storing it in the catalog, so a write that happened is never contradicted by a missing record.
- Production methods of this phase were written without `wf:phase-1:new` markers (only the four test helpers carry them); the naming review used an explicit list of the new callables. The `wf:phase-1:new` markers on `records_index`, `revision_index`, `scope_capabilities` and `render_preview` in `application.py` belong to the suspended gramlot-administration Phase 1 and are left for its own naming review.
