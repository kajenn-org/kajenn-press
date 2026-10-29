"""The administration as Gramlot's gallery: an icon column, the navigation of sites and
starting sites, and one closable tab per opened site holding its page in an iframe."""

from genro_bag import Bag
from gramlot import IndexPage, source

from kajenn_press.admin.host import CURRENT_REQUEST, LOGO_SRC, execute_service
from kajenn_press.admin.views import AdminPage
from kajenn_press.domain import DomainError

# Icons of the column, drawn as data URLs as in Gramlot's gallery.
NAVIGATION_ICON = (
    "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22"
    "%20fill%3D%22none%22%20stroke%3D%22%237b8795%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22%3E"
    "%3Crect%20x%3D%223%22%20y%3D%224%22%20width%3D%2218%22%20height%3D%2216%22%20rx%3D%222%22%2F%3E"
    "%3Cpath%20d%3D%22M9%204v16M5.5%208h1M5.5%2012h1M5.5%2016h1%22%2F%3E%3C%2Fsvg%3E"
)
SIGN_OUT_ICON = (
    "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22"
    "%20fill%3D%22none%22%20stroke%3D%22%237b8795%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22"
    "%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M14%204h4a2%202%200%200%201%202%202v12a2%202%200%200%201-2%202h-4"
    "%22%2F%3E%3Cpath%20d%3D%22M9%2016l-4-4%204-4M5%2012h11%22%2F%3E%3C%2Fsvg%3E"
)


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
        if CURRENT_REQUEST.get().server.applications["press"].sites is None:
            self.navigation = Bag()
            root.main(class_="index-unconfigured").p(
                "Site sources are not configured on this installation."
            )
            return
        self.navigation = await self.sites_navigation()
        # The gallery's frame: the icon column on the left, the index in the center.
        frame = root.framePane(height="100vh", min_height=0, class_="press-frame")
        frame.left.set_attr({"width": "44px", "class": "press-rail-region"})
        rail = frame.left.menu(
            presentation="bar",
            orientation="vertical",
            labelPosition="tooltip",
            iconSize=22,
            width="100%",
            height="100%",
            aria_label="Kajenn Press",
        )
        rail.menuline(
            caption="Navigation",
            tooltip="Navigation: sites and starting sites",
            iconSrc=NAVIGATION_ICON,
            checked="^index.navigationOpen",
            action="pressToggleNavigation",
            overflowable=False,
        )
        rail.spacer(flex=1)
        rail.menuline(
            caption="Sign out",
            tooltip="Sign out · " + self.identity,
            iconSrc=SIGN_OUT_ICON,
            action="pressSignOut",
            overflowable=False,
        )
        IndexPage.main(self, frame.center)

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

    # No top bar: the logo heads the navigation, Sign out is in the icon column.
    top = None

    def left(self, pane):
        header = pane.header(class_="press-navigation-header")
        header.img(src=LOGO_SRC, width="28", height="28", alt="")
        header.strong("Kajenn Press")
        IndexPage.left(self, pane)
        pane.set_attr(
            {
                "class": "index-sidebar",
                "nodeId": "pressNavigation",
                "drawer_label": "Navigation",
                "width": "240px",
            }
        )
        pane.value.get_node("tree").set_attr(
            {"autoCollapse": False, "class": "admin-tree", "labelAttribute": "label"}
        )

    def center(self, pane):
        pane.set_attr({"overflow": "hidden"})
        # Gramlot's index tabs: one closable tab per opened site (d-gramlot-shell).
        IndexPage.center(self, pane)
        pane.value.get_node("tabs").set_attr({"class": "press-pages"})

    # No status bar: each site's name is in its tab.
    bottom = None

    def behavior(self, shell):
        IndexPage.behavior(self, shell)
        shell.dataSetter("index.navigationOpen", True)
        # The drawer's own close button keeps the column's check in step.
        shell.dataController(
            "this.SET('index.navigationOpen', open)",
            subscribe_pressNavigation_closable_change=True,
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
