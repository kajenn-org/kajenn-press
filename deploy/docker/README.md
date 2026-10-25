# Local websites composition

RustFS holds the release bucket; **websites** (administration, internal
installation, render worker) builds and exports releases; a **child**
(`StaticSiteServerApplication`) serves kajenn.org from the bucket with read-only
credentials. Loopback only: ports bind to `127.0.0.1`.

| Service | Role | Address |
|---|---|---|
| `secrets` | Generates local credentials once, in three private volumes | — |
| `rustfs` | S3-compatible release storage (`rustfs/rustfs` 1.0.3) | network only |
| `storage-init` | Creates bucket `releases`, a read-write user for websites, a read-only user for the child | — |
| `websites` | Administration and installation | http://127.0.0.1:8875/admin/ |
| `builder` | Builds, activates and registers kajenn.org through MCP (`examples/kajenn_org/build.py`) | — |
| `child` | Serves kajenn.org | http://kajenn.localhost:8876/ |

## Start, use, stop

```bash
docker compose -f deploy/docker/compose.yaml up -d --build
```

Open http://kajenn.localhost:8876/ for the site. The administration is at
http://127.0.0.1:8875/admin/ with user `operator`; its generated password is in
the websites volume:

```bash
docker compose -f deploy/docker/compose.yaml exec websites cat /secrets/operator_password
```

```bash
docker compose -f deploy/docker/compose.yaml down
```

`down -v` also deletes catalog, bucket and credentials: the next `up` starts
from nothing and generates new credentials.

## Shared volume instead of RustFS

`compose.volume.yaml` replaces RustFS with a Docker volume, `releases`: websites
mounts it read-write, the child read-only. Only configuration changes:
`RELEASE_STORAGE=local` selects the Genro Storage `local` backend in both
entrypoints (genro-storage 0.8.4 or later, whose local writes are atomic). The
volume is shared between containers on one host only.

```bash
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.volume.yaml up -d --build
```

Stop it with the same two files; add `--profile s3` to `down` to remove the
RustFS containers of an earlier run as well.

## Rebuild after changes

Source changes need a rebuild of the images (`up -d --build`). The builder is
re-runnable: it keeps its state in the `child-config` volume and creates new
revisions only for changed sources.

```bash
docker compose -f deploy/docker/compose.yaml up -d --build --force-recreate builder child
```

## Dependencies

Images install hashed locks generated from `pyproject.toml` by `lock.sh`
(`uv pip compile --generate-hashes`), then this checkout with `--no-deps`. The
render worker has its own environment inside the websites image. Base images are
pinned by digest in the Dockerfiles and `compose.yaml`.

## Checks

```bash
KAJENN_DOCKER=1 PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests/docker
```

`test_local_volume_configuration_contract.py` repeats the cycle with the shared volume. The tests remove the composition's volumes, start it from nothing and check the
served site, that the child's credentials cannot write the bucket, that no
credential reaches the bucket, and that an update and a rollback reach the child
within its cache interval.
