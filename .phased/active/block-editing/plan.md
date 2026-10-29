# Context: feat/block-editing
Parent: main
Mode: manual
Must not break: The full suite, the admin suite and the Docker suite keep passing.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened; this plan applies `d-block-editing` and the 40-pixel bar of the section The site tab.
Must not break: Selection marks, labels and the pen exist only in the preview; published pages never carry them.
Must not break: Every UI phase is checked in a real browser against the approved mockup `mockups/block-editing.html`.

## Objective

Block editing and the site tab's frame as in the approved mockup: one thin bar for the site and its tabs, a thin administration bar, every pane at full height; in the preview a single click selects a block (border, label, pen) and follows links; the pen or a double click opens one floating window, full height, on Jodit, with the HTML source sliding out beside it in CodeMirror; Save updates the preview.

Entry: main `8f3d402`. Inventory:
- `src/kajenn_press/admin/pages/index.py`: `top()` is a 64-pixel bar with a 48-pixel logo; `center()` is Gramlot's index center, a tab per opened site (the "Kajenn Press" tab strip); `bottom()` is a 30-pixel status bar.
- `src/kajenn_press/admin/pages/site.py` `site_workspace`: the bar is a `top` region with an `h1`, the holder text, Take the site, the language select, Help me, Save; below it a `tabContainer` with Visual editor, SEO, Published site (a second row).
- `site.py` `visual_editor`: drawer (Pages, Contents, slot Assign and Edit), stage with a status row, Show slots and the preview iframe, and a docked `right` region `block-editor` with tabs CodeMirror, Jodit, Preview, the main-language reference, Save, Confirm translation and the Update plan.
- `site.js`: `PREVIEW_SCRIPT` sends `slot` on any click in a slot (links inside a slot are not followed) and `link` on other links; `initialize` opens the docked editor on `slot`; `openSlot`, `closeEditor`, `saveContent`, `confirmTranslation`.
- Gramlot offers no floating pane; it has the HTML `dialog` element and absolutely positioned `div`s.

## Owner decisions (to take at the gate)

- **BE-D1 · The bars above the editor.** The site tab is a page inside the administration's iframe, so one row cannot span both. (a) Administration bar 40 pixels with a 22-pixel logo, the open-sites tab strip removed (one site open at a time, chosen in the navigation), the site bar 40 pixels with the three tabs inline; 80 pixels in all. (b) The same, keeping the open-sites strip; about 112 pixels. (c) The site bar alone, the administration bar hidden while a site is open; 40 pixels, sign-out moves into the site bar. Recommended: (a).
- **BE-D2 · The floating window.** (a) An absolutely positioned `div` inside the stage, dragged sideways by its header in `Logic`, widened with CSS `resize: horizontal`. (b) A non-modal HTML `dialog`. Recommended: (a): it stays inside the stage and needs no top layer.
- **BE-D3 · The Pages tab's slot box.** The box under the tree (slot name, content select, Assign, Edit) duplicates the selection. (a) Keep Assign for a slot chosen in the tree, drop Edit (the tree's slot node opens the window like the pen). (b) Keep both. Recommended: (a).

## Decisions shared by all phases

- Each phase ends with its tests green, a browser check against the mockup, ruff clean on changed files, one commit on `feat/block-editing`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [ ] **Phase 1**: Thin bars and full height
  - Files: `src/kajenn_press/admin/pages/index.py`, `index.css` (or the admin stylesheet in use), `site.py`, `site.css`, `tests/admin/`.
  - Details: per BE-D1: administration bar 40 pixels, small logo, user and Sign out; the site bar one row of 40 pixels with name, holder, the three tabs, language, Help me, Save (Take the site in place of Save when read only); the tabs drive the existing panes. Drawer, stage, preview iframe, SEO and Published site panes take the full height.
  - Done: the site tab matches the mockup's bar; no pane leaves empty space below it at 1280×800.

- [ ] **Phase 2**: Selecting a block in the preview
  - Files: `site.js` (`PREVIEW_SCRIPT`, `initialize`), `site.py`, `tests/admin/`.
  - Details: a single click on a slot selects it in the preview: border, label "slot · content", a round pen button, all added by the preview script; a single click on a link sends `link` even inside a slot; the pen and a double click send `edit` with the slot. Selection also selects the slot node in the Pages tree.
  - Done: in the browser, links inside blocks are followed; the pen and the double click both ask to edit the right slot.

- [ ] **Phase 3**: The floating editor
  - Files: `site.py` (`visual_editor`), `site.js`, `site.css`, `tests/admin/`.
  - Details: per BE-D2: the docked `block-editor` region is removed; one window over the stage, full height, header with the slot and content, `</> HTML` and close; Jodit on open; the HTML drawer with CodeMirror on the same value, in step both ways; the main-language reference, Confirm translation and the Update plan move into the window; footer with the change state, Cancel and Save; Save re-renders the preview. Per BE-D3 the slot box keeps Assign only.
  - Done: matches the mockup in the browser: open by pen and double click, write in Jodit, see the HTML change, edit the HTML and see Jodit change, Save updates the preview, Cancel discards.

- [ ] **Phase 4**: Documentation and close
  - Files: `xmldocs/booklet/site-tab.xml` (and its renders), `tests/admin/`.
  - Details: the booklet's Visual editor section describes selection, the pen, the floating window and the bar; facts verified by run.
  - Done: full and admin suites green; booklet valid and rendered; plan archived, roadmap updated.
