# Context: feat/seo-tab
Parent: main
Mode: manual
Must not break: The full suite (two interpreters, RustFS endpoint), the admin suite and the Docker suite keep passing.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-seo-inherit: an empty field takes the root value, never the parent's; d-dynamic-seo: iframe slots carry a static fallback).
Must not break: Scripts and marks added for the preview never reach published HTML; the preview iframe never gets `allow-same-origin`.
Must not break: Gramlot constitution: Source, Data, bindings and components; no imperative DOM manipulation. Sibling repositories are not edited; a missing Gramlot capability becomes an upstream item.
Must not break: Every UI phase is checked in a real browser (Browser pane) against its approved mockup before it is closed.

## Objective

Give each page its own SEO and the site its defaults, edited in the SEO tab of the site tab. The root page (URL `/`) holds the site defaults: site name, public origin, organisation, sharing image, robots. Every page has public URL, title, description, canonical, robots, social title, description and image, alt texts of its images, JSON-LD. An empty field takes the root value and the tab shows that value beside it. The tab shows the page as a search result and as a social share. Checks report missing or duplicate titles, missing descriptions, images without alt, broken internal links, and indexed pages with an iframe slot without fallback; Publish shows the same checks. The rendered page carries the SEO in its `head`; `sitemap.xml` leaves out pages with `noindex`; `robots.txt` follows the root robots. The 404 page is the page at `/404/`, always `noindex`.

Entry: main `594e755`; the 35 site operations; page Bag sections `template`, `slots`, `unplaced`, `assets`, `data`; `Site.set_page_url` already adds the 301 redirect and collapses chains; `site/serving.py` already serves `/404/`, `sitemap.xml` and `robots.txt` from the site index; publish plan already carries per-page warnings.

## Owner decisions (2026-10-28): all recommended options chosen; mockup `mockups/seo-tab.html` approved

- **N6-D1 · How the SEO reaches the HTML.** (a) kpress writes it into the `head` of the rendered page, after the template: `title`, `meta description`, `link canonical`, `meta robots`, Open Graph and Twitter tags, JSON-LD; an existing `title` or `meta description` of the template is replaced. Templates need no change. (b) The SEO travels as Data (`seo.title`, …) and each template binds it. Decided: (a).
- **N6-D2 · Where the SEO is stored.** (a) A new page section `seo` (Bag of fields); the root page's section also holds the site defaults. (b) A site section `seo` keyed by page id. Decided: (a): the SEO travels with the page, its fingerprint changes when the SEO changes, and Publish selects it.
- **N6-D3 · Alt texts.** (a) The SEO tab lists the images of the page's slot contents and of its template with their alt; editing one changes this page's copy (a local change, kept out of later Update plans per d-update-local). (b) The SEO tab only reports images without alt; the operator fixes them in the block editor. Decided: (a).
- **N6-D4 · Public origin.** Canonical URLs, `og:url` and the sitemap need the absolute origin. (a) A root default `origin` (for example `https://kajenn.org`); the sitemap keeps using the serving binding. (b) Canonicals relative to the page. Decided: (a); an empty origin leaves canonical and `og:url` out and is reported by the checks.
- **N6-D5 · Checks and Publish.** (a) Checks are warnings: Publish shows them and never refuses. (b) Broken internal links refuse Publish. Decided: (a).

## Decisions shared by all phases

- New operations follow the naming of N3 and are listed at the gate of the phase that adds them.
- The site index schema changes in Phase 3 (per-page `indexable`); indexes of the previous schema fail closed and the site is published again.
- Each phase ends with its tests green, a browser check for UI phases, ruff clean on changed files, one commit on `feat/seo-tab`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: SEO in the site model
  > Done: `src/kajenn_press/site/seo.py` (fields, `set_page_seo`, `effective_seo`, `page_images`, `set_image_alt`); page section `seo` (sources saved before N6 get it empty on load); `page_fingerprint` includes the effective SEO, so a root default change marks every inheriting page changed; operations `page_seo_set` and `page_alt_set` (37 site operations); `site_read` returns `seo`, `seo_effective` and `images` per page. Inheritance: title from the page name; description, robots and social image from the root; canonical from origin + URL; social title and description from the page's own; JSON-LD per page, the root page gets an Organization JSON-LD from the organisation when it has none. An `alt=""` is decorative, not missing. `tests/site/test_seo.py` (14 tests) and one service test. Main suite: 154 passed, 11 skipped.
  - Files: `src/kajenn_press/site/model.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: page section `seo` (N6-D2); `Site.page_seo` (stored fields) and `Site.effective_seo` (stored, else root value, else derived: title from the page name, canonical from origin + URL, social fields from the page fields); the root page is the page at `/` and only it accepts the default fields; the page at `/404/` is always `noindex`. Operation `page_seo_set` (fields; an empty value clears the field); with N6-D3 (a), operation `page_alt_set` (page, image, alt): sets the alt in this page's copy of the content or, for a template image, in the page's template copy, and records it as a local change; `site_read` returns stored and effective SEO per page. Sources of earlier sites get an empty `seo` section when read.
  - Done: inheritance follows d-seo-inherit (root, never parent); moving a page in the tree does not change its effective SEO; the fingerprint of a page changes when its SEO changes.

- [x] **Phase 2**: SEO in the rendered page
  > Done: `seo.head_html` builds title, description, canonical, robots, Open Graph, Twitter card and JSON-LD (every `<` of JSON-LD as `\u003c`); `page_request` carries it as `head`, so preview, Publish and the site server's re-render write the same tags; the worker drops the template's own title, description, robots, canonical, `og:*`, `twitter:*` and JSON-LD nodes before rendering and writes the head before `</head>` (a template without head is refused). The social image is published with the page's assets; `og:image` is written only with a public origin. Test: `test_the_rendered_page_carries_the_seo_in_its_head`. Main suite: 155 passed, 11 skipped.
  - Files: `src/kajenn_press/site/render.py` or a new `src/kajenn_press/site/seo.py`, `tests/site/`.
  - Details: per N6-D1, the effective SEO written into the `head` of the HTML returned by the worker, for preview and for publication alike; values escaped; JSON-LD checked as JSON and written with `</` escaped; Open Graph image as the published asset URL (absolute when an origin is set).
  - Done: the published HTML of the example site carries title, description, canonical, robots, Open Graph and JSON-LD; a template `title` is replaced, not duplicated.

- [x] **Phase 3**: Sitemap and robots from the SEO
  > Done: page objects and index entries carry `indexable` (schema 2); `sitemap.xml` lists only indexable pages; `robots.txt` is `Disallow: /` when the root page is not indexable. The root robots is not a separate index key: the root page entry decides. The current index of schema 1 reads as absent for Publish, so the next Publish writes every selected page and a schema 2 index; until then the site server refuses that index (fail closed). Tests: noindex page out of the sitemap, noindex root closes the site, Publish replaces a schema 1 index. Main suite: 157 passed, 11 skipped.
  - Files: `src/kajenn_press/site/published.py`, `publish.py`, `serving.py`, `tests/site/`.
  - Details: the site index carries per page `indexable` and the root `robots`; `sitemap.xml` lists only indexable pages; `robots.txt` disallows everything when the root robots is `noindex`; schema bump (shared decision).
  - Done: a `noindex` page is served but missing from the sitemap; a site-wide `noindex` gives `Disallow: /`.

- [ ] **Phase 4**: SEO checks
  - Files: `src/kajenn_press/site/seo.py`, `model.py`, `publish.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: operation `seo_check` (site-wide and per page): missing title (effective title equal to the page name is accepted), duplicate titles among indexable pages, missing description, images without alt (slot copies and template), internal links whose path is neither a page URL, a redirect source nor an asset, indexable pages with a `kpress_iframe` slot without fallback, empty origin. The publish plan adds them to each page's warnings (N6-D5).
  - Done: each check has a test that triggers it and one that clears it.

- [ ] **Phase 5**: The SEO tab
  - Files: `src/kajenn_press/admin/pages/site.py`, `site.js`, `site.css`, `tests/admin/`.
  - Details: per the approved mockup: page list with check state, site defaults on the root page only, page fields with the inherited value beside each empty field, URL change with the 301 note, alt texts per N6-D3, search and social previews updated while typing, page and site checks; saves through `page_seo_set`, `page_url_set` and `page_alt_set`.
  - Done: matches the mockup in the browser; a field edited shows in both previews and, after Publish, in the served page.

- [ ] **Phase 6**: Example site and Docker
  - Files: `examples/kajenn_press_site/publish.py`, `tests/docker/`, `README.md`, `deploy/docker/README.md`.
  - Details: the example site sets its root defaults and per-page descriptions; the Docker test checks the SEO tags of a served page and the sitemap.
  - Done: full, admin and Docker suites green.
