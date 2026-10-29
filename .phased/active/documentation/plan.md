# Context: feat/documentation
Parent: main
Mode: manual
Must not break: The full suite, the admin suite and the Docker suite keep passing (the example site contents change in Phase 6).
Must not break: Every statement about behaviour is verified in the code or by a test before it is written, and carries its source (`fact source="path:line" method="read|test|run"`).
Must not break: Persisted documents are in English; xmldocs documents are edited as XML and their HTML and Markdown are regenerated after every change.
Must not break: A public document never links or names a private one.

## Objective

Replace the documentation of the previous model with booklets of the current one. `docs/01`–`docs/14` (Italian, 2,876 lines) describe the catalog, channels, candidates, builds and releases removed in N5 Phase 8; the example site's texts still describe that model. The result: a few instruction booklets that say how to do one thing with what exists today, the README pointing to them, and an example site that describes the product it is published with.

Entry: main `bd7d3a6`. The design lives in `xmldocs/proposal/site-tab-redesign.xml` (N1–N9 decisions), `site-editor.xml`, `redesign-inventory.xml`; there is no booklet yet. Only archived plans in `.phased/done/` name files of `docs/`.

## Owner decisions (2026-10-29): all recommended options chosen

- **N10-D1 · Format.** (a) xmldocs booklets (`xmldocs/booklet/<name>.xml`, generated `.md` and `.html` committed), in English, each with verified facts and their sources. (b) Plain Markdown under `docs/`. Decided: (a); the type holds only verified behaviour, which is what the old documents lacked.
- **N10-D2 · Which booklets.** (a) Five: 1. Building a site in the site tab (Visual editor, slots, copies and Update, SEO, Published site, languages, Help me); 2. Writing a template (Gramlot build code, slots, iframe slots, site texts, assets, page data and resolvers); 3. The site operations over REST and MCP (the 45 operations by group, keys, lock, receipts, errors); 4. Publication and serving (page objects, index, bindings, private links, re-render cache, maintenance, rollback); 5. Installing and running (Docker composition, buckets with versioning, keys and secrets, external S3, Help me key, nginx; HETZNER.md stays the server runbook). (b) One booklet for everything. Decided: (a).
- **N10-D3 · `docs/`.** (a) Removed, with `admin-artifacts.json`, `admin-qualified-freeze.txt` and the `fonti-locali` files: their history stays in git and the archived plans keep their paths. (b) Moved to `docs/archive/`. Decided: (a).
- **N10-D4 · The example site.** (a) Its three pages are rewritten to describe the current product (site tab, per-page publication, languages, Help me), in English with the Italian home hero updated; the other Italian translations stay missing, which the site shows as English. (b) Unchanged. Decided: (a).

## Decisions shared by all phases

- Each booklet phase: write the XML, `xmldocs check` then `xmldocs render`, read the HTML in the browser, one commit. Facts are verified by reading the code at the cited line or by a test that covers it.
- Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Booklet "Building a site in the site tab"
  > Done: `xmldocs/booklet/site-tab.xml` (6 steps: open or create, pages and slots, SEO, languages, Help me, publish; rules, limits, 11 facts with sources), valid, rendered, read in the browser.
  - Files: `xmldocs/booklet/site-tab.{xml,md,html}`.
  - Done: every step is a path through the tab that exists today, with the facts that back it.

- [x] **Phase 2**: Booklet "Writing a template"
  > Done: `xmldocs/booklet/templates.xml` (build code, slots and iframe slots, Data pointers table, SEO head, resolvers; minimal template and the example's menu and language links; 8 facts), valid, rendered.
  - Files: `xmldocs/booklet/templates.{xml,md,html}`.
  - Done: the example layout and a minimal template both appear and match `examples/kajenn_press_site/layout.py` and the tests.

- [x] **Phase 3**: Booklet "The site operations over REST and MCP"
  > Done: `xmldocs/booklet/operations.xml`: calling (REST, MCP, answers, error statuses), editing session, idempotency keys, and five tables generated from `site/service.py` and the route docstrings: 45 rows, checked equal to `OPERATIONS`, each with arguments, permission, lock and key. Valid, rendered.
  - Files: `xmldocs/booklet/operations.{xml,md,html}`.
  - Done: the table lists exactly `OPERATIONS` of `site/service.py`, each with its permission and whether it needs the lock and a key.

- [x] **Phase 4**: Booklet "Publication and serving"
  > Done: `xmldocs/booklet/publication.xml` (objects and keys table, page object content, fingerprint, the site server's order of answers, rollback, maintenance, private sites and links; 10 facts). Valid, rendered.
  - Files: `xmldocs/booklet/publication.{xml,md,html}`.
  - Done: object names, index schema 3, bindings and private links match `published.py`, `publish.py`, `private.py`, `serving.py`.

- [x] **Phase 5**: Booklet "Installing and running"
  > Done: `xmldocs/booklet/install.xml` (workstation with services table, server behind a proxy with external buckets, Help me key, tests; rules, limits, 5 facts); `deploy/docker/README.md` points to it. Valid, rendered.
  - Files: `xmldocs/booklet/install.{xml,md,html}`, `deploy/docker/README.md` (pointer).
  - Done: the commands are the ones the Docker tests run.

- [x] **Phase 6**: The example site describes the current product
  > Done: the six pages rewritten on the current product (site tab, templates and slots, copies and Update, S3 versions, per-page publication, site server, SEO, languages, Help me, Docker start), with the same structure and classes; Italian home hero updated; home page name, descriptions and footer texts no longer name releases; test assertions follow the new texts. Suites: main 207 passed, 12 skipped; Docker 9 passed.
  - Files: `examples/kajenn_press_site/pages/*.html`, `publish.py` (descriptions), `tests/site/`, `tests/docker/`.
  - Done: no page names channels, candidates, builds or releases of the old model; full and Docker suites green.

- [ ] **Phase 7**: `docs/` removed, README pointing to the booklets
  - Files: `docs/` (removed per N10-D3), `README.md`.
  - Done: `git grep` finds no link to `docs/` outside `.phased/done/`; README lists the five booklets.
