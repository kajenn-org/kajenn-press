# Phase 1 — verification checkpoint

## Machine verification

- Full inherited suite in the headless development profile: **102 passed, 1 admin module skipped**, 196.92 seconds. Log: `/tmp/kajenn-macro3-baseline-full.log`.
- After the requested Gallery and New site changes: **11 admin tests passed**, 8.52 seconds. Log: `/tmp/kajenn-admin-gallery-final-tests.log`.
- Relevant original API/service suite after those changes: **15 passed**, 2.11 seconds. Log: `/tmp/kajenn-admin-api-final.log`.
- `ruff check src tests examples`: passed; workflow validator: 0 errors, 0 warnings.
- Plan-owned test names and every contract comment retained; bodies implemented without changing the authored contracts.
- Installed final wheel smoke checks (`python -I`): headless host constructs without Gramlot/adapter; admin host constructs with all Gallery pages, companion JS and CSS present.
- Clean admin and headless installs passed `pip check`. Static worker stays in the previously qualified Gramlot 0.3.8 environment.

## Exact commands and artifacts

```sh
KAJENN_APP_PYTHON=/tmp/kajenn-macro3-headless-env/bin/python KAJENN_RENDER_PYTHON=/tmp/kajenn-macro2-render-env/bin/python /tmp/kajenn-macro3-admin-env/bin/python -m pytest -q tests/admin
KAJENN_APP_PYTHON=/tmp/kajenn-macro3-headless-env/bin/python KAJENN_RENDER_PYTHON=/tmp/kajenn-macro2-render-env/bin/python .venv/bin/python -m pytest -q tests/api tests/services
.venv/bin/python -m ruff check src tests examples
```

Upstream artifact hashes: `docs/admin-artifacts.json`; qualified environment: `docs/admin-qualified-freeze.txt`.
Application wheel SHA256: `954c35716637dec395ab82cad9252653b2b8cb6f0c47426226460d344effa7d4`.
Wheel location: `/tmp/kajenn-macro3-wheels/kajenn_public_site-0.1.0-py3-none-any.whl`.
These temporary artifact locations must be preserved externally or replaced by newly qualified releases; no editable sibling checkout is a substitute.

## MCP exercised

Authenticated real ASGI MCP requests create site, template, content and language variant using Bearer authority without relying on browser cookies; UI and REST read the same revision. Revoked grants reject commands. Missing Origin with Bearer discards cookies before authentication so an invalid credential cannot fall back to a session. Cross-origin browser requests remain rejected.

## Browser status — still open

The owner performed login into the first implementation; session refresh, site/record rendering and absence of console errors were observed. The owner then requested the Gallery tree/iframe structure and New site toolbar. Those supersede the first screenshots; the updated visual contract is `mockups/phase-1.html`, with the earlier approved version preserved as `phase-1-before-gallery.html`.

The new shell requires another human login after the demo restart. **Authenticated Gallery screenshots, new-site UI flow, tree/tab/iframe navigation, narrow view, keyboard checks, logout/revocation browser flow and independent visual judge are pending.** Phase 1 remains in execution, not closed. No manual Verify or naming approval is claimed.

Demo: `GRAMLOT_DEV=YES PYTHONPATH=src /tmp/kajenn-macro3-admin-env/bin/python examples/admin_demo.py`; loopback port 8874; demo / demo. Credentials are disposable demo fixtures. Final screenshots must be captured from the new shell, not the superseded layout.

### Demo login correction

The demo credentials are now `demo` / `demo`, as requested. Command controls use Gramlot `button`: native `html_button` does not execute nested dataRpc/dataController (Gramlot public guide 097). The restarted browser shows the actual Gramlot command button on the login form. Authenticated browser verification still requires the human login.

### Orientation Home

At the owner’s request, Home now opens automatically in a retained iframe tab and remains the first tree entry. The authenticated guide explains the editorial model, first actions, current capabilities, the planned publication UI and LLM commands, with a bilingual page example. Browser verification confirmed automatic opening and readable stacked sections at the current 820px viewport. Screenshot: `mockups/phase-1-home.png`. Admin suite: 11 passed (8.24s); the existing iframe route check now includes Home. Full phase visual/UX verification remains pending.

### English interface (owner correction)

Translated all administration labels, Home prose, login, scope/error messages, dialogs, navigation, accessibility labels and disposable demo content into English. Updated only translated UI expectations in tests; contract comments and behavior are unchanged. Admin suite: 11 passed (8.75s); Ruff and diff checks pass. Demo restarted to load shared modules; the human must sign in again with demo/demo. Earlier Italian screenshots document superseded copy; the owner’s English requirement supersedes the mockup labels.

### First authoring path (owner priority correction)

Added a scope-bound Create page workspace, opened by default for a selected site. It creates/edits Gramlot Python templates using native CodeMirror and one required HTML body through Jodit/HTML source; saves use the common resource/content/variant/draft services. Saved templates can be reused and saved pages reopened. A POST-only `render_preview` REST/MCP command renders exact saved variant revisions through the previously qualified separate RenderWorker. The native HTML preview restricts scripts/resources and is explicitly a quick preview, not publication.

Verification: 12 admin tests passed (45.97s); 15 API/service tests passed in the separate headless environment (7.03s). The new authoring test also passed after adding template reuse, exact-ID argument rejection and GET refusal (5.53s). Three Node tests passed for unknown-effect retries, partial creation, in-flight edits and ignored late responses after disposal. Ruff and diff checks pass. Built an installable wheel and verified packaged author.py/author.js in the admin environment and headless import with no Gramlot. Initial combined admin+API run correctly failed the API test that asserts Gramlot is absent; rerunning that suite in its required headless environment passed without changing its assertions.

The authoring scope is intentionally the first useful slice, not completion of Phase 2: single required HTML body, site-owned Gramlot templates; full block schemas, Markdown/CSS/JS/media workflows and conflict comparison remain pending. Template/source saves preserve exact content, retries preserve submitted snapshots, and stale generations are rejected. Title/language editing after creation is not offered by this first workspace. Browser exit warnings apply where the browser permits them.

Browser qualification remains pending human sign-in. The user reported signing in, but the controlled tab still displayed an empty sign-in form after refresh. Requested another login with the visible result, without automating authentication. Do not claim Jodit typing/rendering has been verified in the browser yet; independent visual judge and phase closure remain pending.

### Login focus report

The owner reported losing focus in Username/Password. A separate browser tab with synthetic text did not reproduce it in native fields; the precise original trigger remains unconfirmed. Replaced both native inputs with the documented Gramlot textbox/passwordbox controls, using their integrated labels and live Data binding. Browser checks on both replacement fields retained focus while typing and inserting mid-text; Username caret/value matched the expected synthetic edit, Password caret/focus were verified without reading credentials. No login was automated. Closed the probe tab and reloaded the owner’s tab. All 12 admin tests passed (29.46s); Ruff/diff checks pass. Human sign-in and the authoring browser flow remain pending.

### Authenticated browser verification (2026-10-23)

Cause of the earlier "still shows login" report: the owner signed in outside the controlled browser tab, and later the demo process had stopped with the previous session. With the demo restarted (`GRAMLOT_DEV=YES PYTHONPATH=src KAJENN_RENDER_PYTHON=/tmp/kajenn-macro2-render-env/bin/python /tmp/kajenn-macro3-admin-env/bin/python examples/admin_demo.py`), the owner signed in as demo in the controlled tab. No credentials were typed by the agent; the agent clicked Sign in once with empty fields, which returned "Sign-in failed" and confirmed the login RPC.

Observed in the real browser, at 1400x900 unless noted:
- Authenticated shell: toolbar site selector, New site, user and Sign out; tree with Home, site sections and Shared across sites; Create page opened by default.
- Create page: typed into the template name and CodeMirror; the CodeMirror Data value read back exactly as typed. Save template stored the revision and moved to Content. Typed title and paragraph in Jodit and applied Bold. Save page reported "Saved". Render saved page rendered the saved revisions through the separate worker; output shows the added template line, title and the bold text. Screenshots: `mockups/phase-1-jodit.jpg`, `mockups/phase-1-render.jpg`.
- Content and Resources tabs list the saved page, template revision and existing records; tabs are retained side by side. Screenshot: `mockups/phase-1-content.jpg`.
- Site switch to Kajenn changes the tree; already open Gramlot tabs keep their site; Kajenn content is distinct. Shared library node expands. Screenshot: `mockups/phase-1-site-switch.jpg`.
- New site created "Verification site" (en) and opened its Create page. Screenshot of the dialog: `mockups/phase-1-new-site.jpg`.
- Keyboard: Tab order is site selector, New site, Sign out, tree; arrow keys move in the tree and Enter opens the selected workspace tab.
- Narrow 390x844: all elements readable; the navigation panel keeps about half the width and the content column wraps heavily. Screenshot: `mockups/phase-1-narrow.jpg`.
- Sign out returns to the login form; opening a workspace URL directly afterwards shows the login form.

Defects found, not yet fixed (no code change authorized in this step):
- New site reloads the whole administration shell (`src/kajenn_public_site/admin/pages/index.py:143`, `window.location.reload()`), closing every open tab. Unsaved buffers in other tabs depend on the browser exit warning.
- Each load of Create page logs `Uncaught (in promise) Error: div 'div_0': remote 'editor' failed: Source node is not mounted` from `gramlot.js`. The editor works afterwards. The cause is not isolated yet; the remote at `src/kajenn_public_site/admin/pages/author.py:40` depends on three Data paths set in one `_onStart` controller.

Independent visual judge (2026-10-23), against `mockups/phase-1.html` and `notes.md`: no blocking finding.
- Should-fix: content/resource list rows render as bordered inline buttons instead of full-width stacked rows (title, languages, revision); login and Home screenshots predate the English UI and must be recaptured; at 390px the open tree leaves about 165px to the content, which needs a narrow-width rule.
- Minor: Language select wider than Page title and "Content block" line without top margin; language variant buttons without gap; primary actions not distinguished from secondary ones in the dark Base theme; New site dialog without backdrop; "Publishing · coming soon" wraps; language order in rows not uniform; two tree rows highlighted at once in the site-switch capture.

Still open for closure: the owner's decision on the two defects and the judge findings, recaptured English login/Home screenshots, and the two human Verify checks.

### Corrections after the visual judge (2026-10-23)

- New site no longer reloads the shell. The site selector is a `site_selector` remote refreshed by `admin.sites_version`; after creation the new site is selected and its Create page opens. Browser check: two Gramlot tabs stayed open, no page reload (`performance` navigation type `navigate`), third tab opened for the new site. Screenshot: `mockups/phase-1-new-site-tabs.jpg`.
- `Source node is not mounted`: `initialize` in `author.js` registered `onDispose` on its own dataController node, which the renderer never mounts, and ran from `_onStart` before the parent pane was mounted. It now runs `_onBuilt` and registers on `node.parentNode`, the pattern of Gramlot's `fileSystemTree`. The throw had also skipped the initial `changed()` call and the listener cleanup. Browser check: no error after reload and after opening a second Create page. The Node test mock now rejects unmounted nodes like the renderer; it fails without the fix and passes with it.
- Content/resource rows: `gramlot-button` styles its native button in shadow DOM; rows now use its public tokens (`--gramlot-button-background`, `--gramlot-border-control`, `--gramlot-radius-sm`, `--gramlot-button-padding`, `--gramlot-button-hover`) and `--gramlot-touch-target:100%` for full width, with a stacked `record-row-text` grid. Screenshot: `mockups/phase-1-content-rows.jpg`.
- Narrow viewport: below 700px the navigation drawer starts closed (`drawer` bound to `admin.nav_drawer`, set from `matchMedia` at start). Checked in the narrow Browser pane; the drawer opens from its handle.
- English captures: `mockups/phase-1-login-en.jpg`, `mockups/phase-1-home-en.jpg`.
- Test body change: `test_workspace_refresh_restores_context_from_authorized_services` now reads site IDs from the `site_selector` source instead of `main`; contract comments unchanged.
- Checks: 12 admin tests passed; 3 Node tests passed; `ruff check src tests examples` passed.

Behavior change surfaced by the dispose fix: `initialize` now completes, so a new untouched Create page computes `author.dirty = true` (no saved template or page yet) and shows "Unsaved changes"; leaving it triggers the exit warning. Before the fix the throw kept it false until the first edit.

Owner decision (2026-10-23): a new draft becomes dirty only after an edit. `initialize` keeps the opening snapshots in `authorState.initial`; `changed` compares an unsaved template/page with them, and a saved one with its saved snapshot. The saved snapshots still drive the skip of identical saves. Node test `a new untouched draft is clean until the first edit` added (4 Node tests pass). Browser: fresh Create page `author.dirty` false; editing the title sets it true, restoring the title sets it false; leaving the untouched page shows no exit warning. 12 admin tests and ruff pass.
