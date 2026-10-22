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
