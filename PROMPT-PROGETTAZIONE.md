# Prompt per la prossima sessione — kajenn-public-site

Lavora nel repository `/Users/gporcari/Sviluppo/kajenn/kajenn-public-site`.
L'obiettivo di questa sessione è progettare in modo ambizioso una piattaforma
editoriale e di pubblicazione nativa della famiglia Genro. Il nome di lavoro è
**kajenn-public-site**. Il repository è stato inizializzato localmente; non contiene
ancora un'applicazione, commit o un remote.

## Direzione del proprietario

Prima identifichiamo un modello di dominio ampio e coerente, poi le funzioni che
esponiamo e l'esperienza di gestione. Non partire da un MVP, da un semplice server
di file o da due endpoint «pubblica/non pubblicare»: erano esempi, non un contratto.
Non iniziare l'implementazione durante questa sessione di progettazione.

Hugo è un riferimento concettuale per contenuti, metadati, template e generazione
di siti statici. Il sito genropy.org usa Hugo. Non serve riprodurne ogni funzione
o assumere compatibilità con i suoi temi: dobbiamo progettare il nostro modello,
con Kajenn, Gramlot, Asqueel e gli altri servizi della famiglia.

Vogliamo:

- Servire HTML completo e semanticamente significativo, leggibile dai motori di
  ricerca senza dipendere dall'esecuzione di JavaScript per il contenuto editoriale.
- Gestire SEO, URL, metadati, sitemap, canonical, lingue e dati strutturati.
- Ospitare siti come applicazioni Kajenn, accanto ad altre applicazioni montate
  sullo stesso server.
- Usare Gramlot per l'amministrazione e la gestione degli articoli, con editor
  Markdown, anteprima, metadati, allegati e cronologia delle revisioni.
- Salvare contenuti e risorse attraverso Genro Storage, con S3 e versioning degli
  articoli come direzione richiesta. Verificare quali capacità sono già disponibili.
- Integrare componenti interattivi Gramlot nelle pagine pubbliche.
- Progettare il ruolo di Asqueel nella persistenza dei dati strutturati.
- Esporre funzioni di gestione attraverso MCP e REST/OpenAPI, basandoci su
  `McpOpenApiApplication` di Kajenn.
- Integrare altri servizi della famiglia, inclusi bot Telegram, senza accoppiarli
  al nucleo editoriale.

## Metodo di lavoro

Leggi le istruzioni dei repository coinvolti e verifica il codice e la
documentazione attuali prima di dichiarare esistente una funzione. Mantieni
separati: capacità già implementate, estensioni necessarie e proposte progettuali.
Non inventare API dei framework o adattatori che nascondano lacune del framework.

Prepara una proposta concreta e ragionata prima di chiedere decisioni al
proprietario. Distingui raccomandazioni da decisioni già concordate; evidenzia
poche scelte davvero strutturali. La progettazione deve poter essere discussa,
non trasformarsi automaticamente in un contratto implementativo.

## Materiale locale da consultare

- Kajenn: `/Users/gporcari/Sviluppo/kajenn/kajenn`.
  In particolare applicazioni, mounting, `McpOpenApiApplication`, routing,
  autorizzazioni, configurazione, storage e gestione dei job, se presente.
- Asqueel: `/Users/gporcari/Sviluppo/asqueel/asqueel`.
- Gramlot: cerca il repository del framework sotto
  `/Users/gporcari/Sviluppo/gramlot`; distingui sorgenti locali e release pubbliche.
- Sito Gramlot: `/Users/gporcari/Sviluppo/gramlot/gramlot-site`.
  Il sito attuale è in `welcome/`, generato da `scripts/build-welcome.py` e
  verificato da `scripts/check-welcome.py`. Non usare come riferimento attuale
  il vecchio PoC e non modificare direttamente `dist-welcome/`.
- Sito Asqueel: `/Users/gporcari/Sviluppo/asqueel-site`.
- Esempio di applicazione Kajenn separata:
  `/Users/gporcari/Sviluppo/kajenn/kajenn-mail-proxy`.
- Individua Genro Storage e le integrazioni Telegram disponibili tramite
  dipendenze e documentazione; non presumerne percorsi o funzioni.

Le anteprime dei siti sono state servite su porte 8242 e 8056; potrebbero non
essere ancora attive. Non sono un requisito per progettare la nuova piattaforma.

## 1. Modello di dominio prima delle API

Proponi entità, responsabilità, relazioni, identificatori e invarianti. Considera:

- Siti, domini, lingue, ambienti e configurazione; valuta il rapporto tra sito,
  istanza Kajenn e gestione di più siti.
- Tipi di contenuto, articoli, pagine, serie/corsi/lezioni, tassonomie, menu,
  riferimenti interni, slug e redirect.
- Identità stabile del contenuto, varianti linguistiche, bozze di lavoro,
  revisioni immutabili, autori, revisori e workflow editoriale.
- Media e allegati con metadati, varianti, riferimenti e ciclo di vita.
- Temi, layout, template, blocchi e componenti Gramlot incorporabili.
- Anteprime, compilazioni, artefatti, release del sito e pubblicazione.
- Ruoli, permessi, audit, eventi, job e integrazioni.

Spiega quali informazioni sono autorevoli in Asqueel e quali nello storage.
Evita copie modificabili indipendentemente dello stesso contenuto. Considera
importazione/esportazione e portabilità, senza imporre compatibilità Hugo.

## 2. Versioni, storage e consistenza

Distingui esplicitamente revisione editoriale, versione dell'oggetto S3 e release
pubblicata: sono concetti diversi. Il versioning S3 da solo non costituisce una
cronologia editoriale completa.

Proponi come legare testo Markdown, metadati, media e configurazione necessaria
al rendering a revisioni riproducibili. Valuta oggetti immutabili, manifest,
checksum propri e uso dei VersionId S3. Verifica letture di versioni specifiche,
scritture condizionali, URL temporanei e politiche di conservazione nel backend
e nell'interfaccia effettiva di Genro Storage.

Tratta autosalvataggio, modifiche concorrenti, conflitti, ripristino di revisioni,
rollback della pubblicazione, eliminazione e recupero. Non assumere una transazione
unica tra database e S3: descrivi consistenza, idempotenza, retry e recupero di
scritture parziali o oggetti orfani. Non usare l'ETag come checksum universale.

## 3. Esperienza editoriale Gramlot

Descrivi l'esperienza completa: elenco e ricerca, editor Markdown, risorse,
metadati e SEO, anteprima fedele, revisioni e confronto, revisione editoriale e
pubblicazione. Chiarisci dove servono componenti nuovi o integrazioni con editor
specializzati: un editor Markdown completo non è stato verificato come componente
nativo Gramlot.

Definisci il rapporto fra Markdown e blocchi interattivi: sintassi, proprietà,
validazione, anteprima e comportamento dell'HTML statico. Il contenuto essenziale
deve rimanere leggibile anche senza l'attivazione dei componenti nel browser.

## 4. Catalogo delle funzioni esposte

Solo dopo il modello, organizza le operazioni per dominio: siti, contenuti,
revisioni, risorse, workflow, anteprima, build, pubblicazione e integrazioni.
Per ogni famiglia indica attore, scopo, input/output concettuali, permessi,
effetti, precondizioni, conflitti e comportamento sincrono o asincrono.

Proponi un unico livello applicativo condiviso da interfaccia Gramlot, REST e
MCP. I nomi delle operazioni sono proposte da discutere, non API già approvate.
Distingui letture, modifiche editoriali e attivazione pubblica di una release.

## 5. Rendering, pubblicazione e integrazioni

Descrivi il percorso dal contenuto al sito servito: risoluzione delle route,
rendering HTML, asset, link, SEO, build completa o incrementale, anteprima,
attivazione coerente della release e rollback. Valuta cosa generare prima e cosa
eseguire a richiesta. Bozze e anteprime non devono diventare pubbliche per errore.

Chiarisci i confini tra applicazione, Kajenn host, storage, cache/CDN e servizi
esterni. Per Telegram e altre integrazioni proponi eventi, notifiche e possibili
comandi autenticati, verificando cosa esiste già. Non inviare messaggi né
configurare servizi durante la progettazione.

## Risultati della sessione

Salva in questo repository documenti leggibili con:

1. Visione e perimetro del prodotto, distinguendo richieste e proposte.
2. Modello di dominio con relazioni e invarianti; diagrammi dove utili.
3. Architettura e flussi di editing, revisione, build e pubblicazione.
4. Catalogo delle funzioni esposte.
5. Esperienza editoriale Gramlot e strategia Markdown/componenti.
6. Contratto concettuale di storage e versioning, consistenza e recupero.
7. Mappa delle capacità verificate nei framework e delle estensioni necessarie.
8. Decisioni aperte, alternative e raccomandazioni motivate.

Aggiorna il README per orientare tra i documenti. Rispondi in italiano; i documenti
di progettazione possono essere in italiano per facilitare il confronto con il
proprietario. Usa fonti primarie per le caratteristiche esterne e registra quali
versioni o sorgenti hai verificato.

Non creare codice applicativo, migrazioni, dipendenze, commit, repository remoto
o deployment in questa sessione. Non modificare i siti esistenti: per il momento
continuano a funzionare con il sistema attuale. Una roadmap implementativa potrà
seguire la discussione del modello, senza ridimensionare in anticipo la visione.
