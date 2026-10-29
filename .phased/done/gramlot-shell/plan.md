# Context: feat/gramlot-shell
Parent: main
Mode: manual
Must not break: The full suite, the admin suite and the Docker suite keep passing.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened; this plan applies `d-gramlot-shell` and `d-css-rules`, and keeps `d-block-editing` (selection, pen, double click).
Must not break: Selection marks, labels and the pen exist only in the preview; published pages never carry them.
Must not break: Every UI phase is checked in a real browser against the approved mockup `mockups/shell.html`.

## Objective

The administration on Gramlot 0.3.20 as in its gallery: an icon column, the list of sites, one closable tab per opened site holding the site's page in an iframe; inside a site, three tabs, each a frame with its own toolbar; the block in a floating window (title bar, a frame with the tabs Preview, Jodit, HTML, CSS, footer Cancel and Save) showing the page's own CSS; the CSS tab with the rules acting on what is seen, edited in place and saved to the style sheet.

Entry: main `7e19ed9`. Inventory:
- `pyproject.toml`: extra `admin` pins `gramlot==0.3.9`, `gramlot-py-server==0.2.12`; extra `render` pins `gramlot==0.3.8` (the render worker's contract, `src/kajenn_press/rendering/contract.py`).
- `src/kajenn_press/admin/host.py` `AdminApplication`: builds collection dictionaries `{"grammar", "module": "/assets/<name>.js"}` and serves `resources/components`. Gramlot 0.3.15 replaced both: collections are prepared `GramlotCollection` packages chosen per page (`gramlots = [...]`), `resources/components` no longer exists, and gramlot-py-server 0.3.20 serves collections under `/gramlot/collections/...` (`collection_resources.py`).
- Gramlot 0.3.17 `IndexPage`: relative data paths, `indexMount(node)`, closable tabs, load states. kajenn's `index.py` overrides `center` with a `stackContainer` (block editing BE-D1, now superseded) and drops the status bar.
- Gramlot 0.3.15 `dataSetter` is consumed after installation.
- `site.py` `site_workspace`: a 40-pixel bar with three tab buttons over a `stackContainer`; the block in a `div` window (`block_window`) with Jodit and CodeMirror side by side.
- New components available in 0.3.20: `framePane` (`frame.top/left/center/bottom`), `menu(presentation="bar")` with `menuline` and `spacer`, `floatingPane` (title bar, `open`, `beforeClose`, exactly one `framePane` child through `window.frame`), `tabContainer` panes with `detachable`. Reference: gramlot-examples `gallery/page.py` and `pages/05-menus/14_floating_editor.py` at tag v0.3.22.
- Assets: pages hold copies of site assets with their original's id and digest; operations exist for `asset_add` and `page_asset_add`, none to rewrite an asset.

## Owner decisions (2026-10-29): all recommended options chosen; mockup `mockups/shell.html` approved

- **GS-D1 · Which Gramlot moves.** (a) The administration only (`admin` extra to gramlot 0.3.20 and gramlot-py-server 0.3.20); the render worker keeps gramlot 0.3.8 and its contract. (b) Both. Decided: (a): the published HTML does not change and the render contract stays as it is.
- **GS-D2 · Rewriting a style sheet.** (a) A new operation `asset_save` (site_id, key, asset_id, data_base64) rewrites a site asset; the pages holding a copy come in the existing Update plan (`copies_update_plan`, `copies_update`). (b) `asset_save` also updates every copy at once. Decided: (a): the same review as for contents.
- **GS-D3 · Which rules the CSS tab shows.** (a) The preview script, inside the page, reads the page's style sheets and returns the rules whose selector matches the slot element or an element inside it, with the style sheet's asset name (the administration tells the script which `data:` URL is which asset); a click in the Preview tab narrows to one element. (b) The server parses the CSS and matches selectors. Decided: (a): the browser matches exactly what is seen.

## Decisions shared by all phases

- Each phase ends with its tests green, a browser check against the mockup for UI phases, ruff clean on changed files, one commit on `feat/gramlot-shell`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Gramlot 0.3.20 without visible change
  > Done: `admin` extra on gramlot 0.3.20 and gramlot-py-server 0.3.20. Finding: gramlot-py-server 0.3.20 requires kajenn >= 0.6.0, so the core dependency moved from `kajenn==0.5.0` to `kajenn==0.7.0` for every image; the main suite passed unchanged on kajenn 0.7.0 before any code change. `AdminApplication` passes Gramlot's prepared collections (`layout`, `tree`, `inputs`, `editors`) and no longer serves `resources/components`; the adapter serves collections under `/gramlot/collections`. Locks regenerated: kajenn 0.7.0 in the three images, gramlot 0.3.20 and gramlot-py-server 0.3.20 in websites; render keeps gramlot 0.3.8 (GS-D1). Checked in the browser on the demo: sign-in, navigation, a site opens, the block window opens; Jodit's height inside the current window shrinks with 0.3.20 (the window is rebuilt in Phase 4). Suites: main 231 passed, admin 3 passed, Docker 12 passed.
  - Files: `pyproject.toml`, `src/kajenn_press/admin/host.py`, `src/kajenn_press/admin/pages/*.py`, `deploy/docker/lock.sh`, `deploy/docker/requirements-websites.txt`, `tests/admin/`.
  - Details: per GS-D1: gramlot 0.3.20 and gramlot-py-server 0.3.20 in the `admin` extra; collections as `GramlotCollection` packages chosen per page; the host serves them as gramlot-py-server 0.3.20 expects; pages adapted to relative index paths and consumed `dataSetter`s; locks regenerated for websites.
  - Done: full, admin and Docker suites green; the demo opens, edits and publishes as before.

- [x] **Phase 2**: The gallery shell
  > Done: `index.py` builds the gallery's frame: a `framePane` whose left is a vertical icon `menu` (Navigation, which opens and closes the navigation drawer like the gallery's, and Sign out with the identity in its tooltip), whose center is Gramlot's index: the navigation of sites and starting sites under the logo, and Gramlot's closable tabs, one iframe per opened page. The top bar, the status bar and BE-D1's `stackContainer` are removed, with their CSS. A page Logic cannot extend another class in Gramlot 0.3.20, so `index.js` delegates `indexMount` to `IndexLogic`. Checked in the browser: the demo site and New site open in two tabs, the site keeps its state when the other closes, Navigation closes the drawer. Admin test follows the shell; admin suite 3 passed.
  - Files: `index.py`, `index.css`, `index.js`, `tests/admin/`.
  - Details: per `d-gramlot-shell`: a `framePane` with a vertical icon `menu` on the left (Sites, Library, Settings, Sign out), the navigation of sites and starting sites beside it, Gramlot's index tabs (closable, one iframe per opened site) in the center; the `stackContainer` of BE-D1 is removed.
  - Done: matches the mockup: two sites open in two tabs, each keeps its state, closing a tab closes the site page.

- [x] **Phase 3**: Each site tab a frame with its toolbar
  > Done: the site page is a `tabContainer` (Visual editor, SEO, Published site; selected page kept in `site.tab`); each tab is a `framePane` whose top is a Gramlot `menu` bar (`toolbar()`): Visual editor (language, Show slots, page path and messages; Help me, Take the site when another holds it, Save), SEO (language and the site checks), Published site (state, address, last Publish, messages; Publish…, Rollback…, Maintenance, Private link, Go live…). SEO and Published site build their frame inside their remote panel. The 40-pixel site bar and its CSS are removed. Checked in the browser: the three tabs switch, Publish… opens its panel, Save writes a version ("Saved as version …"), SEO shows its toolbar. The SEO toolbar has no Save: each SEO form keeps its own Save SEO button. Admin test follows; admin suite 3 passed.
  - Files: `site.py`, `site.js`, `site.css`, `tests/admin/`.
  - Details: a `tabContainer` with Visual editor, SEO, Published site; each a `framePane` whose top is a `menu` bar: Visual editor (language, Show slots, page path, Help me, Save or Take the site), SEO (language, checks, Save), Published site (state, address, Publish…, Rollback…, Maintenance, Private link, Go live…). The 40-pixel site bar goes away.
  - Done: matches the mockup's three toolbars; every command works as before.

- [x] **Phase 4**: The block in a floating window with the page's CSS
  > Done: `block_window` is a Gramlot `floatingPane` (title from `site.editor_title`, open on `site.editor_open`, movable, resizable, collapsible, maximizable; `beforeClose` asks before losing changes) whose `framePane` holds the main-language reference on top, a `tabContainer` (Preview, Jodit, HTML, CSS placeholder) in the center, and in the bottom the Update plan and a menu bar (change state, translation note, Confirm translation, Cancel, Save). The preview script reports, once loaded, the chain of elements holding every slot. Preview is a sandboxed frame built in Logic: the page's style sheets, the chain, the text. Jodit edits in a same-origin iframe: it receives the page's style sheets as `<style>` text decoded from their `data:` URLs (a `<link>` moved from the admin document never loaded) and the chain's classes; the editor's own unlayered styles move into a layer declared first, since unlayered rules beat a site's layered ones. An editor field sits in a label box that did not take the tab's height: the box now does. Checked in the browser: the hero block in Jodit and in Preview with Georgia titles as in the page, HTML at full height, Cancel closes, Save → Update and render → the page preview holds the change. Admin test follows; admin suite 3 passed.
  - Files: `site.py` (`block_window`), `site.js` (preview script, Logic), `site.css`, `tests/admin/`.
  - Details: a `floatingPane` (title, collapse, maximize, close; `beforeClose` asks before losing changes) whose `framePane` center is a `tabContainer` with Preview, Jodit, HTML (CodeMirror) and CSS, and whose bottom is a `menu` bar with the change state, Cancel and Save. The preview script sends, with `edit`, the chain of elements holding the slot (tag, id, classes); Preview and Jodit show the block inside that chain with the page's style sheets. The CSS tab is a placeholder until Phase 5.
  - Done: matches the mockup; the hero block shows in Jodit and Preview as in the page; Cancel, Save and the Update plan work as in block editing.

- [x] **Phase 5**: The CSS tab
  > Done: operation `asset_save` (site_id, key, asset_id, data_base64; lock and key like `content_save`) rewrites a site asset; page copies change only through `copies_update` (GS-D2); 53 operations. `site_read` returns the text of CSS assets. The CSS tab parses each style sheet with `CSSStyleSheet.replaceSync`, walks style rules inside layers and media blocks, rebuilds the block in its chain with `DOMParser` and keeps the rules whose selector (states and pseudo-elements set aside; rules of pseudo-elements only left out) matches the slot element or an element inside it (GS-D3); grouped by style sheet with "used by N pages". A click in Preview reports the element's path from the block's root, narrows the list and opens the tab; Show all widens it again. An edited rule changes its sheet's draft (CSSOM), shown at once in Preview, in Jodit and in the page preview (its `data:` URL replaced). Save writes each changed sheet with `asset_save`, and the content when its text changed; one Update plan lists the copies of every original saved ("site.css · page"); Update and render runs `copies_update` per original. Limit: a saved sheet is the browser's serialization of the rules, so comments and the file's own formatting are not kept. Checked in the browser: h1 picked → `body, h1, …`, `h1, h2`, `h1`; `color: rgb(200, 30, 30)` added to `h1` turns the title red in Jodit, Preview and the page; Save → Update copies for the three pages → Update and render → the page renders red from the saved sheet. Tests: `asset_save` and its copies; admin test follows. Suites: main 232 passed, admin 3 passed.
  - Files: `src/kajenn_press/site/model.py`, `service.py`, `application.py`, `site.js`, `site.py`, `tests/site/`, `tests/admin/`.
  - Details: per GS-D2 and GS-D3: operation `asset_save`; the preview script returns the rules acting on the block, by style sheet; the tab lists them as editable text with "used by N pages", narrows to the element clicked in Preview, applies changes at once to Preview, Jodit and the page preview; Save writes the style sheet and shows the Update plan for its copies.
  - Done: in the browser, changing `.hero h1` changes the title in the window and in the page; Save writes `site.css`; the Update plan lists the pages holding it; tests for `asset_save` and its copies.

- [x] **Phase 6**: Documentation and close
  > Done: booklet site tab (the gallery frame and tabs, the frames and toolbars, the floating block window and its four tabs, the CSS tab, two limits, facts verified by run); booklet operations (53 operations, `asset_save`); README. Suites: main 232 passed, admin 3 passed, Docker 12 passed.
  - Files: `xmldocs/booklet/site-tab.xml`, `xmldocs/booklet/operations.xml`, their renders, `README.md`.
  - Details: the booklets describe the shell, the frames and toolbars, the block window and the CSS tab; operations gain `asset_save`.
  - Done: full, admin and Docker suites green; booklets valid and rendered; plan archived, roadmap updated.
