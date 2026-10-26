"""Gallery-style index with site toolbar and one retained, scope-bound iframe tab per object."""

from uuid import uuid4

from genro_bag import Bag
from gramlot import IndexPage, endpoint, source

from kajenn_press.admin.host import (
    CURRENT_REQUEST,
    LOGO_SRC,
    execute_read,
    execute_site_create,
)
from kajenn_press.admin.views import AdminPage, caption, literal_text
from kajenn_press.domain import DomainError

# Navigation groups of a site: tree key, label and the record kinds each one lists.
GROUPS = (
    ("pages", "Pages", "content"),
    ("templates", "Templates", "template"),
    ("styles", "Styles", "css"),
    ("scripts", "Scripts", "javascript"),
    ("media", "Media", "media"),
)
RESOURCE_KINDS = frozenset(kind for _key, _label, kind in GROUPS) - {"content"}


class Page(AdminPage, IndexPage):
    title = "Kajenn Press"
    datapath = "index"
    css = ("/themes/gramlot-index/theme.css", "/index.css")

    async def main(self, root):
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
            "sites_version": 0,
            "nav_version": 0,
            "open_author": False,
            "nav_drawer": True,
            "new_site": False,
            "name": "",
            "languages": "it,en",
            "error": "",
            "key": uuid4().hex,
        }.items():
            root.dataSetter(f"admin.{name}", value)
        self.navigation = await self.navigation_bag(site, self.sites)
        IndexPage.main(self, root)

    @staticmethod
    async def navigation_bag(site, sites):
        navigation, current = Bag(), Bag()
        navigation.set_item(
            "home",
            None,
            title="Home · How it works",
            label="Home · How it works",
            url="home",
            section="home",
        )
        item = next((item for item in sites if item["record_id"] == site), None)
        if item:
            label = item["attributes"]["name"]
            records = await execute_read("records_index", scope="site:" + site)
            for key, group_label, kind in GROUPS:
                group = Bag()
                if kind == "content":
                    group.set_item(
                        "new_page",
                        None,
                        label="New page",
                        title=label + " · New page",
                        url="author?site=" + site,
                        site=site,
                        section="new_page",
                    )
                for record in sorted(
                    (r for r in records if r["kind"] == kind), key=lambda r: caption(r).casefold()
                ):
                    name = caption(record)
                    # Pages open the page editor; the other kinds open the resource editor.
                    section = "page" if kind == "content" else "resource"
                    target = (
                        "page?site=" + site + "&content="
                        if kind == "content"
                        else ("resource?site=" + site + "&record=")
                    )
                    group.set_item(
                        "r_" + record["record_id"],
                        None,
                        label=name,
                        title=label + " · " + name,
                        url=target + record["record_id"],
                        site=site,
                        record=record["record_id"],
                        section=section,
                    )
                current.set_item(key, group, label=group_label, title=group_label)
            current.set_item(
                "publication",
                None,
                title="Publishing · coming soon",
                label="Publishing · coming soon",
            )
        navigation.set_item(
            "site",
            current,
            title=item["attributes"]["name"] if item else "No site",
            label=item["attributes"]["name"] if item else "No site",
        )
        shared = Bag()
        shared.set_item(
            "resources",
            None,
            title="Shared library",
            label="Shared library",
            url="library",
            section="library",
        )
        navigation.set_item(
            "shared", shared, title="Shared across sites", label="Shared across sites"
        )
        navigation.set_item(
            "deployments",
            None,
            title="Deployments",
            label="Deployments",
            url="deployments",
            section="deployments",
        )
        return navigation

    def top(self, pane):
        pane.set_attr({"height": "64px", "class": "admin-top"})
        bar = pane.header(class_="admin-toolbar")
        brand = bar.div(class_="admin-brand")
        brand.img(src=LOGO_SRC, width="48", height="48", alt="")
        brand.strong("Kajenn Press")
        bar.html_label("Current site", for_="site")
        bar.div(class_="site-selector").remote("site_selector", version="^admin.sites_version")
        bar.button(
            "New site", disabled=not self.can_create, class_="button--secondary"
        ).dataController("this.SET('admin.new_site',true)")
        bar.button("Refresh", class_="button--quiet").dataController(
            "this.SET('admin.nav_version',this.GET('admin.nav_version')+1)"
        )
        account = bar.div(class_="account")
        account.span(self.identity)
        account.button("Sign out", class_="button--quiet").dataRpc(
            "sign_out", _onResult="window.location.reload()"
        )
        # Native dialog uses a public Source attribute; no imperative DOM mutation.
        pane.dataFormula("admin.dialog_open", "visible", visible="^admin.new_site")
        dialog = pane.dialog(
            open="^admin.dialog_open", class_="new-site-dialog", aria_label="New site"
        )
        dialog.h2("New site")
        dialog.html_label("Name", for_="new-site-name")
        dialog.input(id="new-site-name", value="^admin.name", live=True)
        dialog.html_label("Languages (comma-separated)", for_="new-site-languages")
        dialog.input(id="new-site-languages", value="^admin.languages", live=True)
        dialog.p("^admin.error", role="status")
        dialog.button("Create site").dataRpc(
            "create_site",
            name="=admin.name",
            languages="=admin.languages",
            key="=admin.key",
            # Keep the shell and its open tabs: refresh the selector, then open the new site.
            _onResult="if(result.ok){this.SET('admin.new_site',false);this.SET('admin.name','');"
            "this.SET('admin.error','');this.SET('admin.key',crypto.randomUUID());"
            "this.SET('admin.open_author',true);"
            "this.SET('admin.sites_version',this.GET('admin.sites_version')+1);"
            "this.SET('admin.site',result.site_id)}else{this.SET('admin.error',result.message)}",
            _onError="this.SET('admin.error','No response received. Retry without changing your input.')",
        )
        dialog.button("Cancel", class_="button--quiet").dataController(
            "this.SET('admin.new_site',false)"
        )

    @source(auth="editor")
    async def site_selector(self, pane, version=0):
        sites = await execute_read("sites_list")
        select = pane.select(id="site", value="^admin.site")
        if not sites:
            select.option("No accessible sites", value="")
        for item in sites:
            literal_text(select, "option", item["attributes"]["name"], value=item["record_id"])

    def left(self, pane):
        IndexPage.left(self, pane)
        pane.set_attr(
            {
                "class": "index-sidebar",
                "drawer": "^admin.nav_drawer",
                "drawer_label": "Navigation",
                "width": "240px",
            }
        )
        pane.value.get_node("tree").set_attr(
            {"autoCollapse": False, "class": "admin-tree", "labelAttribute": "label"}
        )

    def center(self, pane):
        pane.set_attr({"overflow": "hidden"})
        IndexPage.center(self, pane)

    def bottom(self, pane):
        pane.set_attr({"height": "30px", "class": "admin-footer"})
        # The tree selection follows the active tab; a selected folder leaves the tab unchanged.
        pane.dataSetter("admin.active_title", "No object open")
        pane.dataController(
            "var node=path?navigation.getNode(path):null;"
            "if(node&&node.attr.url){this.SET('admin.active_title',node.attr.title)}",
            path="^index.navigationSelection",
            navigation="=index.navigation",
        )
        status = pane.div(class_="admin-status", role="status")
        status.span("^admin.active_title", class_="active-title")
        status.div(class_="scope-permissions").remote(
            "permissions",
            site="^admin.site",
            section="content",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    def behavior(self, shell):
        IndexPage.behavior(self, shell)
        # A tab asks the shell to open another object, e.g. a page editor opening its template.
        shell.dataController(
            "var group={"
            + ",".join(f"'{kind}':'{key}'" for key, _label, kind in GROUPS)
            + "}[kind];"
            "if(group&&record_id){this.SET('index.navigationSelection','site.'+group+'.r_'+record_id)}",
            subscribe_open_object=True,
        )
        shell.dataController(
            "this.SET('index.navigationSelection',this.GET('admin.site') ? 'site.pages.new_page' : 'home');"
            # Narrow viewports start with the navigation drawer closed.
            "if(window.matchMedia('(max-width: 700px)').matches){this.SET('admin.nav_drawer','close')}",
            _onStart=True,
        )
        shell.dataRpc(
            "navigation_for_site",
            site="^admin.site",
            version="^admin.nav_version",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
            _onResult="var nav=this.GET('index.navigation');var branch=result.getNode('site');nav.setItem('site',branch.value,branch.attr);"
            "this.SET('index.navigationSelection',this.GET('admin.open_author') ? 'site.pages.new_page' : null);"
            "this.SET('admin.open_author',false)",
        )

    @endpoint(auth="editor")
    async def navigation_for_site(self, site, version=0):
        sites = await execute_read("sites_list")
        if site and not any(item["record_id"] == site for item in sites):
            raise DomainError("forbidden", "Site not accessible")
        return await self.navigation_bag(site, sites)

    @source(auth="editor")
    async def index_panel(self, pane, selection):
        # Navigation is client Data: validate its scope and derive the URL again.
        node = selection.get_node("#0")
        section, site = node.attr.get("section"), node.attr.get("site", "")
        if section == "home":
            url, title = "home", "Home · How it works"
        elif section == "library":
            await execute_read("records_index", scope="library")
            url, title = "library", "Shared library"
        elif section == "deployments":
            url, title = "deployments", "Deployments"
        elif section in {"new_page", "resource", "page"}:
            sites = await execute_read("sites_list")
            item = next((item for item in sites if item["record_id"] == site), None)
            if not item:
                raise DomainError("forbidden", "Site not accessible")
            if section == "new_page":
                url, title = "author?site=" + site, item["attributes"]["name"] + " · New page"
            elif section == "page":
                record_id = node.attr.get("record", "")
                records = await execute_read("records_index", scope="site:" + site)
                record = next(
                    (r for r in records if r["record_id"] == record_id and r["kind"] == "content"),
                    None,
                )
                if record is None:
                    raise DomainError("not_found", "Page unavailable in this site")
                url = "page?site=" + site + "&content=" + record_id
                title = item["attributes"]["name"] + " · " + caption(record)
            else:
                record_id = node.attr.get("record", "")
                records = await execute_read("records_index", scope="site:" + site)
                record = next(
                    (
                        r
                        for r in records
                        if r["record_id"] == record_id and r["kind"] in RESOURCE_KINDS
                    ),
                    None,
                )
                if record is None:
                    raise DomainError("not_found", "Object unavailable in this site")
                url = "resource?site=" + site + "&record=" + record_id
                title = item["attributes"]["name"] + " · " + caption(record)
        else:
            raise DomainError("invalid_input", "Page unavailable")
        pane.iframe(src=url, title=title, width="100%", height="100%", border=0)

    @endpoint(auth="editor")
    async def create_site(self, name, languages, key):
        try:
            result = await execute_site_create(
                name=name, languages=[v.strip() for v in languages.split(",") if v.strip()], key=key
            )
            return {"ok": True, "site_id": result["records"][0]["record_id"]}
        except DomainError as error:
            return {"ok": False, "message": str(error)}
