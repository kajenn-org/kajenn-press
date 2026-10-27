<!-- generated from redesign-inventory.xml by xmldocs: do not edit, edit the XML -->

## Kajenn Press: inventory of the code against the site tab redesign
*Proposal · redesign-inventory · 2026-10-27 · draft*

### Problem

 (→ proposal/site-tab-redesign#site-tab-redesign) changes the administration and the publication model. Before any code changes, every part of the existing code, every REST/MCP operation, every test suite and every deployment file needs a stated fate, and the upstream capabilities the redesign relies on need to be checked.

Classification used throughout: `keep` (unchanged), `change` (kept and adapted), `replace` (removed, a named new part takes its role), `remove` (removed with no successor). Capabilities are `exists`, `partial` or `missing`.

### Proposed solution

#### Upstream capabilities

Repositories read on 2026-10-27: genro-storage `dd62bfd`, genro-bag `2293047`, kajenn `6ac7e58`, gramlot `d01bf3d`; genro-builders 0.30.0 as installed in the kajenn-press environment. The kajenn-press environment installs genro-storage 0.8.4, genro-bag 0.28.0 and kajenn 0.5.0 from PyPI; the checkouts read here can differ from those releases. Gramlot is not installed in the kajenn-press development environment; the Gramlot checks ran in the Gramlot checkout's own environment.

*Summary*

| Need | Status | Gap |
|---|---|---|
| S3 object versioning: list, read a version | exists | — |
| S3 object versioning: restore a version as current | missing | no restore API |
| Zip archive as a mount, zip export of a node | exists | writing a zip over S3 not verified |
| Bag with nested Bags and bytes to one file and back | partial | lossless in TYTX JSON and pickle only; no zip |
| Zipped Bag file | missing | no `Bag.to_zip` / `from_zip` |
| Resolvers with a time-based cache | exists | synchronous `load()` only |
| Custom `kpress_slot` attribute on source nodes | exists | client renderer not checked |
| `node_label`, dotted paths, find by attribute | exists | — |
| Hosting containers in static rendering | partial | layout widgets need the JS runtime |
| Editors CodeMirror, Jodit, HTML preview | exists | — |
| Detachable floating window with tabs | missing | investigated (GC-185), not implemented |
| Drag from a tree onto a node of the same page | exists | — |
| Drop into a rendered page inside an iframe | missing | excluded by design |
| Kajenn serving of storage content, response cache | partial | no storage response, no cache |
| Maintenance mode for one site | missing | only whole-server 503 outside RUNNING |

#### Genro Storage

- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:180` · 2026-10-27 — The S3 backend sets `version_aware=True` by default.
- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:549` · 2026-10-27 — The versioning capability is derived from the s3fs client only; the bucket's versioning state is never queried.
- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:788` · 2026-10-27 — `get_versions(path)` lists versions with id, latest flag, date, size and etag; any exception returns an empty list.
- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:847` · 2026-10-27 — `open_version(path, version_id)` opens a version for reading; `delete_version` follows at line 886.

No restore, rollback or promote function exists in genro-storage: a search for them in `src/` found nothing. Restoring today means reading a version and writing it as the current object; this was not tried against S3.

- S3-compatible servers without ListObjectVersions need `version_aware=False`. Whether the Hetzner bucket `kpress-releases` has versioning enabled was not checked. · `genro-storage@dd62bfd:src/genro_storage/storage_grammar.py:151`
- `READ` `genro-storage@dd62bfd:src/genro_storage/storage_grammar.py:256` · 2026-10-27 — A `zip` mount addresses a ZIP archive as a filesystem, with `file`, `mode` and a target protocol.
- `READ` `genro-storage@dd62bfd:src/genro_storage/node.py:1621` · 2026-10-27 — `node.zip()` returns deflated ZIP bytes of a file, a directory or an iterator of nodes.

#### Genro Bag

- `READ` `genro-bag@2293047:src/genro_bag/bag/_serialize.py:270` · 2026-10-27 — `to_tytx(transport="json"|"msgpack")` serializes a Bag, optionally to a file.
- `RUN` `kajenn-press .venv, genro-bag 0.28.0` · 2026-10-27 — A Bag with a nested Bag holding bytes survives `to_tytx`/`from_tytx` in JSON: the value comes back as the same bytes. Through `to_xml`/`from_xml` the bytes come back as a string.

Pickle is also lossless, as reported by the research run; the msgpack transport needs the `msgpack` package, which the environment lacks. Neither was re-run here.

No zipped Bag format exists: a search for `to_zip`/`from_zip` in genro-bag found nothing. A zipped site source needs TYTX plus Python `zipfile`, or the genro-storage zip mount.

- `READ` `genro-bag@2293047:src/genro_bag/resolver.py:15` · 2026-10-27 — `BagResolver` (line 89) takes `cache_time`: 0 no cache, positive a TTL in seconds, negative until `reset()`.
- `READ` `genro-bag@2293047:src/genro_bag/resolver.py:646` · 2026-10-27 — `BagCbResolver` wraps a callback as a resolver with the same cache options.

#### Gramlot and HtmlBuilder

- `RUN` `gramlot@d01bf3d checkout environment` · 2026-10-27 — `div(node_label='info', kpress_slot='main')` and `td(kpress_slot=True)` keep the attribute in the source Bag; `getNode('html_0.body.center.info')` reaches the node by its label path; `findNodeByAttr('kpress_slot', 'main')` returns it; server rendering emits `<div kpress_slot="main">` and `<td kpress_slot="true">`.
- `READ` `gramlot@d01bf3d:src/gramlot/renderer/html_renderer.py:91` · 2026-10-27 — Unknown attribute names pass to the output; names starting with `gramlot_` are an error.
- `READ` `src/kajenn_press/rendering/engines.py:13` · 2026-10-27 — The kajenn-press static profile accepts the HTML tags of `STATIC_TAGS` only; other nodes fail with `unsupported_static_node` (line 204).

Layout widgets such as `contentPane` render as custom elements that need the Gramlot JS runtime, as reported by the research run. In static HTML a slot is therefore a plain element: `div`, `section`, `td` and similar.

- `READ` `gramlot@d01bf3d:src/gramlot/collections/editors.json:14` · 2026-10-27 — The editor collection defines `codeMirror`, `htmlEditor` (line 2599, Jodit) and `htmlPreview` (line 4754).
- `READ` `gramlot@d01bf3d:docs_llm/internal/185-legacy-detachable.md` · 2026-10-27 — Detachable panes and floating palettes of legacy GenroPy are investigated (GC-185, 2026-09-25) and marked "not implemented".
- `READ` `gramlot@d01bf3d:js/src/components/tree.js:9` · 2026-10-27 — The tree component is a drag source.
- `READ` `gramlot@d01bf3d:js/src/renderer/drag-drop.js:6` · 2026-10-27 — Drag and drop works within one renderer; other windows and instances are not admitted.

The HTML preview renders through `srcdoc` in a sandboxed iframe, so a content dragged from the drawer cannot be dropped on a slot of the rendered page as the preview works today.

#### Kajenn

- `READ` `kajenn@6ac7e58:src/kajenn/response.py:195` · 2026-10-27 — `set_result` handles paths, bytes, strings and JSON values; there is no support for storage nodes.
- `READ` `kajenn@6ac7e58:src/kajenn/server.py:406` · 2026-10-27 — The server answers 503 while its lifespan is not running; there is no per-site maintenance state.

Kajenn has no response cache; kajenn-press keeps its own in-memory cache of the release manifest in `child.py`.

#### Upstream items

- **genro-storage**: restore a version as current, through a server-side copy with `VersionId`; query the bucket's versioning state. Reproducer: `node.restore_version(vid)` raises `AttributeError`.
- **genro-bag**: a zipped Bag file holding nested Bags and binary values. Reproducer: `Bag.from_xml(b.to_xml(doc_header=True))['a.bin']` is a string, and no `to_zip` exists.
- **gramlot**: a detachable floating pane holding a tab container (GC-185). Reproducer: no `floatingPane` in the layout collection.
- **gramlot**: drop onto nodes of a rendered page shown inside the editor. Reproducer: a tree with `draggable=True` and a `dropTarget` div inside `htmlPreview`; the drop is not delivered. An alternative that needs no upstream change: render the preview in the same document instead of a sandboxed iframe; to be decided in Phase 5.
- **kajenn**: per-site maintenance state and a response cache on the local filesystem, or both kept in kajenn-press; to be decided in Phase 4.

#### Catalog and services

Today one local catalog holds every record of an installation as immutable JSON revisions with generations, receipts, audit and content-addressed payloads. The redesign keeps a site's source as one zipped Bag on S3, versioned by S3 ( (→ proposal/site-tab-redesign#d-publish-unit)), and pages hold autonomous copies carrying the original id ( (→ proposal/site-tab-redesign#d-content-copy)).

- `READ` `src/kajenn_press/catalog/local.py:54` · 2026-10-27 — `LocalCatalog` is a single-owner, thread-serialized store with an `owner.lock`; `commit` (line 347) writes changes under authorization and an idempotency key, `recover` (line 538) repairs an interrupted publication.
- `READ` `src/kajenn_press/catalog/local.py:43` · 2026-10-27 — `Snapshot` carries generation, records, revisions, receipts, audit and events; `Change` (line 27) carries scope, record id, expected generation, data and payloads.
- `READ` `src/kajenn_press/objects.py:39` · 2026-10-27 — `ObjectStore` keeps immutable payloads addressed by `ObjectRef` (key, sha256, size) through Genro Storage on a local root.
- `READ` `src/kajenn_press/services/editorial.py:28` · 2026-10-27 — `EditorialService.execute` checks identity, binds arguments, authorizes, and for mutations enforces a key of at most 256 characters, returning the prior receipt when the key and input repeat.
- `READ` `src/kajenn_press/services/editorial.py:643` · 2026-10-27 — `resource_copy` records `copied_from` with the source revision; updates keep it (lines 583 and 628).
- `READ` `src/kajenn_press/publication/service.py:225` · 2026-10-27 — The publication service commits to the same catalog; jobs and releases read payloads from it (`publication/jobs.py:114`, `publication/releases.py:102`). Replacing the catalog affects Phase 4.
- `READ` `src/kajenn_press/domain.py:5` · 2026-10-27 — `EDITORIAL_KINDS` are site, content, variant, template, css, javascript, media.
- `READ` `src/kajenn_press/domain.py:62` · 2026-10-27 — `AccessPolicy` maps identity to scopes (installation, library, `site:<id>`, `*`) and permission names, supplied by the host.

*Classification*

| Item | Fate | Successor or change | Decision |
|---|---|---|---|
| `catalog/local.py`: `LocalCatalog`, `Snapshot`, `Change` | replace | Site source Bag: an unpacked working copy while editing, one zipped object on S3 after each save; history from S3 versions | d-publish-unit |
| Generations and `expected_generation` | replace | The editing lock of one editor per site; a stale editor cannot save | d-editing-lock |
| Immutable JSON revisions, `revision_*` history | replace | S3 versions of the source zip and of each published page | d-publish-unit |
| Receipts and idempotency keys | open | Retries from MCP clients (Help me) still need a rule; decided in Phase 7 | — |
| Audit and events | open | No audit appears in the redesign; decided in Phase 7 | — |
| `catalog/filesystem.py` (fsync, private directory, atomic JSON publish) | change | Reused for the unpacked working copy and the local re-render cache | d-rerender-cache |
| `catalog/errors.py` | change | `Conflict`, `OwnershipError`, `IntegrityError` kept for the lock and the zip; `CommitUncertain` and `UnsupportedProfile` follow the catalog | d-editing-lock |
| `objects.py`: `ObjectStore`, `ObjectRef` | replace | Assets stored inside the site and page Bags | d-content-copy |
| `domain.py`: `EDITORIAL_KINDS` | change | site, page, template, content, asset (css, javascript, media); variant reduced to one per page until N9 | d-content-copy |
| `domain.py`: `OPERATIONS`, `MUTATIONS` | change | Operation by operation in Phase 6 | — |
| `domain.py`: `DomainError`, `AccessPolicy` | keep | Scopes `site:<id>` and library remain | d-nav |
| `EditorialService.execute` (identity, binding, authorization) | keep | Same entry point for UI, REST and MCP | — |
| Handlers `site_*`, `records_*`, `scope_capabilities` | change | Read from the site Bag instead of the catalog snapshot | d-publish-unit |
| Handlers `content_create`, `variant_create`, `draft_save` | change | Create a page from a template; save a content; assign a content copy to a slot | d-content-copy, d-slot-id |
| Handlers `resource_save`, `media_save` | change | Save templates and assets in the site or Library Bag | d-template-inherit |
| Handler `resource_copy` and `copied_from` | change | Copy carrying the original id, extended to contents and templates; base of Update and of the use count | d-content-copy |
| Handlers `revision_history`, `revision_compare`, `revision_checkpoint`, `revision_restore`, `revision_index` | replace | Version list and restore over S3 versions; restore needs the genro-storage upstream item | d-publish-unit |
| Handler `dependencies` | change | Where a content, template or asset is copied: pages and slots | d-content-copy |
| Handler `readiness` | change | Empty slots and SEO checks before publishing | d-publish-select, d-seo-inherit |

#### Rendering

Today a template is Python source that authors a Gramlot or HtmlBuilder Source; blocks reach it as prepared HTML in Data. A disposable worker process renders one frozen input built from a pinned catalog snapshot. In the redesign a page Bag holds a template copy, its contents and assets, contents fill slots marked with `kpress_slot`, and a template may use resolvers at render time with a cache.

- `READ` `src/kajenn_press/rendering/engines.py:242` · 2026-10-27 — `render_template` executes the trusted template source, calls `build(source, data)`, validates the static Source and renders HTML with a doctype.
- `READ` `examples/kajenn_press_site/template.py:38` · 2026-10-27 — Blocks are placed by Data pointers: `main.div("^blocks.hero")`, `main.div("^blocks.body")`.
- `READ` `src/kajenn_press/rendering/engines.py:210` · 2026-10-27 — Static validation refuses `==` expressions and pointers that do not resolve in Data (line 220).
- `READ` `src/kajenn_press/rendering/inputs.py:14` · 2026-10-27 — `RenderInputs.freeze` builds the input from one catalog snapshot: the variant, its exact dependency closure and resource sources, up to 32 MiB (line 90); a draft replaces block and resource sources and can use `data:` URLs (line 114).
- `READ` `src/kajenn_press/rendering/preparation.py:104` · 2026-10-27 — `prepare_blocks` converts Markdown and filters HTML with nh3; `script`, `style`, `iframe`, `object`, `embed`, `svg` and `math` are removed with their content.
- `READ` `src/kajenn_press/rendering/process.py:39` · 2026-10-27 — `RenderWorker` runs each render in a new process with only `PATH`, `LANG` and `TZ` in its environment, a timeout of 15 seconds by default (line 18) and a validated result (line 141).
- `READ` `src/kajenn_press/application.py:24` · 2026-10-27 — `render_preview` and `render_draft` are the two render operations; `render_draft` renders unsaved sources without writing.

*Classification*

| Item | Fate | Successor or change | Decision |
|---|---|---|---|
| `contract.py`: `RenderProblem`, `PreparedHTML` | keep | Same diagnostics and the same type boundary for prepared content | — |
| `contract.py`: `RenderInput` | change | Carries the page Bag in TYTX JSON (lossless with bytes, see Upstream capabilities) instead of catalog references | d-content-copy |
| `engines.py`: `render_template` | change | The template Bag (or the Python template that authors it) is filled slot by slot: each node with `kpress_slot` receives the prepared content assigned to it, found with `findNodeByAttr`; `^blocks.*` pointers go | d-slot-id |
| `engines.py`: `STATIC_TAGS`, `validate_static_source` | change | Plain HTML slots stay; validation also checks that every slot name is unique; pointers to resolver nodes must be allowed to resolve at render time | d-slot-id |
| `engines.py`: `installed_profile`, `make_builder`, `populate_data` | keep | Same qualified engines | — |
| `inputs.py`: `RenderInputs.freeze` | replace | The page Bag is already closed over its copies: freezing becomes serializing the page Bag, with the same 32 MiB limit; `data:` URLs stay for the Visual editor | d-content-copy |
| `inputs.py`: `RenderInputs.authorize` | change | Authorization on the site scope instead of each dependency revision | d-nav |
| `preparation.py`: `prepare_blocks` | keep | HTML and Markdown contents are filtered the same way. A dynamic iframe cannot come from a content, because `iframe` is removed: it is a slot kind authored in the template | — |
| `process.py`: `RenderWorker` | change | Resolvers that read a database need configuration the worker does not receive today; the re-render on the serving server reuses the worker with the 10-minute cache in front | d-rerender-cache |
| `worker.py`: `run_request` | change | Reads the page Bag: template, contents by slot, assets | d-content-copy |
| `service.py`: `RenderService` | change | Entry point takes a page of the site instead of a variant revision | d-content-copy |
| Operations `render_preview`, `render_draft` | change | `render_draft` renders the unsaved page for the Visual editor and the floating editor; `render_preview` renders the saved page | — |

Open for Phase 7: which configuration a resolver receives in the worker (database address, credentials) and whether resolver output is filtered like a content.

#### Publication and serving

Today a build renders a candidate (a set of exact variant revisions) into a sealed, content-addressed bundle; a channel activates one bundle at a time and can roll back; activated bundles are exported to Genro Storage with one pointer per channel; a child application serves the active bundle. In the redesign every page is one published object on S3, versioned by S3; Publish sends the changed pages; Kajenn serves them and re-renders pages with resolvers into a local cache.

- `RUN` `Hetzner installation, websites container, 2026-10-27` · 2026-10-27 — `get_bucket_versioning` on bucket `kpress-releases` returns no `Status`: versioning has never been enabled on the bucket. Enabling it is an owner action on the bucket and a precondition of N3 and N4.
- `READ` `src/kajenn_press/publication/service.py:53` · 2026-10-27 — `PublicationService` composes `BuildJobs`, `PreviewGrants`, `Releases`, `Deployments` and `PublicServing` over the editorial catalog.
- `READ` `src/kajenn_press/publication/artifacts.py:257` · 2026-10-27 — `build_artifacts` renders every page of a candidate, rewrites links through `LinkResolver` (line 73), adds canonical and alternate links (line 328) and a sitemap (line 350), and seals the bundle; `verify_png` (line 17) checks PNG media.
- `READ` `src/kajenn_press/publication/export.py:4` · 2026-10-27 — `ReleaseStorage` writes artifacts and manifests once, then one pointer per channel last (line 143); `qualify` (line 33) refuses a backend that loses bytes or exposes a partial object.
- `READ` `src/kajenn_press/publication/gateway.py:44` · 2026-10-27 — `PreviewGateway` refuses a preview origin equal to the management origin.
- `READ` `src/kajenn_press/child.py:74` · 2026-10-27 — `StaticSiteServerApplication` binds public origins to channel pointers and serves the active bundle without catalog, Gramlot or render worker; `ReleaseReader` (line 27) caches the manifest for `cache_seconds`.
- `READ` `deploy/docker/storage-init.sh:2` · 2026-10-27 — The RustFS path creates the bucket and users with `mc`; on Hetzner it is replaced by `compose.external-s3.yaml`, because `minio/mc` is no longer pullable (recorded in the archived kpress-deployment plan).

*Classification: src*

| Item | Fate | Successor or change | Decision |
|---|---|---|---|
| `publication/releases.py`: channels, `release_activate`, `release_rollback`, history | replace | Per-page published objects; rollback of a page through its S3 versions; site rollback through the source zip | d-publish-unit |
| `publication/jobs.py`: `BuildJobs`, candidates | replace | Publish of the changed pages: render each selected page Bag and write its object; one worker slot kept | d-publish-select |
| `publication/artifacts.py`: `build_artifacts`, `verify_bundle` | replace | The page object holds its sources and pre-rendered HTML; no bundle or manifest | d-publish-unit |
| `publication/artifacts.py`: `LinkResolver`, `PageHTML`, `validate_references`, `verify_png` | change | Link rewriting and checks per page; broken internal links feed the SEO checks | d-seo-inherit |
| `publication/artifacts.py`: canonical, alternate, sitemap | change | Generated at Publish from the SEO tab: `sitemap.xml`, `robots.txt`, 301 redirects | d-seo-inherit |
| `publication/routes.py` | change | URL per page from the SEO tab; language prefixes reduced to one language until N9 | d-seo-inherit |
| `publication/export.py`: `ReleaseStorage` export and pointers | replace | Writing page objects to S3 directly; the bucket's versioning keeps the history | d-publish-unit |
| `publication/export.py`: `qualify` | keep | Same qualification of the storage backend, plus a check that versioning is enabled | d-publish-unit |
| `publication/grants.py`: `PreviewGrants` | change | Private links for the optional private publication before going public and for the editor in maintenance | — |
| `publication/gateway.py`: `PreviewGateway` | keep | Management and preview stay on separate origins | — |
| `publication/serving.py`: `PublicServing` | replace | Serving from page objects by the Kajenn server | d-publish-unit |
| `publication/deployments.py`: `Deployments` (children registry) | change | Registry of Kajenn servers the first Publish chooses from | — |
| `publication/service.py`: `PublicationService` | change | Composes Publish, rollback, maintenance, private links and the server registry over the site Bag | d-publish-unit |
| `child.py`: `StaticSiteServerApplication`, `ReleaseReader` | change | Serves page objects; re-renders pages with resolvers into a local filesystem cache; adds per-site maintenance (missing upstream in Kajenn) | d-rerender-cache |

*Classification: deploy and examples*

| Item | Fate | Successor or change |
|---|---|---|
| `deploy/docker/compose.yaml`, `compose.external-s3.yaml`, `websites.py`, `nginx-kpress.conf`, `HETZNER.md`, `credentials.py`, `lock.sh`, requirements files | keep | The manager deployment stays as installed on 2026-10-27 |
| `deploy/docker/child.py`, `Dockerfile.child`, profile `demo` | change | The child becomes the Kajenn server serving page objects, with the render profile when resolvers are used |
| `deploy/docker/storage-init.sh`, profile `rustfs`, `compose.volume.yaml` | change | Local development storage; needs `rustfs/rc` instead of `minio/mc`, and versioning enabled on the local bucket |
| `examples/persistence.py`, `editorial.py`, `serve.py` | replace | One example of the site Bag editing cycle over REST and MCP |
| `examples/private_preview.py`, `verify_private_preview.py`, `publication_cycle.py`, `verify_publication_cycle.py` | replace | One example of Publish, private link and rollback per page |
| `examples/static_rendering.py`, `static_template.py`, `qualify_renderers.py` | change | Templates with `kpress_slot` instead of `^blocks.*` |
| `examples/child_serve.py` | change | Follows `child.py` |
| `examples/admin_demo.py` | change | Follows the administration (Phase 5) |
| `examples/kajenn_org/`, `examples/kajenn_press_site/` | change | Converted to site Bags; their fate is tied to the existing data (Phase 6) |

Decided here for the upstream item of Phase 1: per-site maintenance and the local re-render cache belong to the Kajenn server application of kajenn-press, not to Kajenn, until another Kajenn application needs them.

#### Administration

Today the shell is a Gramlot `IndexPage` with a site selector, a navigation tree grouped by record kind and one iframe tab per object; separate pages edit a new page, an existing page, a resource, publishing and deployments. The redesign has Sites and Library in the tree, one tab per site with Visual editor, SEO and Published site, a drawer with Pages and Contents, and a detachable floating editor.

- `READ` `src/kajenn_press/admin/host.py:115` · 2026-10-27 — `ManagementGuard` admits management requests only on the management origin; the administration CSP is set at line 99, with `frame-ancestors 'self'` at line 101.
- `READ` `src/kajenn_press/admin/views.py:238` · 2026-10-27 — `login_view` shows the Kajenn Press logo and signs in through `sign_in` (line 271) with the server's identity store.
- `READ` `src/kajenn_press/admin/views.py:29` · 2026-10-27 — `scaled_preview` keeps a rendered page at 1280 or 375 px and scales it; the page is shown by `htmlPreview` (line 77).
- `READ` `src/kajenn_press/admin/pages/page.py:14` · 2026-10-27 — The page editor offers Jodit and CodeMirror for HTML blocks, the Markdown editor and CodeMirror for Markdown blocks; `page.js` calls `render_draft` for the live preview (line 177).
- `READ` `src/kajenn_press/admin/pages/index.py:28` · 2026-10-27 — The shell is `IndexPage`; `navigation_bag` (line 62) builds the tree of the selected site; `create_site` (line 325) creates a site from the dialog.

The HTML preview runs in an iframe with an empty `sandbox` (see Upstream capabilities): no script runs inside it. Slot borders can be added by CSS in the rendered HTML, but clicking a slot to detach it and dropping a content on it need either a script inside the preview or the page rendered in the administration document. This becomes decision `d-preview-interaction` in Phase 7.

*Classification*

| Item | Fate | Successor or change | Decision |
|---|---|---|---|
| `host.py`: `AdminApplication`, `ManagementGuard`, CSP | keep | Same origin boundary; the CSP changes only if the preview interaction needs it | — |
| `views.py`: `login_view`, `sign_in`, `sign_out`, `read`, `caption`, `literal_text` | keep | Login, session and service reads unchanged | — |
| `views.py`: `scaled_preview` | change | Center of the Visual editor: rendered site with slot borders on command, navigable through its links | d-nav |
| `views.py`: `workspace`, `detail`, `WorkspacePage`, `pages/library.py` | replace | Library node of the tree with its own lists of templates, styles, scripts and media | d-nav, d-template-inherit |
| `pages/index.py`: `IndexPage` shell, tabs | keep | Same shell with one tab per site | d-nav |
| `pages/index.py`: `navigation_bag`, site selector, New site dialog | replace | Tree Sites (sites and "new site") and Library; "new site" opens an empty site tab | d-nav |
| `pages/home.py` | change | Guide rewritten on the new model, or removed when the site tab explains itself | — |
| `pages/author.py`, `author.js` | replace | Visual editor of the site tab; a new page is created from a template in the Pages tree | d-nav |
| `pages/page.py`, `page.js` | change | The block editors and the `render_draft` loop move into the floating editor of a slot (CodeMirror, Jodit, Preview); the floating pane is missing upstream (GC-185) | d-slot-id |
| `pages/resource.py`, `resource.js` | change | Template, CSS, JavaScript and media editors reached from Library and from the site's templates; block declarations become `kpress_slot` slots read from the template | d-slot-id, d-template-inherit |
| `pages/publishing.py`, `publishing.js` | replace | Published site tab: command bar with Publish, rollback and maintenance, iframe on the live site | d-publish-select |
| `pages/deployments.py` | change | Registry of Kajenn servers, used by the first Publish | — |
| New: drawer with Pages and Contents trees | — | Built on the Gramlot tree and its drag source | d-content-copy |
| New: SEO tab | — | Form per page with root defaults and search/social previews | d-seo-inherit |
| New: Help me chat | — | No existing part | d-help-budget |

#### Operations

44 operations on REST and MCP today: 21 editorial (`src/kajenn_press/domain.py:7`), 2 render (`src/kajenn_press/application.py:24`), 21 publication (`src/kajenn_press/publication/service.py:32`). Successor names are fixed in N2–N4; here each successor is described.

*Editorial*

| Operation | Fate | Successor or change |
|---|---|---|
| `capabilities` | keep | Lists the new operations |
| `scope_capabilities` | keep | Same scopes |
| `sites_list` | keep | Feeds the Sites node of the tree |
| `site_create` | change | Empty site or from a starting site in Library; languages leave the input until N9 |
| `site_configure` | change | Site name and root SEO defaults |
| `records_list`, `records_index` | change | Pages tree, Contents tree with use counts, templates and assets of the site or Library |
| `record_read` | change | Reads a page, content, template or asset from the site Bag |
| `content_create` | replace | Create a page from a site template |
| `variant_create` | remove | One variant per page until N9 |
| `draft_save` | replace | Save a content; assign a content copy to a slot |
| `resource_save`, `media_save` | change | Save a template or an asset in the site or Library Bag |
| `resource_copy` | change | Copy with the original id, for templates, contents and assets; linked or independent for templates |
| `dependencies` | change | Where an original is copied: pages and slots |
| `readiness` | change | Checks before Publish: empty slots, SEO |
| `revision_history`, `revision_index` | replace | List S3 versions of the site source or of a published page |
| `revision_restore` | replace | Restore an S3 version (upstream item in genro-storage) |
| `revision_compare` | replace | Differences between a copy and its original, shown by Update |
| `revision_checkpoint` | remove | Every save is already a deliberate S3 version |
| New | — | Update the copies of an original in selected pages; take and release the editing lock of a site |

*Render and publication*

| Operation | Fate | Successor or change |
|---|---|---|
| `render_preview`, `render_draft` | change | Render a saved or unsaved page Bag |
| `publication_settings_save` | replace | First Publish settings: Kajenn server, domain, DNS |
| `publication_route_save` | replace | URL of a page in the SEO tab |
| `release_activate`, `build_start` | replace | Publish the selected changed pages |
| `build_status` | change | Progress of a Publish |
| `release_rollback` | replace | Restore a previous S3 version of a published page |
| `release_history`, `channel_read` | replace | Published state and version list per page |
| `publication_overview` | change | Feeds the Published site tab |
| `preview_grant_create`, `preview_grant_revoke` | change | Private links: private publication, maintenance |
| `candidate_create`, `candidate_read`, `build_retry`, `channel_create`, `release_read`, `release_export` | remove | No candidates, channels, bundles or export in the new model |
| `child_save`, `child_read`, `child_list` | change | Registry of Kajenn servers |
| `child_channels` | change | Sites served by a Kajenn server |
| New | — | Maintenance on and off for a site |

Totals over the 44 operations: 3 keep, 20 change, 13 replace, 8 remove.

#### Tests

133 tests in 9 suites under `tests/`, counted on 2026-10-27 at `main` `1c49362`.

*Suites*

| Suite | Tests | Fate | Reason |
|---|---|---|---|
| `tests/contracts/phase_1`, `phase_2` | 19 | replace | Catalog and editorial contracts; new contracts on the site Bag, the lock and S3 versions |
| `tests/contracts/rendering_publication` | 24 | replace | Rendering contracts are rewritten for slots; publication contracts follow per-page objects |
| `tests/catalog` | 15 | replace | Follows `LocalCatalog` and `ObjectStore` |
| `tests/services` | 7 | change | `EditorialService.execute` stays, handlers change |
| `tests/api` | 4 | change | Authentication and POST rules stay; operations change |
| `tests/rendering` | 6 | change | Limits stay; inputs become the page Bag |
| `tests/publication` | 20 | replace | Except `test_gateway.py` (keep) and the qualification tests of `test_release_export_contract.py` (keep) |
| `tests/child` | 4 | change | Follows the Kajenn server application |
| `tests/admin` | 23 | replace | Except login and shell checks in `test_admin_phase_1_contract.py` and `test_site_editor_shell.py` (change) |
| `tests/docker` | 11 | keep | The manager deployment stays; `test_docker_composition_contract.py` changes with the `demo` profile |

#### Existing data

- `RUN` `kpress MCP sites_list and records_index, 2026-10-27` · 2026-10-27 — The Hetzner catalog holds one site, "Kajenn Press" (language en), with three pages at `/en/`, `/en/features/`, `/en/get-started/`, each with blocks `hero` and `body` on one template. No release is active. The 2026-10-27 deployment check added channel settings `preview-check`, one candidate, one build and one preview grant.
- `RUN` `examples/kajenn_press_site/pages/home.body.html` · 2026-10-27 — The home page blocks on Hetzner have the same SHA-256 as `examples/kajenn_press_site/pages/home.body.html` and `home.hero.html`: the site was loaded from the example sources.

The text of the site describes the previous model (revisions, candidates, builds, channels). It needs rewriting in any case.

Proposed: no migration code. The Kajenn Press site is rebuilt in the new model from `examples/kajenn_press_site/` with rewritten text, as the first site of N2–N5. The old catalog volume is archived with the backup command of `deploy/docker/HETZNER.md` before the new version is installed. To confirm in Phase 7.

### Related documents

- `proposal/site-tab-redesign` — Kajenn Press: the site tab, page Bags and per-page publication
