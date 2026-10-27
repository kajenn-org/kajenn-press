# Context: docs/redesign-inventory
Parent: main
Mode: manual
Must not break: No file under `src/`, `tests/`, `deploy/` or `examples/` changes. This macro reads and writes documents only.
Must not break: Every statement about existing code is a `fact` with `source="path:line"`, `method` and `verified` date, checked with tools in the same phase. A statement not verified is written as a `p` saying so, never as a fact.
Must not break: Sibling repositories (Kajenn, Gramlot, Genro Storage, Genro Bag) are read, never edited. A missing capability becomes an upstream item with a reproducer, not a workaround.
Must not break: The decisions marked `decided` in `xmldocs/proposal/site-tab-redesign.xml` are not reopened. Only `open` and `proposed` decisions are put to the owner.
Must not break: The Hetzner installation is not touched; its catalog is read through the MCP read operations only.

## Objective

Map the redesign of `xmldocs/proposal/site-tab-redesign.xml` onto the existing code before any code changes. For every module of `src/kajenn_press/`, every REST/MCP operation, every test suite and every deployment file, state what stays, what changes and what is removed, and why. Check which upstream capabilities the redesign needs and which exist. Close the open decisions with the owner. Write the entry contract of N2.

Deliverable: one public document, `xmldocs/proposal/redesign-inventory.xml` (with its generated `.md` and `.html`), filled one section per phase, plus the updated decisions in `xmldocs/proposal/site-tab-redesign.xml`.

Starting point (main `1c49362`): 8 724 lines in `src/kajenn_press/` (catalog 758, services 785, rendering 894, publication 2 112, admin 3 074, application 757, child 162, domain/objects 180); 44 REST/MCP operations; 133 tests in 9 suites under `tests/`; 15 examples; the Docker composition with external S3 on Hetzner holding one site, "Kajenn Press", with three pages.

## Decisions shared by all phases

- Classification: every item gets one of `keep` (unchanged), `change` (kept and adapted; the change is named), `replace` (removed, a new part takes its role; the part is named), `remove` (removed with no successor).
- Each classification cites the decision of the proposal that motivates it (`d-content-copy`, `d-publish-unit`, ...).
- Each phase writes one `section` of the inventory document, regenerates the HTML/MD and ends with one commit on `docs/redesign-inventory`.
- Every phase runs on Opus, never Fable.
- No mockups in this macro; the UI mockups come with N5–N8.

## Work Plan

- [x] **Phase 1**: Upstream capabilities the redesign needs
  > Done: 15 needs classified in `xmldocs/proposal/redesign-inventory.xml` (section "Upstream capabilities"): 7 exist, 3 partial, 5 missing. Five upstream items written with reproducers: genro-storage version restore, genro-bag zipped Bag, gramlot floating pane (GC-185), gramlot drop into the rendered page, kajenn per-site maintenance and response cache.
  > Open for later phases: the Hetzner bucket's versioning state is not checked (Phase 4); preview in the same document instead of a sandboxed iframe (Phase 5).
  - Run: opus / high
  - Files: new `xmldocs/proposal/redesign-inventory.xml` (section "Upstream capabilities").
  - Details: For each need, read the sibling source and record a fact or a limit:
    - Genro Storage: S3 object versioning (list versions, read a version, restore), on Hetzner Object Storage as well; zip handling.
    - Genro Bag: serialization of a Bag with nested Bags and binary assets to one file, zipped; reading it back.
    - Gramlot: which source nodes can host content (content pane, div, grid and table cells); custom attributes such as `kpress_slot` kept on the node; `node_label` explicit and automatic; finding nodes by attribute.
    - Gramlot/Kajenn: resolvers at render time, with a time-based cache.
    - Kajenn: serving a page from a Bag read from storage, with a local filesystem cache; maintenance mode.
    - Gramlot editors: floating window with CodeMirror, Jodit and preview; drag and drop between a tree and a rendered page.
  - Done: one row per need with `exists`, `partial` or `missing`, each backed by a fact or a limit; every `missing` has an upstream item with a reproducer.

- [x] **Phase 2**: Catalog, editorial services and domain
  > Done: 21 items classified in section "Catalog and services": 2 keep, 11 change, 6 replace, 2 open. The catalog, its revisions and generations and the object store are replaced by the site source Bag, S3 versions and the editing lock. `copied_from` of `resource_copy` is the base of the copies carrying the original id. The publication service shares the catalog: Phase 4 inherits that dependency.
  > Open for Phase 7: receipts and idempotency keys for MCP retries; audit and events.
  - Run: opus / high
  - Files: `xmldocs/proposal/redesign-inventory.xml` (section "Catalog and services").
  - Details: classify `catalog/local.py`, `catalog/filesystem.py`, `catalog/errors.py`, `services/editorial.py`, `domain.py`, `objects.py` against the page Bag (`d-content-copy`), the site source zip and S3 versioning (`d-publish-unit`), one editor at a time (`d-editing-lock`). State what happens to generations, receipts, idempotency keys and immutable revisions.
  - Done: every file and every public class of these modules classified, with the motivating decision.

- [x] **Phase 3**: Rendering
  > Done: 12 items classified in section "Rendering": 4 keep, 7 change, 1 replace. Slots are filled by `kpress_slot` instead of `^blocks.*` pointers; freezing a catalog closure is replaced by serializing the page Bag in TYTX JSON; nh3 filtering stays, so a dynamic iframe is a slot kind authored in the template, not a content.
  > Open for Phase 7: configuration given to resolvers in the worker (database address, credentials); filtering of resolver output.
  - Run: opus / high
  - Files: `xmldocs/proposal/redesign-inventory.xml` (section "Rendering").
  - Details: classify `rendering/` (contract, engines, inputs, preparation, process, service, worker) against the page Bag rendering itself, slots declared with `kpress_slot`, resolvers at render time, and `render_draft` for the Visual editor.
  - Done: every file classified; the render input of a page Bag described against the current frozen inputs.

- [x] **Phase 4**: Publication, serving and deployment
  > Done: 14 src items (2 keep, 7 change, 5 replace) and 9 deploy/example groups classified in section "Publication and serving". Channels, candidates, builds, bundles, pointers and in-process serving are replaced by per-page objects on S3; `qualify`, `PreviewGateway` and the manager deployment stay; the child becomes the Kajenn server with the local re-render cache and per-site maintenance, kept in kajenn-press.
  > Owner action found: versioning is not enabled on the Hetzner bucket `kpress-releases` (checked 2026-10-27); it is a precondition of N3 and N4.
  - Run: opus / high
  - Files: `xmldocs/proposal/redesign-inventory.xml` (section "Publication and serving").
  - Details: classify `publication/` (artifacts, deployments, export, gateway, grants, jobs, releases, routes, service, serving), `child.py`, `deploy/docker/` and `examples/` against per-page published objects versioned by S3, the local re-render cache (`d-rerender-cache`), Publish of changed pages (`d-publish-select`), sitemap/robots/redirects, maintenance mode, private preview before going public.
  - Done: every file classified; the fate of channels, routes, candidates, builds, releases, grants and the websites registry stated.

- [x] **Phase 5**: Administration
  > Done: 15 items classified in section "Administration": 4 keep, 6 change, 5 replace, plus 3 new parts (drawer, SEO tab, Help me). Login, origin guard, CSP, the IndexPage shell, the editors and the `render_draft` loop are reused; navigation, the authoring page, the library workspace and the publishing panel are replaced.
  > Found: the preview iframe runs with an empty sandbox, so clicking or dropping on a slot needs a script inside the preview or the page in the administration document. New decision `d-preview-interaction` for Phase 7.
  - Run: opus / high
  - Files: `xmldocs/proposal/redesign-inventory.xml` (section "Administration").
  - Details: classify `admin/host.py`, `admin/views.py` and every page in `admin/pages/` against the navigation Sites/Library (`d-nav`), the three tabs of the site tab, the drawer and the floating editor. Name the parts reused as they are (login, shell, editors, preview container).
  - Done: every file classified; the reused parts listed with file and line.

- [x] **Phase 6**: API surface, tests and existing data
  > Done: 44 operations classified (3 keep, 20 change, 13 replace, 8 remove) plus 3 new ones (update copies, editing lock, maintenance); 9 suites / 133 tests classified (1 keep, 4 change, 5 replace by suite; gateway and qualification tests kept). Existing data: the Hetzner site "Kajenn Press" was loaded from `examples/kajenn_press_site` (same SHA-256); its text describes the old model.
  > Proposed for Phase 7: no migration code; rebuild the site in the new model from the example sources, after archiving the old catalog volume.
  - Run: opus / high
  - Files: `xmldocs/proposal/redesign-inventory.xml` (sections "Operations", "Tests", "Existing data").
  - Details: one row per REST/MCP operation (44) with its classification and its successor; one row per test suite (9 suites, 133 tests) with its classification; the migration of the Hetzner catalog (one site, three pages) to the new model, or the decision to rebuild it.
  - Done: 44 operations and 9 suites classified; a migration path or a rebuild decision for the existing site.

- [ ] **Phase 7**: Open decisions and the N2 entry contract
  - Run: opus / high
  - Files: `xmldocs/proposal/site-tab-redesign.xml` (decisions), `xmldocs/proposal/redesign-inventory.xml` (section "N2 entry contract"), `.phased/roadmap.md`.
  - Details: put to the owner, one at a time, the open decisions `d-update-local`, `d-template-conflict`, `d-slot-removed`, `d-template-switch`, `d-dynamic-seo` and the proposed `d-editing-lock`, plus the two questions raised in Phase 2 (idempotency keys for MCP retries; audit and events) and in Phase 3 (resolver configuration in the worker; filtering of resolver output) and in Phase 5 (`d-preview-interaction`: how clicks and drops reach slots in the preview) and in Phase 6 (rebuild instead of migrating the Hetzner site), with the inventory facts that bear on each. Write what N2 starts from and must deliver, with the upstream items it depends on.
  - Owner actions: one answer per decision.
  - Done: no decision `open` or `proposed` in the proposal; the N2 entry contract written; the roadmap N1 section marked completed; PR opened.

## Notes

- The inventory is a proposal-type document because it describes changes not made yet; it carries no implementation steps. Implementation plans start at N2.
