# Storage delle release

Macro 3b, fase 1. Dopo ogni attivazione o rollback l'installazione copia la
release attiva e il suo puntatore su un mount Genro Storage. Il catalogo resta
l'unica autorità: attivazione e rollback restano condizionali sulla generazione
del canale. Lo storage serve ai server che servono le pagine senza catalogo.

## Configurazione

Alla configurazione `publication` si aggiunge `release_storage`: un mount
Genro Storage senza `name`. Il backend `s3` richiede l'extra `release-s3`
(`genro-storage[s3]`, cioè s3fs).

```python
publication = {
    "management_origin": "https://admin.example.org",
    "preview_origin": "https://preview.example.net",
    "preview_secret": persistent_private_key,
    "render_python": "/opt/kajenn-render/bin/python",
    "release_storage": {
        "protocol": "s3",
        "bucket": "releases",
        "endpoint_url": "http://127.0.0.1:19000",
        "access_key": access_key,
        "secret_key": secret_key,
    },
}
```

Il bucket deve esistere: lo crea il deployment.

## Contenuto dello storage

| Percorso | Contenuto | Scrittura |
|---|---|---|
| `objects/<sha256>` | Byte esatti di ogni artifact pubblico | Una volta sola; se esiste non viene riscritto |
| `manifests/<digest>.json` | Manifest sigillato della build | Una volta sola |
| `pointers/<settings_id>.json` | Release attiva del canale | Riscritto a ogni attivazione, rollback o export |

Ordine di scrittura: artifact, manifest, puntatore. Un lettore che vede il
puntatore trova tutti i file che nomina. Il puntatore contiene `site_id`,
`settings_id`, `public_origin`, `build_id`, `manifest_digest`,
`channel_generation` e `history`, cioè i manifest delle release attivate in
ordine. Bozze, anteprime e credenziali non vengono mai scritte.

## Qualifica del backend all'avvio

All'avvio l'installazione verifica il mount: scrive e rilegge un oggetto, poi
lo riscrive di continuo mentre un lettore concorrente lo legge, per almeno 0,5
secondi e finché il lettore non ha completato 200 letture (limite 20 secondi;
se il limite scade il backend è rifiutato). Un lettore deve
vedere sempre un contenuto intero, vecchio o nuovo. Se vede un contenuto
parziale, il backend viene rifiutato e il server non parte.

| Backend | Esito (2026-10-24) |
|---|---|
| `s3` su RustFS 1.0.3 | Accettato (circa 2,4 secondi). Una lettura può fallire con `OSError` se l'oggetto cambia durante la lettura: il lettore ritenta. Nessun contenuto parziale. |
| `local` (Genro Storage 0.8.1) | Rifiutato. `write_bytes` svuota e riscrive il file; un lettore vede contenuti parziali. Segnalato come [genro-org/genro-storage#83](https://github.com/genro-org/genro-storage/issues/83). |
| `local` (Genro Storage 0.8.4) | Accettato. La 0.8.4 scrive su file temporaneo e sostituisce in modo atomico: issue #83 chiusa. Il progetto richiede `genro-storage>=0.8.4`. |

## Esito dell'export

`release_activate` e `release_rollback` restituiscono un campo `export`:
`exported` con il puntatore scritto, oppure `pending` con il codice
dell'errore. Un errore di storage non annulla l'attivazione, che resta
registrata nel catalogo. `channel_read` mostra lo stato rileggendo il
puntatore: `exported` se coincide con canale e build attivi, altrimenti
`pending`.

`release_export` (REST POST e MCP, permesso `publish`) riscrive lo storage per
il canale attivo. Non usa chiavi di idempotenza e non scrive nel catalogo:
ripeterlo produce lo stesso puntatore e non riscrive gli artifact.

## Sviluppo locale con RustFS

```bash
docker run -d --name kajenn-rustfs-dev -p 127.0.0.1:19000:9000 -e RUSTFS_ACCESS_KEY="$ACCESS" -e RUSTFS_SECRET_KEY="$SECRET" -v "$DATA/rustfs-data:/data" rustfs/rustfs:1.0.3
```

I test dello storage leggono endpoint e credenziali da un file JSON privato
indicato da `KAJENN_RELEASE_S3` (`endpoint_url`, `access_key`, `secret_key`) e
creano un bucket nuovo per ogni test.

## Il figlio: StaticSiteServerApplication

Macro 3b, fase 2. `StaticSiteServerApplication` (`kajenn_press/child.py`)
è un'applicazione kajenn montata sulla radice del server figlio (`mount = ""`):
riceve ogni path che nessun altro mount reclama e serve le pagine pubbliche
leggendo lo storage delle release. Non importa il catalogo, Gramlot, il
rendering né i servizi editoriali, e non scrive mai nello storage: le sue
credenziali devono essere di sola lettura.

```python
from kajenn_press.child import create_static_site_server

server = create_static_site_server(
    bindings={"https://www.example.org": settings_id},
    release_storage={"protocol": "s3", "bucket": "releases", ...},
    cache_seconds=5,
)
```

- `create_static_site_server` costruisce un `AsgiServer` con due applicazioni:
  `StaticSiteServerApplication` sulla radice e `StaticSiteHealth` su
  `/_health/` (route `/_health/health`).
- L'host della richiesta sceglie il canale (`bindings`); un host non configurato
  riceve 404.
- Il figlio rilegge il puntatore al massimo ogni `cache_seconds`. Una nuova
  attivazione o un rollback diventano visibili entro quell'intervallo.
- Prima di servire verifica il digest di ogni manifest e lo SHA256 e la
  dimensione di ogni oggetto. Serve solo i path elencati nel manifest: un
  oggetto presente nello storage ma non elencato non è raggiungibile.
- Puntatore o manifest mancanti o non validi: risposta 503. Se una release era
  già stata validata, il figlio continua a servire quella.
- Le risposte sono costruite dalla stessa funzione del serving dell'installazione
  (`publication/serving.py`, `release_response`): stesso corpo, stato, header,
  redirect della radice, 404 e 405.
- Gli asset `/_releases/...` delle release elencate in `history` restano
  raggiungibili. Il controllo dell'origine usa l'origine del puntatore corrente
  per tutta la storia del canale.

Avvio locale con un file di configurazione privato:

```bash
PYTHONPATH=src .venv/bin/python examples/child_serve.py /percorso/child-config.json --port 8876
```

Profilo di installazione del figlio: `kajenn-press` con l'extra
`release-s3` per S3. Non servono gli extra `render` né `admin`.

## Composizione Docker locale

Macro 3b, fase 4. `deploy/docker/` avvia RustFS, websites, un builder e un
figlio: websites costruisce kajenn.org via MCP e lo esporta nel bucket, il
figlio lo serve da `http://kajenn.localhost:8876/` con credenziali di sola
lettura. Istruzioni in [deploy/docker/README.md](../deploy/docker/README.md).

Macro 3b, fase 5. Con `deploy/docker/compose.volume.yaml` lo storage delle
release è un volume Docker condiviso al posto di RustFS: websites lo monta in
scrittura, il figlio in sola lettura, e cambia solo la configurazione
(`RELEASE_STORAGE=local`). Richiede genro-storage 0.8.4 o successiva; il volume
è condiviso solo tra container dello stesso host.

