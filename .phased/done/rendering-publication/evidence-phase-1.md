# Evidenze — Macro 2, fase 1

- Suite Done: 76 test superati, inclusi tutti i 54 test precedenti; 31.05 secondi.
- Rilettura del Done gate per close-phase: ulteriori 76 test superati in 106.11 secondi; blocco normalizzato del contratto invariato.
- `ruff check src/kajenn_public_site tests examples`, `compileall` e `git diff --check`: superati.
- Contratti: nomi e tutte le righe `wf:contract:` conservati; scheletri e campi Pattern/Files/Decisions/Done del piano invariati rispetto a `01efee3`.
- Installazioni normali non editable del progetto e dei framework. Nessun PYTHONPATH verso checkout upstream.
- Base pulita Python 3.12.9: pip check, import dell'app e coordinatore rendering senza Gramlot/Markdown/nh3/SQL, esempio editoriale REST/MCP e storico al riavvio superati.
- Rendering pulito Python 3.14.7: pip check e qualificazione dei due renderer superati; dipendenze esatte in `constraints/render-qualified.txt`.
- Esempio completo eseguito anche dal profilo base installato con worker opzionale installato: due engine, doppio render deterministico, tentativi distinti, CSS/JS/media separati, fonti conservate.
- Analisi HTML senza esecuzione JS: documento completo, testo, tabella, link e tutti i file CSS/media verificati. Non è una prova di hydration o pubblicazione HTTP.

## Pacchetti installati qualificati

- `gramlot`: `/private/tmp/kajenn-macro2-render-env/lib/python3.14/site-packages/gramlot/__init__.py`
- `genro_builders`: `/private/tmp/kajenn-macro2-render-env/lib/python3.14/site-packages/genro_builders/__init__.py`
- `nh3`: `/private/tmp/kajenn-macro2-render-env/lib/python3.14/site-packages/nh3/__init__.py`
- `markdown_it`: `/private/tmp/kajenn-macro2-render-env/lib/python3.14/site-packages/markdown_it/__init__.py`

## Artefatti della dimostrazione

- `gramlot`: `b177d896c7b72e609d1fc29ca77b64fb076c9a0c57f7336ef4d2d419648a2ed7` — `/tmp/kajenn-static-demo/gramlot.html`
- `htmlbuilder`: `9ad1103b4537ace7e87d7bbd6e991d9e337da2fed93df7688a098761878efc64` — `/tmp/kajenn-static-demo/htmlbuilder.html`

I file derivati della demo restano in `/tmp/kajenn-static-demo`; lo script li rigenera.

## Limiti espliciti

Codice del team fidato, ambiente minimo e timeout/output limitati: non sandbox ostile né quota memoria. Nessun job persistente, preview o pubblicazione in questa fase. URL risorse della demo sostituibili dal coordinatore delle release. Il profilo rifiuta espressioni browser/componenti non qualificati invece di omettere contenuto.

Chiusura: tutti i 49 nomi approvati, marcatori rimossi con equivalenza AST verificata. Worker reinstallato dai sorgenti finali: qualificazione dei due engine, pip check e dimostrazione ripetibile superati nuovamente.
