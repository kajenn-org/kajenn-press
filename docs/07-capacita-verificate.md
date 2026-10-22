# 07 · Capacità verificate e lacune

## Aggiornamento runtime: Macro 2, fase 3

La suite comprende **102 test superati**. Ai renderer, candidati congelati, job
persistenti e anteprime della fase 2 si aggiungono attivazione condizionale,
serving pubblico e rollback senza rendering, con sei ulteriori operazioni REST/MCP.

Sono verificati attivatori concorrenti, interruzioni reali in cinque punti del
commit, riapertura/retry, permessi e revisione correnti, compatibilità di sito e
canale, isolamento delle origini e pinning di HTML/asset durante l'attivazione.
Il ciclo Chromium sull'applicazione installata copre Gramlot e HtmlBuilder,
anteprima, sito pubblico senza JS, aggiornamento della sola lingua italiana,
asset precedenti, rollback agli stessi byte e riavvio con ID inalterati.
Il profilo editoriale resta senza Gramlot, Markdown, nh3, SQLAlchemy e Asqueel.

Versioni e confini sono nei contratti di [rendering](10-rendering-statico.md),
[build/anteprima](11-build-anteprime.md) e [pubblicazione/rollback](12-publication-rollback.md).
Restano da implementare UI/editor, approvazioni, scheduling e componenti
interattivi. Questi esiti aggiornano le osservazioni storiche sotto riportate;
non qualificano S3, CDN, cluster o Asqueel.

## Ricognizione iniziale dei framework

Verifica del 20 ottobre 2026, integrata il 21 ottobre per editor PoC e builder,
mediante lettura di sorgenti, firme e test esistenti.
**«Presente» significa implementazione osservata, non test eseguiti in questa
sessione né disponibilità accertata nel deployment.** Una guida o un README non
certificano da soli una capacità. Revisioni e hash in [09](09-fonti.md).

## Mappa

| Area | Evidenza e stato osservato | Conseguenza per kajenn-public-site |
|---|---|---|
| kajenn: applicazioni | Presente: `BaseApplication`, code/instance/mount e configurazione; [K1](09-fonti.md#k1) | Applicazione separata coerente con l'host; sito editoriale e istanza restano concetti distinti |
| kajenn: mount | Presente: dispatch per primo segmento, root per percorsi non rivendicati; [K1](09-fonti.md#k1) | Riservare mount; virtual hosting per dominio non dimostrato da questo dispatch |
| kajenn: REST/MCP | Presente: `McpOpenApiApplication`, stesso router, filtro canali, esecuzione comune; [K2](09-fonti.md#k2) | Base richiesta utilizzabile; servizi editoriali e di costruzione del sito da realizzare ed esporre esplicitamente su entrambi i canali |
| kajenn: autorizzazione | Presente: autenticazione scope e filtri del router; [K2](09-fonti.md#k2) | Policy editoriali su sito, oggetto, stato e canale da implementare |
| kajenn: storage | Presente: `StorageMixin` costruisce `StorageManager`, espone `server.storage`; modalità sincrona nell'host; [K3](09-fonti.md#k3) | Usare pool/helper sincroni; mount storage non pubblica una route HTTP |
| kajenn: task | Presente: manager, spool, executor e scheduler; claim tramite `move_to`; [K4](09-fonti.md#k4) | Lavori in background disponibili, ma outbox applicativa, fencing e recovery editoriale non sono inclusi |
| Asqueel: persistenza | Presente: query e DML, PostgreSQL/SQLite, transazioni esplicite; [A1](09-fonti.md#a1) | Base per il futuro backend del catalogo, non dipendenza della prima implementazione |
| Asqueel: concorrenza | Presente: stato per thread e connessioni nominate; nessuna API async, pool generale, retry automatico o savepoint documentati come disponibili; [A1](09-fonti.md#a1) | Nel futuro backend SQL: unità intera in un worker e percorso CAS da qualificare, senza inventare metodi |
| Asqueel–kajenn–Gramlot: integrazione | Lacuna segnalata dal proprietario nella discussione progettuale; nessuna nuova verifica runtime effettuata | Integrazione rinviata; PostgreSQL resta il riferimento del futuro backend, mentre si parte su filesystem/storage |
| Asqueel: policy | Documentato: scope/partizioni non equivalgono a permessi di scrittura; profilo gerarchico ancora distinto dal percorso completo; [A1](09-fonti.md#a1) | Usare il profilo supportato e autorizzazioni applicative, non assumere tenant isolation automatica |
| Gramlot: UI | Presente: Source/Data, collezioni, controlli e `textBoxArea`; [G1](09-fonti.md#g1) | Base per pannello e form; persistenza, ricerca e workflow editoriali da costruire |
| Gramlot PoC: editor | Osservati HTML/Jodit, Markdown/ProseMirror e CodeMirror con CSS, JS e Python; [G5](09-fonti.md#g5) | Ripristino richiesto nel core attuale; binding, round-trip e lifecycle da qualificare |
| Gramlot: template statici | `GramlotBuilder` deriva da HtmlBuilder e usa `GramlotHtmlRenderer`; [G3](09-fonti.md#g3), [B1](09-fonti.md#b1) | Base per template alimentati da Data; contratto di prodotto e compatibilità dei componenti da qualificare |
| HtmlBuilder: rendering | Renderer HTML con escaping e inserimento raw esplicito; test del marcatore `::HTML`; [B1](09-fonti.md#b1) | Alternativa richiesta per template statici; il raw non sanitizza i contenuti e non prova hydration |
| Gramlot: hosting kajenn | Presente nell'adapter `gramlot-py-server`: `Application`, pagine, RPC, owner e auth tramite avatar/tag; [G4](09-fonti.md#g4) | Integrazione del pannello possibile; autorizzazione editoriale e composizione con API da progettare |
| Gramlot: regioni pubbliche | Discussione corrente su accompagnamento HTML e regioni interattive, non contratto di sito pronto; [G2](09-fonti.md#g2) | Integrazione diretta nella pagina scelta dal proprietario, iframe solo per isolamento; bootstrap/lifecycle/fallback da qualificare nel framework |
| Storage: S3 | Presente backend fsspec con `version_aware`; extra S3 con s3fs; [S1](09-fonti.md#s1) | Capacità da provare sull'ambiente scelto, non certificazione AWS/MinIO |
| Storage: versioni | Presente `open(version=...)`, listing e apertura storica; [S2](09-fonti.md#s2) | VersionId utilizzabile per riferimenti fisici, separato dalla revisione editoriale |
| Storage: capability | `_check_s3_versioning` verifica `hasattr`, non stato del bucket; [S2](09-fonti.md#s2) | Verifica operativa obbligatoria, flag insufficiente |
| Storage: errori listing | `get_versions` cattura eccezioni e restituisce `[]`; [S2](09-fonti.md#s2) | Per recovery non distinguerebbe assenza e guasto; necessario contratto errori affidabile |
| Storage: scritture | API `write` restituisce bool; backend scrive via `fs.open`; nessuna precondizione di scrittura esplicita trovata; [S3](09-fonti.md#s3) | Ricevuta e create-only/CAS sono estensioni del framework |
| Storage: firme | URL con scadenza presente; opzioni extra non inoltrate a `fs.sign`; [S4](09-fonti.md#s4) | PUT/versioni/header non garantiti dall'API corrente |
| Storage: retention | Nessuna API dedicata verificata; cancellazione versione backend presente, import boto3 distinto dall'extra S3; [S1](09-fonti.md#s1), [S2](09-fonti.md#s2) | Gestione operativa da qualificare; non chiamare la compattazione come retention editoriale |
| Storage: checksum | Codice/documenti impiegano ETag in funzioni hash/compattazione; [S5](09-fonti.md#s5) | Non usarlo come checksum universale; SHA-256 del prodotto |
| Telegram | Presente `TelegramBotApplication`, secret del webhook, invio e policy retry/esiti incerti; [T1](09-fonti.md#t1) | Integrare mediante eventi e principal espliciti; nessun bus editoriale già disponibile |
| App separata | `MailProxyApplication(McpOpenApiApplication)` con nucleo condiviso e scope applicativo; [M1](09-fonti.md#m1) | Esempio utile dei confini, non template da copiare integralmente |
| Siti attuali | Gramlot `welcome/` e Asqueel `site/`, generatori e controlli dedicati; [W1](09-fonti.md#w1) | Casi reali di contenuti/SEO/corsi, non applicazioni già migrate |

## Backend iniziale: decisione e capacità da qualificare

Il proprietario ha scelto di iniziare su filesystem e Genro Storage. Il backend
locale del catalogo è da realizzare: coordinatore unico, commit dei manifest,
durabilità, idempotenza e recupero non sono capacità certificate dalla presente
ricognizione. Nessuna nuova prova runtime è stata eseguita. Il versioning S3
non è attribuito al filesystem ordinario; gli snapshot locali devono essere
conservati esplicitamente. L’integrazione Asqueel resta futura.

## Osservazioni che modificano la proposta

La guida interna task kajenn consultata porta una marcatura «da revisionare».
La proposta si fonda sul codice dello spool: usa spostamenti di directory e
assume atomicità del mount. Non se ne deduce una coda distribuita sicura su S3;
per i task si raccomanda storage locale qualificato, distinto dagli oggetti
editoriali.

Genro Storage include decoratori `smartasync`, mentre kajenn imposta il servizio
sincrono tramite `set_sync`. Non è una contraddizione da risolvere aggiungendo
`await` casuali: l'integrazione deve rispettare la modalità dell'host verificata.

La documentazione di workspace Gramlot riporta ancora versioni 0.2.x, mentre il
README del core e i manifest locali riportano 0.3.5; inoltre il working tree
contiene modifiche. Si usa il core attuale come evidenza di sorgente, e si registra
la release dichiarata separatamente. Nessuna capacità locale viene attribuita
automaticamente al wheel pubblico. Il PoC è una fonte concreta per il ripristino degli editor,
non un runtime già disponibile nel core corrente.

I test locali presenti descrivono casi REST/MCP condivisi, autorizzazione e
versioning MinIO. Sono stati esaminati come evidenze di contratto; **non sono
stati eseguiti**, e nessun servizio S3/Telegram è stato avviato.

## Proprietà delle estensioni

| Responsabile naturale | Estensioni da concordare |
|---|---|
| Genro Storage | Ricevute di scrittura, precondizioni atomiche, errori distinguibili, firme con opzioni dichiarate, verifica effettiva delle capability |
| Gramlot core / componenti | Ripristino degli editor PoC HTML, Markdown, CSS/JS; binding/lifecycle, contratto per regioni interattive e relazione con HTML statico |
| Genro Builders / Gramlot | Qualifica dei template e del rendering Data → HTML, inserimento dei frammenti e diagnostica dei binding |
| gramlot-py-server / kajenn / Asqueel | Futuro contratto condiviso di integrazione da definire: runtime e connessioni, richieste/job, transazioni e identità; collegamento dei servizi alla Data Gramlot, composizione autenticata del pannello e mount |
| kajenn-public-site | Contratto di catalogo, backend filesystem e futura migrazione Asqueel; modello editoriale, sorgenti/template e mapping Data, profili HTML/Markdown, servizi completi REST/MCP per LLM, policy, build, release, outbox, idempotenza e riconciliazione |
| Asqueel | Contratti di runtime, connessioni e transazioni necessari all’integrazione; qualifica del DML scelto, senza attribuirgli un CMS o una transazione S3 |
| Deployment | Domini, TLS, bucket/versioning, retention fisica, credenziali, cache/CDN, backup e risorse worker |
| Applicazioni di integrazione | Traduzione degli eventi, mapping degli utenti e consegna esterna; il nucleo resta indipendente dai provider |

Le estensioni sono necessità progettuali, non autorizzazioni a modificare i
framework in questa sessione. Non è proposta alcuna facciata che simuli metodi
mancanti usando attributi privati.

## Macro 3, fase 1 — amministrazione in verifica

- Artefatti qualificati: Gramlot 0.3.9 e gramlot-py-server 0.2.12, con gli SHA256 in [admin-artifacts.json](admin-artifacts.json). Il wheel Kajenn 0.5.0 headless resta quello già qualificato; non sostituirlo con un checkout omonimo.
- Grammatica e bundle installati contengono CodeMirror, HTML/Jodit, Markdown/ProseMirror e `markdownPreview.allowHtml`. L'integrazione interattiva degli editor e HTML abilitato nel workspace appartengono alla fase 2.
- Undici test amministrativi (nove contratti del piano e due verifiche Gallery/MCP) verificano isolamento delle identità, revoca/logout, origine delle richieste, confini degli ambiti, letture senza payload e parità UI/REST/MCP; la prova include una build e un'anteprima reali.
- La consultazione usa IndexPage/IndexLogic, albero e iframe come la Gallery, Source/Data e Gramlot Base. Nuovo sito è stato anticipato alla fase 1 su richiesta esplicita. Per configurazione, profili separati, sessioni e demo vedere [13 · Amministrazione](13-amministrazione.md).
