# kajenn-public-site

Proposta di piattaforma editoriale e pubblicazione di siti della famiglia Genro.
**Stato al 21 ottobre 2026: progettazione aggiornata alle indicazioni del proprietario, nessuna implementazione.**

La proposta separa identità dei contenuti, revisioni editoriali immutabili e
release pubblicate. Si parte con un backend su filesystem per catalogo e stato
operativo e Genro Storage per contenuti e artefatti, senza dipendenza da un
database. Asqueel/PostgreSQL resta un futuro backend da integrare. kajenn ospita
applicazione e servizi; Gramlot offre
l'ambiente di gestione e le interazioni nelle pagine pubbliche.

La direzione stabilita prevede template Gramlot oppure HtmlBuilder, rendering
statico con contenuti nella Data Bag e ripristino degli editor del PoC per HTML
(Jodit), Markdown, CSS e JavaScript. MCP e REST/OpenAPI devono consentire a un LLM
autorizzato di governare il ciclo completo, dalla costruzione del sito alla
pubblicazione, attraverso gli stessi servizi usati dalla UI.

## Percorso di lettura

| Documento | Contenuto |
|---|---|
| [01 · Visione e perimetro](docs/01-visione.md) | Richieste del proprietario, proposta di prodotto, confini |
| [02 · Modello di dominio](docs/02-dominio.md) | Entità, relazioni, identità, invarianti e autorità dei dati |
| [03 · Architettura e flussi](docs/03-architettura.md) | Editing, revisione, build, serving, pubblicazione e integrazioni |
| [04 · Funzioni esposte](docs/04-funzioni.md) | Catalogo concettuale condiviso da Gramlot, REST e MCP |
| [05 · Esperienza editoriale](docs/05-esperienza-editoriale.md) | Editor del PoC, template, Data, risorse, anteprima e workflow |
| [06 · Storage e consistenza](docs/06-storage-consistenza.md) | Versioni, manifest, concorrenza, retry e recupero |
| [07 · Capacità verificate](docs/07-capacita-verificate.md) | Evidenze locali, limiti e responsabilità delle estensioni |
| [08 · Decisioni aperte](docs/08-decisioni.md) | Direzione acquisita e scelte strutturali ancora aperte |
| [09 · Fonti e verifica](docs/09-fonti.md) | Sorgenti consultati, versioni, fonti esterne e limiti della verifica |

Per iniziare il confronto: leggere 01, 02 e 08. Il catalogo delle funzioni viene
dopo il modello: nomi, schemi e raccomandazioni non sono API approvate.

Il [prompt di progettazione](PROMPT-PROGETTAZIONE.md) è corretto nella nomenclatura; le successive
indicazioni del proprietario sono registrate in [08](docs/08-decisioni.md).
Il nome del progetto e del repository è `kajenn-public-site`.

## Confini della sessione

Sono stati esaminati codice e documentazione locali, distinguendo sorgenti in
lavorazione e release dichiarate. La verifica è statica: non certifica
l'integrazione eseguita, un bucket S3 o un ambiente di produzione.

Non sono stati creati codice applicativo, migrazioni, dipendenze, commit, remote
o deployment. I siti Gramlot e Asqueel continuano con i propri strumenti.
Una roadmap implementativa seguirà la discussione, senza restringere questa
visione a un MVP.
