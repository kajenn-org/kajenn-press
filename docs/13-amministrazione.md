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
`kajenn-demo`. Vengono creati due siti e una Libreria in una directory temporanea.
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
