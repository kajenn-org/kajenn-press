# kajenn-press

Site editing and publishing for the Genro family, served by Kajenn.

A site's source is one zipped Bag on a versioned S3 bucket: templates (Gramlot or
HtmlBuilder Source with slots marked `kpress_slot`), contents, assets and pages. A page
holds copies, not references, each carrying the id of its original, so an update reaches
pages only when the operator asks for it. Publishing writes one object per page to a
versioned release bucket and a site index that pins the version online; a Kajenn server
application serves the pages, renders pages with resolvers again into a local cache, and
answers redirects, `sitemap.xml`, `robots.txt` and maintenance. Every page has its SEO
(title, description, canonical, robots, social share, JSON-LD, alt texts); the root page
holds the site defaults, and checks before Publish report missing descriptions, duplicate
titles, images without alt and broken internal links. A site can have several
languages: each content and site text has one translation per language, marked missing,
to update or to review; URLs carry the language as a prefix (the main language has none);
pages carry `hreflang` and the sitemap lists every language. A site's address is its root
page's public origin: Publish binds it in the release bucket, where running site servers
read it. A site can be private, or in maintenance, and still be seen through a signed
private link. The same operations are offered on REST, MCP and in the Gramlot
administration, whose site tab has the Visual editor, SEO and Published site tabs, and
Help me: a Sonnet chat that builds pages, templates and contents through the same
operations, with tokens and cost shown per chat and per site.

## Booklets

| Booklet | For |
|---|---|
| [Building a site in the site tab](xmldocs/booklet/site-tab.md) | Operators: pages, slots, copies, SEO, languages, Help me, publication |
| [Writing a template](xmldocs/booklet/templates.md) | Template authors: build code, slots, site texts, assets, resolvers |
| [The site operations over REST and MCP](xmldocs/booklet/operations.md) | Programs and agents: the 45 operations, keys, lock, errors |
| [Publication and serving](xmldocs/booklet/publication.md) | Objects in the release bucket, the site server, rollback, private links |
| [Installing and running](xmldocs/booklet/install.md) | Docker composition, external buckets, Help me key, tests |

The design and its decisions are in `xmldocs/proposal/site-tab-redesign`; the plan of work
in `.phased/roadmap.md`.

## Layout

| Path | Content |
|---|---|
| `src/kajenn_press/site/` | Site and page model, slots, copies and Update, linked templates, SEO and its checks, source store on S3, editing lock, receipts, Publish, rollback, addresses and private links, the site server |
| `src/kajenn_press/rendering/` | Render worker: Gramlot/HtmlBuilder engines, content preparation (nh3), page rendering, connection resolvers |
| `src/kajenn_press/application.py` | Kajenn REST/MCP application of the site operations, `create_server` |
| `src/kajenn_press/help/` | Help me: tools from the site operations, SVG cleaning, the chat loop and its store |
| `src/kajenn_press/admin/` | Gramlot administration: navigation Sites/Library, the site tab with the Visual editor, SEO and Published site tabs |
| `deploy/docker/` | Docker composition (manager, RustFS, demo publisher and site server), nginx example, Hetzner runbook |
| `examples/kajenn_press_site/` | The Kajenn Press site in English and Italian: layout, contents, site texts, assets and `publish.py` |

## Run the tests

The tests need a render interpreter, an S3 endpoint with versioning and, for the
administration tests, an admin interpreter; `deploy/docker/README.md` describes them.

```bash
.venv/bin/python -m pytest -q tests
```

## Run it

```bash
cp deploy/docker/.env.example deploy/docker/.env
docker compose -f deploy/docker/compose.yaml --profile demo up -d --build
```

The administration is at http://kpress.localhost:8875/admin/ (user `operator`); the
example site published page by page is at http://press.localhost:8877/.
