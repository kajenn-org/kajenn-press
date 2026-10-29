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
titles, images without alt and broken internal links. The same operations are offered on
REST, MCP and in the Gramlot administration.

The design is in `xmldocs/proposal/site-tab-redesign` and the plan in `.phased/roadmap.md`.
The documents `docs/01`–`docs/14` describe the previous catalog and release model and are
rewritten with the documentation macro (N10).

## Layout

| Path | Content |
|---|---|
| `src/kajenn_press/site/` | Site and page model, slots, copies and Update, linked templates, SEO and its checks, source store on S3, editing lock, receipts, Publish, rollback, the site server |
| `src/kajenn_press/rendering/` | Render worker: Gramlot/HtmlBuilder engines, content preparation (nh3), page rendering, connection resolvers |
| `src/kajenn_press/application.py` | Kajenn REST/MCP application of the site operations, `create_server` |
| `src/kajenn_press/admin/` | Gramlot administration: navigation Sites/Library, the site tab with the Visual editor and the SEO tab |
| `deploy/docker/` | Docker composition (manager, RustFS, demo publisher and site server), nginx example, Hetzner runbook |
| `examples/kajenn_press_site/` | The Kajenn Press site: layout, contents, assets and `publish.py` |

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
