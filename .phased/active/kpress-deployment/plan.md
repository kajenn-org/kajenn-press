# Context: codex/kpress-deployment
Parent: main
Mode: manual
Must not break: One composition serves both targets. The Mac and the Hetzner server run the same `compose.yaml` and the same images; only the `.env` file differs. No file is edited by hand on the server.
Must not break: Management and preview stay on two different origins, as `PreviewGateway` requires. Management credentials never reach the preview origin.
Must not break: The child's storage credentials stay read-only; websites is the only writer of release storage; no credential is committed or written to release storage.
Must not break: Product code under `src/kajenn_press/` is not changed to fit the deployment. A missing product capability stops the phase and is reported.
Must not break: The existing Docker contracts (`tests/docker/`) keep passing.

## Objective

Install the kajenn-press site manager (websites: administration, catalog, render worker, release storage) at `https://kpress.genro.org`, with private previews at `https://preview.kpress.genro.org`, on the owner's Hetzner server, behind the nginx already running there. The same Docker composition runs on the owner's Mac at `http://kpress.localhost:8875` and `http://preview.kpress.localhost:8875`, without a proxy.

Owner decisions (2026-10-26): manager address `kpress.genro.org`; preview address `preview.kpress.genro.org`; the deployment is a Docker composition usable on the Mac as well; the Hetzner server already runs nginx on ports 80/443, and kpress attaches to it.

Starting point (main `64fcad6`, Macro 3b): `deploy/docker/compose.yaml` runs secrets, RustFS, storage-init, websites, builder and one child. Its limits for a public host:

- `WEBSITES_MANAGEMENT_ORIGIN` and `WEBSITES_PREVIEW_ORIGIN` are written in `compose.yaml` (`http://127.0.0.1:8875`, `http://localhost:8875`).
- Ports bind to `127.0.0.1`; there is no TLS.
- `ManagementGuard` and `PreviewGateway` compare `scope["scheme"] + "://" + Host` with the configured origins. Behind a reverse proxy uvicorn reports `http` unless it trusts the proxy's forwarded headers; `deploy/docker/websites.py` calls `uvicorn.run` without `forwarded_allow_ips`.
- `builder` builds the kajenn.org example at every start and `child` needs the `child.json` that builder writes.
- `deploy/docker/websites.py` states that the user store (one `operator` with a generated password) is not a production identity store.

## Decisions shared by all phases

- Configuration: a committed `deploy/docker/.env.example` with Mac values; the server uses its own `.env`, never committed. Variables: management origin, preview origin, trusted proxy addresses.
- Reverse proxy: none in the composition. websites publishes port 8875 on `127.0.0.1` only. On the server the existing nginx terminates TLS for both names and proxies to `127.0.0.1:8875`, passing `Host` and `X-Forwarded-Proto`. On the Mac the browser reaches websites directly over `http`.
- Proxy trust: uvicorn trusts forwarded headers only from the addresses listed in `.env` (on the server, the address nginx connects from). Deployment entrypoint change, not product code.
- Example site: `builder` and `child` move under a Compose profile `demo`. A plain `docker compose up` starts the manager only. The Docker tests run with the profile.
- Accounts: the single `operator` account with generated password stays for this plan. A real identity store is outside this plan.
- Scope: no DNS automation, no CI, no public serving of sites from the Hetzner server, no backup automation. Backup is documented as a manual command.

## Work Plan

- [ ] **Phase 1**: Addresses from `.env`, proxy trust and the `demo` profile
  - Files: `deploy/docker/compose.yaml`, `deploy/docker/compose.volume.yaml`, `deploy/docker/websites.py`, new `deploy/docker/.env.example`, `deploy/docker/README.md`, `tests/docker/`.
  - Details: Origins come from `.env`. uvicorn gets `proxy_headers=True` and `forwarded_allow_ips` limited to the composition network. `builder` and `child` get `profiles: [demo]`; the Docker tests pass `--profile demo`.
  - Done: The four Docker tests pass with the `demo` profile. `docker compose up` without profile starts secrets, RustFS, storage-init and websites only. A new Docker test sends a request with `X-Forwarded-Proto: https` and the configured Host from inside the network and gets the administration login, and gets 403 for a wrong Host.

- [ ] **Phase 2**: Two hostnames on the Mac and the nginx configuration `ui`
  - Files: `deploy/docker/.env.example`, new `deploy/docker/nginx-kpress.conf` (example server blocks for the two names), `deploy/docker/README.md`, `tests/docker/`.
  - Details: The Mac `.env` uses `http://kpress.localhost:8875` and `http://preview.kpress.localhost:8875`. The nginx example has one server block per name, proxying to `127.0.0.1:8875` with `Host`, `X-Forwarded-Proto` and `X-Forwarded-For`; certificate paths are placeholders filled on the server.
  - Done: On the Mac `http://kpress.localhost:8875/admin/` shows the login and accepts the `operator` password; a preview link created from the administration opens on `http://preview.kpress.localhost:8875`. A Docker test runs nginx (image pinned by digest) with the example configuration in front of websites and gets the login through it. Docker tests pass. Browser check by the owner.

- [ ] **Phase 3**: Installation on the Hetzner server
  - Files: new `deploy/docker/HETZNER.md` (runbook), `deploy/docker/README.md`.
  - Details: The runbook lists, in order: DNS records for both names pointing to the server; certificates for both names with the method the server's nginx already uses; `git clone` of kajenn-org/kajenn-press; `.env` with the two origins and the trusted proxy address; `docker compose up -d --build`; the two nginx server blocks and `nginx -t` before reload; reading the operator password; updating with `git pull` and `up -d --build`; a manual backup of the named volumes.
  - Owner actions: create the DNS records, give SSH access or run the commands; no command runs on the server without the owner's go-ahead.
  - Done: `https://kpress.genro.org/admin/` answers with a valid certificate and the operator logs in; a preview opens on `https://preview.kpress.genro.org`; a restart (`docker compose restart`) keeps catalog, releases and password.

## Server facts and owner decisions

- Server (checked by the owner on 2026-10-26): Hetzner host 46.62.203.133, x86_64, nginx 1.24.0 (Ubuntu) on the host listening on 80/443, certbot at `/usr/bin/certbot`, port 8875 free. Its `sites-enabled` already holds asqueel, genroasgi, gramlot, gramlot-galleries, pagspett and sourcerer; kpress adds its own file without touching them. The certbot webroot convention comes from `sourcerer_v2/docker_v2/nginx/sourcerer.genro.com.conf`.
- Trusted proxy address: host nginx reaches the published port through Docker, so websites sees the gateway address of the composition network, not 127.0.0.1. Phase 1 fixes it in `.env` and the Phase 2 nginx test checks it.
- Public sites (owner decision 2026-10-26): this plan installs the manager only; serving published sites from the server comes later.

## Notes

- `tests/docker/` remove the composition volumes (`down -v`). They must never run on the Hetzner server against the real installation.
