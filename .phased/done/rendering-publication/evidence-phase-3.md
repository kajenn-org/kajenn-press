# Evidenze — Macro 2, fase 3

Implementazione: canali, attivazione condizionale, storia immutabile, serving
pubblico con release fissata per richiesta e rollback senza renderer. Sei
operazioni aggiunte alla superficie comune REST/MCP (33 complessive).

## Verifiche

- Gate finale ripetuto: **102 passed in 140.83s** (88 precedenti e 14 nuovi ingressi), nessuno skip/xfail. Comando: `KAJENN_APP_PYTHON=/tmp/kajenn-macro2-editorial-env/bin/python KAJENN_RENDER_PYTHON=/tmp/kajenn-macro2-render-env/bin/python .venv/bin/python -m pytest -q --import-mode=importlib tests`.
- `ruff check src/kajenn_public_site tests examples`, compileall e `git diff --check`: passati.
- `pip check` negli ambienti editoriale e renderer: nessun requisito rotto.
- Installazione non editable aggiornata in `/tmp/kajenn-macro2-editorial-env` (Python 3.12.9); il test isolato verifica percorso site-packages e assenza di Gramlot, markdown_it, nh3, SQLAlchemy e Asqueel. Renderer separato qualificato `/tmp/kajenn-macro2-render-env` (Python 3.14.7), profilo invariato.
- Gli otto nomi e tutti i commenti wf:contract della fase 3 coincidono con lo scheletro approvato; scheletro e campi contrattuali normalizzati del piano invariati rispetto a `01efee3`.
- Due attivatori concorrenti: un solo vincitore; base obsoleta e generazione errata respinte. Puntatore, attivazione, ricevuta, audit ed evento appartengono alla stessa transizione.
- Interruzione reale del processo in cinque punti: intent, manifest, prima del cambio head, dopo replace della head, dopo pubblicazione durevole. Riapertura e retry conservano uno stato completo, senza duplicare la transizione. Chiave riutilizzata con input diversi e attore revocato respinti.
- Autorizzazione corrente indipendente da build, use revocato, review_required, canale/sito errati e impostazioni incompatibili verificati. REST/MCP reali restituiscono dinieghi strutturati.
- Aggiornamento italiano conserva l'inglese pubblicato, esclude bozza inglese e francese mai pubblicato. Rollback completo dopo riavvio funziona con eseguibile renderer deliberatamente assente.
- Una risposta fermata dopo la selezione mantiene HTML e namespace asset originali durante l'attivazione concorrente; la successiva usa la nuova release. Vecchi asset pubblicati restano disponibili; build inedite e percorsi gestionali/privati/ambigui restano inaccessibili sul pubblico.

## Browser e installazione reale

`examples/verify_publication_cycle.py` avvia e termina il proprio server installato.
Il listener è solo 127.0.0.1; gestione, anteprima e due siti hanno hostname distinti.
La prima configurazione a quattro IP loopback non era disponibile su macOS; la
demo finale usa sottodomini `.localhost`, senza aggiungere alias di rete. Test
unitari verificano anche il rifiuto di nomi che imitano localhost.

Playwright/Chromium: Gramlot e HtmlBuilder, due lingue per sito, build -> anteprima
privata -> attivazione -> aggiornamento italiano -> rollback -> riavvio. Pubblico
con JavaScript disabilitato, navigazione, CSS, immagine PNG, tabella, HTML nel
Markdown, canonical/alternate e assenza di cookie pubblici verificati. Il ciclo
HTTP verifica anche sitemap e contenuti esatti; il rollback ripristina gli stessi
byte HTML e gli stessi riferimenti immutabili. Dopo il riavvio canale e record di
attivazione mantengono le loro identità.

Evidenze: [result.json](browser-phase-3/result.json), screenshot dei due motori
prima e dopo aggiornamento in `browser-phase-3/`. Ispezione visiva effettuata:
contenuti, tabella e navigazione leggibili. Token e chiave HMAC restano nella
sola directory temporanea privata; non sono inclusi negli artefatti salvati.

## Limiti e chiusura

Profilo locale POSIX, un proprietario del catalogo, codice del team fidato;
nessuna sandbox contro template ostili, promessa CDN, cluster, S3 o Asqueel.
HTML senza cache condivisa, asset immutabili conservati senza GC automatico.
Nessun deployment, push o lavoro sulle macro successive. UI, editor, approvazioni,
scheduling e componenti interattivi restano fuori da questa fase.

Naming review: tutti i 54 nomi e le 12 segnalazioni accettati dall’utente.
Rimossi i marcatori con equivalenza AST verificata in ogni file Python modificato.
Nessuna modifica di comportamento; il gate completo resta 102 test superati.
