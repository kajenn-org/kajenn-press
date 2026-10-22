# Build persistenti e anteprime private

Macro 2, fase 2. Il backend crea candidati immutabili, esegue build in background
e offre anteprime navigabili e revocabili. L'attivazione pubblica e il rollback
sono implementati nella [fase 3](12-publication-rollback.md): nessuna build o
anteprima modifica un canale pubblico.

## Configurazione

Il profilo editoriale resta senza Gramlot, Markdown, nh3 e database. Il processo
coordinatore usa Kajenn 0.5.0 e Storage locale; l'interprete indicato esegue il
[profilo rendering qualificato](10-rendering-statico.md).

```python
app = create_server(
    catalog_root,
    auth=auth,
    grants={"team": {"*": ["read", "write", "use", "create_site", "build", "preview_grant"]}},
    publication={
        "render_python": "/opt/kajenn-render/bin/python",
        "management_origin": "https://admin.example.org",
        "preview_origin": "https://preview.example.org",
        "preview_secret": private_persistent_key_bytes,  # almeno 32 byte
        "preview_max_age": 3600,
        "worker_timeout": 15,
        "worker_output_limit": 8 * 1024 * 1024,
    },
)
```

La chiave privata deve essere conservata tra i riavvii; ruotarla invalida i link
precedenti. Non inserirla in catalogo, esportazioni, sorgenti o log. La durata
richiesta di ogni grant deve essere positiva e non superare `preview_max_age`.
Il timeout vale per ogni invocazione del worker, non per l'intera release.

Usare HTTPS, hostname separati e credenziali amministrative host-only: una porta
diversa sullo stesso hostname non isola i cookie. L'amministrazione e l'anteprima
rifiutano questa configurazione; anche l'origine pubblica deve avere un hostname
separato. I proxy devono conservare Host e schema configurati tramite una
configurazione fidata; il gateway non interpreta `X-Forwarded-Host`. Non esporre
il server Kajenn interno aggirando il gateway. Nessuna route amministrativa è
montata sull'origine di anteprima. HTTP è ammesso solo su loopback per le prove.

## Operazioni REST e MCP

Le 18 operazioni editoriali restano disponibili; nove operazioni aggiuntive sono
registrate sullo stesso router e usano lo stesso servizio autorizzato. Senza
configurazione `publication`, restituiscono `unavailable` e non avviano worker.
`capabilities` segnala rendering e anteprima solo quando il servizio è attivo;
`publication` vale ora `true` con il servizio configurato (fase 3).

| Operazione | Parametri principali | Permesso sul sito |
|---|---|---|
| `publication_settings_save` | `site_id`, `channel`, `public_origin`, `primary_language`, `landing_variant`, `key` | read + write |
| `publication_route_save` | `variant_id`, `path`, `title`, `description`, `key` | read + write |
| `candidate_create` | `settings_id`, `variant_revisions`, `key`, facoltativo `base_build_id` | read + build; read/use delle dipendenze |
| `candidate_read` | `candidate_id` | read + build; read/use delle dipendenze |
| `build_start` | `candidate_id`, `key` | read + build; read/use delle dipendenze |
| `build_retry` | `build_id`, `expected_generation`, `key` | read + build; read/use delle dipendenze |
| `build_status` | `build_id` | read + build |
| `preview_grant_create` | `build_id`, `lifetime_seconds`, `key` | read + preview_grant + build; read/use delle dipendenze |
| `preview_grant_revoke` | `grant_id`, `expected_generation`, `key` | read + preview_grant |

I due salvataggi accettano `record_id` e `expected_generation` per un aggiornamento;
la creazione usa generazione zero. Tutte le mutazioni sono POST REST o chiamate
MCP autenticate. Ogni mutazione richiede una chiave idempotente; riutilizzarla con
parametri diversi produce `conflict`. Le risposte hanno `ok` e `result` oppure
`error` strutturato. Un risultato di pubblicazione contiene `record_id`,
`revision_id`, `generation`, `kind`, `attributes`; `candidate_read` aggiunge la
selezione, il grant aggiunge `url`. Questi record non compaiono nelle liste,
letture o storie editoriali, né espongono i payload come sorgenti di testo.

## Candidati, percorsi e artefatti

Impostazioni e percorsi sono record versionati separati dai contenuti. Il percorso
passato è relativo alla lingua: `about` per inglese diventa `/en/about/`.
Unicode è normalizzato NFC; vengono rifiutati traversal, encoding ambiguo,
segmenti tecnici riservati e collisioni normalizzate. `/` rimanda alla variante
selezionata della lingua principale. Titolo, descrizione, canonical, hreflang
reciproci e sitemap derivano dalla stessa mappa congelata. Nessun x-default o
lastmod basato sull'ora della build viene inventato.

Un candidato include revisioni esatte di impostazioni, percorsi, varianti,
template, dipendenze e profilo del renderer, prese da uno snapshot. Le modifiche
successive non lo alterano. La selezione esplicita ammette 1–100 varianti e il
payload completo massimo è 48 MiB; restano i limiti del grafo rendering.
Il mantenimento di lingue richiede un `base_build_id` attualmente attivo: riusa
contenuto **e percorso/metadati** della release, non le bozze attuali. Il candidato
registra la generazione del canale e la build di base per il controllo concorrente
che la fase 3 implementerà. Prima dell'attivazione di un canale non esiste una
base valida da mantenere.

Riferimenti stabili nei contenuti:

- `/_content/<content_id>/`: variante selezionata della lingua corrente;
- `/_media/<resource_revision>/`: risorsa esatta dichiarata nel grafo;
- percorsi locali già presenti nella mappa del candidato.

Un riferimento assente fa fallire la build. Gli asset hanno URL
`/_releases/<release_key>/assets/<digest>.<suffisso>`; `release_key` identifica lo
spazio del candidato, il manifest verifica i digest dei byte finali per contesto.
L'anteprima riscrive link e risorse sotto `/preview/<build_id>/`. Il canonical
continua a indicare l'origine pubblica configurata. Asset esterni non sono
scaricati né accettati come dipendenze implicite; link esterni ordinari rimangono
link esterni.

Il primo profilo di consegna ammette CSS, JavaScript UTF-8 e PNG validati come
immagini non interlacciate a 8 bit, massimo 4096×4096 e 32 MiB decodificati.
Dichiarare un MIME non basta. Altri formati media, srcset, import/escape CSS e
riferimenti non risolti ricevono un errore esplicito. Questi limiti riguardano
l'output, non la conservazione del sorgente editoriale originale.

Il coordinatore conserva `queued`, `running`, `failed`, `interrupted`, `succeeded`
con ID del tentativo. Un solo slot esegue worker separati e limitati. Prima di
sigillare, controlla ancora permessi, tentativo/generazione, grafo e tutti i byte,
percorsi, MIME, dimensioni e hash. La revisione `succeeded` del job contiene
atomicamente manifest e payload pubblici/anteprima; non esiste una release pronta
con output parziale. Il totale dei due contesti è limitato a 64 MiB.
Al riavvio, job queued/running diventano interrupted; il retry è esplicito e usa
lo stesso candidato. In chiusura il coordinatore attende il worker limitato prima
di rilasciare il catalogo. Non sono promessi quote di RAM, sandbox per codice
ostile, capacità di produzione, garbage collection o retention automatica.

## Accesso all'anteprima

Il grant è per una sola revisione sigillata di una build. Il link porta il token
nel frammento `#…`, che il browser non trasmette nella richiesta iniziale.
Il bootstrap rimuove il frammento dalla cronologia corrente e lo scambia nel body
di una POST stessa origine con un cookie HttpOnly, SameSite Strict, Secure su
HTTPS e limitato al percorso della build. La prima apertura richiede JavaScript;
la pagina risultante mantiene contenuti e navigazione essenziali senza JavaScript.

Ogni GET/HEAD, inclusi redirect e asset, ricontrolla il grant corrente, la sua
scadenza e revoca. Un hash, un ID o un cookie di un'altra build non autorizzano
l'accesso. Le risposte usano no-store/noindex, no-referrer, nosniff e CSP; i token
non entrano in pagine, manifest o diagnostiche. La revoca impedisce nuove risposte,
non cancella copie o screenshot già acquisiti dal destinatario. I template e il
JavaScript del team restano codice fidato; non sono isolati tra loro come codice
ostile. Il profilo statico non abilita connessioni dinamiche o iframe.

I metadati SEO del template sono sostituiti da quelli della selezione congelata,
anche quando `rel` e `name` usano maiuscole. I valori di `rel` sono letti come
lista di token; i fogli di stile alternativi restano risorse CSS e sono preservati.

## Demo e verifica ripetibile

Usare una directory privata nuova e una porta libera anche su IPv6 localhost:

```sh
python examples/private_preview.py --root /tmp/kajenn-preview-demo \
  --python /opt/kajenn-render/bin/python --port 18765
```

La demo crea due siti e due lingue, uno per motore. Stampa solo il percorso del
file privato `demo-credentials.json` (permessi 0600), che contiene URL e credenziali;
non condividerlo e non versionarlo. I link scadono dopo un'ora. Per revocarli dal
servizio REST, con il server attivo:

```sh
python examples/private_preview.py --root /tmp/kajenn-preview-demo --revoke
```

Verifica browser facoltativa, in un ambiente di sviluppo con Playwright/Chromium:

```sh
python examples/verify_private_preview.py --root /tmp/kajenn-preview-demo \
  --output /tmp/kajenn-preview-verification
```

Controlla navigazione, HTML/Markdown, tabella, CSS, immagine, contenuto senza JS e
revoca di pagine/asset GET/HEAD. Salva solo screenshot senza segreti e un riepilogo
booleano; **revoca entrambi i grant**. Un nuovo ciclo richiede una nuova directory.
I test includono anche riavvio, isolamento dei siti, scadenza e trasporti REST/MCP.
