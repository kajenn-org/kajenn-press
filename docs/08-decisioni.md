# 08 · Direzione acquisita, decisioni aperte e raccomandazioni

Stato al 21 ottobre 2026: direzione su template, Data, editor e pilotaggio LLM
acquisita dal proprietario, insieme al perimetro multisito di D1 e alla scelta
di Genro Storage e delle release coerenti del sito in D2. In D3 sono acquisite
la bozza condivisa, la pubblicazione diretta con revisione configurabile e
la pubblicazione indipendente delle lingue. Si parte con filesystem e Genro
Storage, senza database obbligatorio.
Asqueel/PostgreSQL resta il futuro backend; integrazione, conservazione e
parametri operativi sono rinviati. D4 distingue
la direzione stabilita dai contratti ancora da definire. Il
[prompt di progettazione](../PROMPT-PROGETTAZIONE.md) è stato corretto soltanto
nella nomenclatura: il nome del progetto è `kajenn-public-site`.

## Indicazioni acquisite il 21 ottobre 2026

- Template Gramlot oppure HtmlBuilder, con rendering statico dell'HTML.
- Contenuti nella Data Bag del template, inclusi blocchi HTML prodotti da Jodit
  o dalla trasformazione del Markdown.
- Ripristino degli editor già presenti nel PoC per HTML, Markdown, CSS e JS.
- Uso di kajenn MCP/OpenAPI per permettere a un LLM di pilotare quante più
  funzionalità possibile, comprese costruzione e manutenzione del sito.

Queste indicazioni sostituiscono la precedente raccomandazione di Markdown come
unico sorgente canonico e la scelta ancora libera di un nuovo editor. I dettagli
proposti nei documenti — entità, schemi, nomi delle funzioni e protocollo di
changeset — non sono per questo API approvate. Il ripristino e l'integrazione
restano lavoro futuro; questa sessione aggiorna la progettazione.

## D1 · Più siti con amministrazione comune

**Decisione acquisita:** il perimetro attuale comprende più siti gestiti da un
unico amministratore o team. Il multitenant, con clienti indipendenti e relativi
requisiti di isolamento, è rinviato a una progettazione successiva.

Il sito resta un'identità editoriale distinta, con proprie configurazioni,
contenuti, domini, canali e release. L'amministrazione comune non fonde i siti:
le operazioni indicano il sito bersaglio e i ruoli del team restano configurabili.
Non occorre introdurre ora un modello di tenant o un isolamento fisico per cliente.

È acquisita anche la distinzione tra template e risorse specifici di sito e
template e risorse generici, riutilizzabili fra i siti della stessa gestione.
Questo vale per template, CSS/JS e media; non introduce un tenant.

**Personalizzazione acquisita:** copia indipendente nel sito, con propria
identità e revisioni. La provenienza può essere conservata come informazione;
non esiste ereditarietà né propagazione degli aggiornamenti dalla base generica.
La proposta di release continua a congelare le revisioni utilizzate, anche per
le risorse generiche.
La topologia di serving e la risoluzione dei domini rimangono dettagli
architetturali da qualificare; questa decisione non attribuisce virtual hosting
nativo a kajenn.

## D2 · Dove risiede il contenuto e che cosa si pubblica

**Scelta acquisita per la persistenza:** contenuti, template e risorse in Genro
Storage, sfruttando il versioning del backend per conservare e recuperare le
versioni degli oggetti. Per S3 il bucket deve avere versioning abilitato e
l'accesso alle versioni esatte deve essere qualificato attraverso Genro Storage.
Il versioning non viene ricostruito come cronologia dei byte nel database.

Un backend di catalogo mantiene identità, relazioni, workflow e puntatori alle
versioni selezionate: inizialmente filesystem, in futuro Asqueel. La revisione
editoriale collega oggetti, metadati e decisioni;
la release identifica quali versioni compongono una pubblicazione coerente.
Questi registri applicativi danno significato editoriale alle versioni fisiche.

**Scelta acquisita per la pubblicazione:** ogni pubblicazione produce una
release coerente del sito, anche quando cambia un solo articolo. La release
seleziona versioni esatte di pagine, template, risorse e configurazione;
il rollback ripristina l'insieme della release scelta. Questo non richiede di
ricopiare o ricompilare gli artefatti invariati: il riuso deve mantenere la
coerenza dell'insieme.

Restano dettagli tecnici proposti: snapshot e manifest immutabili, attivazione
tramite commit del backend di catalogo e protocollo di finalizzazione/recupero. L'approvazione
della modalità di pubblicazione non certifica questi meccanismi come implementati.

Costo esplicito della raccomandazione: estensioni Genro Storage e protocollo di
finalizzazione/recupero. Non si elude quel costo con letture `latest`.

## D3 · Quanto controllo editoriale e quale collaborazione

**Scelta acquisita per la collaborazione:** una bozza condivisa per ogni
contenuto e lingua, con rilevamento dei conflitti tra modifiche concorrenti.
Una scrittura basata su una versione superata non sovrascrive silenziosamente
il lavoro altrui. Non sono previsti rami personali da riunire successivamente.

Il meccanismo proposto usa generazione attesa e CAS, snapshot di autosalvataggio
e revisioni deliberate. Il confronto e la risoluzione dei conflitti non implicano
editing simultaneo CRDT/OT. I dettagli tecnici restano da qualificare.

**Scelta acquisita per il workflow:** chi ha il permesso di pubblicare può
pubblicare direttamente. La revisione preventiva è configurabile per sito;
quando abilitata, le approvazioni richieste devono essere soddisfatte prima
della pubblicazione. La regola vale allo stesso modo per UI, REST, MCP e client
LLM autorizzati. Restano sempre necessari i controlli tecnici della release.

La proposta tecnica riferisce richieste e approvazioni a revisioni precise e
registra policy versionate per sito. I dettagli delle policy restano da definire.

**Scelta acquisita per le lingue:** ogni variante si pubblica quando è pronta,
senza attendere le altre traduzioni. La nuova release può aggiornare una lingua
e conservare le revisioni già pubblicate delle altre. Una variante mai pubblicata
resta assente fino alla sua prima pubblicazione; una bozza incompleta non entra
implicitamente nella release. La completezza delle traduzioni non è un requisito
generale di pubblicazione.

Per i siti che abilitano la revisione, restano dettagli configurabili da
definire: separazione autore/revisore, quorum, scadenza e revoca delle
approvazioni. Non costituiscono un obbligo generale di revisione.
Non servono ora nomi definitivi di ogni ruolo o pulsante.

## D4 · Template, Data, editor e componenti

**Direzione stabilita:** template dichiarativi Gramlot o HtmlBuilder; contenuti
separati nella Data Bag; rendering statico. Ripristino degli editor PoC HTML/Jodit,
Markdown e CodeMirror per CSS/JS, con strumenti per il sorgente dei template.

**Scelta acquisita per i contenuti:** il template definisce più blocchi nominati
in Data. Ogni blocco contiene un sorgente HTML oppure Markdown; una stessa
pagina può usare formati diversi nei diversi blocchi. I nomi e la collocazione
dei blocchi appartengono al contratto del template, i valori al contenuto.
Il template dichiara inoltre quali blocchi sono obbligatori e quali facoltativi.
Una bozza può essere salvata con blocchi obbligatori mancanti o vuoti; la
pubblicazione della variante richiede che siano compilati. I blocchi facoltativi
vuoti non impediscono la pubblicazione.

**Contratto tecnico proposto:** ogni blocco conserva il proprio sorgente;
la pipeline produce frammenti HTML preparati e popola Data secondo uno schema
versionato. Template, mapping e asset CSS/JS hanno revisioni proprie e sono
congelati nella release. Il codice dei template e degli asset è modificabile
intenzionalmente dagli autori autorizzati, anche tramite LLM.

Restano da definire: profili HTML/Markdown e round-trip degli editor, contratto
esatto dei binding e dell'inserimento dei frammenti, formato dei riferimenti ai
componenti nell'HTML, diagnostica e ambiente di esecuzione dei template.
La proposta distingue sorgenti persistiti e Data risolta per la build; i percorsi
della Bag e gli schemi non sono ancora API approvate.

**Scelta acquisita per i componenti pubblici:** componenti Gramlot integrati
direttamente nella pagina; iframe solo quando serve isolamento. Il contenuto
essenziale resta leggibile nell’HTML statico anche senza attivazione JavaScript.

Restano contratti tecnici da definire e qualificare nel framework: bootstrap,
lifecycle, accessibilità, scope e condivisione di Data, più istanze e cleanup.
L’iframe non è il ripiego automatico per un’integrazione diretta incompleta.
La sintassi esemplificativa nel documento UX non è ancora un parser approvato.

La copertura MCP/REST deve includere anche questi strumenti. Un LLM può
completare il ciclo di lavoro con i grant necessari; eventuali approvazioni
richieste dalla policy riguardano l'azione su tutti i canali, non la natura LLM
del client. Non si introduce un passaggio manuale obbligatorio per principio.

## D5 · Garanzie operative e conservazione

**Scelta iniziale acquisita:** gestione puramente su filesystem e Genro Storage.
Non si attende l’integrazione Asqueel e non si richiede un database per avviare
il prodotto. Asqueel è un futuro backend di persistenza del catalogo; PostgreSQL
resta il riferimento per quella successiva integrazione. Questa scelta aggiorna
la precedente impostazione che rendeva SQL necessario fin dall’inizio.

**Proposta tecnica iniziale:** catalogo su filesystem locale con un coordinatore
unico delle scritture, controllo delle generazioni e commit di manifest; payload
immutabili via Genro Storage. UI, REST e MCP usano gli stessi servizi e contratti,
indipendenti dal backend. Concorrenza, idempotenza e recupero vanno qualificati
anche senza SQL; il versioning degli oggetti non li fornisce automaticamente.

**Integrazione rinviata:** definire il collegamento Asqueel–kajenn–Gramlot e la
migrazione del catalogo quando il contratto dei framework sarà chiaro. Restano
aperti runtime, connessioni, transazioni e collocazione del supporto riusabile.
Il collegamento della Data Gramlot ai servizi applicativi serve comunque nella
prima implementazione; non dipende da un binding diretto con Asqueel.

**Decisioni operative rinviate dal proprietario:** durate di conservazione,
backup, tempi di recupero, limiti quantitativi e dettagli CDN. I 90 giorni
proposti in conversazione non sono stati approvati. Gli invarianti di integrità
rimangono obiettivi; i valori operativi saranno scelti più avanti.

Da concordare prima della qualifica, senza inventare livelli di servizio:

| Parametro | Perché decide il progetto operativo |
|---|---|
| Dimensione media/massima dei media e volume del catalogo | Upload, memoria, pipeline e tempi di build |
| Finestra di rollback e storia editoriale | Protezione degli oggetti e costo storage |
| Conservazione autosalvataggi e staging | Recupero del lavoro e raccolta degli orfani |
| RPO/RTO | Frequenza backup, repliche e prove di restore |
| Ritardo accettabile della CDN | Policy HTML, invalidazione e significato di «pubblicato» |
| Revoca urgente | Accesso a vecchie release/asset e purge delle cache |
| Autonomia delle integrazioni | Principals, conferma attivazioni e gestione degli esiti incerti |

## Rischi materiali e criterio per chiuderli

| Rischio | Trattamento proposto | Evidenza necessaria |
|---|---|---|
| Scrittura sovrascrive dati storici o non restituisce versione certa | Estendere Genro Storage; immutabilità e ricevute | Test di concorrenza e guasti su backend scelto |
| Port editor perde contenuti o non rispetta il lifecycle | Recupero circoscritto dal PoC nel framework attuale | Round-trip HTML/Markdown, binding, focus, cleanup e dipendenze |
| Template e Data incompatibili o markup inserito male | Schemi versionati e confine esplicito testo/HTML | Rendering di entrambi i motori, escaping, slot mancanti e diagnostica |
| LLM incontra funzioni disponibili solo nella UI | Catalogo condiviso, esposizione REST/MCP esplicita | Scenario completo sui tre canali, stessi esiti e autorizzazioni |
| Due autori o pubblicatori perdono aggiornamenti | Commit condizionato e idempotenza nel backend; coordinatore iniziale, transazioni nel futuro backend SQL | Corse a due client, retry dopo timeout, commit incerto |
| Build riprende dati correnti | Chiusura immutabile delle dipendenze | Ricostruzione con byte identici e confronto build completa/incrementale |
| Bozze/media privati raggiungibili | Gateway, namespace privati e grant | Accessi anonimi negati a HTML, asset e endpoint |
| Retention rompe rollback | Grafo delle dipendenze e protezione GC | Restore di release conservata dopo pulizia e backup |
| Retry invia notifiche doppie | Stato incerto e deduplicazione per evento | Prove provider-specifiche, senza promessa exactly-once |
| Cambiamenti dei framework invalidano la proposta | Provenienza dei sorgenti e qualifica di artefatti | Matrice di compatibilità eseguita nell'implementazione |

## Percorso del confronto

D1 è chiusa per il perimetro attuale: gestione comune di più siti, risorse di
sito o generiche e personalizzazione tramite copia indipendente. D2 è chiusa
nelle scelte di prodotto: persistenza in Genro Storage con versioning e
pubblicazione di release coerenti con rollback dell’insieme. D3 è chiusa nelle
scelte di prodotto: bozza condivisa, revisione preventiva configurabile e lingue
pubblicate indipendentemente. In D4 sono acquisiti i blocchi nominati HTML/Markdown
definiti dal template, la loro obbligatorietà configurabile e i componenti
Gramlot direttamente nella pagina, con iframe solo per isolamento. Affrontare
ora il contratto del backend iniziale filesystem/storage e i contratti tecnici
di D4 necessari a partire. L’integrazione Asqueel e i parametri operativi di D5
restano rinviati; i dettagli delle policy saranno definiti nelle rispettive fasi.

Dopo le decisioni si potranno formulare contratti implementativi, richieste ai
framework e una roadmap. Il catalogo ampio resta il riferimento; l'ordine di
realizzazione non deve trasformarsi retroattivamente in una riduzione del prodotto.
