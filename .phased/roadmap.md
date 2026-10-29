# kajenn-press implementation roadmap

Status: rewritten 2026-10-27 after the owner's redesign of the administration and of the publication model, recorded in `xmldocs/proposal/site-tab-redesign.xml`. Macros 1, 2 and 3b are finalized on main. Macro 3 is retired: the redesign supersedes it. No plan is active.

The product scope is `xmldocs/proposal/site-tab-redesign.xml`. `docs/01-visione.md` through `docs/14-release-storage.md` describe the previous model (catalog revisions, channels, releases) and are rewritten in Macro N10.

## Completed history

### Macro 1 (completed): Filesystem catalog and REST/MCP management

- Delivered: durable local catalog of sites, variants, drafts, named-block contracts, exact source revisions, media and resource copies through authenticated REST and MCP; restart, conflict and recovery contracts without a database.
- On main as `b50a5b5`. Archived plan: [filesystem-storage](done/filesystem-storage/plan.md).

### Macro 2 (completed): Templates, static rendering, preview and coherent publication

- Delivered: rendering of Gramlot/HtmlBuilder templates in a separate worker, private preview grants, channels, conditional activation and rollback of complete releases.
- On main as `3bfe65f`. Archived plan: [rendering-publication](done/rendering-publication/plan.md).

### Macro 3b (completed): websites and release serving from Genro Storage

- Delivered: export of active releases to a Genro Storage mount, the lightweight child `StaticSiteServerApplication`, the websites registry, the Docker composition with RustFS or a shared volume.
- On main through kajenn-org/kajenn-press#1 as `64fcad6`. Archived plan: [websites-release-serving](done/websites-release-serving/plan.md). Deferred findings C (internal `http` serving address), E (child object cache) and F (storage qualification on a real S3) stay open; F was addressed for Hetzner Object Storage by #6 and #7.

### Macro 3 (retired 2026-10-27): Gramlot administration and restored editors

- Phase 1 (authenticated multisite administration) shipped with #1. The site editor of `xmldocs/proposal/site-editor.xml` (shell, `render_draft`, page editor, resource editor, publishing panel) shipped with #5.
- Phases 2–4 and the deferred contracts are not carried forward: the redesign replaces navigation, editors and publication. Archived plan: [gramlot-administration](done/gramlot-administration/plan.md).

## Completed deployment

### kpress deployment (completed 2026-10-27)

- Plan: [kpress-deployment](done/kpress-deployment/plan.md). The websites manager runs at `https://kpress.genro.com` with previews at `https://preview.kpress.genro.com`, releases on Hetzner Object Storage.
- The installation stays useful after the redesign: Docker composition, nginx, TLS and the Hetzner bucket are the base of the Kajenn server that will serve sites.

## New macros

Order: N1 → N2 → N3 → N4 → N5, then N6–N9 in any order, then N10. Each macro gets its own detailed plan when it starts; this roadmap does not authorize later macros.

### N1 (completed 2026-10-27): Inventory against the redesign

- Result: `xmldocs/proposal/redesign-inventory.xml` (accepted) and the decisions of `xmldocs/proposal/site-tab-redesign.xml`, none open. Archived plan: [redesign-inventory](done/redesign-inventory/plan.md).
- Owner action before N3: enable versioning on the Hetzner bucket `kpress-releases` (not enabled on 2026-10-27) and on the local development bucket.

- Objective: map the redesign onto the existing code before changing it.
- Delivers: for each module of `src/kajenn_press/` (catalog, services, rendering, publication, admin, child) and for `deploy/`, what stays, what changes and what is removed; the REST/MCP operations that survive, change or go; the migration of existing catalogs, if any.
- Closes the open decisions of the proposal: Update on a locally changed copy, Library/site template conflicts, a removed slot, a template switch, SEO of dynamic iframe content.

### N2 (completed 2026-10-27, branch feat/page-bag): Page Bag, template slots and copies

- Result: library `src/kajenn_press/site/` and the page entry of `src/kajenn_press/rendering/`, with 58 tests in `tests/site/`; no REST/MCP change. Archived plan: [page-bag](done/page-bag/plan.md).

- Objective: the page as a Bag holding a template Bag, a contents Bag and assets, able to produce its static HTML.
- Delivers: the `kpress_slot` contract on hosting source nodes (`True` or a unique name); templates on Library, site and page level, linked or independent; copies carrying the original id; the Update operation with the list of affected pages and differences; slot kinds HTML, Markdown, dynamic iframe, resolver.

### N3 (completed 2026-10-28, branch feat/site-source): Site source zip and S3 versioning

- Result: `src/kajenn_press/site/` store, lock, receipts, audit and `SiteService`; 25 site operations on REST and MCP; Docker composition with a versioned `sources` bucket. Archived plan: [site-source](done/site-source/plan.md). Pending owner actions on Hetzner: `deploy/docker/HETZNER.md` step 6.

- Objective: one zipped source Bag per site, unpacked for editing and zipped again on save.
- Delivers: S3 versions per deliberate save; restore of a previous source; one editor at a time per site; export and import of a complete site as one zip; starting sites kept in Library.

### N4 (completed 2026-10-28, branch feat/page-publication): Per-page publication and Kajenn serving

- Result: page URLs and redirects; published page objects and the site index pinning versions; Publish, page and site rollback, maintenance (32 site operations); `src/kajenn_press/site/serving.py` with the local re-render cache; the demo publishes and serves the example site page by page. Old publication path removed after N5 (N4-D3). Archived plan: [page-publication](done/page-publication/plan.md). Pending owner actions on Hetzner: `deploy/docker/HETZNER.md` steps 6–7.

- Objective: one published object per page, versioned by S3, served by Kajenn.
- Delivers: Publish of the changed pages with selection; per-page rollback; site rollback through the source zip; re-rendering through resolvers with a local filesystem cache; `sitemap.xml`, `robots.txt` and 301 redirects generated at publication; maintenance mode.
- Replaces: channels, routes, candidates, builds and releases of Macro 2 and the release export of Macro 3b, as decided in N1.

### N5 (completed 2026-10-28, branches feat/visual-editor and feat/retire-old-path): Navigation and the Visual editor tab

- Result: Sites and Library navigation; the site tab with the Visual editor, the Pages and Contents drawer, the docked block editor and the Update plan of copies; the old administration and publication path removed (N4-D3). Archived plan: [visual-editor](done/visual-editor/plan.md).


- Objective: Sites and Library in the navigation tree; one tab per site; the Visual editor.
- Delivers: rendered site opening on the root page and navigable through its links; slot borders on command; detachable blocks in a floating window with CodeMirror, Jodit and Preview; the drawer with the Pages tree (logical, drag and drop, slots under each page) and the Contents tree (use count states and badge); drag of a content into a slot from the preview or the tree; marks for pages changed since publication and for outdated copies.

### N6 (completed 2026-10-29, branch feat/seo-tab): SEO tab

- Result: per-page SEO with root defaults and inheritance, SEO tags in the page head, sitemap and robots from the SEO, SEO checks in the tab and in the publish plan, the SEO tab with search and social previews and alt texts (38 site operations). Archived plan: [seo-tab](done/seo-tab/plan.md).


- Delivers: per-page SEO with root defaults, search and social previews, checks before publishing (titles, descriptions, alt texts, internal links), redirects on URL change, the 404 page as an ordinary page.

### N7 (completed 2026-10-29, branch feat/published-site): Published site tab

- Planned: command top bar with publish, rollback and management commands; iframe on the published site; first Publish (Kajenn server, domain, DNS with or without provider credentials, automatic TLS); optional private publication before going public.
- Result: site addresses in `bindings.json` of the release bucket, read by running site servers; private sites and signed private links; `publication_state`; the Published site tab with Publish, rollback, maintenance and private link (41 site operations). Archived plan: [published-site](done/published-site/plan.md).
- Not done here (N7-D1): the first publication on another server. While private or in maintenance the tab opens the private link in a new browser tab, not in the iframe (a cross-site cookie with SameSite=Lax does not reach the iframe).

### N7b (completed 2026-10-29, branch feat/first-publication): First publication on another server

- Result: a registry of servers (`servers.json`, grant `servers`); bindings schema 2 with server and alias (`www.` or the bare domain answers 301); site servers serve only their own sites and answer Caddy's `ask`; a server agent with four actions and nginx+certbot, Caddy on-demand and Traefik drivers; DNS records planned and checked through 1.1.1.1 and 8.8.8.8; Go live in the Published site tab; `deploy/agent/install.sh` (52 site operations). Archived plan: [first-publication](done/first-publication/plan.md).
- Planned: a registry of Kajenn site servers; domain and `www`; DNS with or without provider credentials; TLS, which Kajenn does not provide (no ACME client): a decision between a proxy with certificates (nginx and certbot, Caddy) and an ACME client in Kajenn comes first.

### N8 (completed 2026-10-29, branch feat/help-me): Help me

- Result: a Sonnet chat in the site tab with 24 tools (21 site operations, choices, CSS and SVG assets), SVG cleaning, chats per site in the source bucket, tokens and cost per chat and per site, the Help me pane, the key from a file of the owner (`compose.help.yaml`). Live checks passed ($0.06 for a two-page site, $0.05 for one page from the tab). Archived plan: [help-me](done/help-me/plan.md).
- Planned: a Sonnet chat in the site tab that interviews the user, offers fonts, colours and SVG drawings as clickable previews, and creates pages, templates and contents through the MCP operations; the conversation kept with the site; tokens and cost shown per chat and per site, for information only; one API key per installation; publishing stays an operator command.

### N9 (completed 2026-10-29, branch feat/languages): Languages

- Result: a main language and others per site; translations of contents and site texts with states missing, to update, to review; URLs with the language prefix (main without), redirects and SEO per language; one published object per page and language (schema 3), `hreflang`, sitemap of every language; the editor in one language at a time; Help me proposes translations to review; the example site in English and Italian (45 site operations). Archived plan: [languages](done/languages/plan.md).

- Planned: languages back into the model, the editor, the SEO and the publication; reopened by the owner on 2026-10-29.

### N10 (completed 2026-10-29, branch feat/documentation): Documentation

- Result: five xmldocs booklets with verified facts (site tab, templates, operations, publication, installation); the example site rewritten on the current product; `docs/01`–`docs/14` and their support files removed; README pointing to the booklets. Archived plan: [documentation](done/documentation/plan.md).
- Planned: `README.md` and `docs/` rewritten on the new model; `docs/01`–`docs/14` replaced or removed.

## Future work outside these macros

- The administration of a published site (Kajenn, Asqueel and Gramlot), when a site needs one.
- Asqueel/PostgreSQL behind resolvers and dynamic slots.
- Concurrent editing of one site by several people.

## Sequencing and scope controls

- Each macro starts with its own plan, reviewed by the owner; the plan is not authorization for later macros.
- A missing framework capability produces a concrete reproducer and a bounded upstream work item; sibling repositories are not edited as an incidental step.
- Every phase runs on Opus, never Fable.
