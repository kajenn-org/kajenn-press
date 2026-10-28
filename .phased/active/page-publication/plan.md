# Context: feat/page-publication
Parent: main
Mode: manual
Must not break: The existing tests keep passing, including the Docker suite. The current channels, builds, releases, export and child keep working until the old code is removed, which happens only when no caller needs it (decision N4-D3).
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-publish-unit, d-publish-select, d-rerender-cache, d-resolver-config, d-resolver-output, d-dynamic-seo, d-seo-inherit in particular).
Must not break: Published objects hold no credential; the serving server holds read-only release credentials and never source credentials; resolver connections come from the serving server's deployment.
Must not break: The Hetzner installation is changed only with the owner's go-ahead, after versioning is enabled on `kpress-releases`.
Must not break: Real tests against real Bags, the real render worker and the versioned RustFS endpoint; never run `ruff format` over untouched files.

## Objective

Publish a site page by page. Each page becomes one published object in the release bucket, versioned by S3, holding its sources and its pre-rendered HTML. One site index per site, also versioned and written last, says which version of each page object is online, its URL, redirects, `sitemap.xml`, `robots.txt` and whether the site is in maintenance. Publish sends the pages changed since the last publication, selected by the operator. A page rolls back to an earlier version; the whole site rolls back through its source version. A Kajenn server application serves a site from its index and page objects, answers redirects and maintenance, and re-renders pages that use resolvers into a local filesystem cache.

Entry: N3 on main (`4b8cb3b`): `SiteService`, `SourceStore`, the page renderer in the worker (`render_page`), the 25 site operations. Inventory: `xmldocs/proposal/redesign-inventory.xml`, section "Publication and serving".

Known facts (2026-10-28):
- Versioning is not enabled on the Hetzner release bucket `kpress-releases`; the old release layout (`artifacts/`, `manifests/`, `pointers/`) lives there and stays readable.
- `page_request` gives asset URLs as `data:` URLs (`src/kajenn_press/site/render.py`); publication must give real URLs.
- The current child serves sealed bundles with `cache-control: immutable` for assets (`src/kajenn_press/publication/serving.py:43`) and a manifest cached for `cache_seconds` (`src/kajenn_press/child.py:27`).
- A page has no URL attribute yet; the SEO tab (N6) owns titles and descriptions, but Publish needs a URL per page now.

## Owner decisions (2026-10-28): all recommended options chosen

- **N4-D1 · Asset URLs.** (a) Content addressed and shared by the whole site: `/_assets/<sha256>.<ext>`, served with `immutable`, so an asset used by many pages is stored once per content. (b) Per page: `/_pages/<page id>/<asset name>`. Decided: (a).
- **N4-D2 · Coherence of a publication.** (a) The site index pins the S3 version id of each page object; pages are written first, the index last, so a reader always sees a complete set; rolling a page back writes an index pointing at an older version, without rewriting the page. (b) The index lists page keys only and rollback copies an old page version as current. Decided: (a).
- **N4-D3 · Removal of the old publication path** (channels, candidates, builds, bundles, pointers, the in-process public serving and its operations). (a) After N5, when the administration no longer calls it. (b) In N4. Decided: (a).
- **N4-D4 · Checks before Publish.** (a) Empty slots, unplaced contents and SEO problems are warnings the operator sees; a page that fails to render is not published. (b) Empty slots block. Decided: (a).
- **N4-D5 · Private link to a site in maintenance and private publication before going public.** Moved to N7 with the Published site tab. Decided: yes.

## Decisions shared by all phases

- New operations follow the naming of N3 (no collision with existing names); proposed at the gate of the phase that adds them.
- Each phase ends with its tests green (full suite with the three interpreters and the RustFS endpoint), ruff clean on changed files, one commit on `feat/page-publication`.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Page URLs and redirects in the site model
  > Done: every page has a `url` attribute: the first page `/`, the others a slug of their name (accents transliterated to ASCII), unique among pages and redirect sources; new site section `redirects`; `Site.set_page_url` validates the path (starts with `/`, no query, fragment, spaces, `//` or dot segments), refuses a path of another page, records old -> new, retargets redirects that pointed at the old path and drops a redirect whose path is taken back; operation `page_url_set` (26 site operations); `site_read` returns URLs and redirects. `tests/site/test_page_urls.py` (13 tests).
  > Suite: 228 passed, 20 skipped (the new Docker test is skipped without `KAJENN_DOCKER`), 0 failed.
  - Run: opus / high
  - Files: `src/kajenn_press/site/model.py`, `src/kajenn_press/site/service.py`, `src/kajenn_press/application.py`, `tests/site/`.
  - Details: every page has a URL path (the first page `/`), unique in the site; changing it records a redirect from the old path; a redirect never points at itself and chains collapse; one operation to set a page URL.
  - Done: URLs unique, redirects recorded and collapsed, the operation on REST and MCP.

- [x] **Phase 2**: Published page object and site index
  > Done: `src/kajenn_press/site/published.py`: `PublishedPage`, `pack_page`/`unpack_page` (deterministic zip: `page.json` with id, URL, fingerprint, HTML SHA-256 and the page Bag in TYTX; `index.html`; `assets/<sha256>.<ext>` checked against their content), `make_index`/`read_index` (schema, site id, source version, maintenance, pages with URL, key, pinned version id, fingerprint and asset names, redirects; unique URLs), `page_fingerprint` (name, URL and page Bag). `tests/site/test_published.py` (8 tests).
  > Deviation: `sitemap.xml` and `robots.txt` are not stored in the index; the serving server builds them from the index and its own public origin, which the manager does not know at Publish time (it arrives with the first Publish in N7).
  - Run: opus / high
  - Files: new `src/kajenn_press/site/published.py`, `tests/site/`.
  - Details: a published page object (zip): the page Bag, its rendered HTML, its asset bytes by content address, the digest of the page it was made from; the site index (JSON): for each page its URL, object key and pinned version id (N4-D2), assets by content address, redirects, `sitemap.xml` and `robots.txt` text, maintenance flag, the source version it was published from; read and write with integrity checks.
  - Done: objects and index survive a round trip; a malformed one fails closed.

- [ ] **Phase 3**: Publish
  - Run: opus / high
  - Files: new `src/kajenn_press/site/publish.py`, `src/kajenn_press/site/render.py`, `src/kajenn_press/site/service.py`, `src/kajenn_press/application.py`, `tests/site/`, `tests/api/`.
  - Details: a Publish plan lists the pages changed since the last publication (page digest against the index), all selected, with the warnings of N4-D4; Publish saves the source, renders each selected page with real asset URLs (N4-D1) in the worker, writes the page objects (new S3 versions), then the index with the pinned versions, `sitemap.xml` and `robots.txt`; records the audit entry; a page that fails to render is reported and left as it was.
  - Done: the first Publish puts every page online; a second Publish after one edit writes one page object and a new index; an unselected changed page stays at its previous version.

- [ ] **Phase 4**: Rollback
  - Run: opus / high
  - Files: `src/kajenn_press/site/publish.py`, `src/kajenn_press/site/service.py`, `src/kajenn_press/application.py`, `tests/site/`.
  - Details: list the versions of a page object; roll a page back by writing an index that pins an older version; roll the site back by restoring a source version and publishing every page from it; both recorded in the audit log.
  - Done: a page rollback changes only that page; a site rollback serves the pages of the chosen source version.

- [ ] **Phase 5**: Kajenn server application
  - Run: opus / high
  - Files: new `src/kajenn_press/site/serving.py` (or the evolution of `child.py`, decided at the gate), `tests/site/`, `tests/child/`.
  - Details: binds public origins to site indexes in the release bucket (read-only credentials); serves page HTML by URL, assets by content address with `immutable`, 301 for redirects, `sitemap.xml`, `robots.txt`, the 404 page; follows a new index within its cache interval; pages whose template uses resolvers are re-rendered by the worker with the server's named connections and kept in a local filesystem cache for the resolver's `cache_time` (d-rerender-cache); a new publication of a page discards its cached copy.
  - Done: a published site is served exactly as rendered; a redirect answers 301; a resolver page refreshes after its cache time; the local cache survives a restart.

- [ ] **Phase 6**: Maintenance and the Docker composition
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `src/kajenn_press/application.py`, `deploy/docker/`, `tests/docker/`.
  - Details: an operation sets and clears maintenance (a flag in a new index); the server answers maintenance pages with 503 and `retry-after`; the Docker child serves the new layout from the versioned release bucket; the release bucket in RustFS gets versioning; the Mac demo publishes the Kajenn Press example site from `examples/kajenn_press_site/layout.py`.
  - Done: the Docker suite passes with a site published page by page, maintenance on and off, a page rollback served.

- [ ] **Phase 7**: Hetzner steps
  - Run: opus / high
  - Files: `deploy/docker/HETZNER.md`, `deploy/docker/README.md`.
  - Details: enable versioning on `kpress-releases`; how a Kajenn server on the host serves a published site (left unapplied until public serving from the host is decided).
  - Owner actions: enable versioning on `kpress-releases`; approve any command on the server.
  - Done: the steps written; applied only with the owner's go-ahead.

## Notes

- SEO fields beyond the URL (title, description, social, JSON-LD, checks) belong to N6; Publish writes what the site model holds at that time.
