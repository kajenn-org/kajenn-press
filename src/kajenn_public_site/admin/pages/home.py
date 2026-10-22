"""Operator orientation, shown on entry and retained in the Gallery navigation."""

from kajenn_public_site.admin.host import CURRENT_REQUEST
from kajenn_public_site.admin.views import AdminPage


class Page(AdminPage):
    title = "Home · Come funziona"

    async def main(self, root):  # wf:phase-1:new
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        home = root.main(class_="guide")
        hero = home.header(class_="guide-hero")
        hero.p("LA TUA REDAZIONE MULTISITO", class_="guide-eyebrow")
        hero.h1("Più siti, un unico spazio di lavoro.")
        hero.p(
            "Kajenn public site ti aiuta a organizzare pagine, lingue e risorse dei tuoi siti. "
            "Il team prepara i contenuti nell’amministrazione; il sito pubblico mostra "
            "le pagine HTML generate dall’ultima pubblicazione.",
            class_="guide-lead",
        )
        status = home.aside(class_="guide-status", aria_label="Stato dell’amministrazione")
        status.strong("Cosa puoi fare oggi")
        status.p(
            "Creare un sito, consultare contenuti e varianti linguistiche, esplorare risorse, "
            "sorgenti e revisioni. Gli editor e i comandi di pubblicazione nell’interfaccia "
            "arriveranno nelle prossime fasi: le schede attuali sono in consultazione."
        )
        start = home.section(class_="guide-section")
        start.h2("Da dove cominciare")
        steps = start.ol(class_="guide-steps")
        for title, text in (
            (
                "Scegli un sito",
                (
                    "Usa il selettore nella barra superiore. Se devi iniziare "
                    "un nuovo progetto, scegli «Nuovo sito» e indica nome e lingue. Il comando "
                    "è disponibile con i permessi necessari."
                ),
            ),
            (
                "Apri Contenuti",
                (
                    "Nell’albero a sinistra, apri Contenuti sotto il nome del sito. "
                    "Seleziona una pagina nell’elenco, poi una lingua per consultarne i blocchi."
                ),
            ),
            (
                "Esplora Risorse e Libreria",
                (
                    "Risorse raccoglie gli elementi del sito scelto; "
                    "la Libreria condivisa raccoglie quelli riutilizzabili tra più siti."
                ),
            ),
        ):
            item = steps.li()
            item.h3(title)
            item.p(text)
        start.p(
            "Ogni voce apre una scheda. Puoi tenere aperti più siti: cambiare il selettore "
            "aggiorna l’albero, mentre le schede già aperte restano legate al loro sito. "
            "Il titolo della scheda indica sempre a quale sito appartiene.",
            class_="guide-tip",
        )
        concepts = home.section(class_="guide-section")
        concepts.h2("Come sono organizzate le pagine")
        grid = concepts.div(class_="guide-grid")
        for title, text in (
            (
                "Sito",
                (
                    "È il progetto che contiene le sue pagine, lingue e risorse. "
                    "Uno stesso amministratore o team può gestirne più di uno."
                ),
            ),
            (
                "Contenuto e lingue",
                (
                    "Un contenuto identifica una pagina, per esempio «Chi siamo». "
                    "Le varianti italiana e inglese hanno testi e percorsi propri. "
                    "Ogni lingua può essere pubblicata quando è pronta."
                ),
            ),
            (
                "Template",
                (
                    "Definisce la struttura della pagina e i blocchi richiesti, "
                    "per esempio introduzione e corpo. Può essere realizzato con Gramlot "
                    "o HtmlBuilder e viene renderizzato in HTML statico."
                ),
            ),
            (
                "Blocchi in Data",
                (
                    "I testi restano separati dal template: ogni variante "
                    "riempie i blocchi nominati con HTML o Markdown. Il Markdown può includere HTML; "
                    "il markup viene filtrato per la pagina senza cambiare il sorgente salvato."
                ),
            ),
            (
                "Risorse e Libreria",
                (
                    "Template, CSS, JavaScript e media possono appartenere "
                    "a un sito oppure alla Libreria condivisa. Una copia nel sito è indipendente "
                    "dall’originale: modificarla non cambia gli altri siti."
                ),
            ),
            (
                "Revisioni",
                (
                    "I salvataggi conservano la storia delle modifiche. "
                    "Il dettaglio permette di consultare informazioni, sorgente e revisioni. "
                    "Una build usa revisioni precise, così il risultato è riproducibile."
                ),
            ),
        ):
            card = grid.article(class_="guide-card")
            card.h3(title)
            card.p(text)
        example = home.section(class_="guide-example")
        example.h2("Un esempio: la pagina «Chi siamo»")
        example.p(
            "Il template «Pagina istituzionale» definisce due blocchi: introduzione e corpo. "
            "La variante italiana contiene i testi per /it/chi-siamo/; quella inglese "
            "contiene i testi per /en/about/. Usano la stessa struttura, ma mantengono "
            "contenuti indipendenti. Puoi pubblicare l’italiano e completare l’inglese più tardi."
        )
        publication = home.section(class_="guide-section")
        publication.h2("Dal contenuto al sito pubblico")
        publication.p(
            "Questo è il percorso previsto. I servizi di build e pubblicazione esistono già; "
            "i relativi comandi saranno aggiunti all’amministrazione nella fase dedicata."
        )
        flow = publication.ol(class_="guide-flow")
        for title, text in (
            ("Salva", "Conserva una nuova revisione. Salvare non modifica il sito pubblico."),
            (
                "Genera",
                "La build combina template, blocchi e risorse per creare le pagine statiche.",
            ),
            ("Controlla", "L’anteprima mostra la build tramite un link temporaneo e revocabile."),
            (
                "Pubblica",
                (
                    "L’attivazione rende visibile la release. Il rollback riattiva "
                    "una release precedente, se necessario."
                ),
            ),
        ):
            item = flow.li()
            item.h3(title)
            item.p(text)
        llm = home.section(class_="guide-section guide-llm")
        llm.h2("Puoi lavorare anche con un assistente AI")
        llm.p(
            "Un LLM collegato alle API MCP/OpenAPI di Kajenn può ricevere comandi per creare "
            "siti, contenuti e varianti linguistiche, usando gli stessi servizi "
            "dell’amministrazione. Per usarlo occorre un collegamento autorizzato: "
            "l’assistente agisce con i permessi assegnati alla sua identità."
        )
        llm.blockquote(
            "«Nel sito Kajenn crea la pagina Chi siamo in italiano, usando il template "
            "Pagina istituzionale, e prepara i blocchi introduzione e corpo.»"
        )
        llm.p(
            "Se un riferimento è ambiguo, l’assistente deve prima individuare il sito "
            "e la revisione del template corretti. Creare o modificare un contenuto "
            "tramite MCP non lo pubblica automaticamente.",
            class_="muted",
        )
