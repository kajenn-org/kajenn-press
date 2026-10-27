## Phase 1

- The owner approved the revised mockup using the actual Gramlot Base stylesheet, compact toolbar, navy navigation and standard blue/yellow colors. Use public FramePage/Source components and the base theme; do not retain the initial custom green design.
- Pre-gate inspection found a combined Gramlot 0.3.9 wheel at `/private/tmp/gramlot-editors-release/gramlot/dist/gramlot-0.3.9-py3-none-any.whl` (SHA256 fe7c937a1018fe8b1208a43ed3d336dfd5f1174dbbb670992528320d81016879) and adapter 0.2.12 at `/private/tmp/gramlot-py-release-dist/gramlot_py_server-0.2.12-py3-none-any.whl` (48ed53a87f89d4d21ac5ee8f432ad7fb4a771c08150954e9dbc493e5b869f9d4). Qualify these artifacts, not a merge of older sibling checkouts.
- Keep the existing installed Kajenn 0.5.0 headless-compatible artifact. The newer source checkout has different mandatory dependencies despite the same version number.
- Add common metadata-only record/revision indexes and effective scope capabilities; selected details reuse record_read. Public adapter request wrapping carries the current request and shared services, resets context in finally and rejects client-supplied identity.
- Origin protection must cover session-authenticated management mutations on REST/MCP as well as admin RPC and login/logout. Bearer clients remain supported. Login/logout use deployment UserStore and current server session, without exposing session identifiers to Data.

- Implementation checkpoint: all nine copied contracts pass in the optional admin environment; original services/API checks pass (15 tests). The separate-origin test builds and opens a real private preview. Browser login is awaiting the human as required by execute-phase; screenshots and independent UI judge are still pending.
- Configuration uses a public ShortcutConfiguration subclass with ConfigurationHandler over DefaultConfiguration: DefaultConfiguration itself does not accept constructor option kwargs. The subclass only adds request(body="raw") for the admin adapter.
- A loopback-only disposable demo is in examples/admin_demo.py (demo / demo); it is explicitly not a production UserStore. No real operator credentials were entered or retained.

- Browser screenshot from the owner exposed white application surfaces combined with automatic dark Base text. Fixed by using upstream theme tokens for all content surfaces, text, borders and focus; checked the login screenshot in actual dark mode. Do not force document theme through DOM manipulation.

- Owner’s explicit correction supersedes the original mockup’s button navigation: top toolbar must contain site selector and New site; use the same tree and iframe-tab coordination as the Gramlot Gallery. Implemented with IndexPage, shipped IndexLogic, native tree/tabContainer and separate WorkspacePage routes. Each tab URL and title binds its site; changing the selector changes navigation for new tabs, existing tabs retain their site. Child pages independently authorize reads.
- New site is moved into Phase 1 by explicit instruction. It calls the existing common site_create service with a stable request key; effective installation capabilities determine button availability, and the service independently rechecks rights. Tests create a site, template, content and language variant over the real MCP ASGI transport with Bearer credentials, without browser session authority.
- The frame-ancestors policy becomes self for admin pages to allow the requested same-origin iframes. Index panel validates the client navigation node and derives its iframe URL from an authorized site/known section; it never trusts a client-supplied URL. Preview/public isolation remains unchanged.

- The original approved mockup is preserved as mockups/phase-1-before-gallery.html. phase-1.html now applies the owner's explicit visual amendments (toolbar site selector + New site, tree and iframe tabs) to the static reference. No extra approval gate is invented for changes the owner directly requested.

- Retired 2026-10-27: the owner redesigned the administration and the publication model (`xmldocs/proposal/site-tab-redesign.xml`). Phases 2-4 and `tests/deferred/` are not carried forward. See `.phased/roadmap.md`.
