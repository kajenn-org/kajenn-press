# Pubblicazione, attivazione e rollback

Macro 2, fase 3. La build produce una release completa e immutabile; un comando
esplicito la rende pubblica. Il rollback riattiva una release già pubblicata,
senza invocare Gramlot o HtmlBuilder. Filesystem e Genro Storage restano gli
unici backend; ID, revisioni, ricevute, audit e sorgenti esatti sono conservati.

## Configurazione delle origini

Alla configurazione `publication` di [build/anteprima](11-build-anteprime.md)
si aggiunge `public_origins`, una mappa fornita dal deployment:

```python
publication = {
    "management_origin": "https://admin.example.org",
    "preview_origin": "https://preview.example.net",
    "preview_secret": persistent_private_key,
    "render_python": "/opt/kajenn-render/bin/python",
    "public_origins": {"https://www.example.org": settings_id},
}
```

`settings_id` identifica impostazioni già salvate. I binding non derivano da
parametri del visitatore e non possono riutilizzare gli hostname di gestione o
anteprima, neppure con una porta diversa. HTTPS è richiesto salvo loopback,
`localhost` e sottodomini `.localhost` per la demo locale. Il server confronta
schema e Host normalizzati, non `X-Forwarded-Host`; un reverse proxy deve
preservare il binding configurato. Il profilo locale non qualifica proxy o CDN.

Con `publication` configurato, `capabilities.publication` vale `true`; senza,
le operazioni restano scopribili ma restituiscono `unavailable`. Un canale privo
di release attiva restituisce 404 sul pubblico. Nessuna credenziale di gestione
viene richiesta o inviata al sito pubblico.

## Operazioni comuni REST e MCP

Le sei operazioni richiedono autenticazione, tag Kajenn `editor` e permessi
correnti `read` e `publish` sul sito. L'attivazione e il rollback verificano
anche `read`/`use` sull'intera chiusura delle risorse. `publish` è indipendente
da `build` e `write`: l'operatore può pubblicare una build preparata da altri.

| Operazione | Parametri | Risultato |
|---|---|---|
| `channel_create` | `settings_id`, `key` | Canale vuoto, generazione 1 |
| `channel_read` | `settings_id` | Stato e generazione del canale; 0 se non esiste |
| `release_read` | `build_id` | Build sigillata e manifest esatto |
| `release_history` | `settings_id` | Attivazioni ordinate per generazione del canale |
| `release_activate` | `settings_id`, `build_id`, `expected_generation`, `key` | Canale aggiornato e record `activation` |
| `release_rollback` | Come `release_activate` | Riattivazione completa della release conservata |

Ogni comando è disponibile come POST REST e come tool MCP attraverso lo stesso
servizio. Gli errori usano la busta strutturata già documentata. I risultati
conservano `record_id`, `revision_id`, generazione e riferimenti immutabili;
l'attivazione aggiunge identità, autore e provenienza della transizione.

La prima attivazione può creare atomicamente il canale mancante usando
`expected_generation=0`. Se si usa `channel_create`, farlo **prima** del candidato:
la creazione avanza la generazione e invalida la base di un candidato precedente.
Ogni attivazione richiede sia la generazione attesa dal chiamante sia la base
congelata nel candidato. Due attivatori concorrenti non possono entrambi vincere.
Un candidato basato su una release sostituita restituisce `stale_base`; una
versione attesa non corrente restituisce `conflict`.

Il servizio ricontrolla sotto il coordinatore permessi, `review_required`,
appartenenza a sito/canale, impostazioni di destinazione e completezza degli
artefatti. La compatibilità confronta il valore delle impostazioni, senza
richiedere la disponibilità del vecchio renderer. Cambiare origine, lingua
principale o landing può rendere una vecchia release `incompatible_release`.
Se il canale possiede già binding pubblici nel deployment, attivazione, rollback
e relativi retry richiedono che l'origine della release sia tra quelli configurati:
un disallineamento restituisce `incompatible_release` senza cambiare il puntatore.
Prima di attivare una destinazione nuova, riconfigurare il serving. I canali senza
binding restano gestibili dal backend, ma non sono raggiungibili via HTTP pubblico
finché il deployment non li associa a un'origine.
I siti con revisione obbligatoria restituiscono `review_required`: l'approvazione
arriverà nella Macro 4. Il rollback richiede una release esatta già presente
nella storia di quel canale; una build mai pubblicata restituisce `not_published`.

## Consistenza e lingue

Puntatore del canale, record di attivazione, ricevuta, audit ed evento vengono
registrati con un'unica transizione del catalogo. Dopo un'interruzione risulta
visibile il vecchio stato oppure il nuovo stato completo. Ripetere la stessa
chiave e gli stessi argomenti restituisce il risultato originale; input diversi
con la stessa chiave confliggono. Il retry ricontrolla la politica corrente:
revocare un permesso o abilitare la revisione può negare anche una ripetizione.

Per pubblicare una sola lingua, creare un candidato con le nuove revisioni e
`base_build_id` uguale alla release attualmente attiva. Le altre lingue mantengono
revisioni, percorsi e metadati pubblicati; bozze successive e nuove lingue non
selezionate non entrano nella release. Il rollback riguarda **tutta** la release.

## Risposte pubbliche e asset

Una richiesta seleziona una sola revisione della release da un unico snapshot.
HTML, canonical, alternate e sitemap provengono da quella selezione. La radice
risponde 307 verso la landing nella lingua principale. GET e HEAD condividono
stato e intestazioni; HEAD omette il corpo. Metodi diversi restituiscono 405;
percorsi sconosciuti, privati o ambigui restituiscono 404.

HTML e sitemap usano `Cache-Control: no-store`. Gli asset sono indirizzati con
`/_releases/<release_key>/assets/...` e cache `public, max-age=31536000, immutable`.
MIME, dimensioni e digest sono verificati; `nosniff` e la CSP del profilo statico
sono applicati. I vecchi asset restano leggibili solo se la revisione esatta è
stata pubblicata sul canale e sull'origine configurati. Non basta indovinare un
ID di candidato o di build. Non esiste una cancellazione automatica delle release.

## Demo ripetibile e verifiche

Preparare gli ambienti separati come in [rendering](10-rendering-statico.md).
Con il Python dell'applicazione installata:

```sh
/path/editorial/bin/python examples/publication_cycle.py \
  --root /tmp/kajenn-publication-demo --python /path/render/bin/python --port 19765
```

La demo ascolta solo su `127.0.0.1`. Gestione: `127.0.0.1`, anteprima: `localhost`,
siti: `gramlot.localhost` e `htmlbuilder.localhost`, sulla stessa porta. Chromium
risolve i nomi `.localhost` localmente. Token, chiave HMAC e link privati restano
nel file `demo-credentials.json` con permessi 0600 della directory temporanea.
In un secondo terminale eseguire gli stessi argomenti aggiungendo, nell'ordine,
`--step activate`, `--step update`, `--step rollback`. I passi usano REST/MCP reali.

`examples/verify_publication_cycle.py`, eseguito in un ambiente con Playwright e
Chromium, avvia e termina il proprio server. Richiede `--root` nuova, `--output`,
`--server-python`, `--render-python` e facoltativamente `--port`. Qualifica due
motori, anteprima, contenuti pubblici senza JS, aggiornamento italiano indipendente,
asset conservati, rollback agli stessi byte e riavvio con identità invariate.

```sh
KAJENN_APP_PYTHON=/path/editorial/bin/python \
KAJENN_RENDER_PYTHON=/path/render/bin/python \
.venv/bin/python -m pytest -q --import-mode=importlib tests
```

Il test del ciclo installato richiede un'installazione non editable del pacchetto
in `KAJENN_APP_PYTHON`. Il profilo editoriale non richiede Gramlot, Markdown, nh3,
SQLAlchemy o Asqueel; queste assenze sono verificate nel processo installato.

## Confini qualificati

102 test coprono anche gare tra attivatori, interruzione reale del processo in
cinque punti del commit, riapertura e retry, REST/MCP e richieste HTTP concorrenti.
Il profilo resta locale POSIX, un proprietario del catalogo e sorgenti del team
fidate. Non è una sandbox per template ostili. Non qualifica propagazione CDN,
cluster, S3, retention/GC, volumi produttivi o l'integrazione Asqueel. UI/editor,
approvazioni, scheduling e componenti interattivi appartengono alle macro successive.
