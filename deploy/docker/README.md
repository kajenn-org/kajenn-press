# websites composition

RustFS holds the release bucket; **websites** (administration, internal
installation, render worker) builds and exports releases. The `demo` profile adds
a **builder** that builds kajenn.org and a **child** (`StaticSiteServerApplication`)
that serves it from the bucket with read-only credentials. Ports bind to
`127.0.0.1`; on a server a reverse proxy on the host terminates TLS.

| Service | Role | Address (Mac `.env`) |
|---|---|---|
| `secrets` | Generates local credentials once, in three private volumes | — |
| `rustfs` | S3-compatible release storage (`rustfs/rustfs` 1.0.3) | network only |
| `storage-init` | Creates bucket `releases`, a read-write user for websites, a read-only user for the child | — |
| `websites` | Administration and installation | http://kpress.localhost:8875/admin/ |
| `builder` (`demo`) | Builds, activates and registers kajenn.org through MCP (`examples/kajenn_org/build.py`) | — |
| `child` (`demo`) | Serves kajenn.org | http://kajenn.localhost:8876/ |

## Addresses

The composition reads `deploy/docker/.env`; every Compose command fails without it.
Start from the example, whose values are for the Mac:

```bash
cp deploy/docker/.env.example deploy/docker/.env
```

| Variable | Meaning |
|---|---|
| `KPRESS_SCHEME` | `http` without a proxy; `https` behind a TLS reverse proxy |
| `KPRESS_MANAGEMENT_HOST` | Host (and port) of the administration |
| `KPRESS_PREVIEW_HOST` | Host of private previews; must differ from the administration |
| `KPRESS_TRUSTED_PROXIES` | Addresses or CIDR networks whose `X-Forwarded-Proto`/`X-Forwarded-For` websites trusts |

websites answers only requests whose scheme and `Host` match these origins. Behind
a proxy the scheme comes from `X-Forwarded-Proto`, read only from a trusted address.
The `demo` builder talks to websites in plain http, so the demo needs `KPRESS_SCHEME=http`.

## Behind nginx on a server

`nginx-kpress.conf` is the host nginx configuration for `kpress.genro.com` and
`preview.kpress.genro.com`: port 80 answers the certbot challenge and redirects to
https; port 443 proxies both names to `127.0.0.1:8875` with `Host`,
`X-Forwarded-Proto` and `X-Forwarded-For`. The server `.env` then sets
`KPRESS_SCHEME=https`, the two names, and in `KPRESS_TRUSTED_PROXIES` the address
nginx reaches websites from. The installation on the Hetzner host, step by step, is in
[HETZNER.md](HETZNER.md).

## Start, use, stop

```bash
docker compose -f deploy/docker/compose.yaml up -d --build
```

This starts the manager only. Add `--profile demo` to `up` (and to `down`) for the
kajenn.org builder and child; the site is then at http://kajenn.localhost:8876/.
The administration is at http://kpress.localhost:8875/admin/ with user
`operator`; its generated password is in the websites volume:

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
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.volume.yaml --profile demo up -d --build
```

Stop it with the same two files; add `--profile s3` to `down` to remove the
RustFS containers of an earlier run as well.

## Rebuild after changes

Source changes need a rebuild of the images (`up -d --build`). The builder is
re-runnable: it keeps its state in the `child-config` volume and creates new
revisions only for changed sources.

```bash
docker compose -f deploy/docker/compose.yaml --profile demo up -d --build --force-recreate builder child
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
within its cache interval. The tests set their own addresses, which take precedence
over `deploy/docker/.env`. `test_proxy_origin_contract.py` starts the manager without
the demo profile on an `https` origin and checks that only a forwarded `https`
request with the configured `Host` reaches the administration. Never run these tests
on a server with a real installation: they delete its volumes.
