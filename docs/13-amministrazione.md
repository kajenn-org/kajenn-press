# Amministrazione Gramlot

La fase 1 offre consultazione autenticata: toolbar con selettore del sito e Nuovo sito, Contenuti, Risorse,
Libreria condivisa, dettagli, sorgenti e revisioni. Usa IndexPage e IndexLogic come la Gallery, albero di navigazione, schede
con iframe mantenuti, Source/Data,
controlli pubblici e il tema Gramlot Base originale. Le superfici usano i token
del tema e seguono la preferenza chiaro/scuro del sistema. La Libreria è un ambito
separato; Pubblicazione è indicata come funzione successiva. Creazione di contenuti, editor,
salvataggio, confronto e media arrivano nella fase 2; il pannello di pubblicazione
nella fase 3. Le operazioni di backend già esistenti restano disponibili via API.

## Profili e dipendenze

Il backend editoriale non importa Gramlot. L'extra `admin` aggiunge Gramlot 0.3.9
e gramlot-py-server 0.2.12. Il worker statico qualificato mantiene Gramlot 0.3.8:
installare `admin` e `render` in ambienti separati, non nello stesso virtualenv.

Gli artefatti non ancora rilasciati sono identificati in
[admin-artifacts.json](admin-artifacts.json) con nome e SHA256. Il numero di versione
non basta: il Kajenn 0.5.0 qui qualificato è il wheel con dipendenze headless della
Macro 1; un checkout più recente con lo stesso numero non è equivalente.

Fornire i tre wheel esatti in una directory privata durevole (`/percorso/wheels`
negli esempi). Verificare ogni SHA256 contro il manifest prima di installare:

```sh
python3.12 -m venv .venv-admin
.venv-admin/bin/python -m pip install . /percorso/wheels/kajenn-0.5.0-py3-none-any.whl /percorso/wheels/gramlot-0.3.9-py3-none-any.whl /percorso/wheels/gramlot_py_server-0.2.12-py3-none-any.whl
.venv-admin/bin/python -m pip check
```

Il manifest registra gli artefatti upstream; `admin-qualified-freeze.txt` registra
anche le dipendenze transitive della qualificazione. I wheel locali non sono
incorporati nel repository né sostituiti con checkout editable. Per ricostruire
l'ambiente occorre conservare quegli artefatti, oppure riqualificare una release.

## Avvio e identità

La factory `create_server` accetta, oltre ad `auth` e `grants`, la configurazione:

```python
administration = {
    "origin": "https://admin.example.org",
    "users": {"store_class": DeploymentUserStore},
}
server = create_server(catalog_root, auth=auth, grants=grants,
                       administration=administration, publication=publication)
```

`DeploymentUserStore` implementa il contratto pubblico Kajenn UserStore; è una
configurazione dell'installazione. Il FileUserStore di Kajenn richiede storage
cifrato e relativa chiave; non usare la memoria della demo come archivio utenti
reale. Gli utenti devono avere il tag Kajenn `editor`; i grant per identità e ambito
decidono ogni operazione. Il tag da solo non concede accesso ai contenuti.

Montaggio: `/admin/` sull'origine amministrativa. Se è presente la pubblicazione,
l'origine deve coincidere con `publication.management_origin`. Usare HTTPS;
HTTP è ammesso solo per loopback. Dietro proxy il server deve ricevere schema e
Host canonici corretti. Cookie di sessione HttpOnly, host-only e Secure su HTTPS;
le credenziali API permanenti non entrano in Data. Login e logout usano la sessione
Kajenn; la password temporanea nel form viene cancellata dopo la risposta.

Ogni richiesta prende l'identità dal request Kajenn corrente: il ContextVar viene
azzerato in `finally`, anche in caso di errore. Il cookie `gramlot_owner` identifica
le pagine, non autentica un operatore. La revoca dei grant vale sulla richiesta
successiva; logout invalida la sessione anche nelle schede già aperte. I dati già
visualizzati non possono essere ritirati dal browser: aggiornare una scheda
scaduta riporta al login. I permessi mostrati si aggiornano cambiando ambito o
ricaricando la pagina; i servizi li ricontrollano sempre.

Le richieste non sicure richiedono l'Origin amministrativo, anche sui trasporti
REST/MCP. Client API possono usare Bearer senza Origin; in questo caso i cookie vengono
esclusi prima dell’autenticazione, quindi un Bearer invalido non può ripiegare
sulla sessione del browser. Login/logout diretti
richiedono POST. Anteprima e pubblico attraversano il dispatcher separato della
Macro 2 e non espongono route o cookie amministrativi.

## Letture comuni e navigazione

| Operazione | Risultato |
| --- | --- |
| `records_index(scope, kind?)` | Metadati editoriali nell'ambito autorizzato, senza payload |
| `revision_index(record_id)` | Metadati delle revisioni, dalla più recente |
| `scope_capabilities(scope)` | Permessi effettivi dell'identità corrente nell'ambito |
| `sites_list()` | Siti leggibili dall'operatore |
| `record_read(record_id, revision_id?)` | Dettaglio autorizzato con sorgenti esatti |

UI, REST e MCP condividono gli stessi servizi. I record operativi di pubblicazione
restano esclusi dalle letture editoriali. I riferimenti alterati o non più
accessibili restituiscono un esito di errore; non attraversano l'ambito selezionato.
Le schede conservano il sito indicato nel titolo e nel proprio URL: il selettore
aggiorna la navigazione per aprire nuove schede senza alterare quelle già aperte.
Il ricaricamento ricostruisce i siti dai servizi e seleziona il primo leggibile;
non mantiene una cache locale dei contenuti o handle del filesystem.

## Demo locale e verifiche

```sh
.venv-admin/bin/python examples/admin_demo.py --port 8874
```

Aprire `http://127.0.0.1:8874/admin/`. Solo per questa demo: utente `demo`, password
`demo`. Vengono creati due siti e una Libreria in una directory temporanea.
Il server ascolta esclusivamente su loopback; il catalogo e gli utenti sono
sacrificabili. Per vedere l'applicazione dopo un riavvio accedere nuovamente.

```sh
KAJENN_APP_PYTHON=/percorso/headless/bin/python KAJENN_RENDER_PYTHON=/percorso/render/bin/python KAJENN_ADMIN_WHEELS=/percorso/wheels .venv-admin/bin/python -m pytest -q tests/admin
KAJENN_APP_PYTHON=/percorso/headless/bin/python KAJENN_RENDER_PYTHON=/percorso/render/bin/python .venv/bin/python -m pytest -q tests
.venv/bin/python -m ruff check src tests examples
```

Il secondo comando verifica il profilo senza Gramlot: i test admin vengono
eseguiti separatamente nel primo comando. La qualificazione della grammatica e del
bundle rileva CodeMirror, Jodit, ProseMirror e `markdownPreview.allowHtml`.
L'uso interattivo degli editor e l'abilitazione HTML nel workspace sono oggetto
della fase 2; qui non si dichiara già disponibile un editor di contenuti.

## Comandi MCP per un LLM

Il trasporto `/mcp` usa `tools/list` e `tools/call` con JSON-RPC 2.0. L’identità
viene dal Bearer configurato nell’installazione; il payload non può sceglierla.
Il test `test_new_site_uses_shared_authority_and_mcp_creates_content` esegue con
un vero client MCP la sequenza `site_create`, `resource_save` (template),
`content_create`, `variant_create`, quindi confronta il risultato con REST e UI.
Verifica anche il rifiuto dopo revoca dei permessi. Nessun token dimostrativo va
riutilizzato in produzione. Esempio di chiamata dopo aver ottenuto l’ID del sito:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"content_create","arguments":{"site_id":"ID_DEL_SITO","title":"Chi siamo","key":"operazione-univoca"}}}
```

Ripetere la stessa operazione con la stessa chiave evita duplicati. Il catalogo
dei tool descrive gli argomenti; le capability effettive e i servizi stabiliscono
ciò che l’identità del LLM può eseguire.

### Home di orientamento

Dopo l’accesso, se esiste un sito, si apre **Create page**. **Home · How it works** resta raggiungibile dall’albero di navigazione. La guida presenta i primi passi, il rapporto tra siti, contenuti, varianti, template e blocchi Data, la Libreria condivisa e le revisioni. Un esempio bilingue illustra il percorso fino alla pubblicazione. La Home distingue le funzioni già disponibili da editor e comandi di pubblicazione previsti nelle prossime fasi, e spiega l’utilizzo di un assistente autorizzato tramite MCP/OpenAPI.

### Interface language

All administration UI is in English, including the orientation Home, authentication, navigation, forms, permissions and feedback. The disposable demo also uses English sample titles and text. Editorial language variants remain independent of the administration language.

### First authoring workflow

Select a site and open **Create page**. The first tab provides a working Gramlot Python template in CodeMirror. **Save template** stores an exact resource revision. In **Content**, enter the title and language and edit the HTML `body` block using Jodit or HTML source. **Save page** creates the content/variant or conditionally saves a new revision. **Render saved page** renders those saved revisions in the separately installed worker and shows a restricted quick preview; it does not publish a release.

Saved templates can be reused for new pages; saved pages can be reopened. This initial slice supports site-owned Gramlot templates with one required HTML `body` block. Multi-block/Markdown/CSS/JS/media editing and full conflict comparison remain in phase 2. Existing incompatible or shared templates produce an explicit explanation rather than being rewritten. Title and language become immutable in this first editor after creation. New template revisions affect a page only after its content is explicitly saved against them.

Drafts stay in memory. A browser navigation/exit warning protects unsaved work where the browser permits it. A save snapshots its submitted text; later typing stays dirty. A transport failure retains the same operation key and snapshot for retry. Revision conflicts preserve the draft and never overwrite a newer revision.

The `render_preview` REST/MCP operation requires exact variant/revision IDs, POST for REST, current read/use/build grants and the existing optional publication worker configuration. It uses the existing RenderService/RenderWorker; no Python executes in the administration process. The demo can enable it with `KAJENN_RENDER_PYTHON=/path/to/qualified-render-env/bin/python`; the qualified development worker is `/tmp/kajenn-macro2-render-env/bin/python`. The demo is disposable; deployed catalog roots are configured separately.

The `render_draft` REST/MCP operation renders unsaved sources over an exact saved variant and writes nothing to the catalog. Besides `variant_id` and `revision_id` it takes `blocks` (declared block name → source text) and `resources` (revision ID of a template, CSS or JavaScript resource in the page's dependency closure → source text). It needs the same grants as `render_preview`, plus `write` in the scope of every drafted resource, because a drafted template is Python the worker executes. CSS, JavaScript and media reach the template as `data:` URLs of their exact bytes, so the preview shows the site's styles and images. The administration CSP therefore admits `data:` in `style-src` as well as `img-src`; scripts still never run in the sandboxed preview.

**Render saved page** uses `render_draft` without drafted sources. Once a page is saved, the preview follows unsaved edits to the body and the template about 800 ms after the last change; a reply superseded by a newer request is discarded. The page renders at 1280 or 375 px and is scaled to 0.5, 0.75 or 1.

### Page editor

Each entry under **Pages** opens its editor in a tab of its own (`page?site=…&content=…`). A language selector chooses the variant; it is locked while the draft has unsaved changes. The editor shows one tab per block declared by the variant's template: HTML blocks in Jodit or as source, Markdown blocks in the Markdown editor or as source. A splitter separates the blocks from the scaled preview, which follows every unsaved block through `render_draft`.

The toolbar saves all blocks with `draft_save` against the variant's generation (a conflict keeps the draft; an uncertain result retries the same submitted version and key), reverts to the saved revision, loads an earlier revision as an unsaved draft, opens the template's tab in the shell, checks `readiness` on the saved revision and adds a missing site language with `variant_create`, starting from the current blocks and recording `translated_from`. The page title stays read-only: the service has no operation that renames a content. **New page** still creates pages with the starter single-block template.

### Resource editor

Templates, Styles, Scripts and Media open their editor in a tab (`resource?site=…&record=…`). Templates, CSS and JavaScript are edited in CodeMirror; a template also edits its block declarations (name, format, required) and chooses which revision of each style, script or media item it depends on, current or latest. Media show the image and accept a replacement file, read in the browser and saved with `media_save`. Saving creates a new revision with the record's generation; a conflict keeps the draft. Dependencies the editor does not list are kept unchanged.

The preview renders a sample page: a variant of the site whose exact dependency closure contains a revision of the resource. The unsaved source replaces the revision that page uses, through `render_draft`. Unsaved block or dependency changes of a template are not applied to the preview, and media render as saved.

Pages reference exact revisions. A new revision of a style reaches a page when its template is saved with that revision as a dependency, and the page is then saved against the new template revision. The page editor shows when its template has a newer revision and offers **Use latest template**: it saves the page against the latest revision, keeping the blocks whose name and format still match, and reloads the editor. There is no command that updates every page at once. Resources of the shared library remain read-only in **Shared library**.

### Publishing

**Publishing** under the site opens the publishing panel (`publishing?site=…`). It reads the site's state with `publication_overview` and has three sections. **Channel** creates or updates a channel's settings: name, public origin, primary language and landing page. **Routes** gives each page a path in its language, a title and a description. **Build, preview and activate** creates a candidate with the latest saved revision of the selected pages, starts the build and follows `build_status` until it ends; a succeeded build offers a private preview link valid for one hour and **Activate**, and every activation in the history except the active one offers **Roll back**. Activate and Roll back ask for confirmation. Each command is enabled by the matching permission: `write`, `build`, `preview_grant` or `publish`.

The panel does not register children or configure public serving: that stays in **Deployments** and in the deployment configuration. Publishing a single language over an active release (`base_build_id`) is available through the API only.

## Deployments

The **Deployments** node lists the children registered in this installation: servers that serve a site from release storage (`StaticSiteServerApplication`, see [14](14-release-storage.md)). For each child the table shows the bound site, the release the catalog has active and the release read back from storage at that moment, with a state: Up to date, Storage differs from catalog, Not in storage, Nothing to serve, No release storage, Storage unreadable (storage cannot be read or holds a malformed pointer). A difference is shown and never corrected automatically; **Re-export** writes the active release and its pointer to storage again. **Register child** records a name, a channel and a declared serving address; the public origin comes from the channel. The same operations are available on REST and MCP: `child_save` (permission `publish`), `child_read`, `child_list`, `child_channels` (permission `read`).

