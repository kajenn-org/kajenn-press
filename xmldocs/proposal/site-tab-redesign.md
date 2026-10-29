<!-- generated from site-tab-redesign.xml by xmldocs: do not edit, edit the XML -->

## Kajenn Press: the site tab, page Bags and per-page publication
*Proposal · site-tab-redesign · 2026-10-27 · draft*

### Problem

The administration mirrors the data model and the API instead of the operator's tasks. The navigation groups are record kinds and the buttons are service operations. An operator who wants a site online meets templates in Python, channels, routes, candidates, builds and generations before seeing a result.

This proposal designs the administration from the operator's point of view first. The inventory of code changes comes after the design is agreed.

### Current state

- `READ` `src/kajenn_press/admin/pages/index.py:18` · 2026-10-27 — The navigation tree of a site has one group per record kind: Pages, Templates, Styles, Scripts, Media.
- `READ` `src/kajenn_press/admin/pages/index.py:82` · 2026-10-27 — The only creation entry in the tree is New page; Templates, Styles, Scripts and Media have none.
- `READ` `src/kajenn_press/admin/pages/author.py:161` · 2026-10-27 — The New page workspace supports one HTML block named `body` and opens with a Gramlot template in Python to write or save first.
- `READ` `src/kajenn_press/admin/pages/publishing.py:199` · 2026-10-27 — A build needs a channel first; the page shows "Save a channel first."
- `READ` `src/kajenn_press/admin/pages/publishing.py:213` · 2026-10-27 — A page without a route cannot be selected for a build; the operator finds out only in Publishing.
- `READ` `src/kajenn_press/admin/pages/home.py:69` · 2026-10-27 — Open tabs keep their original site when the site selector changes; the guide asks the operator to check the tab title.

### Proposed solution

#### Principles

- The published image is static. Only the editor changes it.
- Sites are always served by Kajenn under its rules. A fully static site is a choice, not a limit: a slot can be a dynamic iframe backed by Gramlot and the database.
- Versioning is delegated to S3. Kajenn Press keeps no version history of its own.
- Pages hold autonomous copies of templates, contents and assets. Every copy carries the id of its original, so all copies of an original can be found and updated on request.
- A site can speak several languages; one is the main language (see Languages).

#### Navigation

```text
Sites
    kajenn.org
    genro.com
    acme.org
    -new site-
Library
    (shared CSS, common Gramlot templates, ...)
```

- Selecting a site opens its site tab. Each site has its own tab.
- -new site- opens an empty site tab. It can start empty or from a starting site: a source zip kept in Library.
- Library holds what several sites share: CSS, common Gramlot templates, media.

#### The site tab

The site tab has three tabs: Visual editor, SEO, Published site.

#### Visual editor

- The center shows the site rendered as it would be served locally. It opens on the root page; the operator moves to other pages through the links, as a visitor would.
- On command, a very thin border marks every slot.
- A block can be detached into a floating window with three tabs: CodeMirror (source), Jodit (visual editing), Preview.

A side drawer holds a tab container with two tabs.

- **Pages**: a logical tree of all pages, managed with drag and drop. The tree organises the editing only; public URLs are independent of it. Every page expands into the named slots of its template. A page that no link reaches is still reachable here.
- **Contents**: the contents of the site. A content used nowhere is shown in italic grey; used once, normal; used more than once, normal with a badge giving the number of uses.

A content is dragged into an empty slot, either on the slot in the rendered page or on the slot node in the Pages tree.

Every page and template in the tree shows two marks: changed since the last publication, and holding copies that are older than their original.

#### SEO

- Every page has its own SEO: title, description, public URL, canonical, robots, Open Graph and social card, JSON-LD, image alt texts.
- The root page has the most complete SEO and holds the site defaults: site name, sharing image, organisation, robots. An empty field of a page takes the root value; the tab shows that value beside the empty field.
- The tab shows how the page looks in a search result and in a social share.
- Before publishing it reports missing or duplicate titles, missing descriptions, images without alt and broken internal links.
- Changing the URL of a page creates a 301 redirect from the old URL.
- The 404 page of the site is an ordinary page.
- The renderer reads all SEO data from here; `sitemap.xml` and `robots.txt` are generated at every publication.

#### Published site

- A command top bar and, in the center, an iframe on the published site.
- The top bar holds publication, rollback and the management commands, such as maintenance mode.
- Maintenance mode makes Kajenn serve a maintenance page; the editor keeps seeing the real site through a private link.
- An optional step publishes to a private address of the same server first, then makes it public.
- The published site can have its own administration when needed. Its content is not designed here; Kajenn, Asqueel and Gramlot can build it.

#### Pages, templates and slots

- A page is a Bag holding a template Bag (always a copy, however made), a contents Bag and the other assets. A page can produce its static HTML.
- A template is a Bag of Gramlot source: nested containers. It declares its slots.
- A slot is any object able to host content (a content pane, a div, a grid or table cell) that the author marks with `kpress_slot`. The value is `True` or a unique name. Every container has a `node_label`, set by the author or automatic, so every slot also has a path such as `center.info.top.tab1`.
- Slot kinds: HTML, Markdown, dynamic iframe, content computed by a resolver. Empty slots are reported before publishing.
- Templates live on three levels: Library (generic), site, page. A site template inherits from a Library template; the operator chooses linked (Library changes reach it) or independent copy. A linked template is the Library Bag plus the site's additions, removals and changes of nodes. A page-local customised copy is a later option.

#### Copies and updates

1. The operator edits a content, a template or an asset and sees the result.
2. Update shows the pages that hold a copy of it and the differences. Pages whose copy has local changes are flagged and start unselected.
3. The confirmed pages get the new copy and are rendered again. Update and publish can run as one step, so changing a shared CSS is one operation.

The badge in Contents counts the copies that carry the same original id.

#### Storage, publication and rendering

*Objects on S3*

| Object | Unit | Content | Versioning |
|---|---|---|---|
| Source | one per site | one zipped Bag with everything; the editor unpacks it, works and zips it again | one S3 version per deliberate save |
| Published page | one per page | the page Bag, possibly zipped: sources in one branch, pre-rendered pure HTML in a parallel branch | one S3 version per publication of the page |

- Rolling back a page restores the previous S3 version of its object. Rolling back the site restores a previous source zip and republishes the pages.
- A complete site travels as one source zip: move, backup, handover, starting site.
- Publish lists the pages changed since the last publication, all selected; the operator can unselect some and confirms.
- A published page holds what is needed to render it again at any time. Its Python template can read the database or do other work at render time through resolvers, with a cache of, for example, 10 minutes.
- Re-rendered HTML is stored on the local filesystem of the serving server, not on S3. S3 holds only what the editor published. A new publication of a page discards its local copy.

#### First publication

1. Choose the Kajenn server among the ones registered in Kajenn Press.
2. Enter the domain and whether `www` is served too.
3. DNS: with the provider's credentials Kajenn Press creates the records; without them it shows the exact records to create and checks when they become visible.
4. The TLS certificate is automatic, because the server is a Kajenn server.
5. All pages are published, the address is checked and the site appears in the Published site iframe.

Whether a Python process is needed to re-render follows from the presence of resolvers in the templates; the operator is not asked.

#### Help me

The site tab has a Help me button that opens a chat with Sonnet. Sonnet knows how Kajenn Press works, helps the user say what to create, offers fonts and colours, draws SVG elements such as logo and icons, and creates everything needed.

- Choices appear as clickable previews: palettes, font pairs, logo versions.
- Sonnet works through the MCP operations; the result is ordinary pages, templates and contents, editable by hand.
- The visual editor shows the site taking shape beside the chat.
- Help me is available on a new site and on an existing one.
- The conversation is kept with the site and can be resumed.
- Sonnet creates and saves; publishing stays an operator command.
- One API key per Kajenn Press installation, part of the standard configuration.
- Tokens and cost are shown per chat and in total per site, for information only: no budget, no limit while the tool is used internally.

#### Languages

A site has a main language and may have others. A page exists once; its texts exist once per language.

- Each content has one version per language. The template is shared: its own texts, such as menu and footer, are page data and are translated like contents.
- URLs carry the language as a prefix, such as `/it/chi-siamo/` and `/en/about/`; the main language also answers without prefix.
- A missing translation shows the text of the main language, and the editor marks it as missing.
- When a text of the main language changes, its translations are marked as to update, as copies are today.
- A language selector in the site bar sets the language of the Visual editor, the SEO tab and the preview. The Contents tree shows what is missing or to update in that language.
- Title, description and URL are per language; the versions of a page point to each other with `hreflang`; the sitemap lists every language; the site defaults of the root page are per language.
- Help me can propose translations; the operator confirms them, and proposed translations stay marked to review until then.
- The published site offers a language selector in the template. The root never redirects by the browser's language.

#### Editing by several people

A site is edited by one person at a time. Whoever opens the editor takes the site; the others see who holds it and can only look. This prevents a second editor's zip from overwriting the first one's work.

### Decisions

- **d-nav** `decided` — How does the operator choose and create a site?
   1. **Sites and Library in the navigation tree; one tab per site**
   2. **Site selector in the top bar and New site dialog (today)**
   → Choice: **Sites and Library in the navigation tree; one tab per site** (GP, 2026-10-27) — Everything about a site lives in its tab.
- **d-content-copy** `decided` — Does a page hold references to contents or copies?
   1. **References**: A change shows everywhere at once.
   2. **Autonomous copies carrying the original id**: The operator edits, checks, then asks to update the copies.
   → Choice: **Autonomous copies carrying the original id** (GP, 2026-10-27) — Changes never propagate by accident.
- **d-slot-id** `decided` — How is a slot identified?
   1. **Path of node labels**
   2. **kpress_slot attribute declared by the template, True or a unique name**
   → Choice: **kpress_slot attribute declared by the template, True or a unique name** (GP, 2026-10-27) — Every template declares its slots.
- **d-template-inherit** `decided` — Does a site template follow later changes of its Library template?
   1. **Linked**
   2. **Independent copy**
   3. **The operator chooses**
   → Choice: **The operator chooses** (GP, 2026-10-27) — A linked template is the Library Bag plus the site's node changes.
- **d-publish-unit** `decided` — What is published and how is it versioned?
   1. **One object per site**
   2. **One object per page; source as one zip per site**
   → Choice: **One object per page; source as one zip per site** (GP, 2026-10-27) — S3 versions each page; the site travels as one zip.
- **d-rerender-cache** `decided` — Where does re-rendered HTML go?
   1. **Written back to S3**: Every re-render creates a new S3 version.
   2. **Local filesystem of the serving server**
   → Choice: **Local filesystem of the serving server** (GP, 2026-10-27) — S3 holds only what the editor published.
- **d-seo-inherit** `decided` — Where does an empty SEO field of a page take its value?
   1. **From the root page**
   2. **From the page above in the tree**: Moving a page in the tree would change its published SEO.
   → Choice: **From the root page** (GP, 2026-10-27) — The tree is for editing only.
- **d-publish-select** `decided` — Which pages does Publish publish?
   1. **Changed pages, all selected, the operator can unselect**
   2. **All pages**
   → Choice: **Changed pages, all selected, the operator can unselect** (GP, 2026-10-27) — One click in the usual case; a page not ready can stay back.
- **d-help-budget** `decided` — Does Help me limit token consumption?
   1. **Information only**
   2. **Budget with a limit**
   → Choice: **Information only** (GP, 2026-10-27) — The tool is used internally for now.
- **d-editing-lock** `decided` — How do two people edit the same site?
   1. **One editor at a time per site**: The lock expires after inactivity (for example 30 minutes); another user can take the site with an explicit command, warning the holder, whose unsaved changes are lost; Help me works under the lock of the user who opened it.
   2. **Concurrent editing with merge of the source zip**: Needs a merge of the same Bag and conflict resolution per node; nothing provides it today.
   → Choice: **One editor at a time per site** (GP, 2026-10-27) — The source is one zip; a merge mechanism does not exist.
- **d-update-local** `decided` — When a page changed its copy of a content, does Update overwrite it, skip it or ask?
   1. **Always overwrite**
   2. **Always skip**
   3. **Flag and let the operator choose**: Pages with local changes are flagged and start unselected; selecting one shows the differences and overwrites on confirmation. Each copy carries the original id and the digest of the original at copy time; a different current digest means a local change.
   → Choice: **Flag and let the operator choose** (GP, 2026-10-27) — Nothing is lost without the operator seeing it.
- **d-template-conflict** `decided` — When a Library template changes a node that a linked site template changed or removed, which version wins?
   1. **The site wins**
   2. **The Library wins**
   3. **Report and let the operator choose per node**: The update of that template stops and lists the conflicting nodes, including renamed labels; per node the operator keeps the site version or takes the Library one. Until then the site template stays on the Library version it records.
   → Choice: **Report and let the operator choose per node** (GP, 2026-10-27) — Same rule as Update of copies.
- **d-slot-removed** `decided` — What do pages show when their template no longer declares a slot that held a content?
   1. **The copy is discarded**
   2. **The copy stays without a slot**: The page does not show it; the Pages tree lists it under the page as without slot, with a warning; the check before Publish reports it; the operator moves or deletes it.
   3. **The template cannot be saved while pages use the slot**
   → Choice: **The copy stays without a slot** (GP, 2026-10-27) — Nothing is lost and templates stay free to change.
- **d-template-switch** `decided` — When a page switches template, do slots with the same name keep their contents?
   1. **By name**
   2. **All contents become without slot**
   3. **Guided mapping**: A panel shows old and new slots matched by name; the operator corrects and confirms; unmatched contents become without slot.
   → Choice: **Guided mapping** (GP, 2026-10-27) — Equal names need one confirmation; renamed slots are seen before contents are detached.
- **d-dynamic-seo** `decided` — Content in dynamic iframes is not indexed. How does a page with dynamic slots stay indexable?
   1. **Accept: iframe content is not indexed**
   2. **Dynamic iframes only on noindex pages**
   3. **Static fallback content in the iframe slot**: Written by hand or produced by a resolver, rendered in the page HTML and indexed; the iframe replaces it when the browser loads it. The SEO tab warns when an indexed page has an iframe slot without fallback.
   → Choice: **Static fallback content in the iframe slot** (GP, 2026-10-27) — Iframes stay free and pages do not reach search engines or no-JS readers empty.
- **d-resolver-config** `decided` — How does a resolver in the render worker reach a database?
   1. **Named connections in the server deployment**: The Kajenn server's `.env` and secrets define named connections; the page Bag names the connection only; the worker receives it per render. Credentials never enter a Bag or S3.
   2. **Resolvers in the server process**
   3. **Resolvers call HTTP APIs with a token**
   → Choice: **Named connections in the server deployment** (GP, 2026-10-27) — Credentials stay out of files that move and are versioned.
- **d-resolver-output** `decided` — Is resolver output filtered?
   1. **Text by default, HTML through nh3**
   2. **Trusted like the template**
   → Choice: **Text by default, HTML through nh3** (GP, 2026-10-27) — Database values can hold text written by users.
- **d-idempotency** `decided` — Do mutations keep idempotency keys?
   1. **Keep keys; receipts kept 24 hours in the site working copy**
   2. **Drop keys; clients re-read before retrying**
   → Choice: **Keep keys; receipts kept 24 hours in the site working copy** (GP, 2026-10-27) — Help me makes many MCP calls and may retry them.
- **d-audit** `decided` — Is there an audit of changes?
   1. **Minimal log in the site Bag**: Who, when and what for each save, Publish, rollback and lock take; Help me actions are recorded as made by the user through Help me; the log travels with the zip.
   2. **No audit**
   → Choice: **Minimal log in the site Bag** (GP, 2026-10-27) — An S3 version does not say who changed what.
- **d-preview-interaction** `decided` — How do clicks and drops reach slots in the sandboxed preview?
   1. **A script in the preview with postMessage**: `sandbox="allow-scripts"` without `allow-same-origin`; the script is added to the preview HTML only, never to published HTML. Verified as the first step of N5; if native drag into the sandboxed iframe fails, the first version keeps click-to-select in the preview and drop on the Pages tree.
   2. **Page in the administration document inside a shadow DOM**
   3. **Cross-window drag and drop in Gramlot**
   → Choice: **A script in the preview with postMessage** (GP, 2026-10-27) — The administration stays isolated from the page.
- **d-site-rebuild** `decided` — What happens to the Kajenn Press site in the Hetzner catalog?
   1. **Rebuild from the example sources**: No migration code; the catalog volume is archived with the backup command of `deploy/docker/HETZNER.md` before the new version is installed.
   2. **Migrate with a converter**
   → Choice: **Rebuild from the example sources** (GP, 2026-10-27) — The site comes from `examples/kajenn_press_site` and its text must be rewritten anyway.
- **d-lang-unit** `decided` — What is translated?
   1. **The contents of one page, one version per language; one shared template**
   2. **One page per language, linked to its translations**
   → Choice: **The contents of one page, one version per language; one shared template** (GP, 2026-10-29) — One page, one structure: layout changes reach every language.
- **d-lang-url** `decided` — How do URLs carry the language?
   1. **A prefix per language; the main language also without prefix**
   2. **One domain per language**
   → Choice: **A prefix per language; the main language also without prefix** (GP, 2026-10-29) — One address per site, one binding.
- **d-lang-template** `decided` — How are the template's own texts translated?
   1. **The template reads them from page data, translated like contents**
   2. **One template per language**
   → Choice: **The template reads them from page data, translated like contents** (GP, 2026-10-29) — One template per site keeps one layout.
- **d-lang-missing** `decided` — What does a page show when a translation is missing?
   1. **The text of the main language, marked as missing in the editor**
   2. **The page does not exist in that language**
   → Choice: **The text of the main language, marked as missing in the editor** (GP, 2026-10-29) — A visitor never meets a hole.
- **d-lang-outdated** `decided` — What happens to translations when the main text changes?
   1. **They are marked as to update, as copies are**
   2. **Nothing**
   → Choice: **They are marked as to update, as copies are** (GP, 2026-10-29) — The operator sees what is behind.
- **d-lang-editor** `decided` — How does the editor show languages?
   1. **A language selector in the site bar for the Visual editor, SEO and preview**
   2. **Languages side by side**
   → Choice: **A language selector in the site bar for the Visual editor, SEO and preview** (GP, 2026-10-29) — One language at a time keeps the tab as it is.
- **d-lang-seo** `decided` — How does SEO handle languages?
   1. **Title, description and URL per language, hreflang, every language in the sitemap**
   2. **SEO in the main language only**
   → Choice: **Title, description and URL per language, hreflang, every language in the sitemap** (GP, 2026-10-29) — Search engines index each language.
- **d-lang-help** `decided` — Does Help me translate?
   1. **It proposes translations, marked to review until the operator confirms**
   2. **No automatic translation**
   → Choice: **It proposes translations, marked to review until the operator confirms** (GP, 2026-10-29) — Drafts save time; the operator stays responsible.
- **d-lang-visitor** `decided` — How does a visitor change language?
   1. **A selector in the template; no redirect by browser language**
   2. **Automatic redirect from the root**
   → Choice: **A selector in the template; no redirect by browser language** (GP, 2026-10-29) — Every URL shows the same page to everyone, robots included.

### Consequences

This proposal replaces the navigation and the editors of  (→ proposal/site-editor#site-editor): the site selector, the per-kind groups, the New page workspace and the publishing panel.

The publication model changes: channels, routes, candidates, builds and releases give way to per-page published objects versioned by S3 and a source zip per site. The catalog's own revision history is no longer the versioning mechanism.

A shared asset copied into every page costs storage per page, and changing it means updating and republishing every page that holds it.

The inventory of code changes is a separate step, after this design is agreed.

### Related documents

- `proposal/site-editor` — Kajenn Press administration as a site editor
