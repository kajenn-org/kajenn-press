# 06 · Storage, versioning e consistenza

Stato: gestione iniziale su filesystem e Genro Storage acquisita; Asqueel è un
futuro backend del catalogo. La persistenza locale della fase 1 è implementata e
verificata nei limiti descritti nella sezione finale. Le sezioni progettuali più
ampie includono ancora funzioni future. Conservazione, backup e parametri
operativi sono rinviati.

## Due responsabilità di persistenza

Il backend del catalogo conserva identità, grant, workflow, teste delle bozze,
release attiva, audit, ricevute idempotenti, job ed eventi pendenti. Inizialmente
usa file locali; in futuro potrà usare Asqueel/PostgreSQL. Genro Storage conserva
contenuti, sorgenti, media, manifest e artefatti con riferimenti esatti.

Il filesystem ordinario non offre automaticamente versioning S3: su file locali
si conservano snapshot immutabili e generazioni esplicite. Quando si usa S3,
il versioning deve essere abilitato e verificato. La sua mancata disponibilità
nel profilo locale non autorizza a sovrascrivere gli snapshot storici.
Le lacune specifiche S3 sotto si applicano al relativo profilo, non costituiscono
un requisito per iniziare con soli file locali. Le primitive storage generali
mancanti vanno risolte in Genro Storage; non si accede ai backend privati.

## Tre versioni diverse

| Concetto | Identifica | Non garantisce da solo |
|---|---|---|
| Revisione editoriale | Snapshot di variante con testo, metadati, riferimenti, autore e provenienza | Pubblicazione o approvazione |
| VersionId S3 | Una versione fisica di una chiave in un bucket | Identità editoriale, collegamento ai metadati, workflow o release |
| Release del sito | Composizione congelata di contenuti, configurazione e artefatti | Essere attiva; l'attivazione appartiene al canale |

Il versioning S3 protegge dalla perdita di versioni fisiche, ma non sostituisce
la storia editoriale ([documentazione AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)).
Un autosalvataggio è inoltre un DraftSnapshot, non necessariamente una revisione
da mostrare nella cronologia delle decisioni.

## Oggetti e manifest

Proposta di namespace logici: staging privato, snapshot editoriali, media,
bundle fidati, candidati, build e release. Non sono ancora mount o nomi di bucket
concordati. Gli ID logici sono separati dalla posizione fisica; il prefisso del
sito non sostituisce i controlli di accesso. Template e risorse generici hanno
un ambito logico di libreria comune, distinto dai namespace di sito; nei manifest
si registrano ambito e revisione esatta anche per le dipendenze condivise.

Ogni oggetto finalizzato porta:

- Riferimento logico, localizzatore storage, lunghezza, tipo MIME.
- SHA-256 calcolato dal prodotto sui byte esatti e algoritmo dichiarato.
- VersionId S3 quando disponibile, distinto da ID editoriale e checksum.
- Schema del payload, creazione e operazione che lo ha prodotto.

Il digest dei sorgenti HTML, Markdown, Python, CSS e JS riguarda i byte UTF-8
conservati. Le normalizzazioni eventuali avvengono prima del salvataggio e sono
definite dal profilo. Il digest
del manifest richiede una serializzazione deterministica: chiavi ordinate,
encoding, numeri, valori nulli e newline definiti; il campo del digest stesso è
escluso dal calcolo. I blob binari non sono normalizzati.

Manifest concettuale di revisione:

| Parte | Dati congelati |
|---|---|
| Identità | Site, Content, Variant, lingua, revisione predecessore, snapshot origine |
| Blocchi | ID, nome nel contratto del template, revisione del contratto, formato sorgente HTML/Markdown, riferimento esatto al blob e digest; eventuali derivati separati |
| Metadati | Titolo, sommario, slug proposto, SEO, date editoriali, tipo e revisione schema |
| Relazioni | Usi di media con revisioni, termini, riferimenti interni e blocchi/componenti |
| Attribuzione | Autore del cambiamento e riferimento al profilo pubblico versionato |
| Provenienza | Operazione/import/ripristino, versione formato |

Una revisione testuale non congela necessariamente tutto il sito. Il candidato
congela anche menu, configurazione, collezioni, temi, definizioni dei componenti,
risoluzione delle traduzioni, sorgenti Gramlot/HtmlBuilder, CSS/JS, contratto e
mapping Data, profili HTML/Markdown, sanitizzazione, renderer e dipendenze.
La Data Bag risolta può essere conservata come snapshot di build oppure ricostruita
da una ricetta deterministica con input esatti; non è un secondo contenuto
editabile. I manifest dei sorgenti registrano linguaggio/motore, percorso logico,
revisione e digest; quelli degli asset collegano sorgente, trasformatore e output.
Il manifest di release unisce
questi input ai digest degli artefatti e al route manifest. Non contiene
credenziali o URL temporanei.

La riproducibilità dei byte richiede di conservare l'esatto ambiente di build o
le sue dipendenze verificabili, locale/fuso, font, tool di trasformazione, seed e
timestamp deterministici. Registrarne i numeri di versione non basta. Artefatti
già conservati permettono rollback anche quando non è più possibile ricostruire
l'ambiente. Registrare gli artefatti usati non impone pin permanenti alle
dipendenze in sviluppo.

## Capacità S3: backend e interfaccia effettiva

| Necessità | Osservazione locale in Genro Storage 0.8.1 | Contratto richiesto |
|---|---|---|
| Leggere una versione specifica | `StorageNode.open(version=ID)` inoltra a `open_version`; S3 passa `version_id` a s3fs | Usare ID esatto, mai indice relativo o data per una release |
| Elencare versioni | `versions`/`get_versions` presenti | Errori distinguibili da elenco vuoto; elenco non prova completamento di una nostra scrittura |
| Verificare versioning del bucket | `_check_s3_versioning` controlla la presenza di un metodo s3fs | Verificare configurazione e accesso effettivi al bucket; il flag corrente non basta |
| Ottenere ricevuta di scrittura | `write` restituisce bool, metodi backend restituiscono `None` | Ricevuta con localizzatore, versione e integrità della scrittura appena conclusa |
| Creare senza sovrascrivere | Nessun parametro pubblico per precondizioni di scrittura trovato | Create-only atomico ed errore tipizzato; da estendere nel framework |
| Confrontare e scrivere | `skip_if_unchanged` evita alcuni duplicati, non è CAS | Precondizioni documentate; la finalizzazione della testa compete al backend del catalogo |
| URL temporanei | `node.url(expires_in=...)` e firma S3 presenti | Firma esplicita per metodo, versione, header e limiti se necessaria |
| URL di upload/versionato | Il backend `url` accetta kwargs ma non li inoltra a `fs.sign` | Non assumere PUT o VersionId firmati dall'interfaccia corrente |
| Retention / Object Lock / lifecycle | Nessuna superficie dedicata trovata nelle classi ispezionate | Policy gestite dal deployment e qualificate; eventuale esposizione nativa da progettare |
| Eliminare una versione | Metodo backend presente, usa boto3 | Qualificare dipendenze e semantica; l'extra S3 dichiara s3fs, non boto3 |

Riferimenti puntuali in [07](07-capacita-verificate.md). La documentazione AWS
descrive `If-None-Match` e `If-Match`; la capacità del servizio non prova che
Genro Storage la esponga
([scritture condizionali](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)).
Si raccomanda di estendere il contratto pubblico del framework. Accedere a
`node._backend.fs` dal prodotto nasconderebbe la lacuna.

ETag può essere un validatore opaco per una precondizione S3, ma non un checksum
universale dei contenuti: upload multipart e modalità di cifratura richiedono
attenzione. Il prodotto verifica il proprio SHA-256 e, se disponibile, il checksum
S3 con algoritmo e tipo dichiarati
([integrità AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html)).
Non usa `compact_versions` come politica di conservazione editoriale.

## Protocollo proposto per il backend filesystem

Profilo iniziale proposto: un solo coordinatore delle mutazioni su un filesystem
locale qualificato. Tutti i processi e worker inviano i comandi al coordinatore;
nessun secondo writer modifica direttamente il catalogo. L’avvio deve impedire
due coordinatori sullo stesso catalogo. NFS, object store come filesystem e
scritture concorrenti da host diversi non ereditano queste garanzie.

Il catalogo usa manifest immutabili per generazione e un riferimento autorevole
alla generazione corrente dell’installazione. La scelta di un solo riferimento
permette di includere nello stesso commit modifiche di sito e libreria generica.
È una proposta iniziale semplice, da misurare su dimensioni reali; non richiede
riscrivere tutti i payload a ogni salvataggio.

1. **Preparazione:** autenticare e registrare durevolmente l’intenzione con chiave
   idempotente, hash richiesta, base attesa e oggetti previsti. Questo non avanza
   le teste editoriali; un retry può ritrovare l’operazione.
2. **Payload:** scrivere oggetti immutabili in staging/namespace definitivo con
   primitive create-only qualificate; verificare dimensioni, hash e riferimenti.
   Gli upload e il rendering non bloccano il coordinatore per tutta la durata.
3. **Finalizzazione serializzata:** rileggere generazioni e autorizzazioni
   correnti; preparare un manifest che includa puntatori, esito idempotente,
   audit, eventi pendenti e riferimenti ai registri immutabili della storia.
   Un conflitto non avanza nessun puntatore del changeset.
4. **Commit locale:** rendere durevoli i nuovi file; sostituire il riferimento
   corrente mediante un’operazione atomica sullo stesso filesystem, con flush
   dei file e delle directory richiesti dalla piattaforma. Rename da solo non
   dimostra durabilità dopo un crash. Rispondere «salvato» solo dopo il completamento.
5. **Recupero:** riconciliare le intenzioni con il catalogo commesso. Oggetti
   preparati ma non raggiungibili restano privati; i retry leggono la ricevuta
   commessa prima di ripetere effetti. Un esito incerto blocca il replay cieco.

Lettori e serving risolvono una sola generazione per operazione e leggono i file
immutabili che essa referenzia. Il controllo della base sotto il coordinatore
realizza la semantica condizionale richiesta dai servizi: non si attribuisce
un CAS distribuito a un normale file. Lock, sostituzione atomica e durabilità
sono requisiti da verificare, non capability già provate in questa sessione.

Il changeset finalizza insieme template, mapping Data e CSS/JS tramite lo stesso
manifest. I job registrano intenzione, tentativi, annullamento e risultato nel
catalogo; la finalizzazione accetta solo il tentativo corrente. Worker scaduti
possono lasciare artefatti isolati, ma non aggiornare il catalogo. Lease e token
di tentativo, quando necessari, fanno parte del contratto da qualificare.

Gli eventi da consegnare sono visibili insieme al cambiamento che li genera.
Un relay può ritentare la consegna usando ID stabili. Lo spool kajenn esegue i
lavori, ma non diventa una seconda autorità sull’esito. La cancellazione di un
job è cooperativa e non annulla effetti già commessi.

L’attivazione cambia nel nuovo manifest il puntatore del canale alla release
verificata, insieme ad audit e ricevuta idempotente. Il rollback usa la stessa
operazione. Un eventuale puntatore replicato nello storage è una proiezione,
non una seconda fonte modificabile. Non serve una transazione distribuita fra
catalogo locale e storage: gli oggetti precedono il commit che li rende visibili.

## Futuro backend Asqueel

PostgreSQL resta il riferimento per il futuro backend SQL. Esso implementerà
lo stesso contratto mediante transazioni brevi, aggiornamenti condizionati alle
generazioni, ricevute idempotenti e audit/outbox nello stesso commit. Gestione
del runtime, connessioni e integrazione kajenn restano aperte. Non si assume
un’API CAS già pronta in Asqueel.

Il passaggio richiede importazione verificata del catalogo a scritture sospese,
conservazione di ID, revisioni, generazioni, audit, ricevute e job, confronto dei
risultati dei servizi e cambio dell’unica autorità. I payload storage non devono
essere duplicati per il solo cambio di backend. Fino al completamento della
migrazione il catalogo filesystem resta autorevole.

## Matrice dei guasti e recupero

| Punto di guasto | Stato osservabile | Recupero |
|---|---|---|
| Prima del commit preparatorio | Nessuna operazione durevole | Retry con stessa chiave |
| Dopo preparazione, prima dell'upload | Operazione pendente senza oggetti | Riprendere o scadere; nessun riferimento pubblicabile |
| Upload parziale o timeout | Oggetto incompleto/assente o esito incerto | Verificare per localizzatore e digest; completare con primitive qualificate, senza sovrascrittura cieca |
| Oggetti presenti, finalizzazione del catalogo fallita | Oggetti non referenziati dalla testa | Riconciliare stessa operazione; se base superata, conflitto e raccolta differita |
| Commit del catalogo dall'esito ignoto | Possibile testa già aggiornata | Leggere ricevuta operativa univoca e generazione; sospendere replay fino a chiarimento |
| Commit riuscito, risposta persa | Operazione completata | Stessa chiave restituisce l'esito, dopo controllo accessi |
| Worker muore in build | Tentativo pendente/scaduto | Nuovo tentativo con fence; riuso solo di artefatti verificati |
| Attivazione commessa, outbox non consegnata | Nuova release attiva, eventi pendenti | Relay riparte; nessuna riattivazione necessaria |
| CDN non aggiornata | Origine nuova, edge vecchio | Stato di propagazione, retry invalidazione; non dichiarare completamento globale |
| Oggetto referenziato mancante/corrotto | Allarme di integrità | Bloccare nuova attivazione; ripristino da replica/versione esatta; niente fallback silenzioso a `latest` |
| Invio esterno dall'esito incerto | Delivery `uncertain` | Riconciliazione/manualità secondo provider; non promettere exactly-once |

L'idempotenza riguarda gli effetti del dominio; non elimina automaticamente
duplicati di email o messaggi Telegram.

## Conservazione, eliminazione e ripristino

Classi distinte: buffer/autosalvataggi, revisioni editoriali, release attive,
release mantenute per rollback, media, audit e staging. Durate da decidere; una
release protetta mantiene la propria chiusura di dipendenze. Una preview valida
e un job pendente sono anch'essi radici di conservazione.

La pulizia procede per marcatura dei riferimenti, piano consultabile, grazia e
nuova verifica coordinata con le mutazioni del catalogo prima della cancellazione. Il passaggio a
«in eliminazione» impedisce nuovi riferimenti; la finalizzazione dei salvataggi
verifica lo stato degli oggetti. Non basta contare i link in una scansione mentre
altri worker salvano. Una lease attiva protegge gli oggetti di upload.

Le regole lifecycle S3 devono rispettare le radici protette, incluse versioni
non correnti e repliche. Il lifecycle può eliminare oggetti indipendentemente
dalla storia applicativa; una policy troppo aggressiva distrugge la riproducibilità
([lifecycle AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)).
L'attivazione del versioning e le policy del bucket sono configurazione operativa,
non dedotte dal flag capabilities di Genro Storage.

Il soft-delete conserva identità e recuperabilità. Il purge richiede che nessuna
radice protetta referenzi l'oggetto e lascia una traccia non contenutistica.
Un ripristino editoriale crea una nuova bozza/revisione; ripristinare un oggetto
S3 è un intervento di recupero fisico. Non sono la stessa azione.

Il futuro piano di disaster recovery deve coordinare backup del catalogo e oggetti tramite
manifest e punto di ripristino dichiarato. Dopo restore: riconciliare operazioni,
verificare release attiva, ricostruire indici, sospendere consegne e job fino a
controllo. Copiare solo il catalogo non basta. RPO/RTO e durate di conservazione
sono decisioni esplicitamente rinviate, da concordare e provare prima dell’esercizio
con le relative garanzie. Non viene adottata ora una scadenza di 90 giorni.

## Accesso pubblico e privato

Bucket privati per sorgenti, staging e artefatti non attivati. Il serving pubblica
solo gli artefatti autorizzati dalla release; l'accesso a release storiche è una
policy esplicita. Un URL contenente hash non è autorizzazione.

URL firmati sono credenziali temporanee trasferibili; valgono entro scadenza e
permessi del firmatario ([AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)).
Per preview revocabili immediatamente si raccomanda un gateway applicativo che
controlla il grant a ogni richiesta. Le firme dirette già emesse non garantiscono
quella revoca. Non inserire firme nei manifest o nelle pagine pubbliche permanenti.

Un ritiro urgente può richiedere blocco di una release, purge delle cache e
revoca degli accessi ai suoi asset; non può cancellare copie già scaricate.
Il blocco di emergenza ha un'autorità separata, auditata e verificata anche al
serving: è un'eccezione intenzionale alla disponibilità delle vecchie release.

## Prove richieste prima dell'implementazione dichiarata completa

Avvio simultaneo di due coordinatori; sostituzione atomica e durabilità del
riferimento corrente; lettura coerente durante commit; recupero del manifest e
delle ricevute dopo crash. Concorrenza a due autori e a due pubblicatori; riuso errato della chiave
idempotente; crash a ogni confine della matrice; worker con lease scaduta;
versioning disabilitato; lettura VersionId; precondizione fallita; upload multipart;
checksum errato; errore di listing; URL con metodo/versione; lifecycle incompatibile;
GC in gara con salvataggio; rollback dopo restore del catalogo; richieste pubbliche durante
attivazione e revoca. Le prove S3 valgono per il profilo S3; quelle sui file
locali per il backend iniziale. Il futuro backend Asqueel richiederà gli stessi
controlli semantici e prove di migrazione. Sono prove future, non test eseguiti
in questa sessione.


## Phase 1 implementation evidence — 2026-10-21

The local implementation now lives in `src/kajenn_public_site/catalog/` and
`objects.py`. Earlier architectural sections describe the wider target; jobs,
release activation, event delivery, retention, S3 and Asqueel are still future work.

The private root contains `owner.lock`, `current.json`, `manifests/`, `intents/`,
`staging/` and `payloads/`. JSON uses schema version 1, deterministic UTF-8 encoding
and SHA-256 over stored bytes. Catalog references identify a manifest by generated
name, generation and hash. Record and revision IDs are independently generated;
each record has its own generation. Historical manifests and all revisions remain
reachable. There is no automatic pruning.

A process holds `flock` for its entire coordinator lifetime; an `RLock` serializes
threads. Authorization and expected-generation checks precede preparation under
that lock. Authorization may read snapshots but cannot recursively mutate or
close the coordinator. Receipts are scoped by authenticated principal, command
scope and idempotency key; different input under the same key conflicts.

The coordinator writes a durable intent, then immutable payloads through public
`StorageNode.open('xb')`, flushes the returned streams, checks their digest, and
synchronizes the explicitly configured payload directory. It writes a complete
catalog manifest containing heads, revisions, receipt, audit and event identities.
Only replacement of `current.json` makes these changes visible. Catalog metadata
uses same-filesystem temporary files and `os.replace`, followed by directory sync;
Storage `move_to` is never a commit primitive. Payload bytes never use private
backend attributes or direct filesystem reads/writes.

Startup qualifies exclusive creation, public stream `fileno`/flush/fsync,
F_FULLFSYNC on macOS, directory synchronization and catalog replacement. Missing
required primitives reject the profile. Opening an existing catalog checks hashes,
schemas, exact revision associations and ancestry; corruption is an error rather
than an implicit rollback. An uncertain commit poisons further writes until the
coordinator is reopened. Recovery distinguishes committed intents from uncommitted
preparations and missing/incomplete payloads, without deleting or activating them.

Qualification uses real temporary directories and process termination after the
intent, during a payload, after payload completion, after the manifest, before
head replacement, immediately after replacement and after the final sync. Old or
new complete state is observed after restart; idempotent replay creates no duplicate
receipt/revision/audit/event. Tests also cover stale multi-record changesets, scoped
authorization, concurrent threads, owner death, corruption and symlink/traversal
rejection. This verifies process-crash behavior on the tested local platform, not
arbitrary power-loss/hardware-cache behavior or network filesystems.

The runnable example is `python3 examples/persistence.py /tmp/kajenn-public-site-demo`
after installing the project in a virtual environment. Run it twice: generation 2
and the same stable IDs survive close/reopen and replay. Backend read APIs remain
trusted internal operations; Phase 2 supplies authenticated site/library grants
for all external consumers. The JSON snapshot implementation is intentionally
unoptimized; large-history scalability remains a limitation to measure.
