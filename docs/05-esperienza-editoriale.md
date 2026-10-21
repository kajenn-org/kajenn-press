# 05 · Esperienza editoriale Gramlot

Stato: proposta UX e contratto dei contenuti; nessun componente nuovo è stato
implementato. Le capacità Gramlot realmente osservate sono in
[07](07-capacita-verificate.md).

## Ambiente di lavoro

L'ingresso è una panoramica del sito: contenuti in lavorazione, revisioni da
valutare, traduzioni superate, build fallite e release attiva per canale. Il sito
e il canale sono sempre visibili. Le azioni mostrate dipendono dai permessi,
verificati nuovamente sul server.

L'elenco permette ricerca per testo/titolo, tipo, lingua, autore, tassonomie,
assegnazione e presenza nella release attiva. Mostra separatamente bozza,
revisione approvata e versione pubblicata. Filtri salvati e operazioni collettive
usano la stessa logica applicativa, con risultati per elemento; non si nascondono
successi parziali.

La scheda contenuto propone:

- Elenco dei blocchi nominati definiti dal template e area centrale con editor
  HTML/Jodit o Markdown secondo il formato del blocco selezionato, comandi di
  inserimento e stato del salvataggio.
- Pannello per titolo, sommario, tipo, slug, autore, lingua e classificazioni.
- Schede dedicate a SEO, risorse, riferimenti in ingresso/uscita e traduzioni.
- Anteprima affiancata o a pieno schermo, con viewport desktop e mobile.
- Cronologia e confronto, commenti di revisione e percorso verso la pubblicazione.

Layout responsive, navigazione da tastiera, focus preservato fra pannelli e
annunci accessibili sul salvataggio fanno parte dell'esperienza. Un utente senza
permesso di pubblicazione può comunque vedere dove il proprio lavoro è usato.

## Editor e autosalvataggio

La direzione è ripristinare gli editor già presenti nel PoC mediante componenti
Gramlot riusabili, con binding Source/Data, validazione e lifecycle nativi.
Le basi osservate sono HTML con Jodit, Markdown con ProseMirror e CodeMirror
per sorgenti, inclusi CSS e JavaScript; il loader comprende anche Python.
Non si considera il PoC un runtime già integrato nel core attuale.

Il port deve conservare editing visuale/sorgente dove previsto, selezione,
undo/redo, focus e teardown. Per il prodotto servono inoltre riferimenti interni,
media, blocchi e diagnostica posizionale. Occorre qualificare il round-trip: il
PoC Markdown tratta alcuni costrutti come blocchi raw e il suo profilo non
costituisce automaticamente il parser di pubblicazione. `textBoxArea` non
sostituisce il ripristino di questi editor.

Il buffer può contenere testo o metadati momentaneamente invalidi. La UI non li
perde, ma non dichiara salvato uno snapshot che il server ha rifiutato. Si devono
distinguere «modifiche locali», «salvataggio in corso», «salvato» e «conflitto».
Una bozza può essere incompleta per la pubblicazione; il salvataggio richiede
comunque un formato serializzabile e riferimenti interpretabili. Il template
indica i blocchi obbligatori e facoltativi: quelli obbligatori mancanti o vuoti
sono segnalati senza impedire il salvataggio della bozza, ma bloccano la
pubblicazione della variante. Un blocco facoltativo vuoto non è un errore.

Autosalvataggio dopo inattività e prima del cambio contenuto, con richieste
ordinate e numero di generazione. Il client non invia una nuova testa sulla base
di una precedente richiesta ancora incerta. Alla riconnessione interroga l'esito
idempotente e offre recupero del buffer. Un eventuale recupero locale persistente
deve essere deciso considerando computer condivisi e riservatezza.

Se un altro autore ha modificato la bozza, confronto a tre vie: base letta,
versione locale, versione corrente. Testo, campi e riferimenti sono confrontati
separatamente; i conflitti semantici richiedono scelta esplicita. Il risultato è
un nuovo snapshot con nuova generazione attesa. Presenza e avvisi di modifica
contemporanea sono utili; non costituiscono collaborazione CRDT già disponibile.

## Ambiente per template, Data, CSS e JS

Il progettista dispone di un albero delle risorse e schede per i template
Python Gramlot/HtmlBuilder, CSS, JS e contenuti HTML/Markdown. La scelta del motore
è esplicita per template. Il template dichiara i blocchi nominati in Data;
l’editor presenta questi blocchi e ne modifica i valori senza ridefinirne il
layout. Il pannello Data mostra schema, mapping, slot e valori
risolti su una revisione di esempio; per cambiare un valore derivato rimanda al
contenuto sorgente, evitando una seconda copia modificabile.

Anteprima statica e diagnostica usano la pipeline della build. Un errore porta
al file, al blocco o al percorso Data coinvolto. Il confronto mostra sorgenti e
pagine interessate; una modifica coordinata di template, mapping e CSS può
essere finalizzata come insieme coerente. Autosalvataggio e conflitti seguono
le stesse regole dei contenuti.

Il client LLM accede agli stessi servizi per leggere, modificare e controllare
questi materiali; la UI mostra le revisioni risultanti e la loro attribuzione
nel normale audit. Le operazioni non dipendono dall'automazione del browser.

## Risorse e metadati

Il selettore media mostra anteprima, diritti, stato di verifica, lingue e usi.
Trascinare un file avvia upload privato, controlli e finalizzazione. Solo una
MediaRevision verificata è inseribile in una revisione pronta alla pubblicazione.
Un derivato in elaborazione ha stato esplicito.

Alt text e didascalia sono proprietà dell'uso nel contesto; il copyright generale
è della revisione media. Sostituire un file crea una nuova revisione e propone
quali usi aggiornare. Video e audio possono avere trascrizione, sottotitoli,
poster e capitoli come risorse versionate collegate.

Il pannello SEO distingue testo editoriale e override intenzionali. Mostra URL
previsto, canonical, social card e traduzioni collegate; segnala slug in conflitto,
descrizioni mancanti e riferimenti rotti. Il cambio slug propone un redirect,
la cui attivazione avviene con la release.

## Revisione e pubblicazione

Il confronto evidenzia testo, metadati, media e componenti; un cambiamento di tema
o menu è visibile nel confronto di release. I commenti hanno ancore su revisione
e intervallo/blocco; se il testo cambia, l'ancora può essere «superata», senza
spostarla silenziosamente.

Il revisore vede esattamente la revisione richiesta e la sua anteprima. Approva,
rifiuta o chiede modifiche con motivazione. Una nuova bozza non altera ciò che
ha appena valutato.

Il pubblicatore compone il candidato e vede aggiunte/rimozioni, URL, redirect,
lingue escluse e cambiamenti globali. Prima dell'attivazione controlla l'anteprima
di sito e il rapporto di build. L'esito distingue release pronta, attiva
all'origine, eventuale propagazione e fallimento. La vista rollback mostra
chiaramente l'edizione di destinazione e le modifiche che tornerebbero online.

## HTML, Markdown e componenti

Raccomandazione: profilo Markdown versionato, basato su
[CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/), con estensioni esplicite
per tabelle, note e blocchi. La scelta della libreria di parsing resta aperta.
La base CommonMark non rende automaticamente sicuri HTML e URL: occorrono regole
del prodotto, sanitizzazione e prove sui renderer.

Ogni blocco ha un formato canonico dichiarato: HTML per l'editing Jodit oppure
Markdown per il relativo editor. Non si mantengono due copie modificabili dello
stesso blocco. Entrambi producono frammenti HTML preparati, inseriti nella Data
Bag del template insieme a metadati e dati strutturati. Il sorgente rimane
conservato; il derivato registra profilo di trasformazione/sanitizzazione e hash.
I campi editoriali vivono nel manifest, non in un secondo front matter
modificabile. Un'esportazione con front matter può essere generata dal manifest;
l'import riconcilia i campi e respinge le ambiguità.

CSS e JS appartengono a risorse dedicate del sito modificabili con gli editor di
codice e via API. Il contenuto HTML redazionale segue una policy esplicita per
elementi, attributi e URL; non diventa un canale implicito per script. I template
inseriscono soltanto i frammenti preparati nei punti previsti dal contratto Data,
mantenendo l'escaping del testo ordinario.

Per i blocchi Markdown, sintassi proposta per un riferimento interno: `[Introduzione](content:ID)`,
risolta in base al sito e alla lingua del candidato. Un selettore può richiedere
una lingua esplicita; manca una traduzione → diagnostica e fallback deciso,
mai traduzione inventata. Gli anchor stabili sono parte dell'indice di revisione.

Sintassi illustrativa di blocco, da approvare prima di definirne il parser:

````text
```public-site-component
{
  "instance_id": "esempio-prezzo",
  "type": "calcolatore",
  "schema_version": 1,
  "props": {"valore_iniziale": 100},
  "fallback": {
    "kind": "markdown",
    "text": "Con il valore iniziale di 100, il risultato dell'esempio è 120."
  }
}
```
````

`public-site-component` è una proposta del prodotto, non una sintassi Gramlot esistente.
L'istanza seleziona una definizione registrata e versionata; non contiene import,
codice Python/JS, URL arbitrari di moduli o espressioni eseguibili. Le proprietà
sono validate contro lo schema. I riferimenti ai media usano ID e revisione;
nessun segreto viene serializzato. L'ID del blocco resta stabile durante l'editing
per commenti e diff.

Il fallback è obbligatorio per i blocchi che comunicano informazione essenziale.
Il renderer lo trasforma in HTML semantico ordinario nel corpo della pagina,
visibile anche senza script. Non basta un elemento custom vuoto o testo dentro
unicamente a `noscript`. La regione interattiva ha un contenitore distinto,
titolo accessibile e contratto che evita letture duplicate dopo l'attivazione.
Errori di JS lasciano utilizzabile il contenuto statico.

Per grafici o simulazioni il fallback include spiegazione, ipotesi e dati/risultato
di riferimento. Per azioni che richiedono il server, esplicita cosa è disponibile
solo interattivamente. I dati statici del fallback sono congelati; eventuali dati
live sono chiaramente etichettati e non cambiano le affermazioni editoriali.

Per HTML/Jodit va definito e qualificato un segnaposto che preservi ID, proprietà
e riferimenti dei componenti durante il round-trip visuale/sorgente; il formato
non è ancora approvato. La sintassi Markdown sopra non si trasferisce
automaticamente all'HTML.

La UI offre una maschera delle proprietà e una rappresentazione del blocco nel
testo; entrambe modificano la stessa struttura serializzata, senza copie
indipendenti. Anteprima ed export impiegano lo stesso parser. Nell'export Markdown
generico i blocchi diventano fallback leggibili con una nota di provenienza;
l'archivio completo conserva anche la definizione strutturata.

## Confini Gramlot da rispettare

Il core corrente contiene binding, controlli, componenti, layout e renderer HTML;
l'adapter kajenn gestisce il protocollo delle pagine. La connessione degli editor
specializzati a Data, selezione, focus, validazione e teardown richiede un
contratto di framework, non DOM manuale nella pagina redazionale.

È acquisita l’integrazione delle regioni Gramlot direttamente nella pagina;
si usano iframe solo quando serve isolamento. Restano da definire e qualificare
bootstrap, isolamento degli scope Data, più istanze nella pagina, collezioni
condivise, cleanup, autenticazione e fallback. La presenza di un renderer non
dimostra hydration delle sue uscite. L’integrazione nello stesso documento
richiede qualifica del lifecycle. Il ripristino degli editor recupera
il lavoro del PoC con port circoscritti nel framework attuale e verifica delle
dipendenze e dei contratti; non presuppone compatibilità integrale dei runtime.

Un form amministrativo costruito con Gramlot non implica persistenza automatica
Asqueel: caricamento, salvataggio, errori e permessi passano dai servizi editoriali.
Campi `readonly` e controlli nascosti non sono autorizzazione.
