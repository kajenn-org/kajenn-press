"""Gallery-style index: Sites and Library in the tree, one retained iframe tab per site."""

from genro_bag import Bag
from gramlot import IndexPage, source

from kajenn_press.admin.host import CURRENT_REQUEST, LOGO_SRC, execute_service
from kajenn_press.admin.views import AdminPage
from kajenn_press.domain import DomainError


class Page(AdminPage, IndexPage):
    title = "Kajenn Press"
    datapath = "index"
    css = ("/themes/gramlot-index/theme.css", "/index.css")

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        self.identity = avatar.identity
        root.dataSetter("admin.nav_drawer", True)
        if CURRENT_REQUEST.get().server.applications["press"].sites is None:
            self.navigation = Bag()
            root.main(class_="index-unconfigured").p(
                "Site sources are not configured on this installation."
            )
            return
        self.navigation = await self.sites_navigation()
        IndexPage.main(self, root)

    @staticmethod
    async def sites_navigation():
        """Sites (each site with its holder, and "new site") and Library (starting sites)."""
        navigation, sites, library = Bag(), Bag(), Bag()
        for item in await execute_service("site_list", {}):
            holder = f" · {item['holder']}" if item["holder"] else ""
            sites.set_item(
                "s_" + item["site_id"],
                None,
                label=item["name"] + holder,
                title=item["name"],
                url="site?site=" + item["site_id"],
                site=item["site_id"],
                section="site_tab",
            )
        sites.set_item(
            "new", None, label="+ new site", title="New site", url="site", section="site_new"
        )
        for item in await execute_service("starters_list", {}):
            library.set_item(
                "t_" + item["starter_id"],
                None,
                label=item["name"],
                title="Starting site · " + item["name"],
                url="site",
                section="site_new",
            )
        navigation.set_item("sites", sites, label="Sites", title="Sites")
        navigation.set_item("library", library, label="Library", title="Library · starting sites")
        return navigation

    def top(self, pane):
        pane.set_attr({"height": "64px", "class": "admin-top"})
        bar = pane.header(class_="admin-toolbar")
        brand = bar.div(class_="admin-brand")
        brand.img(src=LOGO_SRC, width="48", height="48", alt="")
        brand.strong("Kajenn Press")
        account = bar.div(class_="account")
        account.span(self.identity)
        account.button("Sign out", class_="button--quiet").dataRpc(
            "sign_out", _onResult="window.location.reload()"
        )

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
        pane.dataSetter("admin.active_title", "No site open")
        pane.dataController(
            "var node=path?navigation.getNode(path):null;"
            "if(node&&node.attr.url){this.SET('admin.active_title',node.attr.title)}",
            path="^index.navigationSelection",
            navigation="=index.navigation",
        )
        pane.div(class_="admin-status", role="status").span(
            "^admin.active_title", class_="active-title"
        )

    @source(auth="editor")
    async def index_panel(self, pane, selection):
        # Navigation is client Data: validate the section and derive the URL again.
        node = selection.get_node("#0")
        section, site = node.attr.get("section"), node.attr.get("site", "")
        if section == "site_tab":
            read = await execute_service("site_read", {"site_id": site})
            url, title = "site?site=" + site, read["name"]
        elif section == "site_new":
            url, title = "site", "New site"
        else:
            raise DomainError("invalid_input", "Page unavailable")
        pane.iframe(src=url, title=title, width="100%", height="100%", border=0)
