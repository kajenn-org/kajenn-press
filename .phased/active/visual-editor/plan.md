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

- [ ] **Phase 2**: Preview interaction qualification
  - Files: `tests/admin/` (browser check), `src/kajenn_press/admin/` (a qualification page).
  - Details: d-preview-interaction: a rendered page in `htmlPreview` with `sandbox="allow-scripts"` and no `allow-same-origin`; a script added to the preview HTML only reports clicks on slot nodes and drops of a dragged tree item through `postMessage`; check in a real browser that clicks arrive, that native drag from the tree into the sandboxed iframe delivers the drop, and that the administration's cookies and DOM are not reachable from the preview.
  - Done: each capability recorded as working or not; if the drop does not work, the first version drops on the Pages tree only.

- [ ] **Phase 3**: Shell, navigation and the site tab
  - Files: `src/kajenn_press/admin/pages/` (new site tab page, index), `tests/admin/`.
  - Details: tree Sites (sites, "new site") and Library (starting sites, N5-D3); a site opens its tab and takes the editing lock (`site_open`), showing who holds it otherwise; "new site" opens an empty site tab (name, optional starting site); three tabs: Visual editor, SEO and Published site as placeholders; Save and versions in the site tab toolbar.
  - Done: matches the approved mockup in the browser; two sites open in two tabs; a site held by another user opens read-only with the holder's name.

- [ ] **Phase 4**: Visual editor preview
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: the center renders the working copy's root page (`page_render`), navigation follows links inside the preview (Phase 2 messages), a page selector from the drawer, slot borders on command (CSS added to the preview HTML only), width and scale selectors from the current preview.
  - Done: matches the mockup; navigating and toggling borders works in the browser.

- [ ] **Phase 5**: Drawer with Pages and Contents
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: Pages tree with folders, drag and drop moves (Phase 1), slots under each page with their content, the two marks; Contents tree with use states and badge; drag a content onto a slot node (and onto the preview if Phase 2 qualified it) calls `slot_assign`; new page, new folder, new content.
  - Done: matches the mockup; a drop assigns a content; counts and marks update.

- [ ] **Phase 6**: Detached block editor
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: per N5-D1 and N5-D2: opening a slot (click in the preview or in the tree) shows the docked editor with CodeMirror, Jodit and Preview; saving the content shows the Update plan of its copies with the selection rule; confirming applies it and refreshes the preview.
  - Done: matches the mockup; editing a content used by two pages updates both after confirmation, and a page with a local change stays unselected.

- [ ] **Phase 7**: Help strings, empty states and checks
  - Files: `src/kajenn_press/admin/pages/`, `tests/admin/`.
  - Details: empty site, page without slots, unplaced contents shown under their page, errors of the lock and of the receipts shown to the operator in plain words.
  - Done: each state reached in the browser and readable.

- [ ] **Phase 8**: Retire the old administration and publication path
  - Files: `src/kajenn_press/admin/pages/` (author, page, resource, publishing, library, home), `src/kajenn_press/publication/` (channels, candidates, builds, bundles, pointers, in-process public serving, export), `src/kajenn_press/child.py`, the old operations in `application.py`, `deploy/docker/` (builder, child), `examples/` and `tests/` of the old path, `docs/`.
  - Details: N4-D3: remove what the new site tab and per-page publication replace, as classified in `xmldocs/proposal/redesign-inventory.xml`; keep what the inventory keeps (login, origin guard, preview gateway, editors, engines, preparation, worker).
  - Done: no caller of the removed code is left; the full and Docker suites pass on the new path only.
