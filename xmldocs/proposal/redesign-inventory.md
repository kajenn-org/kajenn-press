<!-- generated from redesign-inventory.xml by xmldocs: do not edit, edit the XML -->

## Kajenn Press: inventory of the code against the site tab redesign
*Proposal · redesign-inventory · 2026-10-27 · draft*

### Problem

 (→ proposal/site-tab-redesign#site-tab-redesign) changes the administration and the publication model. Before any code changes, every part of the existing code, every REST/MCP operation, every test suite and every deployment file needs a stated fate, and the upstream capabilities the redesign relies on need to be checked.

Classification used throughout: `keep` (unchanged), `change` (kept and adapted), `replace` (removed, a named new part takes its role), `remove` (removed with no successor). Capabilities are `exists`, `partial` or `missing`.

### Proposed solution

#### Upstream capabilities

Repositories read on 2026-10-27: genro-storage `dd62bfd`, genro-bag `2293047`, kajenn `6ac7e58`, gramlot `d01bf3d`; genro-builders 0.30.0 as installed in the kajenn-press environment. The kajenn-press environment installs genro-storage 0.8.4, genro-bag 0.28.0 and kajenn 0.5.0 from PyPI; the checkouts read here can differ from those releases. Gramlot is not installed in the kajenn-press development environment; the Gramlot checks ran in the Gramlot checkout's own environment.

*Summary*

| Need | Status | Gap |
|---|---|---|
| S3 object versioning: list, read a version | exists | — |
| S3 object versioning: restore a version as current | missing | no restore API |
| Zip archive as a mount, zip export of a node | exists | writing a zip over S3 not verified |
| Bag with nested Bags and bytes to one file and back | partial | lossless in TYTX JSON and pickle only; no zip |
| Zipped Bag file | missing | no `Bag.to_zip` / `from_zip` |
| Resolvers with a time-based cache | exists | synchronous `load()` only |
| Custom `kpress_slot` attribute on source nodes | exists | client renderer not checked |
| `node_label`, dotted paths, find by attribute | exists | — |
| Hosting containers in static rendering | partial | layout widgets need the JS runtime |
| Editors CodeMirror, Jodit, HTML preview | exists | — |
| Detachable floating window with tabs | missing | investigated (GC-185), not implemented |
| Drag from a tree onto a node of the same page | exists | — |
| Drop into a rendered page inside an iframe | missing | excluded by design |
| Kajenn serving of storage content, response cache | partial | no storage response, no cache |
| Maintenance mode for one site | missing | only whole-server 503 outside RUNNING |

#### Genro Storage

- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:180` · 2026-10-27 — The S3 backend sets `version_aware=True` by default.
- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:549` · 2026-10-27 — The versioning capability is derived from the s3fs client only; the bucket's versioning state is never queried.
- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:788` · 2026-10-27 — `get_versions(path)` lists versions with id, latest flag, date, size and etag; any exception returns an empty list.
- `READ` `genro-storage@dd62bfd:src/genro_storage/backends/fsspec.py:847` · 2026-10-27 — `open_version(path, version_id)` opens a version for reading; `delete_version` follows at line 886.

No restore, rollback or promote function exists in genro-storage: a search for them in `src/` found nothing. Restoring today means reading a version and writing it as the current object; this was not tried against S3.

- S3-compatible servers without ListObjectVersions need `version_aware=False`. Whether the Hetzner bucket `kpress-releases` has versioning enabled was not checked. · `genro-storage@dd62bfd:src/genro_storage/storage_grammar.py:151`
- `READ` `genro-storage@dd62bfd:src/genro_storage/storage_grammar.py:256` · 2026-10-27 — A `zip` mount addresses a ZIP archive as a filesystem, with `file`, `mode` and a target protocol.
- `READ` `genro-storage@dd62bfd:src/genro_storage/node.py:1621` · 2026-10-27 — `node.zip()` returns deflated ZIP bytes of a file, a directory or an iterator of nodes.

#### Genro Bag

- `READ` `genro-bag@2293047:src/genro_bag/bag/_serialize.py:270` · 2026-10-27 — `to_tytx(transport="json"|"msgpack")` serializes a Bag, optionally to a file.
- `RUN` `kajenn-press .venv, genro-bag 0.28.0` · 2026-10-27 — A Bag with a nested Bag holding bytes survives `to_tytx`/`from_tytx` in JSON: the value comes back as the same bytes. Through `to_xml`/`from_xml` the bytes come back as a string.

Pickle is also lossless, as reported by the research run; the msgpack transport needs the `msgpack` package, which the environment lacks. Neither was re-run here.

No zipped Bag format exists: a search for `to_zip`/`from_zip` in genro-bag found nothing. A zipped site source needs TYTX plus Python `zipfile`, or the genro-storage zip mount.

- `READ` `genro-bag@2293047:src/genro_bag/resolver.py:15` · 2026-10-27 — `BagResolver` (line 89) takes `cache_time`: 0 no cache, positive a TTL in seconds, negative until `reset()`.
- `READ` `genro-bag@2293047:src/genro_bag/resolver.py:646` · 2026-10-27 — `BagCbResolver` wraps a callback as a resolver with the same cache options.

#### Gramlot and HtmlBuilder

- `RUN` `gramlot@d01bf3d checkout environment` · 2026-10-27 — `div(node_label='info', kpress_slot='main')` and `td(kpress_slot=True)` keep the attribute in the source Bag; `getNode('html_0.body.center.info')` reaches the node by its label path; `findNodeByAttr('kpress_slot', 'main')` returns it; server rendering emits `<div kpress_slot="main">` and `<td kpress_slot="true">`.
- `READ` `gramlot@d01bf3d:src/gramlot/renderer/html_renderer.py:91` · 2026-10-27 — Unknown attribute names pass to the output; names starting with `gramlot_` are an error.
- `READ` `src/kajenn_press/rendering/engines.py:13` · 2026-10-27 — The kajenn-press static profile accepts the HTML tags of `STATIC_TAGS` only; other nodes fail with `unsupported_static_node` (line 204).

Layout widgets such as `contentPane` render as custom elements that need the Gramlot JS runtime, as reported by the research run. In static HTML a slot is therefore a plain element: `div`, `section`, `td` and similar.

- `READ` `gramlot@d01bf3d:src/gramlot/collections/editors.json:14` · 2026-10-27 — The editor collection defines `codeMirror`, `htmlEditor` (line 2599, Jodit) and `htmlPreview` (line 4754).
- `READ` `gramlot@d01bf3d:docs_llm/internal/185-legacy-detachable.md` · 2026-10-27 — Detachable panes and floating palettes of legacy GenroPy are investigated (GC-185, 2026-09-25) and marked "not implemented".
- `READ` `gramlot@d01bf3d:js/src/components/tree.js:9` · 2026-10-27 — The tree component is a drag source.
- `READ` `gramlot@d01bf3d:js/src/renderer/drag-drop.js:6` · 2026-10-27 — Drag and drop works within one renderer; other windows and instances are not admitted.

The HTML preview renders through `srcdoc` in a sandboxed iframe, so a content dragged from the drawer cannot be dropped on a slot of the rendered page as the preview works today.

#### Kajenn

- `READ` `kajenn@6ac7e58:src/kajenn/response.py:195` · 2026-10-27 — `set_result` handles paths, bytes, strings and JSON values; there is no support for storage nodes.
- `READ` `kajenn@6ac7e58:src/kajenn/server.py:406` · 2026-10-27 — The server answers 503 while its lifespan is not running; there is no per-site maintenance state.

Kajenn has no response cache; kajenn-press keeps its own in-memory cache of the release manifest in `child.py`.

#### Upstream items

- **genro-storage**: restore a version as current, through a server-side copy with `VersionId`; query the bucket's versioning state. Reproducer: `node.restore_version(vid)` raises `AttributeError`.
- **genro-bag**: a zipped Bag file holding nested Bags and binary values. Reproducer: `Bag.from_xml(b.to_xml(doc_header=True))['a.bin']` is a string, and no `to_zip` exists.
- **gramlot**: a detachable floating pane holding a tab container (GC-185). Reproducer: no `floatingPane` in the layout collection.
- **gramlot**: drop onto nodes of a rendered page shown inside the editor. Reproducer: a tree with `draggable=True` and a `dropTarget` div inside `htmlPreview`; the drop is not delivered. An alternative that needs no upstream change: render the preview in the same document instead of a sandboxed iframe; to be decided in Phase 5.
- **kajenn**: per-site maintenance state and a response cache on the local filesystem, or both kept in kajenn-press; to be decided in Phase 4.

### Related documents

- `proposal/site-tab-redesign` — Kajenn Press: the site tab, page Bags and per-page publication
