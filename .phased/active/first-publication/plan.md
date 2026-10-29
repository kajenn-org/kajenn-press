# Context: feat/first-publication
Parent: main
Mode: manual
Must not break: The full suite, the admin suite and the Docker suite keep passing.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-tls-proxy, d-server-agent, d-server-registry, d-dns, d-www, d-manager-host in particular).
Must not break: The agent has a fixed set of actions and no generic shell; it answers only the manager with its own token; it runs without root. Site servers keep read-only keys on the release bucket.
Must not break: No change on the Hetzner host without the owner's go-ahead; no real DNS record or public certificate is created by tests.
Must not break: Every UI phase is checked in a real browser against its approved mockup.

## Objective

The first publication of a site on a server other than the manager (proposal, sections First publication and Servers): a registry of servers; bindings that name the server and the canonical name between the domain and `www.`; site servers that serve only their own sites; an agent per server that configures the installed proxy (nginx with certbot, Caddy, Traefik) for a domain and reports the certificate; DNS records shown and checked; a guided first publication in the Published site tab; moving a site to another server.

Entry: main `f66db9b`. Inventory: `bindings.json` (schema 1) maps origin → site id and state, written by Publish from the root page's public origin (`publish.py`); every site server serves every binding of the release bucket (`serving.py`); there is no registry of servers, no agent, no notion of `www` or of DNS; the Docker composition runs one site server on 8877 without TLS.

## Owner decisions (2026-10-29): all recommended options chosen; mockup `mockups/first-publication.html` approved

- **N7b-D1 · Agent transport.** (a) HTTPS from the manager to the agent with a per-server bearer token stored by the manager as a secret file (never in Bags or buckets), plus an address allow-list in the agent; the network limit (firewall or WireGuard) is part of the server's installation. (b) An SSH key and a forced command. Decided: (a); the agent is a Kajenn application like the others.
- **N7b-D2 · Who registers a server.** (a) An account with the new grant `servers` on `installation`; the registry is `servers.json` in the source bucket. (b) Any editor. Decided: (a).
- **N7b-D3 · DNS check.** (a) Resolve through public resolvers (dnspython, querying 1.1.1.1 and 8.8.8.8) so a record cached by the manager's resolver does not mislead; the check passes when both names answer the server's addresses. (b) The system resolver. Decided: (a).
- **N7b-D4 · Testing the drivers.** (a) Each driver produces files and commands checked by unit tests; one Docker test runs Caddy with its internal CA and on-demand TLS against a site server and the agent, end to end; nginx and Traefik configurations are checked with `nginx -t` and Traefik's own validation in containers. No public CA is reached. (b) Unit tests only. Decided: (a).

## Decisions shared by all phases

- New operations follow the naming of N3 and are listed at the gate of the phase that adds them.
- Each phase ends with its tests green, a browser check for UI phases, ruff clean on changed files, one commit on `feat/first-publication`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Server registry
  > Done: `src/kajenn_press/site/servers.py` (`servers.json` in the source bucket: name, IPv4, IPv6, agent URL; https, http only on loopback; no token stored); operations `server_add`, `server_list`, `server_remove` (48 operations); add and remove need the grant `servers` on `installation` and an idempotency key; list is open to any signed-in editor. Removal is refused while a site is bound to the server: the check reads the bindings' `server`, which Phase 2 adds. Tests: `tests/site/test_servers.py` (8).
  - Files: `src/kajenn_press/site/servers.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: per N7b-D2: `servers.json` in the source bucket (name, IPv4, IPv6, agent URL; token file names, never tokens); operations `server_add`, `server_list`, `server_remove` (refused while a site is bound to it).
  - Done: servers are added, listed and removed by the right grant only; a server with sites cannot be removed.

- [x] **Phase 2**: Bindings with server and canonical name
  > Done: bindings schema 2: origin → site id, state, server, `redirect` (None for the address, the address for its alias); each site has one address and at most one alias; schema 1 files read with the server `default`. Site info holds `server` and `alias`; `site_server_set` (publishing grant, lock, key; refuses an unknown server) sets them and rebinds a bound site, which is how a site moves. Publish binds the address and, when wanted, the alias (`www.` added or removed). A site server is created with its server name (`SITE_SERVER_NAME`, default `default`) and serves only its own bindings; an alias answers 301 to the address keeping the path. Server removal counts distinct sites. Tests: two servers on one bucket, alias redirect, move, removal refused, schema 1 read. Suites: main 216 passed, 12 skipped; Docker 9 passed.
  - Files: `published.py`, `publish.py`, `serving.py`, `deploy/docker/site_server.py`, `tests/site/`, `tests/docker/`.
  - Details: bindings schema 2: origin → site id, state, server, and the alias (`www.` or bare) that answers 301 to it; operation `site_server_set` (server and canonical choice, also before the first Publish; moving a site moves its binding); the site server is started with its server name and serves only its sites; the alias answers 301 keeping the path; a schema 1 bindings file is read as schema 2 with the server of the installation's own site server.
  - Done: two site servers on one bucket serve each its own sites; the alias redirects; moving a site moves it from one to the other.

- [ ] **Phase 3**: The agent and the proxy drivers
  - Files: `src/kajenn_press/agent/` (application, drivers `nginx.py`, `caddy.py`, `traefik.py`), `deploy/agent/` (image, systemd unit, sudoers example), `tests/agent/`, `tests/docker/`.
  - Details: per N7b-D1 and N7b-D4: actions `domain_add`, `domain_remove`, `domain_status`, `proxy_reload`; nginx driver writes a server block per domain and runs certbot (webroot), Caddy driver relies on on-demand TLS with an `ask` endpoint of the site server that answers 200 only for bound origins, Traefik driver writes one dynamic file per domain; every command runs from a fixed list with sudo where needed.
  - Done: unit tests of each driver; Docker test: Caddy with its internal CA serves a new domain over https after `domain_add`, without restart; `nginx -t` and Traefik validation pass on the generated files.

- [ ] **Phase 4**: DNS records and checks
  - Files: `src/kajenn_press/site/dns.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: per d-dns and N7b-D3: operation `dns_plan` (records to create for the domain and its alias, towards the server's addresses) and `dns_check` (what public resolvers answer, per record).
  - Done: the plan lists A and AAAA for both names; the check reports missing, wrong and correct records (resolvers replaced by a fake in tests).

- [ ] **Phase 5**: First publication in the Published site tab
  - Files: `src/kajenn_press/admin/pages/site.py`, `site.js`, `site.css`, `src/kajenn_press/site/publish.py`, `tests/admin/`.
  - Details: per the approved mockup: for a site never published, steps server → domain and canonical name → DNS records and check → Publish (pages, then `domain_add` on the agent, then certificate status) → address check; the same steps to move a site; operation `site_go_live` that orchestrates them and reports each outcome.
  - Done: matches the mockup in the browser against a local server registered with a local agent (Caddy internal CA).

- [ ] **Phase 6**: Deployment and documentation
  - Files: `deploy/agent/`, `deploy/docker/`, `xmldocs/booklet/install.xml`, `xmldocs/booklet/publication.xml`, `xmldocs/booklet/site-tab.xml`, `README.md`.
  - Details: install script of a server for each proxy (site server image, agent, sudoers, firewall note); booklets updated.
  - Done: full, admin and Docker suites green; booklets valid and rendered.
