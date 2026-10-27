# Context: feat/page-bag
Parent: main
Mode: manual
Must not break: The 133 existing tests keep passing. The current catalog, services, publication and administration keep working unchanged; N2 adds code beside them and removes nothing. Removal happens when N3–N5 replace each part.
Must not break: No REST/MCP operation is added, changed or removed in N2. The new model is a library with its own tests; it is exposed through the services in N3, together with the working copy, the editing lock, receipts and the audit log.
Must not break: The decisions of `xmldocs/proposal/site-tab-redesign.xml` are not reopened. A missing framework capability stops the phase and becomes an upstream item with a reproducer; sibling repositories are not edited.
Must not break: Credentials never enter a Bag, a test fixture or a log. Resolver connections are named; their values come from the deployment.
Must not break: Real tests with real Bags, real engines and the real render worker; mocks only for network and external services.

## Objective

Build the page model of the redesign as a library under `src/kajenn_press/site/`: a site holds templates, contents, assets and pages as Bags; a page holds a copy of its template, copies of the contents assigned to its slots and its assets; every copy carries the id of its original and the digest of the original at copy time. A page renders to static HTML with its slots filled. The site saves to and loads from a local directory in TYTX JSON (the unpacked working copy that N3 zips and versions on S3).

Entry contract: `xmldocs/proposal/redesign-inventory.xml`, section "N2 entry contract". Decisions in force: d-content-copy, d-slot-id, d-template-inherit, d-update-local, d-template-conflict, d-slot-removed, d-template-switch, d-resolver-config, d-resolver-output.

Starting point (main `937cd52`): templates are Python source with `build(source, data)` executed in the worker (`src/kajenn_press/rendering/engines.py:242`); blocks reach them through `^blocks.*` pointers (`examples/kajenn_press_site/template.py:38`); `prepare_blocks` filters content with nh3 (`src/kajenn_press/rendering/preparation.py:97`). A probe on 2026-10-27 in the Gramlot checkout showed: a builder Source with `kpress_slot` nodes survives `to_tytx`/`from_tytx`, but rendering a deserialized Source through a new builder fails with `AttributeError: 'NoneType' object has no attribute 'runtime_values'` (`genro_builders/renderer/base.py:144`): the loaded nodes have no builder attached.

## Owner decisions (2026-10-27)

- **N2-D1 · Template storage.** (a) The template is stored as its Source Bag, produced once from a Python `build` or by an editor, so that linked templates can be the Library Bag plus node changes (d-template-inherit, d-template-conflict). (b) The template stays Python source and slots are discovered by running it; node-level linking and conflicts would then work on text, not nodes. Decided: (a).
- **N2-D2 · Scope.** N2 is a library with tests; no REST/MCP operation until N3. Decided: yes, because receipts, lock and audit live in the working copy that N3 introduces.
- **N2-D3 · Location.** New package `src/kajenn_press/site/`; rendering gains a page entry beside the current one. Decided: yes.

## Decisions shared by all phases

- Class and function names are proposed in each phase and reviewed at its gate; names used here describe roles, not final identifiers.
- Each phase ends with its tests green, ruff clean, one commit on `feat/page-bag`.
- Every phase runs on Opus, never Fable.

## Work Plan

- [ ] **Phase 1**: Qualification of the Source Bag path
  - Run: opus / high
  - Files: new `tests/site/test_source_qualification.py`; `pyproject.toml` only if a dependency bound is needed.
  - Details: with the qualified engines of the render profile, check: a Gramlot and an HtmlBuilder Source with `kpress_slot` nodes serialized to TYTX JSON and rendered after loading, with the same HTML as before serialization; slot nodes found by `kpress_slot` after loading; a `BagCbResolver` in Data with `cache_time` resolved during a static render; the worker accepting a Source Bag instead of Python source. Find the public way to attach a loaded Source to a builder.
  - Done: every check passes, or the phase stops with an upstream item and a reproducer (the probe failure above is the first candidate).

- [ ] **Phase 2**: Site and page Bags and the local working copy
  - Run: opus / high
  - Files: new `src/kajenn_press/site/` (model, storage), `tests/site/`.
  - Details: site Bag with `templates`, `contents`, `assets`, `pages`; page Bag with its template copy, slot assignments (slot name → content copy), unplaced contents, assets; ids stable across saves; save and load of a site as TYTX JSON files in a private local directory, reusing `catalog/filesystem.py` for atomic writes and fsync.
  - Done: a site with two pages, two templates, contents and a binary asset survives save, close and load byte for byte; a malformed or partial directory fails closed.

- [ ] **Phase 3**: Template slots
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `tests/site/`.
  - Details: read the slots of a template Source: every node with `kpress_slot`; name = the value when it is a string, the label path when it is `True`; names unique per template, duplicates refused with the paths; tag checked against the hosting tags of the static profile; the iframe slot kind with its static fallback (d-dynamic-seo) marked on the node.
  - Done: slots listed with name, path, tag and kind for the converted `examples/kajenn_press_site` template; duplicate names and non-hosting tags refused with diagnostics.

- [ ] **Phase 4**: Copies, use count and Update
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `tests/site/`.
  - Details: copying a content, template or asset into a page records the original id and the original's digest; use count and where-used per original; an Update plan lists the pages holding copies, the differences and the copies changed locally (current digest ≠ recorded digest), those unselected (d-update-local); applying the plan replaces only the selected copies.
  - Done: use counts 0, 1 and >1 computed; a locally changed copy is flagged and left unchanged unless selected; applying twice changes nothing more.

- [ ] **Phase 5**: Linked templates and conflicts
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `tests/site/`.
  - Details: a site template is independent (a copy) or linked: the Library Bag version it is based on plus node changes (add, remove, change) addressed by label path. Rebasing on a new Library version applies cleanly or stops with the list of conflicting nodes, including renamed labels; per node the operator keeps the site version or takes the Library one (d-template-conflict).
  - Done: a clean rebase, a conflict on a changed node, a conflict on a removed node and a renamed label each produce the expected result or conflict list.

- [ ] **Phase 6**: Unplaced contents and template switch
  - Run: opus / high
  - Files: `src/kajenn_press/site/`, `tests/site/`.
  - Details: when a template update removes a slot, its content copy moves to the page's unplaced contents (d-slot-removed); a template switch proposes a mapping matched by name, accepts the operator's corrections and moves unmatched contents to unplaced (d-template-switch); a check lists empty slots and unplaced contents for the later Publish check.
  - Done: removing, renaming and switching slots keep every content copy, placed or unplaced; the check reports them.

- [ ] **Phase 7**: Rendering a page Bag
  - Run: opus / high
  - Files: `src/kajenn_press/rendering/` (a page entry beside the current one: contract, engines, worker, process, service), `tests/rendering/`, `examples/kajenn_press_site/` converted.
  - Details: the worker receives the page Bag in TYTX JSON; it loads the template Source, prepares each slot content with `prepare_blocks`, places it in its slot node, renders static HTML; iframe slots render their fallback; resolver output enters as text, HTML through nh3 (d-resolver-output); named resolver connections reach the worker from the deployment configuration, never from the Bag (d-resolver-config). Same limits (32 MiB input, timeout, output validation).
  - Done: the converted Kajenn Press site renders its three pages with the same visible text as the current release build; a resolver with `cache_time` fills a slot; an HTML value from a resolver is filtered; a missing connection name is a diagnostic; all 133 existing tests still pass.

## Notes

- The current `^blocks.*` rendering path, the catalog and the publication code stay until N3–N5 replace them.
- Probe 2026-10-27 (Gramlot checkout environment): `Bag.from_tytx(source.to_tytx(transport="json"))` returns a `GramlotBuilderBag` with the same top node; `builder.source.update(loaded)` followed by `render` raised the AttributeError above.
