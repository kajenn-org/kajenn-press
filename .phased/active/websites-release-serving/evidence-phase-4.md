# Phase 4 — local Docker composition with RustFS

## Delivered

- `deploy/docker/`: `compose.yaml` (secrets, rustfs, storage-init, websites, builder, child), `Dockerfile.websites` (installation, administration, separate render environment), `Dockerfile.child` (child only), `credentials.py`, `storage-init.sh`, `websites.py`, `child.py`, hashed locks `requirements-{websites,render,child}.txt` produced by `lock.sh`, `README.md`.
- `examples/kajenn_org/`: template, CSS, logo (`kajenn-mark.png`, Apache 2.0, from the kajenn repository) and page blocks; `build.py` builds, activates and registers kajenn.org through MCP.
- `.dockerignore` at the repository root.
- genro-storage 0.8.4 adopted (`pyproject.toml`), Phase 1 refusal test rewritten with a simulated non-atomic backend.

## Pinned artifacts

- `python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`
- `rustfs/rustfs@sha256:9ca9559533b537d10482fe923288b676ad08f92a7069d9a17327fbae3cab688b` (1.0.3)
- `minio/mc@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727`
- Locks: websites 48 pins, render 33, child 46, all with hashes; genro-storage 0.8.4, kajenn 0.5.0, gramlot 0.3.9 (admin) and 0.3.8 (render), s3fs 2026.9.0.
- Built images on 2026-10-25: `kajenn-websites:local` `sha256:9c99fde41da60ab13e6159400b2ba42443b5bc75beba93cee120e9fc2e022878`, `kajenn-child:local` `sha256:289e067c3ddd349b4bf7de033031270dd0c2687a25452b393ab12adf1de6669d`.

## Verification

- `KAJENN_DOCKER=1 PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests/docker`: 3 passed in 27 s, starting from `down -v`:
  - the builder publishes kajenn.org through MCP; the child serves `/en/`, `/en/concepts/`, `/en/get-started/`, `/sitemap.xml` with 200 and `/` with 307; the registry shows `kajenn-org` up to date;
  - a write with the child's credentials fails with "Insufficient permissions"; no generated credential appears in the bucket; tracked files under `deploy/` are only scripts, locks, compose and README;
  - an update activated in websites and a rollback reach the child within 8 s (cache 5 s).
- Phase 1 contracts with genro-storage 0.8.4: 4 passed.
- Full base suite: 109 passed, 7 skipped (admin and Docker tests run separately), 304 s.
- Admin suite: 13 passed, 1 failed — the known Gramlot 0.3.9 wheel hash check.
- `ruff check src tests examples deploy`: passed.
- Browser: the child's kajenn.org at http://kajenn.localhost:8876/en/ renders as before.

## Commands

```bash
bash deploy/docker/lock.sh
docker compose -f deploy/docker/compose.yaml up -d --build
KAJENN_DOCKER=1 PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests/docker
```
