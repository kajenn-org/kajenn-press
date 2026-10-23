# kajenn-public-site implementation roadmap

Status: updated 2026-10-23. Macros 1 and 2 are finalized on main. Macro 3 has an approved four-phase plan whose acceptance target is kajenn.org built through the administration UI; Phase 1 is in execution on `codex/gramlot-administration`. Later macros retain entry/exit contracts and explicit scoping questions.

The full product scope remains `docs/01-visione.md` through `docs/08-decisioni.md`. Filesystem/Genro Storage is the initial implementation; Asqueel is a future catalog backend. This roadmap does not require a database, shrink the product to a file server, or claim an upstream integration is already ready.

## Macro 1 (completed): Filesystem catalog and REST/MCP management

- Objective: Establish durable local persistence and a shared service surface that later UI, rendering and LLM clients can consume.
- Starts from: Design-only repository, approved product decisions and inspected Kajenn/Genro Storage source examples.
- Ends at: A locally runnable application manages sites, language variants, shared drafts, named-block contracts, exact source revisions, media and generic-resource copies through authenticated REST and MCP; restart, conflict and recovery contracts pass without a database.
- Delivers: The two completed phases, 19 contract tests and API/setup documentation, consolidated on main as `b50a5b5`. Archived plan and execution evidence remain on `codex/filesystem-storage` at `.phased/done/filesystem-storage/`.
- Consumes: Public Kajenn application/router/auth/storage interfaces and Genro Storage local payload access; local filesystem primitives for the explicit catalog backend.
- Requires of earlier work: Preserve all approved product decisions and document static evidence separately from executed qualification.
- Open decisions: No unresolved product choice is delegated to this macro. Concrete Python names are implementation proposals reviewed through the interactive gate; a framework capability gap is a reported dependency, not authority to weaken the tests.

## Macro 2 (completed): Templates, static rendering, preview and coherent publication

- Objective: Turn selected revisions into complete public HTML, private previews and reversible releases using Gramlot or HtmlBuilder templates and Data.
- Starts from: Macro 1's reliable catalog, exact source reads, source-format/block declarations, resource scopes, authentication and readiness diagnostics.
- Ends at: A selected site can be rendered, inspected privately, activated and rolled back as a coherent release. Each language is selected independently; incomplete required blocks cannot be published. Essential editorial text, URLs, canonical, alternate links and sitemap are correct without browser JavaScript.
- Delivers: Named-block preparation, template execution, CSS/JS/media dependency closure, artifact manifests, route/SEO generation, preview grants, build diagnostics and release lifecycle through the common services/REST/MCP.
- Consumes: Macro 1 generations, receipts, immutable source/resource references, template declarations, language identities and grants; qualified Gramlot/HtmlBuilder renderers.
- Requires of earlier work: Source text and format survive unchanged; metadata/text are distinguishable from prepared HTML; dependency references are exact and private; the backend supports atomic catalog changes and durable job/intention records.
- Detailed plan: `codex/rendering-publication:.phased/done/rendering-publication/plan.md`, approved 2026-10-21: three interactive phases in this chat, with plan-time contract skeletons. Trusted team code runs in a separate worker; Markdown may contain filtered HTML; all language URLs are prefixed; private preview uses expiring revocable links on a separate origin. Qualify both installed renderers and the preparation profile before building their consumers; no database is introduced.

- Implementation evidence: Macro 2 phases 1–3 implement rendering, private previews, conditional activation and rollback. All three phases are closed. Extended quality-check completed at 7b65ffd, with two corrections verified at b7d4195, 102 passing tests and a repeated installed two-engine browser cycle. Finalized and pushed to main as `3bfe65fcebd0f92e87ff7835e6feb1f9cce4a289`. Archived plan and phase-3 evidence remain on `codex/rendering-publication` under `.phased/done/rendering-publication/`.

## Macro 3: Gramlot administration and restored editors

- Objective: Make the services usable through a coherent multi-site editorial and source-authoring UI, proven by building kajenn.org with it.
- Starts from: Macro 2's complete preview/publication service cycle and Macro 1's service contracts.
- Ends at: A team can select a site, manage its pages and routes, edit named HTML/Markdown blocks and template/CSS/JS sources, upload PNG resources, inspect a preview and publish/rollback through Gramlot without UI-only business rules. kajenn.org, the third sibling of gramlot.org and asqueel.org with Kajenn colors and logo, is built entirely through the administration UI; its deployment and DNS are not part of this macro.
- Delivers: Site/page/resource workspaces, the site page list in template Data for navigation, source tabs, Data inspection, editor integration, save/conflict feedback and publication views; the kajenn.org catalog with library template and CSS; browser and visual acceptance evidence.
- Consumes: Macro 1/2 schemas, exact sources, diagnostics, grants, previews and release operations; the upstream Gramlot editor-control and PoC restoration work.
- Approved detailed plan: [gramlot-administration](active/gramlot-administration/plan.md), four phases (rewritten by the owner on 2026-10-23): authenticated multisite administration; site pages, navigation Data and editors; publication workspace; kajenn.org built through the UI. Explicit Save with dirty-exit protection; per-site navigation and separate library; PNG resources referenced by exact revision. Each phase has plan-owned contract skeletons, a mockup and browser/human acceptance checks.
- Upstream evidence (2026-10-22): CodeMirror, Jodit and ProseMirror already exist; 27 focused editor tests passed. Embedded Markdown HTML is supported via `markdownPreview.allowHtml` in source, Python grammar and shipped bundle, filtered with DOMPurify without changing source. Newer Gramlot/adapter release branches contain per-request identity support; the combined new-editor/adapter artifact still requires application qualification. The static nh3 render profile remains separate. No upstream port or private API workaround is authorized.
- Requires of earlier work: Public common services, exact source/revision/generation contracts, discoverable template block declarations, current-grant enforcement and private artifact separation. Add authorized read projections where UI discovery is absent; expose new application functions through REST/MCP as well.
- Scope boundary: Source/Data-native administration and generic editors. Deferred from this macro on 2026-10-23, with their contracts kept verbatim in the plan's `tests/deferred/`: conflict comparison/resolution UI, revision diff/restore UI, per-variant media references, the media picker and block insertion, JPEG/WebP verification with Pillow. Cursor-aware rich insertion, Typst, component authoring, advanced editorial organization (menus as records, taxonomies) and automatic image derivatives are not added implicitly. Existing later-macro contracts remain in force.
- Open decisions: No unresolved product choice is delegated to execution. Visual presentation is negotiated through each phase's mockup. A missing compatible public framework capability is a qualification stop with a reproducible upstream dependency, not permission to weaken contracts or edit sibling repositories.

## Macro 4: Editorial organization and configurable review

- Objective: Complete the domain for structured publishing and teams while preserving direct publication when review is disabled.
- Starts from: Macro 3's usable editing/publication UI and the durable version/permission contracts retained from Macro 1.
- Ends at: Content types, taxonomy, menus, courses/collections, contributor metadata, translations, review requests/decisions and scheduling can be managed consistently through UI, REST and MCP; changes generate coherent releases.
- Delivers: Structure and navigation editors/services, reference validation, language provenance, revision-bound review, configurable policies, scheduled activation and corresponding diagnostics.
- Consumes: Stable IDs, immutable revisions, independent language variants, release candidates, jobs, audit and authenticated common services from earlier macros.
- Requires of earlier work: Content identity must be independent of URL; generic/site scope and stable resource references survive every intermediate macro; publication rechecks current grants and configured review requirements; no assumption that all languages share one publication state.
- Open decisions: Exact schema-editing UX and policy details such as reviewer separation, quorum, expiry and revocation. The already-approved publication flexibility and independent languages are not reopened.

## Macro 5: Direct public Gramlot components

- Objective: Add interactive Gramlot regions to the static site without removing essential readable content.
- Starts from: Macro 4's editorial site, Macro 2's renderer/dependency manifests and Macro 3's generic source editors and content/resource workspaces. Component-specific property, definition and fallback authoring is new work in this macro.
- Ends at: Multiple components mount directly into one public page, keep Data/IDs and lifecycle correct, load dependencies coherently and retain essential static content when JS is disabled or a component fails. Iframes are used only where explicit isolation is required.
- Delivers: Registered component definitions, instance properties/validation, static fallback content, authoring support, public bootstrap and verified teardown/resource behavior.
- Consumes: Earlier versioned template/resource references, the static HTML preparation pipeline, generic editors/workspaces, catalog/asset contracts and qualified upstream Gramlot/adapter capabilities. Component definitions, instance properties, fallback authoring and their versioned references are produced here using those existing contracts.
- Requires of earlier work: Immutable component dependency references and per-instance identity must be representable; sanitization must preserve only explicitly registered component placeholders; neither HTML rendering nor Source mounting is treated as hydration proof.
- Open decisions: Component placeholder syntax/serialization, mount/bootstrap contract, Data sharing, RPC/authentication, CSS isolation and accessibility after activation. Core gaps belong in Gramlot; host protocol gaps belong in its adapter/Kajenn and are qualified before product integration.

## Macro 6: Portability, integrations and full-system qualification

- Objective: Complete the remaining catalogue and validate the complete filesystem-backed product with both human and LLM clients.
- Starts from: Macro 5's static/interactive publishing platform and all durable contracts preserved through previous macros.
- Ends at: Import/export and recovery checks preserve IDs and revision closure; jobs/audit/delivery state are inspectable; approved integrations are qualified; the full implemented catalogue has a documented UI/REST/MCP coverage matrix and reproducible end-to-end acceptance scenarios.
- Delivers: Portable archives, search/operational completion, outbox delivery integrations including the Telegram adapter when configured, job cancellation/retry, media rendition completion, integrity/reconciliation tooling and a full product acceptance report. Catalog functions not closed earlier remain visible here rather than disappearing from scope.
- Consumes: All prior domain/service contracts, exact manifests, receipts, audit and pending events; separate integration applications and environments where explicitly configured.
- Requires of earlier work: Audit/event identity is durable; uncertain external effects are distinguishable from definite failures; indexes remain rebuildable; export includes schema/version/provenance without secrets; external integrations do not become core dependencies.
- Open decisions: Provider configuration and real delivery tests, operational volumes, retention/backup/RPO/RTO and CDN guarantees when the owner chooses to address them. S3 is a separate qualified payload profile: activate it only after public Storage version/receipt/precondition contracts are sufficient. No automatic purge or production SLA is implied while these decisions remain deferred.

## Future work outside the initial implementation

- Asqueel/PostgreSQL catalog backend and migration: revisit after the framework integration is defined. Requires preserved IDs, revisions, generations, audit, receipts, pending jobs and exact payload references from Macro 1 through Macro 6; one authoritative backend at a time, no implicit dual writes.
- Independent-client multitenancy: deferred; the current site/library distinction is not a tenant-isolation claim.
- Multiple catalog writers/hosts: separate backend capability and qualification, not a property inherited from local files or S3 versioning.

## Sequencing and scope controls

- Macros and phases run in order. At each macro boundary, compare delivered evidence with the next macro's entry contract, then detail only that next macro in a new active plan.
- Later consumer requirements pass through all intermediate macros unchanged unless the owner approves a recorded design change.
- A missing framework capability produces a concrete reproducer and a bounded upstream work item; do not edit sibling projects as an incidental step. This roadmap plans those dependencies but does not launch separate chats or authorize external effects.
- The active plan is not executable authorization for later macro scopes. No UI phases are claimed ready before their framework contracts and visual gate are prepared.
