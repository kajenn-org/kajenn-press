<!-- generated from install.xml by xmldocs: do not edit, edit the XML -->

## Installing and running
*Instruction booklet · booklet/install · 2026-10-29*

### Purpose

How to run Kajenn Press with Docker: on a workstation with local S3 storage, on a server behind nginx with external buckets, with Help me, and how to run its tests. The step-by-step installation of the Hetzner host is `deploy/docker/HETZNER.md`.

### Requirements

- Docker with Compose, and this repository checked out.
- On a server: an S3-compatible service with two buckets with versioning, a reverse proxy with TLS, DNS for the administration's name.

#### 1. Run it on a workstation

```bash
cp deploy/docker/.env.example deploy/docker/.env
docker compose -f deploy/docker/compose.yaml --profile demo up -d --build
docker compose -f deploy/docker/compose.yaml exec websites cat /secrets/operator_password
```

The composition starts:

*Services*

| Service | Role |
|---|---|
| `secrets` | Generates the local credentials once: storage users, operator password, MCP token, and one private-link secret written to both the websites and the site-server volumes. |
| `rustfs`, `storage-init` | Local S3 storage; creates the buckets `sources` and `releases` with versioning, a read-write user for websites and a user for the site server that reads only `releases`. |
| `websites` | Administration, REST and MCP, render worker, on port 8875: `http://kpress.localhost:8875/admin/`, user `operator`. |
| `site-publisher` (profile `demo`) | Publishes the example site through MCP. |
| `site-server` (profile `demo`) | Serves the published sites on port 8877: `http://press.localhost:8877/`. |

`down` keeps volumes; `down -v` deletes working copies, buckets and credentials.

#### 2. Run it on a server

Set `KPRESS_SCHEME=https`, the administration's name in `KPRESS_MANAGEMENT_HOST`, and in `KPRESS_TRUSTED_PROXIES` the address the proxy connects from: websites answers only requests whose scheme and host match the administration's origin, and reads the scheme from `X-Forwarded-Proto` only from a trusted address. `deploy/docker/nginx-kpress.conf` is the nginx configuration of the Hetzner host.

With external buckets, add `compose.external-s3.yaml`; it does not start RustFS nor the demo services and reads:

*External storage*

| Variable | Meaning |
|---|---|
| `KPRESS_S3_ENDPOINT` | The S3 endpoint. |
| `KPRESS_S3_BUCKET` | The release bucket. |
| `KPRESS_SOURCES_BUCKET` | The source bucket; empty turns the site operations off. |
| `KPRESS_S3_CREDENTIALS_DIR` | Host directory with the files `access` and `secret`, mounted read-only. |

```bash
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.external-s3.yaml up -d --build
```

websites refuses to start with a bucket whose versioning is not enabled.

#### 3. Enable Help me

Put the installation's Claude API key in a private file readable by websites, name it in `KPRESS_HELP_KEY_FILE`, and add `compose.help.yaml` to every Compose command. The key is never generated and never enters a volume. Without it, the Help me pane says Help me is not configured.

#### 4. Run the tests

The full suite needs a render interpreter and a disposable S3 endpoint; the administration tests an interpreter with the `admin` extra; the Docker tests drive the composition and delete its volumes.

```bash
KAJENN_RENDER_PYTHON=/path/to/render/python KAJENN_RELEASE_S3=/path/to/s3.json .venv/bin/python -m pytest -q tests
KAJENN_DOCKER=1 PYTHONPATH=src .venv/bin/python -m pytest -q --import-mode=importlib tests/docker
```

`KAJENN_RELEASE_S3` is a private JSON file with `endpoint_url`, `access_key` and `secret_key`. The live Help me tests run only with `KAJENN_HELP_LIVE=1` and cost tokens.

### Rules

- **must-not** — Run `tests/docker` on a server with a real installation. *(They delete the composition's volumes.)*
- **must** — Enable versioning on both buckets before the first start. *(Pages and sources are read and restored by version.)*
- **must-not** — Give site servers keys that read the source bucket. *(Project-wide keys would let a site server read the sources.)*

### Current limits

- The hashed dependency locks target `aarch64` Linux. · `deploy/docker/lock.sh:7`
- Kajenn has no ACME client: TLS comes from the reverse proxy.

### Verified facts

- `RUN` `deploy/docker/compose.yaml:41` · 2026-10-29 — The composition starts websites on 8875 and, with the demo profile, the site publisher and the site server on 8877.
- `READ` `deploy/docker/credentials.py:32` · 2026-10-29 — One private-link secret is written to both the websites and the site-server volumes.
- `READ` `src/kajenn_press/site/store.py:19` · 2026-10-29 — websites refuses a source or release bucket whose versioning is not enabled.
- `READ` `deploy/docker/websites.py:58` · 2026-10-29 — Help me is configured only when `ANTHROPIC_API_KEY_FILE` names a file.
- `RUN` `tests/docker/test_external_s3_contract.py:1` · 2026-10-29 — The external-bucket composition writes sources and releases to the given buckets.

### Related documents

- `booklet/publication`
