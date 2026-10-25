# Phase 5 — the same composition on a shared Docker volume

## Delivered

- `deploy/docker/compose.volume.yaml`: override that disables RustFS and storage-init (profile `s3`), adds `releases-init` and the `releases` volume, mounts it read-write in websites and read-only in the child, and sets `RELEASE_STORAGE=local`.
- `deploy/docker/websites.py`, `deploy/docker/child.py`: `release_storage()` reads `RELEASE_STORAGE` (`s3` default, `local` → `/releases`).
- `tests/docker/test_local_volume_configuration_contract.py`; `update_and_rollback()` shared with the Phase 4 Docker test.
- `deploy/docker/README.md` and `docs/14-release-storage.md` sections.

## Verification

- Phase contract copied verbatim: `KAJENN_DOCKER=1 PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests/docker/test_local_volume_configuration_contract.py` passed in 30 s from `down -v`: RustFS not running; websites started on the local mount (startup qualification accepted it with genro-storage 0.8.4); the builder published kajenn.org; the child served `/en/`, `/en/concepts/`, `/en/get-started/`, `/sitemap.xml` (200) and `/` (307); the volume holds the release files; a write from the child fails with "Read-only file system"; no generated credential is in the volume; an update and a rollback reach the child within the cache interval.
- Phase 4 and Phase 5 Docker tests together: 4 passed in 47 s.
- `ruff check src tests examples deploy`: passed.
- No product code changed in this phase (`src/` untouched).
