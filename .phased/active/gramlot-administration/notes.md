## Phase 1

- The owner approved the revised mockup using the actual Gramlot Base stylesheet, compact toolbar, navy navigation and standard blue/yellow colors. Use public FramePage/Source components and the base theme; do not retain the initial custom green design.
- Pre-gate inspection found a combined Gramlot 0.3.9 wheel at `/private/tmp/gramlot-editors-release/gramlot/dist/gramlot-0.3.9-py3-none-any.whl` (SHA256 fe7c937a1018fe8b1208a43ed3d336dfd5f1174dbbb670992528320d81016879) and adapter 0.2.12 at `/private/tmp/gramlot-py-release-dist/gramlot_py_server-0.2.12-py3-none-any.whl` (48ed53a87f89d4d21ac5ee8f432ad7fb4a771c08150954e9dbc493e5b869f9d4). Qualify these artifacts, not a merge of older sibling checkouts.
- Keep the existing installed Kajenn 0.5.0 headless-compatible artifact. The newer source checkout has different mandatory dependencies despite the same version number.
- Add common metadata-only record/revision indexes and effective scope capabilities; selected details reuse record_read. Public adapter request wrapping carries the current request and shared services, resets context in finally and rejects client-supplied identity.
- Origin protection must cover session-authenticated management mutations on REST/MCP as well as admin RPC and login/logout. Bearer clients remain supported. Login/logout use deployment UserStore and current server session, without exposing session identifiers to Data.

- Implementation checkpoint: all nine copied contracts pass in the optional admin environment; original services/API checks pass (15 tests). The separate-origin test builds and opens a real private preview. Browser login is awaiting the human as required by execute-phase; screenshots and independent UI judge are still pending.
- Configuration uses a public ShortcutConfiguration subclass with ConfigurationHandler over DefaultConfiguration: DefaultConfiguration itself does not accept constructor option kwargs. The subclass only adds request(body="raw") for the admin adapter.
- A loopback-only disposable demo is in examples/admin_demo.py (demo / kajenn-demo); it is explicitly not a production UserStore. No real operator credentials were entered or retained.

- Browser screenshot from the owner exposed white application surfaces combined with automatic dark Base text. Fixed by using upstream theme tokens for all content surfaces, text, borders and focus; checked the login screenshot in actual dark mode. Do not force document theme through DOM manipulation.
