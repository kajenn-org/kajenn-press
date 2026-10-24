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
lo riscrive 40 volte mentre un lettore concorrente lo legge. Un lettore deve
vedere sempre un contenuto intero, vecchio o nuovo. Se vede un contenuto
parziale, il backend viene rifiutato e il server non parte.

| Backend | Esito (2026-10-24) |
|---|---|
| `s3` su RustFS 1.0.3 | Accettato. Una lettura può fallire con `OSError` se l'oggetto cambia durante la lettura: il lettore ritenta. Nessun contenuto parziale. |
| `local` (Genro Storage 0.8.1) | Rifiutato. `write_bytes` svuota e riscrive il file; un lettore vede contenuti parziali. Segnalato come [genro-org/genro-storage#83](https://github.com/genro-org/genro-storage/issues/83). |

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
