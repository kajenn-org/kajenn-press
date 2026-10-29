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

## Owner decisions (to take at the gate)

- **GS-D1 · Which Gramlot moves.** (a) The administration only (`admin` extra to gramlot 0.3.20 and gramlot-py-server 0.3.20); the render worker keeps gramlot 0.3.8 and its contract. (b) Both. Recommended: (a): the published HTML does not change and the render contract stays as it is.
- **GS-D2 · Rewriting a style sheet.** (a) A new operation `asset_save` (site_id, key, asset_id, data_base64) rewrites a site asset; the pages holding a copy come in the existing Update plan (`copies_update_plan`, `copies_update`). (b) `asset_save` also updates every copy at once. Recommended: (a): the same review as for contents.
- **GS-D3 · Which rules the CSS tab shows.** (a) The preview script, inside the page, reads the page's style sheets and returns the rules whose selector matches the slot element or an element inside it, with the style sheet's asset name (the administration tells the script which `data:` URL is which asset); a click in the Preview tab narrows to one element. (b) The server parses the CSS and matches selectors. Recommended: (a): the browser matches exactly what is seen.

## Decisions shared by all phases

- Each phase ends with its tests green, a browser check against the mockup for UI phases, ruff clean on changed files, one commit on `feat/gramlot-shell`. Phases run back to back without confirmation between them; the run stops only at a gate, a blocker or the end.
- Every phase runs on Opus, never Fable.

## Work Plan

- [ ] **Phase 1**: Gramlot 0.3.20 without visible change
  - Files: `pyproject.toml`, `src/kajenn_press/admin/host.py`, `src/kajenn_press/admin/pages/*.py`, `deploy/docker/lock.sh`, `deploy/docker/requirements-websites.txt`, `tests/admin/`.
  - Details: per GS-D1: gramlot 0.3.20 and gramlot-py-server 0.3.20 in the `admin` extra; collections as `GramlotCollection` packages chosen per page; the host serves them as gramlot-py-server 0.3.20 expects; pages adapted to relative index paths and consumed `dataSetter`s; locks regenerated for websites.
  - Done: full, admin and Docker suites green; the demo opens, edits and publishes as before.

- [ ] **Phase 2**: The gallery shell
  - Files: `index.py`, `index.css`, `index.js`, `tests/admin/`.
  - Details: per `d-gramlot-shell`: a `framePane` with a vertical icon `menu` on the left (Sites, Library, Settings, Sign out), the navigation of sites and starting sites beside it, Gramlot's index tabs (closable, one iframe per opened site) in the center; the `stackContainer` of BE-D1 is removed.
  - Done: matches the mockup: two sites open in two tabs, each keeps its state, closing a tab closes the site page.

- [ ] **Phase 3**: Each site tab a frame with its toolbar
  - Files: `site.py`, `site.js`, `site.css`, `tests/admin/`.
  - Details: a `tabContainer` with Visual editor, SEO, Published site; each a `framePane` whose top is a `menu` bar: Visual editor (language, Show slots, page path, Help me, Save or Take the site), SEO (language, checks, Save), Published site (state, address, Publish…, Rollback…, Maintenance, Private link, Go live…). The 40-pixel site bar goes away.
  - Done: matches the mockup's three toolbars; every command works as before.

- [ ] **Phase 4**: The block in a floating window with the page's CSS
  - Files: `site.py` (`block_window`), `site.js` (preview script, Logic), `site.css`, `tests/admin/`.
  - Details: a `floatingPane` (title, collapse, maximize, close; `beforeClose` asks before losing changes) whose `framePane` center is a `tabContainer` with Preview, Jodit, HTML (CodeMirror) and CSS, and whose bottom is a `menu` bar with the change state, Cancel and Save. The preview script sends, with `edit`, the chain of elements holding the slot (tag, id, classes); Preview and Jodit show the block inside that chain with the page's style sheets. The CSS tab is a placeholder until Phase 5.
  - Done: matches the mockup; the hero block shows in Jodit and Preview as in the page; Cancel, Save and the Update plan work as in block editing.

- [ ] **Phase 5**: The CSS tab
  - Files: `src/kajenn_press/site/model.py`, `service.py`, `application.py`, `site.js`, `site.py`, `tests/site/`, `tests/admin/`.
  - Details: per GS-D2 and GS-D3: operation `asset_save`; the preview script returns the rules acting on the block, by style sheet; the tab lists them as editable text with "used by N pages", narrows to the element clicked in Preview, applies changes at once to Preview, Jodit and the page preview; Save writes the style sheet and shows the Update plan for its copies.
  - Done: in the browser, changing `.hero h1` changes the title in the window and in the page; Save writes `site.css`; the Update plan lists the pages holding it; tests for `asset_save` and its copies.

- [ ] **Phase 6**: Documentation and close
  - Files: `xmldocs/booklet/site-tab.xml`, `xmldocs/booklet/operations.xml`, their renders, `README.md`.
  - Details: the booklets describe the shell, the frames and toolbars, the block window and the CSS tab; operations gain `asset_save`.
  - Done: full, admin and Docker suites green; booklets valid and rendered; plan archived, roadmap updated.
