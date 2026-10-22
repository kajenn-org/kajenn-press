"""Gallery-style index with site toolbar and retained, scope-bound iframe pages."""

from uuid import uuid4

from genro_bag import Bag
from gramlot import IndexPage, endpoint, source

from kajenn_public_site.admin.host import CURRENT_REQUEST, execute_read, execute_site_create
from kajenn_public_site.admin.views import AdminPage, literal_text
from kajenn_public_site.domain import DomainError


class Page(AdminPage, IndexPage):
    title = "Kajenn public site"
    datapath = "index"
    css = ("/themes/gramlot-index/theme.css", "/index.css")

    async def main(self, root):  # wf:phase-1:new
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        self.sites = await execute_read("sites_list")
        self.identity = avatar.identity
        self.can_create = (
            "create_site"
            in (await execute_read("scope_capabilities", scope="installation"))["permissions"]
        )
        site = self.sites[0]["record_id"] if self.sites else ""
        for name, value in {
            "site": site,
            "new_site": False,
            "name": "",
            "languages": "it,en",
            "error": "",
            "key": uuid4().hex,
        }.items():
            root.dataSetter(f"admin.{name}", value)
        self.navigation = self.navigation_bag(site, self.sites)
        IndexPage.main(self, root)

    @staticmethod
    def navigation_bag(site, sites):  # wf:phase-1:new
        navigation, current = Bag(), Bag()
        item = next((item for item in sites if item["record_id"] == site), None)
        if item:
            label = item["attributes"]["name"]
            current.set_item(
                "content",
                None,
                label="Contenuti",
                title="Sito " + label + " · Contenuti",
                url="content?site=" + site,
                site=site,
                section="content",
            )
            current.set_item(
                "resource",
                None,
                label="Risorse",
                title="Sito " + label + " · Risorse",
                url="resources?site=" + site,
                site=site,
                section="resource",
            )
            current.set_item(
                "publication",
                None,
                title="Pubblicazione · in seguito",
                label="Pubblicazione · in seguito",
            )
        navigation.set_item(
            "site",
            current,
            title=item["attributes"]["name"] if item else "Nessun sito",
            label=item["attributes"]["name"] if item else "Nessun sito",
        )
        shared = Bag()
        shared.set_item(
            "resources",
            None,
            title="Libreria condivisa",
            label="Libreria condivisa",
            url="library",
            section="library",
        )
        navigation.set_item(
            "shared", shared, title="Condiviso tra i siti", label="Condiviso tra i siti"
        )
        return navigation

    def top(self, pane):  # wf:phase-1:new
        pane.set_attr({"height": "54px", "class": "admin-top"})
        bar = pane.header(class_="admin-toolbar")
        bar.strong("kajenn public site")
        bar.html_label("Sito corrente", for_="site")
        select = bar.select(id="site", value="^admin.site")
        if not self.sites:
            select.option("Nessun sito accessibile", value="")
        for item in self.sites:
            literal_text(select, "option", item["attributes"]["name"], value=item["record_id"])
        bar.html_button(
            "Nuovo sito", disabled=not self.can_create, class_="button--secondary"
        ).dataController("this.SET('admin.new_site',true)")
        account = bar.div(class_="account")
        account.span(self.identity)
        account.html_button("Esci", class_="button--quiet").dataRpc(
            "sign_out", _onResult="window.location.reload()"
        )
        # Native dialog uses a public Source attribute; no imperative DOM mutation.
        pane.dataFormula("admin.dialog_open", "visible", visible="^admin.new_site")
        dialog = pane.dialog(
            open="^admin.dialog_open", class_="new-site-dialog", aria_label="Nuovo sito"
        )
        dialog.h2("Nuovo sito")
        dialog.html_label("Nome", for_="new-site-name")
        dialog.input(id="new-site-name", value="^admin.name", live=True)
        dialog.html_label("Lingue (separate da virgola)", for_="new-site-languages")
        dialog.input(id="new-site-languages", value="^admin.languages", live=True)
        dialog.p("^admin.error", role="status")
        dialog.html_button("Crea sito").dataRpc(
            "create_site",
            name="=admin.name",
            languages="=admin.languages",
            key="=admin.key",
            _onResult="if(result.ok){window.location.reload()}else{this.SET('admin.error',result.message)}",
            _onError="this.SET('admin.error','Risposta non disponibile. Riprova senza cambiare i dati.')",
        )
        dialog.html_button("Annulla", class_="button--quiet").dataController(
            "this.SET('admin.new_site',false)"
        )

    def left(self, pane):  # wf:phase-1:new
        IndexPage.left(self, pane)
        pane.set_attr({"class": "index-sidebar", "drawer_label": "Navigazione", "width": "225px"})
        pane.value.get_node("tree").set_attr(
            {"autoCollapse": False, "class": "admin-tree", "labelAttribute": "label"}
        )
        pane.div(class_="scope-permissions").remote(
            "permissions",
            site="^admin.site",
            section="content",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    def center(self, pane):  # wf:phase-1:new
        pane.set_attr({"overflow": "hidden"})
        IndexPage.center(self, pane)

    def bottom(self, pane):  # wf:phase-1:new
        pane.set_attr({"height": "28px", "class": "admin-footer"})
        pane.span("Kajenn public site · Consultazione · Le schede mantengono il proprio sito")

    def behavior(self, shell):  # wf:phase-1:new
        IndexPage.behavior(self, shell)
        shell.dataRpc(
            "navigation_for_site",
            site="^admin.site",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
            _onResult="var nav=this.GET('index.navigation');var branch=result.getNode('site');nav.setItem('site',branch.value,branch.attr);this.SET('index.navigationSelection',null)",
        )

    @endpoint(auth="editor")
    async def navigation_for_site(self, site):  # wf:phase-1:new
        sites = await execute_read("sites_list")
        if site and not any(item["record_id"] == site for item in sites):
            raise DomainError("forbidden", "Sito non accessibile")
        return self.navigation_bag(site, sites)

    @source(auth="editor")
    async def index_panel(self, pane, selection):  # wf:phase-1:new
        # Navigation is client Data: validate its scope and derive the URL again.
        node = selection.get_node("#0")
        section, site = node.attr.get("section"), node.attr.get("site", "")
        if section == "library":
            await execute_read("records_index", scope="library")
            url, title = "library", "Libreria condivisa"
        elif section in {"content", "resource"}:
            sites = await execute_read("sites_list")
            item = next((item for item in sites if item["record_id"] == site), None)
            if not item:
                raise DomainError("forbidden", "Sito non accessibile")
            url = ("content" if section == "content" else "resources") + "?site=" + site
            title = (
                item["attributes"]["name"]
                + " · "
                + ("Contenuti" if section == "content" else "Risorse")
            )
        else:
            raise DomainError("invalid_input", "Pagina non disponibile")
        pane.iframe(src=url, title=title, width="100%", height="100%", border=0)

    @endpoint(auth="editor")
    async def create_site(self, name, languages, key):  # wf:phase-1:new
        try:
            result = await execute_site_create(
                name=name, languages=[v.strip() for v in languages.split(",") if v.strip()], key=key
            )
            return {"ok": True, "site_id": result["records"][0]["record_id"]}
        except DomainError as error:
            return {"ok": False, "message": str(error)}
