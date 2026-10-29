# websites composition

`compose.yaml` runs the kajenn-press manager (websites: administration, site operations,
render worker) with RustFS as S3 storage for site sources and releases. The `demo` profile
adds a **site publisher**, which publishes the Kajenn Press example site page by page
through MCP, and a **site server**, which serves it.

| Service | Role | Address |
|---|---|---|
| `secrets` | Generates local credentials once, in three private volumes; the private-link secret goes to websites (signs links) and the site server (checks them) | — |
| `rustfs` | S3-compatible storage | — |
| `storage-init` | Creates the buckets `releases` and `sources` with versioning, a read-write user for websites, a user for the site server that reads only `releases` | — |
| `websites` | Administration, REST and MCP, render worker | http://kpress.localhost:8875/admin/ |
| `site-publisher` (`demo`) | Publishes `examples/kajenn_press_site` through MCP | — |
| `site-server` (`demo`) | Serves the sites bound in `bindings.json` of the release bucket; a new address needs no restart | http://press.localhost:8877/ |

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
| `KPRESS_TRUSTED_PROXIES` | Addresses or CIDR networks whose `X-Forwarded-Proto`/`X-Forwarded-For` websites trusts |

websites answers only requests whose scheme and `Host` match the administration origin. Behind
a proxy the scheme comes from `X-Forwarded-Proto`, read only from a trusted address.
The `demo` publisher talks to websites in plain http, so the demo needs `KPRESS_SCHEME=http`.

## Behind nginx on a server

`nginx-kpress.conf` is the host nginx configuration for `kpress.genro.com`: port 80
answers the certbot challenge and redirects to https; port 443 proxies to
`127.0.0.1:8875` with `Host`, `X-Forwarded-Proto` and `X-Forwarded-For`. The server
`.env` then sets `KPRESS_SCHEME=https`, the name, and in `KPRESS_TRUSTED_PROXIES` the
address nginx reaches websites from. The installation on the Hetzner host, step by step, is in
[HETZNER.md](HETZNER.md).

## Start, use, stop

```bash
docker compose -f deploy/docker/compose.yaml up -d --build
```

This starts the manager only. Add `--profile demo` to `up` (and to `down`) for the
site publisher and the site server; the example site is then at http://press.localhost:8877/.
The administration is at http://kpress.localhost:8875/admin/ with user
`operator`; its generated password is in the websites volume:

```bash
docker compose -f deploy/docker/compose.yaml exec websites cat /secrets/operator_password
```

```bash
docker compose -f deploy/docker/compose.yaml down
```

`down -v` also deletes working copies, buckets and credentials: the next `up` starts
from nothing and generates new credentials.

## External S3 bucket instead of RustFS

`compose.external-s3.yaml` uses existing S3-compatible buckets, such as Hetzner Object
Storage, and does not start `rustfs`, `storage-init` and the demo services. Both buckets
need versioning. The override fills `RELEASE_S3_*` and `SOURCES_S3_*` from `.env`:

| Variable | Meaning |
|---|---|
| `KPRESS_S3_ENDPOINT` | S3 endpoint, e.g. `https://fsn1.your-objectstorage.com` |
| `KPRESS_S3_BUCKET` | Existing release bucket |
| `KPRESS_SOURCES_BUCKET` | Existing source bucket; empty turns the site operations off |
| `KPRESS_S3_BASE_PATH` | Optional folder inside the bucket |
| `KPRESS_S3_CREDENTIALS_DIR` | Host directory with two files, `access` and `secret`, mounted read-only |

```bash
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml up -d --build
```

websites refuses a source or release bucket whose versioning is not enabled.

## Dependencies

Images install hashed locks generated from `pyproject.toml` by `lock.sh`
(`uv pip compile --generate-hashes`), then this checkout with `--no-deps`. The
render worker has its own environment inside the websites image. Base images are
pinned by digest in the Dockerfiles and `compose.yaml`.

## Checks

```bash
KAJENN_DOCKER=1 PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests/docker
```

The tests remove the composition's volumes, start it from nothing and check: the example
site served page by page with its SEO, maintenance on and off, a private link opening the site during maintenance, a site source saved in four versions, that the site server's credentials cannot write releases nor read sources,
that no credential reaches storage or git, and the external-bucket setup. They set their
own addresses, which take precedence over `deploy/docker/.env`. `test_proxy_origin_contract.py` starts the manager without
the demo profile on an `https` origin and checks that only a forwarded `https`
request with the configured `Host` reaches the administration. Never run these tests
on a server with a real installation: they delete its volumes.

## Environment of the full test suite

Two interpreters and one S3 endpoint, all outside the repository:

- `KAJENN_RENDER_PYTHON`: an interpreter with `pip install -e '.[render]' -c constraints/render-qualified.txt`. Editable, so the worker sees the current source.
- An admin interpreter with `pip install -e '.[admin,dev,release-s3]'` runs `tests/admin`.
- `KAJENN_RELEASE_S3`: a private JSON file (mode 600) with `endpoint_url`, `access_key` and `secret_key` of a disposable S3 server. Each test creates its own bucket; the site source tests enable S3 versioning on theirs through `PutBucketVersioning`.

A disposable RustFS for that file:

```bash
docker run -d --name kajenn-press-test-rustfs -p 127.0.0.1:19100:9000 -e RUSTFS_ACCESS_KEY=<access> -e RUSTFS_SECRET_KEY=<secret> -e RUSTFS_VOLUMES=/data rustfs/rustfs:1.0.3
```

```bash
.venv/bin/python -m pytest -q tests
```
