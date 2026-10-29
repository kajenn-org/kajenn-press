# Context: feat/published-site
Parent: main
Mode: manual
Must not break: The full suite (two interpreters, RustFS endpoint), the admin suite and the Docker suite keep passing.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-publish-unit, N4-D1, N4-D2, N4-D3 in particular).
Must not break: Public pages carry no session and no cookie; the private link is the only exception and works only for its site and until it expires.
Must not break: Credentials never reach Bags, zips, logs, git or responses; the site server keeps read-only access to the release bucket.
Must not break: Gramlot constitution: Source, Data, bindings and components; no imperative DOM manipulation. Sibling repositories are not edited; a missing Gramlot capability becomes an upstream item.
Must not break: Every UI phase is checked in a real browser (Browser pane) against its approved mockup before it is closed.

## Objective

Give the operator the Published site tab: a top bar with the state of the site (public, private, maintenance), its address, Publish with the plan and its warnings, page and site rollback, maintenance on and off, and a private link; in the center an iframe on the published site. A site gets its public address from the administration, without restarting the site server. A site can be published privately first and made public later; during maintenance and while private, the private link shows the real site.

Entry: main `0c7e9bc`; the 38 site operations, among them `publish_plan`, `publish`, `page_versions`, `page_rollback`, `site_rollback`, `maintenance_set`; `site/serving.py` with bindings fixed at start (`/config/sites.json` written by the demo publisher); the root page SEO field `origin` (N6).

Known facts that change the proposal's "First publication":
- Kajenn has no automatic TLS (no ACME client in the package); on the Hetzner host TLS comes from nginx and certbot (`deploy/docker/HETZNER.md`).
- Kajenn Press has no registry of Kajenn servers and no DNS provider integration.
- `deploy/docker/HETZNER.md` still describes the removed preview host and `KPRESS_PREVIEW_HOST`.

## Owner decisions (2026-10-29): all recommended options chosen; mockup `mockups/published-tab.html` approved

- **N7-D1 · Scope.** (a) This macro: the Published site tab, addresses managed from the administration for the installation's own site server, private publication, private link. The first publication on another server (server registry, DNS with provider credentials, TLS) becomes its own macro N7b, after a decision on TLS. (b) Everything in one macro. Decided: (a).
- **N7-D2 · How the site server learns its sites.** (a) Kajenn Press writes `bindings.json` (origin → site id and state) to the release bucket; the site server reads it like a site index, with the same cache interval, so a new address works without a restart. (b) The static `/config/sites.json` stays, and a new address needs a restart. Decided: (a); `sites.json` is removed.
- **N7-D3 · The address of a site.** (a) The root page's public origin (N6) is the address: one value for canonical URLs, sitemap and binding; changing it moves the binding. (b) A separate address field. Decided: (a).
- **N7-D4 · Private link and private state.** (a) A link `/_private/<token>`: the token is signed (HMAC) with a secret shared by websites and the site server, names the site and an expiry (8 hours or 7 days); the site server answers with an HttpOnly, Secure-when-https, SameSite=Lax cookie for that host only, and redirects to `/`. With that cookie a private site and a site in maintenance are served as they are. A private site answers 404 to everyone else. (b) A separate private host per site. Decided: (a); revoking every link means rotating the secret.
- **N7-D5 · Iframe on the published site.** (a) The iframe loads the public address (or the private link while private or in maintenance), `sandbox="allow-scripts allow-same-origin"`: the published site keeps its own origin, never the administration's. (b) The administration renders the published HTML itself in `srcdoc`. Decided: (a); a site whose address does not resolve from the operator's browser shows the address and the reason instead.

## Decisions shared by all phases

- New operations follow the naming of N3 and are listed at the gate of the phase that adds them.
- Each phase ends with its tests green, a browser check for UI phases, ruff clean on changed files, one commit on `feat/published-site`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Bindings in the release bucket
  > Done: `bindings.json` (schema 1, origin -> {site_id, state}) in the release bucket; Publish checks the address before writing pages and binds the site's root public origin after the index (normalised by `publication.routes.origin`: https, or http on loopback); an address of another site is refused with `conflict`; an empty origin unbinds. The site server reads the bindings with its cache interval (the last valid ones are kept) and creates a reader per bound site on demand. `sites.json`, `--config` and the `sites-config` volume are gone; the Docker test finds the site through `site_list`. Tests: an address set later is served by a running server and the old one answers 404; two sites cannot share an address. Suites: main 167 passed, 11 skipped; Docker 10 passed.
  - Files: `src/kajenn_press/site/publish.py`, `published.py`, `serving.py`, `deploy/docker/site_server.py`, `deploy/docker/compose.yaml`, `examples/kajenn_press_site/publish.py`, `tests/site/`, `tests/docker/`.
  - Details: per N7-D2 and N7-D3: `bindings.json` (canonical JSON, schema, origin → {site_id, state}) written by Publish from the root origin; state `public` or `private`; an origin already bound to another site is refused; the site server reads it with its cache interval and serves only bound origins; `sites.json` and the `sites-config` volume go away.
  - Done: an address set after the site server started is served within the cache interval; changing the origin moves the binding; two sites cannot share an origin.

- [x] **Phase 2**: Private state and private link
  > Done: `src/kajenn_press/site/private.py` (HMAC-SHA256 tokens naming site and expiry, 8 hours or 7 days, cookie `kpress_private`); operations `site_visibility_set` (binds the site's address public or private, also before the first Publish) and `private_link` (40 site operations). The site server answers `/_private/<token>` with 303 to `/` and an HttpOnly cookie (Secure on https, SameSite=Lax, for that host); a private site answers 404 and a site in maintenance 503 without a valid cookie; what the cookie shows carries `cache-control: private, no-store`; no other response sets a cookie. Docker: `credentials.py` writes one `private_link` secret into the websites and site-server volumes (the unused `preview_secret` is gone); websites signs, the site server checks. Tests: private site hidden and opened by its link, forged, foreign and expired tokens refused, maintenance bypass, Docker private link during maintenance, secret absent from storage and git. Suites: main 169 passed, 11 skipped; Docker 10 passed.
  - Files: `src/kajenn_press/site/serving.py`, a new `src/kajenn_press/site/private.py`, `service.py`, `application.py`, `deploy/docker/`, `tests/site/`, `tests/docker/`.
  - Details: per N7-D4: operations `site_visibility_set` (public or private) and `private_link` (expiry); the shared secret generated by the `secrets` service into both secret volumes; `/_private/<token>` sets the cookie and redirects; a private site answers 404 without the cookie; maintenance answers 503 without it; the cookie never appears on other responses.
  - Done: a private site is invisible without the link and visible with it; an expired or foreign token is refused; making the site public serves it to everyone.

- [ ] **Phase 3**: Publication state for the tab
  - Files: `src/kajenn_press/site/publish.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: operation `publication_state` (address, state public/private/maintenance, time of the last Publish, pages changed since, index version); `site_versions` and `page_versions` already give the rollback lists.
  - Done: the state follows Publish, maintenance and visibility changes.

- [ ] **Phase 4**: The Published site tab
  - Files: `src/kajenn_press/admin/pages/site.py`, `site.js`, `site.css`, `tests/admin/`.
  - Details: per the approved mockup: top bar with state, address, Publish panel (plan, selection, warnings), Rollback panel (page or whole site, versions with the one online), maintenance toggle, private link panel with copy and Make public; iframe per N7-D5.
  - Done: matches the mockup in the browser; Publish, a page rollback, maintenance and the private link work from the tab against the local demo.

- [ ] **Phase 5**: Documentation and Docker
  - Files: `README.md`, `deploy/docker/README.md`, `deploy/docker/HETZNER.md`, `tests/docker/`.
  - Details: HETZNER.md without the preview host, with the source bucket and the site server behind nginx; the Docker test covers an address set at run time, the private link and maintenance bypass.
  - Done: full, admin and Docker suites green.
