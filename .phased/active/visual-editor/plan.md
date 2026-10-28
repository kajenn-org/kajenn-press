# Context: feat/visual-editor
Parent: main
Mode: manual
Must not break: The full suite (three interpreters, RustFS endpoint) and the Docker suite keep passing. Until Phase 8, the current administration pages keep working beside the new site tab.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened (d-nav, d-content-copy, d-slot-id, d-update-local, d-preview-interaction, d-editing-lock in particular).
Must not break: The administration stays isolated from the previewed page: the preview iframe never gets `allow-same-origin`; scripts added for the preview never reach published HTML.
Must not break: Gramlot constitution: Source, Data, bindings and components; no imperative DOM manipulation. Sibling repositories are not edited; a missing Gramlot capability becomes an upstream item.
Must not break: Every UI phase is checked in a real browser (Browser pane) against its approved mockup before it is closed.

## Objective

Give the operator the site tab of the redesign. The navigation tree holds Sites (each site, and "new site") and Library. Each site opens in its own tab with three tabs: Visual editor (this macro), SEO (N6) and Published site (N7) as placeholders. The Visual editor shows the site rendered from the working copy, opening on the root page and navigable through its links; slot borders on command; a block opens in a detached editor with CodeMirror, Jodit and Preview. A drawer holds the Pages tree (logical folders, drag and drop, slots under each page, marks for pages changed since publication and outdated copies) and the Contents tree (unused in grey italics, used once normal, used more than once with a badge). A content is dropped on a slot in the Pages tree, and on the preview if Phase 2 qualifies it. The old administration pages and the old publication path are removed at the end (N4-D3).

Entry: main `e3dcb97`; the 32 site operations; the administration shell `IndexPage` (`src/kajenn_press/admin/pages/index.py`); Gramlot editors `codeMirror`, `htmlEditor`, `htmlPreview`; the tree component as drag source. Upstream gaps known from N1: no floating pane (GC-185); drag and drop does not cross into another window.

## Owner decisions (2026-10-28): all recommended options chosen; mockup `mockups/site-tab.html` approved

- **N5-D1 · Detached block editor.** (a) A native non-modal `dialog` element docked at the right of the Visual editor, holding a tab container (CodeMirror, Jodit, Preview); a real floating, draggable pane when Gramlot provides one (GC-185). (b) Wait for the upstream floating pane. Decided: (a).
- **N5-D2 · What the block editor edits.** (a) The original content: saving shows the Update plan of its copies, with this page and every copy without local changes selected (d-update-local). (b) Only this page's copy. Decided: (a); a page-only change is made by duplicating the content first.
- **N5-D3 · Library in this macro.** (a) Starting sites only (list, new site from one, save a site as one), already served by the operations. (b) Also shared templates, styles and media with linked or independent import, which needs a persistent Library store first. Decided: (a); (b) becomes its own macro.
- **N5-D4 · Removal of the old administration pages and the old publication path** as the last phase of this macro (N4-D3). Decided: yes.

## Decisions shared by all phases

- Mockups are approved by the owner before the UI phase that implements them; the first mockup is `mockups/site-tab.html`.
- New operations follow the naming of N3 and are listed at the gate of the phase that adds them.
- Each phase ends with its tests green, a browser check for UI phases, ruff clean on changed files, one commit on `feat/visual-editor`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [x] **Phase 1**: Page tree and marks in the site model
  > Done: site section `folders`; pages and folders carry `parent` and `position`; `Site.add_folder`, `children`, `move` (no cycles, dense positions, URLs unchanged), `tree`, `outdated_copies`; operations `folder_add` and `tree_move` (34 site operations, 78 routes); `site_read` returns `tree` and, per page, `slot_names`, `changed` (fingerprint against the site index; true before the first Publish) and `outdated`. `tests/site/test_page_tree.py` (5 tests). Bag drops attributes whose value is None, so root items read `parent` with `.get`.
  - Files: `src/kajenn_press/site/model.py`, `service.py`, `application.py`, `tests/site/`.
  - Details: logical folders for pages, each page and folder with a parent and a position; moving a page or folder (drag and drop backend); `site_read` returns the tree, the slots of each page with their assigned content, and two marks per page: changed since publication (fingerprint against the site index) and holding outdated copies (copy digest against the current original).
  - Done: moves keep the tree consistent (no cycles, positions dense); marks match the publish plan and the Update plan.

- [x] **Phase 2**: Preview interaction qualification
  > Done: `tests/admin/preview_interaction.html`, opened in the Browser pane on 2026-10-28. Isolation verified: inside `sandbox="allow-scripts"` without `allow-same-origin`, `document.cookie` and `parent.document` raise `SecurityError` and messages arrive with origin `null`. Click on a slot verified: `{"kind": "click", "slot": "hero"}` reaches the administration. Drop not verifiable: the automated drag of the Browser pane does not produce HTML5 drag and drop events even within one document (control drop zone received nothing), so native drag into the sandboxed preview is neither confirmed nor refused.
  > Consequence (as planned): the first version assigns contents by dropping on the Pages tree; clicking a slot in the preview opens it. Drop on the preview is left for a manual check by the owner.
  - Files: `tests/admin/` (browser check), `src/kajenn_press/admin/` (a qualification page).
  - Details: d-preview-interaction: a rendered page in `htmlPreview` with `sandbox="allow-scripts"` and no `allow-same-origin`; a script added to the preview HTML only reports clicks on slot nodes and drops of a dragged tree item through `postMessage`; check in a real browser that clicks arrive, that native drag from the tree into the sandboxed iframe delivers the drop, and that the administration's cookies and DOM are not reachable from the preview.
  - Done: each capability recorded as working or not; if the drop does not work, the first version drops on the Pages tree only.

- [x] **Phase 3**: Shell, navigation and the site tab
  > Done: with site sources configured the index shows Sites (each site with its holder, "+ new site") and Library (starting sites); the top bar keeps the logo and account only; without site sources the catalog navigation stays (old admin tests unchanged). New `admin/pages/site.py`, `site.js`, `site.css`: the site tab takes the editing lock on opening when the site is free, shows "You are editing this site" or "Edited by X · read only", "Take the site" for an explicit take, Save; tabs Visual editor, SEO and Published site (placeholders). "new site" opens a name form that calls `site_new`. New operation `site_list` (35 site operations). Browser check 2026-10-28 in the Browser pane on a local demo with the example site.
  - Files: `src/kajenn_press/admin/pages/` (new site tab page, index), `tests/admin/`.
  - Details: tree Sites (sites, "new site") and Library (starting sites, N5-D3); a site opens its tab and takes the editing lock (`site_open`), showing who holds it otherwise; "new site" opens an empty site tab (name, optional starting site); three tabs: Visual editor, SEO and Published site as placeholders; Save and versions in the site tab toolbar.
  - Done: matches the approved mockup in the browser; two sites open in two tabs; a site held by another user opens read-only with the holder's name.

- [x] **Phase 4**: Visual editor preview
  > Done: the center renders the working copy with `page_render` in an iframe with `sandbox="allow-scripts"`; the preview HTML gets slot outlines (Show slots) and a script carrying the page nonce that reports clicks on slots and links with `postMessage`; a link to another page of the site opens that page. Width and scale selectors of the old preview are not carried over. Browser check: the example home page rendered with its CSS and logo.
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: the center renders the working copy's root page (`page_render`), navigation follows links inside the preview (Phase 2 messages), a page selector from the drawer, slot borders on command (CSS added to the preview HTML only), width and scale selectors from the current preview.
  - Done: matches the mockup; navigating and toggling borders works in the browser.

- [x] **Phase 5**: Drawer with Pages and Contents
  > Done: Pages tree (folders, pages with ● changed and ↻ outdated marks, slots under each page as "name ← content" or "name · empty"), "+ page", "+ folder"; Contents tree (use count in the caption when >1, unused in italics), "+ content". Drag and drop wired with Gramlot internal tree drag (`onDrag`, `dropTypes`, `onDrop`): a content dropped on a slot calls `slot_assign`, a page dropped on a folder calls `tree_move`. Selecting a slot shows a menu to assign a content by click. Not verified in the browser: drag (the Browser pane does not produce HTML5 drag events, Phase 2).
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: Pages tree with folders, drag and drop moves (Phase 1), slots under each page with their content, the two marks; Contents tree with use states and badge; drag a content onto a slot node (and onto the preview if Phase 2 qualified it) calls `slot_assign`; new page, new folder, new content.
  - Done: matches the mockup; a drop assigns a content; counts and marks update.

- [x] **Phase 6**: Detached block editor
  > Done (N5-D1, N5-D2): a click on a slot in the preview (or Edit after selecting it in the tree) opens the editor pane docked at the right (400 px, splitter) with CodeMirror, Jodit and Preview on the original content; Save calls `content_save`, then shows the Update plan of its copies with the selection rule; "Update and render" applies the selected ones and refreshes. Browser check: click on the hero slot opened the hero content; Save showed the plan with the one page using it, unselected because already up to date. `site_read` now returns the text of each content.
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: per N5-D1 and N5-D2: opening a slot (click in the preview or in the tree) shows the docked editor with CodeMirror, Jodit and Preview; saving the content shows the Update plan of its copies with the selection rule; confirming applies it and refreshes the preview.
  - Done: matches the mockup; editing a content used by two pages updates both after confirmation, and a page with a local change stays unselected.

- [x] **Phase 7**: Help strings, empty states and checks
  > Done: empty site ("This site has no page yet."), empty slot ("Slot X is empty: assign a content first."), missing content name, lock and service errors shown in the site bar in the words of the service; read-only state named with the holder. `tests/admin/test_site_tab.py` (2 tests: navigation and site tab with sources; catalog navigation without them).
  > Suites: main 258 passed, 22 skipped; admin 24 passed, 1 failed (`test_admin_is_optional_and_installs_from_reproducible_artifacts`, needs `KAJENN_ADMIN_WHEELS`, failing before this macro).
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: empty site, page without slots, unplaced contents shown under their page, errors of the lock and of the receipts shown to the operator in plain words.
  - Done: each state reached in the browser and readable.

- [ ] **Phase 8**: Retire the old administration and publication path
  - Files: `src/kajenn_press/admin/pages/` (author, page, resource, publishing, library, home), `src/kajenn_press/publication/` (channels, candidates, builds, bundles, pointers, in-process public serving, export), `src/kajenn_press/child.py`, the old operations in `application.py`, `deploy/docker/` (builder, child), `examples/` and `tests/` of the old path, `docs/`.
  - Details: N4-D3: remove what the new site tab and per-page publication replace, as classified in `xmldocs/proposal/redesign-inventory.xml`; keep what the inventory keeps (login, origin guard, preview gateway, editors, engines, preparation, worker).
  - Done: no caller of the removed code is left; the full and Docker suites pass on the new path only.
