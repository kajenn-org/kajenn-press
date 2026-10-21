# 04 · Catalogo delle funzioni esposte

Stato: proposta successiva al [modello](02-dominio.md). I nomi sono etichette
concettuali da discutere, non endpoint, tool MCP o metodi già approvati.

## Contratto comune

Le tre interfacce usano lo stesso livello applicativo. La prima implementazione
usa un backend filesystem/storage; i contratti dei servizi non richiedono
Asqueel e devono restare validi per la sua futura integrazione. Il client fornisce ID e
intenzione; il server ricava identità e privilegi dal contesto autenticato.
Non accetta un ruolo dichiarato nel payload come prova di autorizzazione.

Ogni comando modificativo porta ambito (sito o libreria generica), bersaglio,
generazione attesa e chiave di
idempotenza. Quest'ultima è associata ad attore, operazione, ambito e hash della
richiesta: stesso contenuto restituisce lo stesso esito, contenuto diverso produce
conflitto. Il recupero dell'esito richiede ancora autorizzazione.

Gli esiti concettuali sono risultato, job accettato, conflitto di generazione,
validazione fallita, operazione vietata, oggetto non disponibile o esito in
riconciliazione. REST e MCP preservano gli stessi codici applicativi, con envelope
adatto al trasporto. Un'eccezione storage non diventa «contenuto inesistente».

Le letture sono paginate, filtrate per ambito e con ordinamento stabile; un cursore
concettuale non implica una funzione keyset già fornita da Asqueel. Dimensioni e
quote sono configurabili. I campi editoriali sono dati; le operazioni dedicate
alla modifica dei sorgenti accettano invece template Python, CSS e JS con
linguaggio, base e permessi espliciti. Un LLM può usare entrambi i percorsi.
Il salvataggio dei sorgenti e la loro esecuzione in build sono operazioni distinte.

## Pilotaggio completo tramite LLM

Requisito acquisito: rendere pilotabili quante più funzionalità applicative
possibile tramite MCP e REST/OpenAPI kajenn. La copertura prevista comprende
tutte le famiglie di questo catalogo, inclusi costruzione del sito, accessi,
operazioni e recupero, nei limiti dei grant assegnati. Ogni futura funzione
applicativa deve dichiarare la disponibilità nei due canali; eventuali esclusioni
vanno motivate. Cursore, focus e disposizione dei pannelli rimangono stato della UI.

Il client deve poter scoprire operazioni, schemi, formati, capacità effettive e
permessi; leggere sorgenti e revisioni; applicare modifiche; validare; leggere
HTML, asset e diagnostica dell'anteprima; correggere; preparare, pubblicare e
controllare una release. Non basta restituire un URL di preview che richieda
una successiva operazione manuale. Gli artefatti privati restano accessibili con
lo stesso controllo di ambito della preview.

Le risposte includono ID e revisioni esatte, generazioni, dipendenze, esito e
azioni ammesse. La diagnostica è strutturata: codice, gravità, risorsa/revisione,
percorso Data o blocco e posizione nel sorgente quando disponibile. I job sono
ispezionabili, annullabili e ripetibili secondo il loro stato; errori e conflitti
devono offrire al client gli elementi per correggere e riprovare.

La qualifica dovrà dimostrare lo stesso scenario da UI, REST e MCP: creare un
template, collegare blocchi HTML/Markdown in Data, modificare CSS/JS, leggere e
correggere un errore, ispezionare la preview, pubblicare e fare rollback.
I canali devono rispettare gli stessi grant, CAS, idempotenza e audit.
Questa è una verifica futura del prodotto, non una capacità già certificata.

## Attori e permessi proposti

| Attore | Ambito tipico |
|---|---|
| Amministratore installazione | Associa deployment e risorse; non assume automaticamente il ruolo editoriale |
| Responsabile sito | Configura tipi, lingue, membri, navigazione e policy del sito |
| Progettista del sito | Modifica template Gramlot/HtmlBuilder, contratti Data e sorgenti CSS/JS secondo i grant |
| Client LLM | Agisce con il principal e i grant assegnati; può coprire tutti gli ambiti autorizzati, senza ruolo tecnico implicito |
| Autore / traduttore | Lavora sui contenuti assegnati e legge le risorse autorizzate |
| Revisore | Valuta revisioni assegnate; separazione dall'autore configurabile |
| Pubblicatore | Compone e attiva release per canali concessi |
| Operatore | Gestisce job, incidenti, recupero e retention secondo permessi specifici |
| Principal di servizio | Integrazione con grant minimo, scadenza e ambito espliciti |
| Lettore | Accede solo agli artefatti pubblicati; nessuna API amministrativa anonima |

Le capacità nelle tabelle sono vocabolario proposto: `site.manage`,
`content.write`, `review.decide`, `release.activate`, ecc. I tag kajenn filtrano
la superficie; il servizio verifica anche sito, oggetto, assegnazione e canale.
Un permesso di modifica non include pubblicazione; un permesso di rollback è
equivalente a un'attivazione pubblica. Gli ID non fungono da segreti.

## Siti, struttura e accessi

| Funzione / attore e scopo | Input → output | Permesso e precondizioni | Effetti, conflitti, modalità |
|---|---|---|---|
| Elencare/ispezionare siti · membro | Filtri → siti e capacità | `site.read`, appartenenza | Lettura sincrona |
| Creare sito · amministratore | Identità, lingue iniziali → Site privato | `installation.manage`, codice libero | Record e configurazione iniziale; duplicato in conflitto; sincrona, nessun DNS |
| Revisionare configurazione · responsabile | Snapshot e generazione → SiteConfigRevision | `site.manage`, schema valido | Nuova bozza di configurazione; conflitti di versione; sincrona, nessun effetto pubblico |
| Associare/verificare dominio · amministratore | Dominio, canale, prova → binding/stato | `domain.manage`, controllo del dominio e assenza di collisioni | Job di verifica; associazione operativa solo all'esito valido; non emette certificati |
| Gestire membri e policy · responsabile | Grant/policy attesi → nuovo stato | `access.manage`, protezioni contro perdita dell'ultimo amministratore | Commit del catalogo e audit; conflitto di generazione; sincrona; revoche applicate ai nuovi comandi |
| Definire tipo, tassonomia, menu o collezione · responsabile | Schema/albero/sequenza → revisione | `structure.write`, riferimenti accessibili e grafo valido | Nuovo snapshot; cicli, ID o percorsi duplicati bloccano; sincrona, trasformazioni massive tramite job |

Una modifica del dominio operativo non può cambiare silenziosamente l'origine
canonica di una release. Il comando prepara un piano di transizione e richiede
una release compatibile; il provisioning esterno rimane separato.

## Template, Data e sorgenti del sito

Nomi e grant della tabella sono proposte di contratto, da esporre su entrambi i
canali; i servizi devono essere riusabili dagli editor Gramlot.

| Funzione | Input → output | Permesso e precondizioni | Effetti e modalità |
|---|---|---|---|
| Esplorare sorgenti e contratti | Sito, revisione, percorso/filtri → albero, sorgente paginabile, schemi e dipendenze | `source.read`, ambito del sito | Lettura di versioni precise, ricerca e confronto senza perdita del formato |
| Creare/modificare template | Motore Gramlot/HtmlBuilder, sorgente, base, generazione → nuova revisione di lavoro | `template.write`, percorso libero o base valida | Salvataggio versionato; nessuna attivazione pubblica |
| Creare/modificare CSS e JS | Linguaggio, sorgente o patch, base → revisione risorsa | `source.write`, risorse autorizzate | Nuova revisione; riferimenti del tema aggiornati nel changeset |
| Definire Data e slot | Template, dichiarazione dei blocchi nominati, schema e mapping → DataContractRevision | `structure.write`, compatibilità con template | Validazione dei percorsi, dei tipi e dei riferimenti |
| Comporre blocchi editoriali | Contenuto, revisione del contratto template, nome blocco, formato HTML/Markdown e sorgente → snapshot | `content.write`, generazione attesa | Stessa semantica degli editor; conversioni esplicite con rapporto delle perdite |
| Validare sorgenti e Data | Selezione esatta → diagnostica e Data risolta ispezionabile | Lettura degli input e permesso di build per eseguire template | Sintassi, schemi, dipendenze, binding, markup e asset; analisi statica o job dichiarato |
| Preparare modifiche coordinate | Insieme di patch e basi → changeset, diff e pagine interessate | Grant richiesto per ogni risorsa | Validazione insieme; finalizzazione del catalogo tutta o niente, blob preparati prima |
| Comporre tema e dipendenze | Revisioni template/risorse e contratto Data → ThemeRevision | `theme.write`, chiusura dipendenze | Bundle immutabile selezionabile nel candidato |
| Ispezionare rendering | Candidato/build, pagina/risorsa → HTML, asset, Data pubblicabile e diagnostica | `preview.read`, grant valido | Lettura autenticata; mai serializzazione dei segreti o della Data privata della UI |

UI, REST e MCP espongono la dichiarazione dei blocchi del template selezionato,
così che autori e LLM possano leggere i nomi disponibili e compilare ciascun
blocco nel suo formato, conoscendone anche l’obbligatorietà. La posizione nel
layout è definita dal template. I comandi di salvataggio accettano bozze con
blocchi obbligatori mancanti o vuoti; la validazione per la pubblicazione li
segnala come errori bloccanti, con variante e nome del blocco. I blocchi
facoltativi vuoti non bloccano la pubblicazione.

Le patch dichiarano formato e revisione base; non si applicano a una testa
cambiata nel frattempo. Il changeset congela risorse e basi prima della
finalizzazione: conflitti su una di esse impediscono l'aggiornamento dell'insieme.
Le operazioni massive indipendenti espongono invece gli esiti per elemento e
dichiarano la propria atomicità; non si confondono con il changeset.

## Contenuti, traduzioni e revisioni

| Funzione / attore e scopo | Input → output | Permesso e precondizioni | Effetti, conflitti, modalità |
|---|---|---|---|
| Cercare/aprire contenuti · membro | Filtri, lingua, ID → metadati, snapshot, generazione | `content.read` sul sito e oggetto | Lettura sincrona; indice dichiara eventuale ritardo |
| Creare contenuto/variante · autore | Tipo, lingua, revisione tradotta eventuale → ID e bozza | `content.create`, lingua/tipo consentiti | Unicità variante; sincrona; nessuna pubblicazione |
| Salvare/autosalvare bozza · autore | Snapshot completo, base, generazione → nuova testa | `content.write`, schema e riferimenti validi | Oggetti immutabili e CAS; conflitto conserva il lavoro del client; sincrona per payload limitati |
| Creare revisione · autore | ID snapshot e messaggio → EditorialRevision | `revision.create`, snapshot finalizzato e appartenente alla variante | Checkpoint immutabile; sincrona; non approva |
| Confrontare revisioni · autore/revisore | Due ID → differenze testo/campi/media | `revision.read` su entrambe | Lettura sincrona o job per grandi insiemi |
| Ripristinare revisione · autore | Revisione storica, generazione bozza → nuova bozza | `content.write`, schema ancora gestibile | Nuovo snapshot con provenienza; non cambia release o decisioni pregresse; sincrona |
| Archiviare/recuperare contenuto · responsabile | ID, motivo, generazione → stato | `content.archive`, controllo dipendenze | Soft-delete operativo e audit; conflitto se riferimenti impediscono l'operazione; sincrona; ritiro pubblico separato |
| Importare/esportare · responsabile | Archivio o selezione, policy ID → rapporto/archivio | `content.import` / `content.export`, quota e accessi a tutte le risorse | Job con staging e validazione; collisioni richiedono scelta; import crea bozze, non pubblica |

L'autosalvataggio aggiorna la bozza di testo insieme ai suoi metadati. Non sono
previste due API indipendenti che possano lasciare testo e front matter fuori
sincronia. L'esito «salvato» significa finalizzazione durevole, non semplice
ricezione HTTP.

## Risorse e temi

Template, CSS/JS e media possono essere di sito oppure generici. UI, REST e MCP
consentono di indicare e filtrare l’ambito, leggere le revisioni accessibili e
selezionarle per un sito. Per le operazioni sui sorgenti e sugli upload l’ambito
generico sostituisce quello del sito e richiede i grant della libreria comune;
le tabelle descrivono i casi di sito. Il permesso di usare una risorsa generica
non include quello di modificarla. La personalizzazione crea una copia
indipendente nel sito, senza aggiornamenti ereditati dalla risorsa generica.
Il comando di copia, disponibile su UI, REST e MCP, riceve revisione sorgente
esatta, sito e destinazione; verifica lettura della sorgente e scrittura nel sito,
e restituisce nuova identità, revisione e provenienza. Le dipendenze sono
esplicite e versionate; le risorse dipendenti da personalizzare vengono copiate
a loro volta. Collisioni di destinazione e retry seguono le regole comuni di
concorrenza e idempotenza.

| Funzione / attore e scopo | Input → output | Permesso e precondizioni | Effetti, conflitti, modalità |
|---|---|---|---|
| Avviare upload · autore | Nome, dimensione, MIME dichiarato → sessione di staging | `media.upload`, quota | Riserva privata; sincrona; URL di upload diretto solo dopo estensione storage qualificata |
| Finalizzare upload · autore | Sessione, checksum atteso → MediaRevision o Job | `media.upload`, oggetto completo | Verifica MIME effettivo/hash, controlli file e metadati; errore resta in quarantena; trasformazioni asincrone |
| Cercare/ispezionare media · membro | Filtri/ID → revisioni e usi | `media.read`, ambito del sito | Lettura sincrona; download privato autorizzato |
| Revisionare metadati/produrre varianti · autore | Revisione, ricetta, metadati → nuova revisione/derivati | `media.write`, ricetta consentita | Metadati immutabili; derivazione tramite job; nessuna sostituzione degli usi pubblicati |
| Ritirare/eliminare media · responsabile/operatore | ID, motivo, policy → rapporto e stato | `media.retire` o `storage.purge`, nessun riferimento protetto per purge | Ritiro logico sincrono; cancellazione fisica tramite job e grazia; uso corrente genera conflitto |
| Registrare tema/componente · gestore fidato | Bundle, schema, digest → revisione disponibile | `theme.manage`, provenienza e compatibilità verificate | Job di verifica; codice fidato distinto da contenuti degli autori; nessuna attivazione implicita |

## Workflow, anteprime, build e pubblicazione

La pubblicazione diretta è consentita a chi dispone del relativo permesso.
Il sito può abilitare la revisione preventiva: in quel caso l’attivazione
richiede le approvazioni previste dalla policy. Le verifiche tecniche restano
necessarie in entrambe le modalità, su UI, REST e MCP.

| Funzione / attore e scopo | Input → output | Permesso e precondizioni | Effetti, conflitti, modalità |
|---|---|---|---|
| Richiedere revisione · autore | Revision ID, revisori → ReviewRequest | `review.request`, revisione finalizzata | Audit/outbox; duplicato idempotente; sincrona |
| Approvare/chiedere modifiche/rifiutare · revisore | Richiesta, revisione, motivazione, generazione → decisione | `review.decide`, assegnazione e separazione dei ruoli | Decisione immutabile; richiesta superata in conflitto; sincrona |
| Revocare approvazione · revisore/responsabile | Decisione, motivo → revoca collegata | `review.revoke` | Blocca attivazioni future che la richiedono; eventuale ritiro della release attiva è operazione distinta |
| Comporre candidato · pubblicatore | Selezione revisioni/configurazione/canale → candidato e differenze | `release.prepare`, riferimenti accessibili | Selezione congelata; dipendenze/collisioni segnalate; sincrona o job per grandi cataloghi |
| Preparare/condividere anteprima · autore/revisore | Candidato e ambito → Job, artefatto e grant | `preview.create/share`, autorizzazioni sui contenuti | Build privata asincrona; grant revocabile/scadente; nessun URL pubblico permanente |
| Revocare anteprima · titolare/responsabile | Grant ID → esito | `preview.revoke` | Sincrona; revoca controllata a ogni accesso |
| Compilare/validare · pubblicatore | Candidato, profilo → Job e rapporto | `build.run`, dipendenze disponibili | Build asincrona; errori non toccano il pubblico; retry crea nuovo tentativo |
| Ispezionare release/differenze · pubblicatore | Release o candidato, base → route e cambiamenti | `release.read` | Lettura; include rimozioni, redirect, lingue e risorse |
| Attivare · pubblicatore | Release pronta, canale, generazione, motivo → Activation | `release.activate`, verifiche valide e approvazioni quando richieste dalla policy | Commit condizionato del catalogo e audit/outbox; conflitto se canale cambiato; commit sincrono, propagazione eventuale tracciata |
| Programmare/annullare attivazione · pubblicatore | Release esatta, istante/fuso, base attesa → Job/stato | `release.schedule`, accesso al canale | Intento durevole; all'esecuzione ricontrolla permessi e base, non sovrascrive nuove pubblicazioni |
| Rollback · pubblicatore | Release storica, base attesa, motivo → Activation | `release.activate`, artefatti conservati e non revocati | Stessa semantica di attivazione; nessuna modifica editoriale |
| Ritirare dal pubblico · pubblicatore | Contenuti/route e strategia → candidato di ritiro | `release.prepare` e poi `release.activate` | Nuova release con 404/410/redirect; build e attivazione separate |

I comandi di pubblicazione rendono leggibili target, cambiamenti e conseguenze
su ogni canale. Un LLM con i grant necessari può completare anche l'attivazione
e il rollback. Non si introduce una conferma umana obbligatoria per il solo uso
di MCP o di un LLM. Se la policy del sito richiede una conferma, questa è legata
all'hash del piano e alla generazione e si applica anche agli altri client;
non è un consenso generico riutilizzabile né una funzione implicita del protocollo.

## Integrazioni e operazioni

| Funzione / attore e scopo | Input → output | Permesso e precondizioni | Effetti, conflitti, modalità |
|---|---|---|---|
| Configurare sottoscrizione · responsabile | Eventi, destinatario, riferimento segreto → configurazione | `integration.manage`, destinazione autorizzata | Sincrona; verifica di connettività come job esplicito, mai messaggio implicito |
| Consultare consegne/riprovare · operatore | Delivery ID e motivo → stato/tentativo | `integration.operate`, esito riconciliato | Job; esito esterno incerto richiede scelta, non replay automatico |
| Consultare/cancellare job · titolare/operatore | Job ID → progresso/esito | `job.read/cancel` | Cancellazione cooperativa; nessun undo di un'attivazione già commessa |
| Riconciliare/pianificare pulizia · operatore | Ambito e modalità analisi → rapporto/piano | `storage.inspect`, per esecuzione `storage.purge` | Job; fence e grazia impediscono gare con salvataggi/build |
| Consultare audit · responsabile | Filtri/correlazione → eventi paginati | `audit.read`, redazione dei dati sensibili | Lettura; nessuna funzione ordinaria per alterare le registrazioni |

Una pipeline asincrona restituisce Job ID, stato e correlazione; REST può usare
polling e MCP una funzione di stato. Gli aggiornamenti push sono un'ottimizzazione,
non l'unico modo di conoscere l'esito. Le capabilities del framework non
autorizzano automaticamente tutte le operazioni elencate: esposizione REST/MCP
e policy sono selezionate esplicitamente.
