# Rendering statico: contratto v1

Il profilo opzionale `.[render]` qualifica Gramlot 0.3.8, Genro Builders 0.30.0,
Genro Bag 0.28.0, Markdown-it-py 4.2.0 e nh3 0.3.7. Il backend editoriale
continua a funzionare senza Gramlot. I renderer vengono caricati nel processo
di rendering, senza usare i checkout sorgente dei framework.

Un template Python fidato dichiara `build(source, data)`, modifica Source e
ritorna `None`. `source` è la SourceBag pubblica dell'engine; `data` è la sua
Bag esistente. Non si invoca `create()`, che negli engine ha semantiche diverse.
L'adapter usa `render(mode="html", target=False)` e normalizza il doctype.

```python
def build(source, data):
    document = source.html(lang="^language")
    document.head().title("^page.title")
    body = document.body()
    body.h1("^page.title")
    body.div("^blocks.body")
```

Il contratto `kajenn-static-v1` espone Data con `site.id`, `site.name`,
`page.id`, `page.variant_id`, `page.title`, `language`, `blocks.<nome>` e
`resources.<revision_id>.url`/`kind`. I blocchi sono valori HTML preparati,
distinti dalle normali stringhe. Metadati e attributi restano sottoposti a
escaping, anche se terminano con `::HTML`. Il marker grezzo è una convenzione
interna del renderer, non un formato editoriale. La distinzione è una protezione
dagli errori: il codice Python del team resta esplicitamente fidato.

Il template deve costruire un unico `html`, con `head` e `body`. Il primo
profilo accetta elementi HTML statici e puntatori assoluti a Data esistente.
Espressioni `==`, puntatori irrisolti, controller, componenti e sub-builder non
qualificati producono un errore contestuale. Non si omettono silenziosamente
contenuti che richiedono JavaScript. Il supporto ai componenti registrati resta
alla macro dedicata. CSS e JavaScript del template sono risorse fidate separate.

Eseguire `python examples/qualify_renderers.py` nell'ambiente opzionale verifica
entrambi gli engine reali e riporta versioni e percorsi dei pacchetti installati.

`RenderInputs.freeze` legge una generazione del catalogo, include revisione della
variante, template e chiusura delle dipendenze, più sito/contenuto della stessa
generazione. Il valore risultante contiene byte JSON canonici immutabili, fonti
esatte in base64 e relativo digest. Un successivo cambiamento delle teste non
modifica lo snapshot. Sono richiesti `build` e `read` sul sito, `read` e `use`
sulle risorse, anche di libreria. I permessi vengono ricontrollati prima di usare
uno snapshot salvato. `write` non implica `build`.

Data contiene soltanto metadati della pagina e URL delle risorse esatte; nessun
catalogo o servizio è passato alla funzione template. Gli URL predefiniti
`/_resources/<sha256>.<tipo>` sono riferimenti per la dimostrazione, non endpoint
pubblici. Il futuro coordinatore dei candidati fornirà la mappa degli URL della
release. La fase corrente non serve né pubblica alcun contenuto.

`editorial-html-v1` abilita HTML incorporato, tabelle, barrato e codice fenced
nel Markdown. nh3 filtra entrambi i formati con la stessa allowlist: titoli,
liste, immagini, collegamenti, tabelle, codice, classi e formattazione ordinaria.
Gli stili ammessi sono colore/sfondo, allineamento, peso/stile/dimensione del font,
decorazione e interlinea. Sono rimossi script, handler, iframe/object/embed,
SVG/MathML e protocolli diversi da http/https/mailto/tel (URL relativi ammessi).
I valori CSS con URL, espressioni, variabili, escape o at-rule vengono esclusi.
Il profilo non garantisce ogni funzionalità futura di Jodit.

La diagnostica `html_filtered` segnala per nome del blocco la normalizzazione
o il filtraggio, senza affermare che ogni differenza sia un attacco. Un blocco
obbligatorio deve conservare testo significativo o un'immagine con `src` dopo
il filtro; blocchi vuoti opzionali restano leciti. Le fonti non vengono riscritte.

## Esecuzione e prove ripetibili

Creare un ambiente distinto per il rendering. L'interprete del coordinatore
editoriale può mantenere le sole dipendenze base:

```sh
python3 -m venv /tmp/kajenn-render
/tmp/kajenn-render/bin/python -m pip install '.[render]' -c constraints/render-qualified.txt
/tmp/kajenn-render/bin/python -m pip check
/tmp/kajenn-render/bin/python examples/qualify_renderers.py
export KAJENN_RENDER_PYTHON=/tmp/kajenn-render/bin/python
.venv/bin/python examples/static_rendering.py --python "$KAJENN_RENDER_PYTHON" /tmp/kajenn-static-demo
.venv/bin/python -m pytest -q --import-mode=importlib tests
```

L'esempio genera `gramlot.html`, `htmlbuilder.html`, risorse locali e un rapporto
con digest e profilo. I link fra pagine, testo, tabella, codice, CSS e immagine
funzionano anche disabilitando JavaScript. Per ogni engine confronta due render
degli stessi input. Non avvia un server e non crea link di anteprima.

`RenderService.freeze(identity, variant_id)` prepara gli input con il profilo
riportato dall'interprete configurato. `render(identity, frozen)` ricontrolla i
permessi e restituisce `status`, `attempt_id`, `input_digest`, diagnostica e,
soltanto in caso di successo, HTML, digest e profilo. Sono API del coordinatore
fidato; la fase successiva aggiungerà i trasporti REST/MCP per build e anteprima.
Nessun template viene eseguito da salvataggio, import dell'app o discovery.

Il worker usa un interprete assoluto, `-I`, directory temporanea, ambiente minimo
(PATH di sistema, locale e fuso orario), nessun token amministrativo ereditato,
nessun handle del catalogo. Timeout predefinito 15 secondi, output aggregato
stdout/stderr massimo 8 MiB, entrambi configurabili con valori positivi;
input esatti massimo 32 MiB e protocollo codificato massimo 48 MiB, 256 riferimenti.
Il supervisore termina il gruppo di processi, scarta output falliti e valida
schema, profilo e hash prima di dichiarare successo. I fallimenti non scrivono
nel catalogo. Non sono ancora job persistenti né garanzie di capacità produttiva.

Questo contenimento gestisce errori del codice fidato. Non impedisce a Python
ostile di accedere al filesystem o alla rete come lo stesso utente OS, non pone
un limite alla memoria allocata e non costituisce una sandbox di sicurezza.

Il profilo registra versioni esatte di Python e dipendenze, versione del filtro
e digest del codice degli adapter. Un worker diverso rifiuta input preparati
con un altro profilo; l'ID del tentativo non entra nei dati del template o nel
digest dell'artefatto. La riproducibilità vale per template deterministici:
il team può comunque scrivere codice che legge orologio, rete o casualità.
