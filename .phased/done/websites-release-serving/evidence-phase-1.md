# Phase 1 — release export to Genro Storage

## Delivered

- `src/kajenn_public_site/publication/export.py`: `ReleaseStorage` configures one Genro Storage mount, qualifies it at startup, writes artifacts (`objects/<sha256>`, write-once), sealed manifests (`manifests/<digest>.json`, write-once) and the pointer (`pointers/<settings_id>.json`, written last), and reports status by reading the pointer back.
- `PublicationService(..., release_storage=...)`: export after the catalog commit of `release_activate` and `release_rollback`; result field `export` (`exported` or `pending` with error code); `channel_read` shows the export state; new `release_export` operation (no key, no catalog commit, permission `publish`).
- `application.py`: `release_export` route on REST (POST required) and MCP.
- `pyproject.toml`: optional `release-s3` extra (`genro-storage[s3]>=0.8.1,<0.9`).
- `docs/14-release-storage.md`, README reading table row.

## Backend findings

- Genro Storage 0.8.1 `local`: declares `atomic_operations` but `write_bytes` truncates and rewrites. Concurrent reader: 41 invalid reads of 374 and 21 of 393. Reported as genro-org/genro-storage#83. The startup qualification refused it in 8 of 8 runs (about 0.08 s each).
- RustFS 1.0.3 through the `s3` backend (s3fs 2026.9.0): no partial content. During replacement a read can fail with `OSError: preconditions did not hold`; a retry returns a complete object. Exclusive create (`open("xb")`) on an existing key raises `OSError`, not `FileExistsError`, so write-once uses an existence check (single writer). The qualification accepted it in 8 of 8 runs (about 1.2 s each).

## Verification

Environment: RustFS `rustfs/rustfs:1.0.3` (image `sha256:9ca9559533b5…`) on `127.0.0.1:19000` with private generated credentials; render worker `kajenn-org-site-data/render-env` (Gramlot 0.3.8, Genro Builders 0.30.0, Genro Bag 0.28.0, markdown-it-py 4.2.0, nh3 0.3.7); noneditable headless install `kajenn-org-site-data/headless-env`.

- Phase contracts, copied verbatim to `tests/publication/test_release_export_contract.py`: 4 passed (40 s).
- Full suite from the repository root: 106 passed, 3 skipped (admin tests skip without Gramlot), 390 s.
  `KAJENN_RELEASE_S3=… KAJENN_RENDER_PYTHON=… KAJENN_APP_PYTHON=… PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests`
- Admin suite in `kajenn-org-site-data/admin-env`: 11 passed, 1 failed. The failure is `test_admin_is_optional_and_installs_from_reproducible_artifacts`: the qualified Gramlot 0.3.9 prerelease wheel (sha256 `fe7c937a…`) was in `/tmp` and was lost on the 2026-10-24 reboot; the PyPI 0.3.9 wheel has sha256 `f14c388e…`. Unrelated to this phase; the admin artifact needs requalification.
- A first full-suite run started from `tests/` failed `test_real_process_interruption_retry_and_fence` with `No module named 'tests'` in a spawned process; it passes from the repository root, as documented.
- `ruff check src tests examples`: passed.
