# kajenn-public-site

Proposta di piattaforma editoriale e pubblicazione di siti della famiglia Genro.
**Stato al 21 ottobre 2026: implementati persistenza locale e servizi editoriali REST/MCP autenticati; rendering, pubblicazione ed editor appartengono alle macro successive.**

La proposta separa identità dei contenuti, revisioni editoriali immutabili e
release pubblicate. Si parte con un backend su filesystem per catalogo e stato
operativo e Genro Storage per contenuti e artefatti, senza dipendenza da un
database. Asqueel/PostgreSQL resta un futuro backend da integrare. kajenn ospita
applicazione e servizi; Gramlot offre
l'ambiente di gestione e le interazioni nelle pagine pubbliche.

La direzione stabilita prevede template Gramlot oppure HtmlBuilder, rendering
statico con contenuti nella Data Bag e ripristino degli editor del PoC per HTML
(Jodit), Markdown, CSS e JavaScript. MCP e REST/OpenAPI devono consentire a un LLM
autorizzato di governare il ciclo completo, dalla costruzione del sito alla
pubblicazione, attraverso gli stessi servizi usati dalla UI.

## Percorso di lettura

| Documento | Contenuto |
|---|---|
| [01 · Visione e perimetro](docs/01-visione.md) | Richieste del proprietario, proposta di prodotto, confini |
| [02 · Modello di dominio](docs/02-dominio.md) | Entità, relazioni, identità, invarianti e autorità dei dati |
| [03 · Architettura e flussi](docs/03-architettura.md) | Editing, revisione, build, serving, pubblicazione e integrazioni |
| [04 · Funzioni esposte](docs/04-funzioni.md) | Catalogo concettuale condiviso da Gramlot, REST e MCP |
| [05 · Esperienza editoriale](docs/05-esperienza-editoriale.md) | Editor del PoC, template, Data, risorse, anteprima e workflow |
| [06 · Storage e consistenza](docs/06-storage-consistenza.md) | Versioni, manifest, concorrenza, retry e recupero |
| [07 · Capacità verificate](docs/07-capacita-verificate.md) | Evidenze locali, limiti e responsabilità delle estensioni |
| [08 · Decisioni aperte](docs/08-decisioni.md) | Direzione acquisita e scelte strutturali ancora aperte |
| [09 · Fonti e verifica](docs/09-fonti.md) | Sorgenti consultati, versioni, fonti esterne e limiti della verifica |

Per iniziare il confronto: leggere 01, 02 e 08. Il catalogo delle funzioni viene
dopo il modello: nomi, schemi e raccomandazioni non sono API approvate.

Il [prompt di progettazione](PROMPT-PROGETTAZIONE.md) è corretto nella nomenclatura; le successive
indicazioni del proprietario sono registrate in [08](docs/08-decisioni.md).
Il nome del progetto e del repository è `kajenn-public-site`.

## Run the local persistence example

Python >=3.11, a local POSIX filesystem with `flock`, private application-owned
roots, and public Genro Storage streams are required. The qualified platform is
macOS/Python 3.12.9. Linux needs its own deployment filesystem qualification;
Windows, NFS and multiple hosts are not supported profiles in this phase.

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
python3 examples/persistence.py /tmp/kajenn-public-site-demo
python3 examples/persistence.py /tmp/kajenn-public-site-demo
```

The example creates a record, updates its exact source bytes, closes/reopens the
coordinator and reads its first revision. Both runs print generation **2** and the
same record/revision IDs: retrying an operation does not create extra history.
Use a dedicated private directory; this example has fixed operation keys.

```sh
python3 -m pytest -q --import-mode=importlib tests/contracts tests/catalog tests/services tests/api
ruff check src/kajenn_public_site tests examples
python3 -m compileall -q src/kajenn_public_site
```

## Implemented persistence API

`LocalCatalog` and `Change` live in `kajenn_public_site.catalog.local`.
Use the catalog as a context manager; one process owns its lock until close.
Concurrent request threads are serialized. All changes in a command succeed
or conflict together; each existing record requires `expected_generation`.
New record and revision IDs are generated internally.

- `read(generation=None)` returns a detached, pinned snapshot.
- `commit(principal=..., scope=..., key=..., changes=..., authorize=...)` prepares
  exact payloads and atomically publishes records, revisions, receipt, audit and
  domain-event identities. The required trusted authorization callback runs
  under the writer lock, including retries. Reentrant writes/close are rejected.
- `read_payload(revision_id, name, generation=None)` reads an exact committed
  source and verifies its size/hash. Logical names never become filesystem paths.
- `receipt(principal, scope, key)` returns the original completed result.
- `recover()` distinguishes committed operations from prepared, missing or
  incomplete payloads and reports leftover staging files. It never publishes or
  deletes data automatically.

`ObjectRef` in `kajenn_public_site.objects` can reuse an already committed payload
in a new revision; raw `bytes` create a new immutable object. Metadata is JSON and
editorial content remains exact bytes. The editorial service now validates named-block contracts, resource scopes and exact dependencies.

These are **trusted backend APIs**, not public endpoints: `EditorialService` checks
scoped grants and the Kajenn adapter derives the principal from authentication. The example
uses an explicit local demonstration principal. No public file server is started.

## Qualification and boundaries

The automated suite exercises real directories, concurrent threads, a second
process trying to acquire ownership, forced process termination at seven write
boundaries, restart, historical reads, retries and malformed references. File
flush/fsync, macOS F_FULLFSYNC, directory fsync and atomic catalog replacement are
checked at runtime. Process-crash tests do not certify arbitrary power loss,
hardware caches, backup recovery or a production SLA.

A commit IO error raises `CommitUncertain`: close and reopen, inspect the receipt
and recovery report, then retry with the same command key and input. Do not invent
a new key for an uncertain operation. Corruption fails closed instead of silently
selecting an older generation. Keep `owner.lock` in place; never replace/unlink it
while a coordinator may exist. Private roots must not be modified concurrently
by other programs; symlink checks are not an OS sandbox against a hostile owner.

Full immutable JSON snapshots are intentionally simple and can become expensive
as history grows. No retention, garbage collection or database backend is added.
The runtime uses Genro Storage >=0.8.1,<0.9 and the **published Kajenn 0.5.0** wheel.
That release has no Gramlot dependency. The inspected local Kajenn checkout adds
Gramlot in uncommitted server-interface changes; it is not the artifact used here.
Do not replace the pinned release with that editable checkout and assume the same
installation contract. This application imports no Asqueel/SQL driver or Gramlot.

See the [implementation roadmap](.phased/roadmap.md) and
[storage protocol](docs/06-storage-consistenza.md) for the full scope and limits.


## Authenticated REST and MCP

After the virtual-environment installation above, exercise the full local scenario:

```sh
python3 examples/editorial.py /tmp/kajenn-public-site-editorial-demo
```

It drives real Kajenn REST/MCP transports in-process, without opening a listening
socket: two sites, an exact generic template, HTML/Markdown blocks, independent
Italian/English drafts, an incomplete save, readiness diagnostics, an independent
site copy, historical reads and a second server startup. The second run must
preserve IDs and revisions. Use a directory distinct from the low-level Phase 1
example, which intentionally stores generic records without editorial schemas.

Start a loopback server with a private token when needed:

```sh
export KAJENN_PUBLIC_SITE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 examples/serve.py /tmp/kajenn-public-site-server --port 8080
```

Keep the token private. The example admits one configured `local-admin`, with the
Kajenn `editor` tag and explicit administrator scope grants; it has no anonymous
editor mode. Real deployments supply their own credential and grant mappings to
`create_server(catalog_root, auth=..., grants=...)`.

```sh
curl -sS -H "Authorization: Bearer $KAJENN_PUBLIC_SITE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"key":"first-site","name":"Example","languages":["it","en"]}' \
  http://127.0.0.1:8080/site_create

curl -sS -H "Authorization: Bearer $KAJENN_PUBLIC_SITE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  http://127.0.0.1:8080/mcp
```

OpenAPI is available at `/_meta/schema_json` with the same authorization header;
MCP uses `/mcp`. The same 18 domain operations are discoverable on both faces.
The [implemented API reference](docs/04-funzioni.md#phase-2-implemented-api) records
actual names, payload conventions, scope grants, errors and remaining limits.

Every mutation carries an idempotency `key`; updates also carry the **record's**
`expected_generation`, not the global catalog generation. Responses include
stable `record_id`, `revision_id`, generation, immutable payload references and
exact sources. Read a site with `record_read`; read historical content by supplying
its exact `revision_id`. For a restart/retry use the original key and input.

`readiness` currently checks named required blocks against the exact template
revision. It does not execute a template, sanitize HTML, approve a release or
publish anything. Lists/history are unpaginated, source/media payloads are limited
to 8 MiB each, and media MIME declarations are explicitly unverified. Production
volume limits, scanning, retention, delivery and publication remain separate work.
