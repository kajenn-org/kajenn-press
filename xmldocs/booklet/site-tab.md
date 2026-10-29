<!-- generated from site-tab.xml by xmldocs: do not edit, edit the XML -->

## Building a site in the site tab
*Instruction booklet · booklet/site-tab · 2026-10-29*

### Purpose

How an operator builds, translates and publishes a site in the Kajenn Press administration: the navigation, the site tab with its three tabs (Visual editor, SEO, Published site), languages and Help me.

### Requirements

- A websites installation with site sources: a source bucket and a release bucket, both with S3 versioning (booklet *Installing and running*).
- An account with the `editor` tag and grants `read`, `write`, `create_site`, `build` and `publish` on the sites it works on.
- For Help me, the installation's Claude API key.

#### 1. Open or create a site

The administration is framed as Gramlot's gallery. A column of icons on the left opens and closes the navigation and signs out. The navigation has two groups: **Sites** lists every site the account can read, with who is editing it, and **+ new site**; **Library** lists the starting sites. Each page opened gets a closable tab; a site keeps its state while another tab is shown.

A site has three tabs, Visual editor, SEO and Published site. Each is a frame with its own toolbar on top: the Visual editor's holds the language, **Show slots**, the page shown, **Help me**, **Take the site** when another person holds it, and **Save**; SEO's holds the language and the site's checks; Published site's holds the state, the address and the publication commands. Every pane takes the full height.

Opening a site takes it: one person edits a site at a time. The others see who holds it and can only look; **Take the site** takes it from the holder, whose unsaved changes are lost. The lock expires after 30 minutes without changes.

**Save** writes the site as a new S3 version of its source. Every change before that lives in the holder's working copy.

#### 2. Pages, slots and contents

The Visual editor has a drawer with two trees and, in the centre, the page rendered as it will be published.

- **Pages**: pages and folders. Folders only organise the editor; they never change URLs. Each page shows its slots and the content assigned to each. **+ page** adds a page with the site's template, **+ folder** a folder; pages and folders move by drag and drop.
- **Contents**: every HTML or Markdown content of the site. An unused content is in italics; a content used by several pages shows how many. **+ content** adds one.

A content is placed by dropping it on a slot in the Pages tree, or by choosing it in the slot's menu and pressing **Assign**. **Show slots** outlines the slots in the preview.

In the preview a click on a block selects it: a blue border, a label with the slot and its content, and a round button with a pen. A click on a link follows it, as a visitor would, also inside a block. The pen, a double click on the block, or a slot chosen in the Pages tree opens the block in a floating window: a title bar that moves it, collapses it, maximizes it and closes it, asking first when changes are not saved. One block is open at a time. The window has four tabs:

- **Preview**: the block as in the page, with the page's style sheets and inside the elements that hold its slot; a click on an element opens the CSS tab on that element's rules;
- **Jodit**, ready to write, with the page's style sheets too; **HTML**, the source in CodeMirror; the two stay in step;
- **CSS**: the rules of the page's style sheets that act on the block, by style sheet, each with the number of pages using it; each rule is edited as text and the change shows at once in Preview, in Jodit and in the page.

The window's footer says whether there are changes not saved; **Cancel** discards them, **Save** writes the content and the style sheets changed.

A page holds a *copy* of each content it shows. Editing a content or a style sheet in the block window changes the original; **Save** then shows the Update plan: every page holding a copy, selected unless its copy was changed in the page. **Update and render** brings the selected copies up to date. A page with a copy older than its original shows ↻; a page changed since the last Publish shows ●.

#### 3. SEO

The SEO tab lists the pages with the state of their checks. For the selected page it shows the public URL, title, description, canonical, robots, social share fields, the images with their alt texts and JSON-LD. An empty field shows, beside it, the value it takes: the root page's for description, robots and sharing image, the page name for the title.

The root page (URL `/`) also holds the site defaults: languages, site name, public origin, organisation, sharing image and robots. The public origin is the site's address.

Changing a page's URL adds a 301 redirect from the old one. The right column shows the page as a search result and as a social share, and the checks of the page: duplicate titles, missing descriptions, images without alt, broken internal links, iframe slots without fallback, missing origin. Publish shows the same checks as warnings; they never block it.

#### 4. Languages

The site's languages are set in the root page's site defaults, main language first, as tags such as `it, en`. With several languages, a selector in the site bar sets the language shown by the Visual editor, the SEO tab and the preview.

- A content shown in another language has its own translation. In the Pages and Contents trees a translation is marked ○ missing, ↻ to update (its main text changed since) or ◐ to review (proposed by Help me).
- A missing translation shows the main text: the preview outlines those slots in red, the published page shows the main text without marks.
- The block window shows the main text above the translation; **Save** writes the translation, **Confirm translation** accepts one proposed by Help me.
- In the SEO tab each language has its own URL and fields; the URL of another language is written without its prefix, which Kajenn Press adds (`/en/about/`). An empty field takes the main language's value.

#### 5. Help me

**Help me** opens a chat with Sonnet beside the Visual editor. It reads the site, asks what the site is for, offers palettes, font stacks and SVG logo sketches as cards to click, and builds templates, contents, assets, pages, slots, SEO and translations; it saves when a piece of work is done. Its translations stay to review until the operator confirms them.

Help me works under the lock of the operator who opened it; its changes are recorded as the operator's, made through Help me. It cannot publish, roll back, change maintenance or visibility, or create links: those stay in the Published site tab. Each chat is kept with the site and can be resumed from the chat menu; the cost line shows tokens and dollars per chat and per site, for information only.

#### 6. Publish and manage the published site

The Published site tab shows the state of the site (Not published, Public, Private, Maintenance), its address, the last Publish and the pages changed since, and the published site itself.

- **Publish…** lists every page in every language with its state (new, changed, unchanged, removed) and warnings; changed pages are selected. Each language publishes on its own.
- **Rollback…** puts an earlier version of one page in one language online, or restores a saved source version of the whole site and republishes it.
- **Maintenance on** makes the site answer 503 to visitors.
- **Private link** creates a link valid 8 hours or 7 days that shows the real site while it is private or in maintenance, and switches the site between private (404 to visitors) and public.

**Go live…** puts the site online on a registered server, or moves it to another one:

1. **Server**: one of the registered servers, with its addresses.
2. **Address**: the domain and which name is the address (the domain or `www.`); the other answers 301. **Save server and address** writes the root page's public origin and the server.
3. **DNS records**: the records to create at the DNS provider and what public resolvers see; **Check again** reads them again.
4. **Publish and go live**: publishes, asks the server to serve the address and obtain its certificate, checks the address, and shows each step.

A site server reads its addresses from the release bucket and serves a new one without restart (booklet *Publication and serving*).

### Rules

- **must** — Take the site before editing it. *(Changes are refused to anyone but the holder of the site.)*
- **should** — Save after a coherent piece of work. *(A working copy is lost when someone else takes the site.)*
- **must-not** — Edit a shared content inside one page when every page should change: edit the content. *(A copy changed in the page is left out of Update.)*

### Current limits

- A style sheet saved from the CSS tab is the browser's serialization of its rules: comments and the file's own formatting are not kept.
- The CSS tab ignores states and pseudo-elements when it matches rules: a rule for `a:hover` is shown for the link; a rule only for `::selection` is not shown.
- SEO checks run in the main language only. · `src/kajenn_press/site/seo.py:398`
- Servers are registered through `server_add` (REST or MCP); the tab has no form for it.
- While the site is private or in maintenance, the private link opens in a new browser tab: inside the administration's frame the browser does not send its cookie.

### Verified facts

- `RUN` `src/kajenn_press/admin/pages/site.js:9` · 2026-10-29 — In the preview a click selects a block, a link inside a block is followed, and the pen or a double click asks to edit it.
- `RUN` `src/kajenn_press/admin/pages/index.py:45` · 2026-10-29 — Two pages opened from the navigation show in two closable tabs; closing one keeps the other's state.
- `RUN` `src/kajenn_press/admin/pages/site.py:483` · 2026-10-29 — The block window shows the hero in Jodit and Preview with the page's Georgia titles; Save and Update and render show the change in the page.
- `RUN` `src/kajenn_press/admin/pages/site.js:277` · 2026-10-29 — For the h1 picked in Preview the CSS tab shows `body, h1, …`, `h1, h2` and `h1`; a colour added to `h1` shows at once and, after Save and Update and render, in the rendered page.
- `READ` `src/kajenn_press/admin/pages/index.py:33` · 2026-10-29 — The navigation lists Sites (with holder and `+ new site`) and Library (starting sites).
- `READ` `src/kajenn_press/site/lock.py:15` · 2026-10-29 — The editing lock expires after 30 minutes without activity.
- `READ` `src/kajenn_press/site/service.py:344` · 2026-10-29 — `site_save` writes the working copy as a new version of the source zip.
- `TEST` `src/kajenn_press/site/model.py:471` · 2026-10-29 — The Update plan selects every copy not changed in its page that differs from the original, translations included.
- `READ` `src/kajenn_press/admin/pages/site.py:593` · 2026-10-29 — Changing a page URL adds a 301 redirect from the old one.
- `TEST` `src/kajenn_press/site/seo.py:137` · 2026-10-29 — An empty SEO field takes the root page's value, never the parent's; in another language, the main language's value.
- `TEST` `src/kajenn_press/site/languages.py:117` · 2026-10-29 — A translation is missing, to update, to review or done.
- `RUN` `src/kajenn_press/admin/pages/site.py:357` · 2026-10-29 — The language selector re-renders the Visual editor and outlines main-text slots in red in the preview.
- `TEST` `src/kajenn_press/help/tools.py:45` · 2026-10-29 — Translations written by Help me are always to review.
- `RUN` `src/kajenn_press/help/chat.py:111` · 2026-10-29 — A Help me turn from the tab added a page and saved the site against the Claude API.
- `RUN` `src/kajenn_press/admin/pages/site.py:895` · 2026-10-29 — Go live on the local demo saved server and address, showed the DNS records seen, and reported dns, publish, certificate and online.
- `RUN` `src/kajenn_press/admin/pages/site.py:783` · 2026-10-29 — The Published site tab published one page, set maintenance, created a private link and rolled back one page on the local demo.

### Related documents

- `booklet/templates`
- `booklet/publication`
- `proposal/site-tab-redesign`
