# Evidenze — Macro 2, fase 2

Implementazione: candidati e percorsi versionati, build persistenti e manifest
sigillati, anteprime private revocabili, nove operazioni REST/MCP.

## Verifiche eseguite

- `KAJENN_RENDER_PYTHON=/tmp/kajenn-macro2-render-env/bin/python .venv/bin/python -m pytest -q tests`: **88 passed**, nessuno skip/xfail e nessun warning nella verifica finale.
- `ruff check src/kajenn_public_site tests examples`: passato.
- `python -m compileall -q src/kajenn_public_site`: passato.
- `git diff --check`: passato.
- Otto nomi e tutti i commenti wf:contract della fase 2 preservati. Scheletri originali e blocchi contrattuali del piano confrontati con 01efee3: invariati.
- Processo reale interrotto con os._exit: riapertura, stato interrupted, retry dello stesso candidato, completamento obsoleto respinto, timeout e chiusura prima del rilascio del catalogo verificati.
- Trasporti Kajenn REST/MCP reali: candidati, build idempotenti, stato, grant idempotenti, revoca e dinieghi strutturati. Nessuna fuga dei record operativi nelle API editoriali.
- Grafo esatto, mantenimento di lingue senza bozze successive, conflitti di percorso, SEO e sitemap, sorgenti inalterati, dipendenze mancanti/incrociate/cicliche, byte e tipi non qualificati verificati.
- Scadenza e revoca su GET/HEAD di pagine/asset, riavvio, scope di singola build, due siti, host falsi/pubblici, assenza di segreti negli artefatti verificati.

## Browser

Playwright con Chromium 156 disponibile localmente, server su loopback e hostname
127.0.0.1/localhost distinti. Un sito usa Gramlot, l'altro HtmlBuilder; entrambi
hanno italiano e inglese. Passano navigazione, CSS, PNG, HTML nel Markdown,
tabella, contenuti essenziali con JavaScript disabilitato dopo il bootstrap e
revoca delle pagine e delle immagini, GET e HEAD.

Evidenza ripetibile: `examples/private_preview.py` e
`examples/verify_private_preview.py`; gli URL/token sono nel solo file temporaneo
privato della demo. Gli screenshot [prima](browser-phase-2/site-1-it.png) e
[dopo revoca](browser-phase-2/site-1-revoked.png), i corrispondenti del secondo
motore e [result.json](browser-phase-2/result.json) non contengono segreti.
La prima navigazione aveva raggiunto un altro servizio su localhost IPv6:8765;
la verifica è stata ripetuta con successo su una porta libera.

## Installazione e limiti

Installazione non editable del parent in `/tmp/kajenn-macro2-editorial-env`
(Python 3.12.9), import senza Gramlot/Markdown/nh3/SQL e `pip check` passati.
Il worker separato qualificato è `/tmp/kajenn-macro2-render-env` (Python 3.14.7),
con gli stessi pacchetti della fase 1 e `pip check` passato. Il parent installato
esegue la demo preparatoria dei due motori con due release complete e grant.

Codice Python/JavaScript del team fidato, nessuna sandbox contro codice ostile.
Profilo iniziale PNG non interlacciato 8 bit, CSS senza import/escape e senza
srcset; limiti espliciti e documentati. La prima apertura del link richiede JS;
i contenuti risultanti no. Nessuna attivazione, rollback, UI editoriale,
componente interattivo o promessa di retention/capacità di produzione.

## Chiusura

Tutti i 105 nomi, comprese le cinque deleghe/accessor segnalate, sono stati
accettati dall’utente. Marcatori rimossi con equivalenza AST verificata: nessun
cambiamento di comportamento. Ultimo gate completo: 88 passed in 68.93s.
