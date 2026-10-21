# 09 · Fonti, provenienza e verifica

Ricognizione iniziale del **20 ottobre 2026**, integrata il **21 ottobre 2026**
per template, Data ed editor PoC; fuso di riferimento Europe/Rome.
Metodo: ispezione statica di sorgenti e documentazione locale, confronto tra
firme e implementazione per le capacità critiche, consultazione di fonti primarie
esterne. Nessuna installazione, esecuzione delle suite dei framework, chiamata
S3, invio Telegram o prova di deployment.

Il [registro dei sorgenti](fonti-locali.json) conserva percorsi, commit base,
stato dei file campionati e SHA-256. Il commit base non descrive da solo un
working tree modificato. I percorsi assoluti sotto sono utili in questo workspace;
ID, percorsi relativi e hash nel registro permettono di riconoscere le fonti su
un'altra macchina. Gli hash identificano i file letti, non costituiscono una
copia archiviata dei sorgenti.

## Versioni osservate

| Repository | Base Git osservata | Versione nel sorgente / limite |
|---|---|---|
| kajenn | `6ac7e586c36cbae0f9a301b48f1bf37dbf0359d2` | 0.5.0; checkout inizialmente pulito |
| Asqueel | `926000dde5f7dbaa07d56aa4c5a4985bd8162c85` | 0.6.0; documentazione e altri file locali modificati/non tracciati |
| Gramlot core | `d01bf3dc6389ad9bca91ef0f4bdbaafbfcc10242` | Manifest e README: 0.3.5; working tree con modifiche anche runtime |
| gramlot-py-server | `285f03181b2e9bb5f4c3ea4de613af18818b73f8` | README: release 0.2.10; artifact pubblico non installato |
| Genro Storage | `df695894d7d2777376d1981de8a1231631a71dd0` | `__version__`: 0.8.1; pyproject e altri file modificati |
| kajenn-mail-proxy | `1e4f78c76da9d8134b663a544e78784e5245fce7` | 0.7.7; test locale non tracciato, non eseguito |
| kajenn-bot-application | `0a9a51498601b7ac2f343d03ef3a98b7d5712577` | 0.3.0b1 nel sorgente; README dichiara pubblicazione pendente |
| Sito Gramlot | `81c9d4dd054feb0b4704b388f719b87b1a544406` | `welcome/` e script correnti includono file non tracciati |
| Sito Asqueel | `d199fd0046ec8c3aed1521478e7eeef7de80535d` | `site/` corrente; template e CSS modificati |

La release Gramlot 0.3.5 è **dichiarata** dal README locale. L'accesso web tentato
alla pagina PyPI e alla release GitHub non ha restituito contenuto verificabile:
non viene presentata come verifica indipendente del pacchetto pubblicato. Le
ricevute di pubblicazione riportate nei documenti del progetto sono evidenza
documentale preesistente, non una prova rieseguita qui.

## Evidenze locali

<a id="k1"></a>
### K1 · Applicazioni, configurazione e mount

- [BaseApplication: identità e configurazione](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/application.py:112).
- [Registrazione e mount del server](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/server.py:234);
  dispatch descritto e implementato nella sezione intorno alla riga 431.

<a id="k2"></a>
### K2 · REST, MCP e autorizzazione

- [McpOpenApiApplication](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/applications/mcp.py:387):
  router condiviso, canali e costruzione del trasporto.
- [OpenApiApplication](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/applications/openapi.py:67).
- [Esecuzione comune autenticata](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/routed_application.py:234).
- [Test dei due canali](/Users/gporcari/Sviluppo/kajenn/kajenn/tests/core/test_mcp_application.py:313):
  risultato comune, visibilità REST-only, schema; test di autorizzazione da riga 400.

<a id="k3"></a>
### K3 · Storage nell'host

- [StorageMixin](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/storage_mixin.py:79):
  costruzione manager e modalità sincrona, proprietà a riga 124.
- [Guida storage corrente](/Users/gporcari/Sviluppo/kajenn/kajenn/docs/guides/storage.md:1):
  accesso locale, worker pool, separazione fra mount storage e route pubblica.

<a id="k4"></a>
### K4 · Task

- [TaskSpool](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/tasks/spool.py:15):
  modello delle directory; claim a riga 210.
- [TaskManager](/Users/gporcari/Sviluppo/kajenn/kajenn/src/kajenn/tasks/manager.py:134):
  ciclo worker e dispatch dei pending.
- [Nota interna task](/Users/gporcari/Sviluppo/kajenn/kajenn/internals/10_server/070_tasks/README.md:1):
  marcata da revisionare, non usata come certificazione di affidabilità distribuita.

<a id="a1"></a>
### A1 · Asqueel

- [Limiti correnti](/Users/gporcari/Sviluppo/asqueel/asqueel/docs/guide/limitations.md:1)
  e [transazioni](/Users/gporcari/Sviluppo/asqueel/asqueel/docs/guide/transactions.md:1).
- [Runtime: esecuzione e completamento](/Users/gporcari/Sviluppo/asqueel/asqueel/src/asqueel/runtime.py:194):
  commit/rollback a riga 240; cleanup a riga 268.
- [Scritture e controllo righe](/Users/gporcari/Sviluppo/asqueel/asqueel/src/asqueel/writes.py:90).
- [Interfaccia di tabella](/Users/gporcari/Sviluppo/asqueel/asqueel/src/asqueel/application_table.py:433):
  update/raw_update; non è una funzione CAS già confezionata.

<a id="g1"></a>
### G1 · Gramlot corrente

- [README del core](/Users/gporcari/Sviluppo/gramlot/gramlot/README.md:1),
  [checkpoint corrente](/Users/gporcari/Sviluppo/gramlot/gramlot/docs/internal/070-work-status.md:1)
  e [guida componenti](/Users/gporcari/Sviluppo/gramlot/gramlot/docs/public/105-components.md:1).
- [TextBoxArea](/Users/gporcari/Sviluppo/gramlot/gramlot/js/src/components/inputs.js:83):
  wrapper textarea con binding, non editor Markdown avanzato.
- [Registro collezioni](/Users/gporcari/Sviluppo/gramlot/gramlot/js/src/components/registry.js:35):
  definizioni e generazione della grammatica.

<a id="g2"></a>
### G2 · Editor e regioni: confine delle proposte

- [Confronto editor del 20 ottobre](/Users/gporcari/Sviluppo/gramlot/gramlot/docs/internal/198-legacy-editors.md:1):
  esplicitamente analisi e proposta, senza implementazione approvata.
- [Stato corrente](/Users/gporcari/Sviluppo/gramlot/gramlot/docs/internal/070-work-status.md:1):
  distingue sviluppo, pubblicazione e disegno differito del sito.
- [Costituzione](/Users/gporcari/Sviluppo/gramlot/gramlot/docs/00-constitution.md:1):
  ownership di Source/Data, componenti, host e divieto di surrogati applicativi.

<a id="g3"></a>
### G3 · Renderer

- [GramlotHtmlRenderer](/Users/gporcari/Sviluppo/gramlot/gramlot/src/gramlot/renderer/html_renderer.py:16):
  serializzazione HTML/SVG, filtri attributi, gestione testo e doctype.

<a id="g4"></a>
### G4 · Adapter kajenn attuale

- [Application dell'adapter](/Users/gporcari/Sviluppo/gramlot/gramlot-py-server/src/gramlot_py_server/kajenn.py:151):
  identità del browser e propagazione avatar nella sezione `operation`, riga 289.
- [Guida kajenn](/Users/gporcari/Sviluppo/gramlot/gramlot-py-server/docs/505-kajenn.md:1):
  mount e body raw; non usare l'adapter archiviato come riferimento attuale.

<a id="s1"></a>
### S1 · Dipendenze e backend storage

- [Dipendenza kajenn](/Users/gporcari/Sviluppo/kajenn/kajenn/pyproject.toml:42):
  `genro-storage[encryption]>=0.8.1`.
- [Extra S3](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/pyproject.toml:40)
  e [versione sorgente](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/__init__.py:64).
- [Backend fsspec](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/fsspec.py:75):
  attivazione version awareness per S3.

<a id="s2"></a>
### S2 · Versioni S3

- [Apertura del nodo](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/node.py:598).
- [Capability check](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/fsspec.py:438).
- [Listing](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/fsspec.py:648),
  lettura versione a riga 707, cancellazione a riga 746.
- [Test MinIO](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/tests/test_s3_versioning.py:1):
  richiedono servizio e bucket versionato, non eseguiti.

<a id="s3"></a>
### S3 · Scritture e precondizioni

- [StorageNode.write](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/node.py:971).
- [Scritture backend](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/fsspec.py:542)
  e [contratto base](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/base.py:363).
- Ricerca nelle sorgenti `src/genro_storage` di `IfMatch`, `IfNoneMatch`,
  `if_match`, `if_none_match`: trovato un uso HTTP per risposta condizionale in
  `node.py`, non una precondizione di scrittura. Le firme di `write` e backend
  confermano l'assenza osservata della superficie necessaria.

<a id="s4"></a>
### S4 · URL

- [StorageNode.url](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/node.py:2119)
  e [firma nel backend](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/fsspec.py:945):
  `kwargs` non inoltrati alla chiamata `fs.sign`.

<a id="s5"></a>
### S5 · Hash e compattazione

- [Hash del backend](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/backends/fsspec.py:808).
- [Compattazione](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/src/genro_storage/node.py:2278)
  e [guida versioning](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-storage/docs/versioning.rst:1).
  Le indicazioni ETag/MD5 vanno confrontate con il limite documentato da AWS.

<a id="t1"></a>
### T1 · Telegram

- [README e stato release](/Users/gporcari/Sviluppo/kajenn/kajenn-bot-application/README.md:1).
- [Webhook](/Users/gporcari/Sviluppo/kajenn/kajenn-bot-application/src/kajenn_bot_application/telegram.py:202):
  controllo `x-telegram-bot-api-secret-token` con confronto costante.
- [Consegne e incertezza](/Users/gporcari/Sviluppo/kajenn/kajenn-bot-application/src/kajenn_bot_application/telegram_delivery.py:15):
  limiti di retry documentati, nessuna garanzia exactly-once.

<a id="m1"></a>
### M1 · Applicazione separata

- [MailProxyApplication](/Users/gporcari/Sviluppo/kajenn/kajenn-mail-proxy/src/kajenn_mail_proxy/mail_proxy_application.py:1):
  base MCP/OpenAPI, nucleo mail e controlli di ambito tenant.

<a id="w1"></a>
### W1 · Siti esistenti

- [Build welcome Gramlot](/Users/gporcari/Sviluppo/gramlot/gramlot-site/scripts/build-welcome.py:1)
  e [verificatore corrente](/Users/gporcari/Sviluppo/gramlot/gramlot-site/scripts/check-welcome.py:1).
- [README Asqueel site](/Users/gporcari/Sviluppo/asqueel-site/README.md:1)
  e [build da site/](/Users/gporcari/Sviluppo/asqueel-site/scripts/build.py:1).

I sorgenti correnti descrivono shell editoriale, navigazione, SEO, risorse e
corsi. Non sono state modificate né rigenerate directory `dist` o `dist-welcome`.

## Integrazione delle fonti del 21 ottobre 2026

Il [registro aggiuntivo](fonti-locali-2026-10-21.json) fotografa i sorgenti
consultati per questa integrazione. Il registro del 20 ottobre rimane storico;
non si presume che i checkout dei framework siano rimasti invariati.

<a id="g5"></a>
### G5 · Editor da ripristinare dal PoC

- [HTML/Jodit](/Users/gporcari/Sviluppo/gramlot/gramlot-poc/js/dom/src/collections/html-editor.js:80):
  caricamento dell'editor e chiamata a `Jodit.make`.
- [Markdown](/Users/gporcari/Sviluppo/gramlot/gramlot-poc/js/dom/src/collections/markdown-editor.js:14):
  schema ProseMirror, parser/serializer e conservazione di blocchi raw.
- [Dipendenze editor](/Users/gporcari/Sviluppo/gramlot/gramlot-poc/js/dom/src/editor-dependencies.js:20):
  CodeMirror, linguaggi CSS/Python e fallback JavaScript; dipendenze Markdown.
- [Componente CodeMirror](/Users/gporcari/Sviluppo/gramlot/gramlot-poc/js/pages/src/codemirror-component.js:17):
  integrazione del motore nel PoC.

La presenza di questi sorgenti conferma la base da recuperare. Il port nel core,
la parità funzionale e la compatibilità con il nuovo prodotto non sono stati
implementati né verificati in esecuzione.

<a id="b1"></a>
### B1 · Gramlot, HtmlBuilder e frammenti HTML

- [GramlotBuilder](/Users/gporcari/Sviluppo/gramlot/gramlot/src/gramlot/page/builder.py:59):
  deriva da HtmlBuilder; selezione di `GramlotHtmlRenderer` a riga 129.
- [Test renderer Gramlot](/Users/gporcari/Sviluppo/gramlot/gramlot/tests/test_renderers.py:1):
  esempi di authoring con Source/Data e rendering statico.
- [Renderer HTML base](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-builders/src/genro_builders/contrib/html/html_renderer.py:151):
  gestione dei figli, escaping e suffisso raw `::HTML`.
- [Test degli input](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-builders/tests/test_template_inputs.py:56):
  distinzione fra HTML raw e testo escapato; non un test di sanitizzazione.

Il suffisso è evidenza del meccanismo esistente, non il contratto editoriale
approvato. La pipeline del prodotto deve qualificare il passaggio dei frammenti
attraverso Data e i due renderer. I test citati sono stati letti, non eseguiti.

## Fonti primarie esterne

Consultate nella ricognizione iniziale del 20 ottobre; le capacità del fornitore sono distinte da
quelle esposte dai framework locali.

| Fonte | Questione verificata |
|---|---|
| [AWS · Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html) | Versioni fisiche di uno stesso oggetto |
| [AWS · Scritture condizionali](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html) | Precondizioni del servizio e conflitti |
| [AWS · Integrità upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html) | Checksum e limiti dell'ETag |
| [AWS · URL firmati](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html) | Metodo, accesso temporaneo e limiti della firma |
| [AWS · Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) | Scadenza e transizione degli oggetti |
| [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) | Base proposta del formato Markdown |
| [Google · Localizzazione](https://developers.google.com/search/docs/specialty/international/localized-versions) | Alternate e lingue |
| [Google · Canonical](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) | Coerenza degli URL canonici |
| [Google · Dati strutturati](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data) | Relazione con contenuto visibile e limiti dei risultati |
| [Sitemaps.org · Protocollo](https://www.sitemaps.org/protocol.html) | Sitemap e indici |

## Verifica dei documenti e limiti

Controlli della consegna: presenza degli otto elaborati richiesti, indice README,
link locali e anchor, validità del registro JSON, corrispondenza dei digest,
delimitatori dei blocchi Markdown e revisione degli invarianti tra documenti.
Non sono test del prodotto futuro.

Esito della consegna iniziale del 20 ottobre: verificati 10 documenti Markdown (README incluso), 100 link locali con
controllo dei percorsi, delle righe citate e degli anchor espliciti, 4 blocchi
delimitati e 61 hash di fonti locali. I diagrammi Mermaid sono stati riletti come
testo; non è stata effettuata una verifica grafica con un renderer Mermaid.

Aggiornamento del 21 ottobre: ricontrollati 10 documenti Markdown, 114 link
locali (percorsi, righe citate e anchor), 4 blocchi delimitati, coerenza delle
colonne delle tabelle, assenza di spazi finali e validità dei due registri JSON.
Verificati gli 8 hash del registro aggiuntivo; i 61 hash del registro iniziale
restano la fotografia storica del 20 ottobre. Riletti i documenti per eliminare
il vincolo Markdown-only e allineare template, Data, editor e copertura LLM.
La successiva scelta filesystem/storage è stata propagata in autorità dei dati,
flussi, catalogo funzioni e protocollo di consistenza: le parti SQL sono ora
esplicitamente future. Questa revisione non certifica l’atomicità o la durabilità
del backend locale proposto.

Restano da eseguire durante l'implementazione: qualifica dei pacchetti realmente
installati, prove transazionali e di concorrenza, S3/MinIO, rendering nel browser
con e senza JS, autorizzazione fra canali, backup/restore e prove di fault
injection. La presenza di un file di test nei framework non certifica che passi
oggi, né che copra questo nuovo prodotto.
