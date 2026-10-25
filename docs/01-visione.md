# 01 · Visione e perimetro

Stato: proposta aggiornata il 21 ottobre 2026. Le richieste derivano dal
[prompt del proprietario](../PROMPT-PROGETTAZIONE.md) e dalle successive
[indicazioni acquisite](08-decisioni.md). I dettagli raccomandati restano da
discutere. Evidenze tecniche in [07](07-capacita-verificate.md).

## Prodotto

kajenn-press è un ambiente per ideare, organizzare, revisionare e pubblicare
conoscenza: siti istituzionali, riviste, documentazione, corsi e collezioni di
risorse. Un articolo è un oggetto editoriale con identità e storia; il sito
pubblico è una composizione deliberata di revisioni, navigazione, lingue e tema.

Il valore del prodotto sta nel governare questo percorso intero. La pubblicazione
deve permettere di sapere che cosa è online, chi lo ha pubblicato ed eventualmente approvato, quali materiali
lo compongono e come ritornare a una versione precedente.

## Richieste già espresse

| Richiesta | Conseguenza sul progetto |
|---|---|
| Modello ampio prima delle API | Articoli, pagine, corsi, media, tassonomie, workflow e release partecipano allo stesso dominio |
| HTML completo e SEO | Il testo editoriale è nel documento ricevuto; JavaScript arricchisce l'esperienza |
| Siti ospitati come applicazioni kajenn | Coesistenza con altre applicazioni e rispetto dei mount dell'host |
| Amministrazione Gramlot | Ripristino degli editor del PoC: HTML/Jodit, Markdown, CSS e JS; anteprima, metadati, allegati e storia |
| Template Gramlot o HtmlBuilder, contenuti in Data | Layout dichiarativi separati dai contenuti; preparazione della Data Bag e generazione statica di HTML completo |
| Genro Storage, S3 e versioning | Persistenza degli oggetti attraverso lo storage della famiglia, con cronologia editoriale esplicita |
| Backend iniziale filesystem/storage | Gestione completa senza database obbligatorio; contratti di persistenza separati dai servizi |
| Ruolo futuro di Asqueel | Backend alternativo per catalogo, relazioni, transizioni e ricerca; integrazione rinviata |
| REST/OpenAPI e MCP per pilotaggio LLM | Base `McpOpenApiApplication`, servizi condivisi e copertura delle funzioni editoriali, di costruzione del sito e operative |
| Componenti Gramlot pubblici e altri servizi | Contratti di incorporamento ed eventi; Telegram separato dal nucleo |
| Progettazione, senza implementazione | Documenti discutibili, nessuna API dichiarata approvata o migrazione avviata |

Hugo è un riferimento concettuale. Non si promettono compatibilità con temi,
shortcode, front matter o pipeline Hugo. Un eventuale importatore dichiarerà il
proprio sottoinsieme e segnalerà ciò che non può tradurre.

## Raccomandazione di insieme

Il perimetro stabilito è multisito: più siti gestiti da un unico amministratore
o team. Il multitenant per clienti indipendenti è rinviato. I siti mantengono
identità editoriali distinte; un sito può avere più domini e canali, per esempio
collaudo e produzione. Un processo kajenn non è l'identità del sito. Template,
CSS/JS e media possono essere specifici di sito oppure generici e riutilizzabili
fra i siti della gestione comune.

È acquisita una bozza condivisa per ogni contenuto e lingua, con rilevamento
dei conflitti tra modifiche concorrenti. Il modello prevede revisioni immutabili.
Chi ha il permesso può pubblicare direttamente; la revisione preventiva è
configurabile per sito. Quando richiesta, l'approvazione riguarda una revisione
precisa. Ogni lingua si pubblica quando è pronta, senza attendere le altre;
le versioni già pubblicate delle altre lingue possono rimanere online. È acquisita la pubblicazione per release:
ogni pubblicazione, anche di un solo articolo, identifica un insieme coerente
del sito e dei suoi artefatti, ripristinabile con rollback. La proposta tecnica
attiva la release modificando un unico puntatore del canale. Una pubblicazione può comprendere un corso intero, aggiornamenti di
menu e redirect, oltre a un articolo.

La persistenza di contenuti, template e risorse in Genro Storage è una scelta
acquisita, motivata anche dal versioning del backend.
Il backend iniziale su filesystem custodisce identità, relazioni operative,
permessi, workflow e puntatori; Genro Storage custodisce payload, media e manifest.
Gli indici del contenuto sono proiezioni ricostruibili. Asqueel/PostgreSQL potrà
sostituire il backend del catalogo dopo la definizione dell’integrazione, senza
cambiare il dominio o imporre modifiche ai client.
Il dettaglio dell'autorità è in [02](02-dominio.md).

## Esperienze che il modello deve sostenere

- Una redazione prepara un dossier multilingue, coordina traduzioni e revisori,
  controlla l'anteprima dell'intero sito e pubblica le varianti pronte, anche
  in momenti diversi.
- Un docente ordina lezioni e materiali, aggiorna una lezione senza cambiare
  identità ai riferimenti, mantiene scaricabili le risorse delle edizioni passate.
- Un responsabile corregge uno slug conservando i collegamenti tramite redirect,
  verifica canonical e sitemap e ripristina rapidamente una release.
- Un autore incorpora una simulazione Gramlot con spiegazione e risultati
  essenziali leggibili anche se il browser non attiva JavaScript.
- Un LLM autorizzato costruisce template, prepara contenuti e Data, modifica CSS/JS,
  legge la diagnostica, corregge e controlla l'anteprima tramite MCP o REST; può
  pubblicare e ripristinare release quando i grant assegnati lo consentono.
- Un bot notifica l'esito della revisione usando il proprio ambito di accesso.

## Perimetro e confini

Sono nel prodotto il dominio editoriale, i workflow configurabili, la gestione
multilingue, i media, il rendering, le anteprime, i temi, le funzioni di gestione,
gli eventi e gli strumenti operativi di recupero. Sono comprese la costruzione
e la manutenzione di template Gramlot/HtmlBuilder, dei mapping Data e degli asset
CSS/JS; le operazioni applicative devono essere disponibili anche ai client LLM.

Identità di base, trasporto, mount e worker appartengono a kajenn; accesso agli
oggetti a Genro Storage; futuro modello SQL e transazioni ad Asqueel; binding e componenti
riusabili a Gramlot. Le estensioni necessarie vanno risolte nei rispettivi
framework: il prodotto non introduce surrogati silenziosi.

DNS, certificati, bucket, CDN e segreti sono responsabilità del deployment.
Il prodotto registra e verifica i collegamenti, ma crearli non è un effetto
implicito del comando «crea sito». Commenti dei lettori, commercio, avanzamento
degli studenti e account pubblici possono integrare il sito come applicazioni
separate; non diventano automaticamente responsabilità del nucleo editoriale.

## Criteri di riuscita del progetto

Il modello deve consentire pubblicazioni riproducibili, recupero dagli errori
parziali, assenza di sovrascritture silenziose, separazione delle bozze dal pubblico
e identiche autorizzazioni sui tre canali di gestione. Deve poter esportare un
sito senza dipendere dai nomi dei bucket o dagli ID assegnati da S3.

Non sono promesse prestazioni, tempi di conservazione o disponibilità misurati.
Le garanzie richieste e le verifiche che dovranno dimostrarle sono esplicite in
[06](06-storage-consistenza.md) e [08](08-decisioni.md).
