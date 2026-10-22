"""Multisite browsing through Gramlot Source and request-authorized service reads."""

import asyncio
import json
from uuid import uuid4

from gramlot import Page as GramlotPage
from gramlot import endpoint, source

from kajenn_public_site.admin.host import CURRENT_REQUEST, execute_read
from kajenn_public_site.domain import DomainError

SECTIONS = {"content": "Contenuti", "resource": "Risorse", "library": "Libreria"}
KINDS = {
    "content": {"content", "variant"},
    "resource": {"template", "css", "javascript", "media"},
    "library": {"template", "css", "javascript", "media"},
}


def caption(record):  # wf:phase-1:new
    attrs = record["attributes"]
    return attrs.get("title") or attrs.get("name") or attrs.get("language") or record["record_id"]


def literal_text(pane, tag, text, **attributes):  # wf:phase-1:new
    """Saved text is Data, never a Source expression (even when it starts with == or ^)."""
    path = "display_text." + uuid4().hex
    pane.dataSetter(path, text)
    return getattr(pane, tag)("^" + path, **attributes)


class AdminPage(GramlotPage):
    css = ("/index.css",)

    async def scope_records(self, site, section):  # wf:phase-1:new
        if section not in KINDS:
            raise DomainError("invalid_input", "Sezione non disponibile")
        scope = "library" if section == "library" else "site:" + site
        records = await execute_read("records_index", scope=scope)
        return scope, [r for r in records if r["kind"] in KINDS[section]]

    @source(auth="editor")
    async def permissions(self, pane, site="", section="content"):  # wf:phase-1:new
        try:
            scope = "library" if section == "library" else "site:" + site
            rights = await execute_read("scope_capabilities", scope=scope)
            labels = {
                "read": "Lettura",
                "write": "Scrittura",
                "use": "Utilizzo",
                "build": "Build",
                "preview_grant": "Anteprima",
                "publish": "Pubblicazione",
            }
            pane.p("Permessi nell’ambito corrente")
            pane.span(" · ".join(labels[k] for k in rights["permissions"]))
        except DomainError:
            pane.span("Ambito non accessibile")

    @source(auth="editor")
    async def workspace(
        self, pane, site="", section="content", search="", refresh=0
    ):  # wf:phase-1:new
        try:
            _scope, records = await self.scope_records(site, section)
            site_label = (
                "Libreria condivisa"
                if section == "library"
                else (await execute_read("record_read", record_id=site))["attributes"]["name"]
            )
            literal_text(pane, "p", site_label, class_="breadcrumb")
            heading = pane.div(class_="heading")
            heading.h1("Libreria condivisa" if section == "library" else SECTIONS[section])
            heading.span("Consultazione", class_="status")
            visible = [
                r
                for r in records
                if r["kind"] != "variant" and (search or "").casefold() in caption(r).casefold()
            ]
            layout = pane.div(class_="workspace")
            listing = layout.section(class_="record-list", aria_label="Elenco")
            listing.div("Titolo / ultima revisione", class_="list-heading")
            if not visible:
                listing.p("Nessun elemento disponibile.", class_="empty")
            for record in visible:
                button = listing.button(class_="record-row")
                literal_text(button, "strong", caption(record))
                language = " · ".join(
                    r["attributes"]["language"]
                    for r in records
                    if r["kind"] == "variant"
                    and r["attributes"]["content_id"] == record["record_id"]
                )
                button.span(language or record["kind"], class_="muted")
                button.small(f"Revisione {record['generation']}")
                button.dataController(
                    "this.SET('admin.selected', record); this.SET('admin.revision','');",
                    record=record["record_id"],
                )
            layout.section(class_="record-detail", aria_label="Dettaglio selezionato").remote(
                "detail",
                site=site,
                section=section,
                selected="^admin.selected",
                fallback=visible[0]["record_id"] if visible else "",
                revision="^admin.revision",
                _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
            )
        except DomainError as error:
            pane.h1("Ambito non disponibile")
            pane.p(str(error), role="status")

    @source(auth="editor")
    async def detail(
        self, pane, site="", section="content", selected="", fallback="", revision=""
    ):  # wf:phase-1:new
        try:
            scope, records = await self.scope_records(site, section)
            record_id = selected or fallback
            allowed = {r["record_id"] for r in records}
            if not record_id:
                pane.p("Seleziona un elemento.")
                return
            if record_id not in allowed:
                raise DomainError("not_found", "Selezione non disponibile in questo ambito")
            record = await execute_read(
                "record_read", record_id=record_id, revision_id=revision or None
            )
            history = await execute_read("revision_index", record_id=record_id)
            pane.span("Sola lettura", class_="status")
            literal_text(pane, "h2", caption(record))
            tabs = pane.tabContainer(selectedPage="^admin.tab", height="420px")
            info = tabs.contentPane(title="Informazioni", pageName="info", padding="12px")
            attributes = info.dl()
            for label, value in [
                ("Ambito", "Libreria condivisa" if scope == "library" else "Sito corrente"),
                ("Identificativo", record_id),
                ("Revisione", record["revision_id"]),
                ("Generazione", str(record["generation"])),
            ]:
                attributes.dt(label)
                attributes.dd(value)
            if record["kind"] == "content":
                info.h3("Varianti linguistiche")
                for variant in records:
                    if (
                        variant["kind"] == "variant"
                        and variant["attributes"]["content_id"] == record_id
                    ):
                        info.button(
                            variant["attributes"]["language"], class_="button--secondary"
                        ).dataController(
                            "this.SET('admin.selected',record);this.SET('admin.revision','')",
                            record=variant["record_id"],
                        )
            else:
                info.pre(json.dumps(record["attributes"], ensure_ascii=False, indent=2))
            source_pane = tabs.contentPane(
                title="Sorgente", pageName="source", padding="12px", overflow="auto"
            )
            if not record["sources"]:
                source_pane.p(
                    "Questo record non contiene sorgenti. Seleziona una variante linguistica."
                )
            for name, payload in record["sources"].items():
                source_pane.h3(name)
                literal_text(
                    source_pane,
                    "pre",
                    payload.get("text", "Contenuto binario; originale conservato."),
                )
            revisions = tabs.contentPane(
                title="Revisioni", pageName="history", padding="12px", overflow="auto"
            )
            for item in history:
                revisions.button(
                    f"Revisione {item['generation']}", class_="button--secondary"
                ).dataController(
                    "this.SET('admin.revision', revision)", revision=item["revision_id"]
                )
        except DomainError as error:
            pane.p(str(error), role="status")

    def login_view(self, root):  # wf:phase-1:new
        root.dataSetter("login.username", "")
        root.dataSetter("login.password", "")
        root.dataSetter("login.error", "")
        box = root.main(class_="login-shell").section(class_="login-card")
        box.p("kajenn public site", class_="muted")
        box.h1("Accedi ai tuoi siti")
        box.html_label("Nome utente", for_="username")
        box.input(id="username", value="^login.username", autocomplete="username")
        box.html_label("Password", for_="password")
        box.input(
            id="password", type="password", value="^login.password", autocomplete="current-password"
        )
        box.button("Accedi").dataRpc(
            "sign_in",
            username="=login.username",
            password="=login.password",
            _onResult="this.SET('login.password',''); if(!result){window.location.reload();}else{this.SET('login.error',result)}",
            _onError="this.SET('login.password','');this.SET('login.error','Accesso non disponibile')",
        )
        box.p("^login.error", role="status")

    @endpoint
    async def sign_in(self, username="", password=""):  # wf:phase-1:new
        request = CURRENT_REQUEST.get()
        server_app = request.server.application_at("_server")
        result = await asyncio.to_thread(
            server_app.login, identity=username, password=password, _request=request
        )
        return "Accesso non riuscito" if "error" in result else ""

    @endpoint(auth="editor")
    def sign_out(self):  # wf:phase-1:new
        request = CURRENT_REQUEST.get()
        request.server.session_store.delete(request.session.id)
        return True

    @endpoint(auth="editor")
    async def read(self, operation, arguments=None):  # wf:phase-1:new
        return await execute_read(operation, **(arguments or {}))


class WorkspacePage(AdminPage):
    section = "content"

    async def main(self, root):  # wf:phase-1:new
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {
            "site": "",
            "selected": "",
            "search": "",
            "refresh": 0,
            "revision": "",
            "tab": "info",
        }.items():
            root.dataSetter(f"admin.{name}", value)
        root.dataController(
            "this.SET('admin.site', new URLSearchParams(window.location.search).get('site') || '');",
            _onStart=True,
        )
        root.dataController(
            "this.SET('admin.selected','');this.SET('admin.revision','');", site="^admin.site"
        )
        toolbar = root.div(class_="toolbar")
        toolbar.input(
            value="^admin.search",
            placeholder="Cerca per titolo…",
            aria_label="Cerca per titolo",
            type="search",
            live=True,
        )
        toolbar.button("Aggiorna").dataController(
            "this.SET('admin.refresh', (this.GET('admin.refresh')||0)+1)"
        )
        root.div(class_="workspace-host").remote(
            "workspace",
            site="^admin.site",
            section=self.section,
            search="^admin.search",
            refresh="^admin.refresh",
            _delay=150,
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )
