# Phase 2 — StaticSiteServerApplication

## Delivered

- `src/kajenn_public_site/child.py`: `ReleaseReader` (pointer reread at most every `cache_seconds`, manifest digest and object SHA256/size checks, retry on S3 replacement `OSError`, last validated release kept on failure), `StaticSiteServerApplication` (Kajenn application on the site root, host binding inside), `StaticSiteHealth` (`/_health/health`), `create_static_site_server` (Kajenn server with both applications and sessions disabled).
- `src/kajenn_public_site/publication/serving.py`: `method_response` and `release_response` extracted from `PublicServing.public_response`; both servers use them.
- `examples/child_serve.py`, `docs/14-release-storage.md` child section, README row.

## Verification

Environment as in Phase 1: RustFS `rustfs/rustfs:1.0.3` on `127.0.0.1:19000`; render worker `kajenn-org-site-data/render-env`; headless install refreshed from this checkout.

- Phase contracts copied verbatim to `tests/child/test_child_serving_contract.py`: 3 passed.
  - Import probe: loading `kajenn_public_site.child` loads no `gramlot`, catalog, rendering, services or publication service module.
  - Parity: for every public artifact path, the root redirect, `/sitemap.xml` and a missing path, with GET, HEAD and POST, the child and the installation return identical status, body and headers.
  - An unlisted stored object answers 404; a tampered manifest answers 503 on a fresh child.
  - With `cache_seconds=1`, an activation and a rollback are visible within 3 seconds; a corrupted pointer keeps the last validated release served; an unknown channel answers 503.
- Existing serving, gateway and release tests after the extraction: 5 passed.
- Full suite from the repository root before the restructuring: 109 passed, 3 skipped (admin tests skip without Gramlot), 174 s.
- After restructuring into a Kajenn application, the parity contract first failed on a `session_id` cookie added by the Kajenn session stage; with sessions disabled the 3 contracts pass again. Full suite after the restructuring: 109 passed, 3 skipped, 156 s.
- `ruff check src tests examples`: passed.
