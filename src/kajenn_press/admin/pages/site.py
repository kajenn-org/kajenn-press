"""The site tab (N5): Visual editor, SEO and Published site, over the site operations.

The Visual editor shows the working copy rendered page by page in a sandboxed iframe
(scripts allowed, never the administration's origin). A drawer holds the Pages tree, with
the slots of each page, and the Contents tree; a content is assigned to a slot by dropping
it on the slot, or by choosing it from the slot's menu. A slot opens in the block editor,
docked at the right (N5-D1), which edits the original content and then offers the Update
plan of its copies (N5-D2).
"""

import json

from genro_bag import Bag
from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, execute_service
from kajenn_press.admin.views import AdminPage, literal_text
from kajenn_press.domain import DomainError

COMMANDS = frozenset(
    {
        "site_open",
        "site_save",
        "site_restore",
        "site_new",
        "page_render",
        "slot_assign",
        "content_add",
        "content_save",
        "page_add",
        "folder_add",
        "tree_move",
        "copies_update_plan",
        "copies_update",
    }
)


def pages_bag(read):
    """The Pages tree for the tree component: folders, pages, and slots under each page."""
    pages = {page["id"]: page for page in read["pages"]}
    contents = {content["id"]: content["name"] for content in read["contents"]}

    def fill(bag, items):
        for item in items:
            if item["type"] == "folder":
                folder = Bag()
                fill(folder, item["children"])
                bag.set_item(
                    item["id"], folder, caption=item["name"], kind="folder", item=item["id"]
                )
                continue
            page = pages[item["id"]]
            marks = ("  ●" if page["changed"] else "") + ("  ↻" if page["outdated"] else "")
            slots = Bag()
            for name in page["slot_names"]:
                assigned = page["slots"].get(name)
                caption = f"{name} ← {contents[assigned]}" if assigned else f"{name} · empty"
                slots.set_item(
                    "slot_" + name,
                    None,
                    caption=caption,
                    kind="slot",
                    page=item["id"],
                    slot=name,
                    content=assigned or "",
                )
            bag.set_item(
                item["id"], slots, caption=page["name"] + marks, kind="page", page=item["id"]
            )

    root = Bag()
    fill(root, read["tree"])
    return root


def contents_bag(read):
    bag = Bag()
    for content in read["contents"]:
        uses = content["uses"]
        caption = content["name"] + (f"  ({uses})" if uses > 1 else "")
        bag.set_item(
            content["id"],
            None,
            caption=caption,
            kind="content",
            content=content["id"],
            unused=uses == 0,
        )
    return bag


class Page(AdminPage):
    title = "Site"
    css = ("/themes/gramlot-index/theme.css", "/site.css")

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {"id": "", "version": 0}.items():
            root.dataSetter(f"site.{name}", value)
        root.dataController(
            "var q=new URLSearchParams(window.location.search);"
            "this.SET('site.id',q.get('site')||'');",
            _onStart=True,
        )
        root.div(class_="site-host").remote(
            "site_workspace",
            site="^site.id",
            version="^site.version",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    @source(auth="editor")
    async def site_workspace(self, pane, site="", version=0):
        if not site:
            self.new_site(pane)
            return
        identity = CURRENT_REQUEST.get().avatar().identity
        try:
            read = await execute_service("site_read", {"site_id": site})
        except DomainError as error:
            pane.p(str(error), role="status")
            return
        holder = read["holder"]
        first_page = read["pages"][0]["id"] if read["pages"] else ""
        for name, value in {
            "name": read["name"],
            "holder": holder or "",
            "editing": holder == identity,
            "identity": identity,
            "page": first_page,
            "pages_json": json.dumps(
                {p["id"]: {"name": p["name"], "url": p["url"]} for p in read["pages"]}
            ),
            "contents_json": json.dumps(
                {c["id"]: {"name": c["name"], "text": c["text"]} for c in read["contents"]}
            ),
            "template_id": read["templates"][0]["id"] if read["templates"] else "",
            "show_slots": True,
            "preview": "",
            "status": "",
            "message": "",
            "busy": False,
            "editor_open": False,
            "editor_content": "",
            "editor_title": "",
            "editor_text": "",
            "plan_json": "",
            "assign_slot": "",
            "assign_page": "",
            "assign_content": "",
            "new_content_name": "",
        }.items():
            pane.dataSetter("site." + name, value)
        pane.dataFormula("site.assign_hidden", "!slot", slot="^site.assign_slot", _init=True)
        pane.dataFormula("site.editor_hidden", "!open", open="^site.editor_open", _init=True)
        pane.dataSetter("site.pages_tree", pages_bag(read))
        pane.dataSetter("site.contents_tree", contents_bag(read))
        pane.dataController(func="initialize", _onBuilt=True)
        pane.dataController(
            func="renderPage", page="^site.page", slots="^site.show_slots", _onBuilt=True
        )
        layout = pane.borderContainer(height="100vh", class_="site-tab")
        top = layout.contentPane(region="top", class_="site-bar")
        literal_text(top, "h1", read["name"])
        pane.dataFormula(
            "site.holder_text",
            "editing ? 'You are editing this site' : (holder ? 'Edited by ' + holder"
            " + ' · read only' : 'Nobody is editing this site')",
            editing="^site.editing",
            holder="^site.holder",
            _init=True,
        )
        top.span("^site.holder_text", class_="site-holder")
        actions = top.div(class_="site-actions")
        actions.button(
            "Take the site", class_="button--secondary", hidden="^site.editing"
        ).dataController(func="takeSite")
        actions.button("Save", disabled="^site.busy").dataController(func="save")
        top.span("^site.message", role="status", class_="site-message")
        tabs = layout.contentPane(region="center").tabContainer(height="100%")
        visual = tabs.contentPane(title="Visual editor", pageName="visual")
        self.visual_editor(visual, read["contents"])
        tabs.contentPane(title="SEO", pageName="seo", padding="24px").p(
            "SEO comes with N6.", class_="muted"
        )
        tabs.contentPane(title="Published site", pageName="published", padding="24px").p(
            "The published site comes with N7.", class_="muted"
        )

    def visual_editor(self, pane, contents):
        layout = pane.borderContainer(height="100%")
        drawer = layout.contentPane(
            region="left", splitter=True, width="260px", class_="site-drawer"
        )
        trees = drawer.tabContainer(height="100%")
        pages = trees.contentPane(title="Pages", pageName="pages", padding="8px")
        pages.tree(
            storepath="site.pages_tree",
            hideValues=True,
            labelAttribute="caption",
            draggable=True,
            dragTags="page",
            onDrag="preparePage",
            dropTargetCb="acceptDrop",
            dropTypes="app/kpress-content,app/kpress-page",
            onDrop="dropOnTree",
            selectedPath="^site.selected_path",
            id="pages-tree",
        )
        pane.dataController(func="selectTreeItem", path="^site.selected_path")
        row = pages.div(class_="drawer-actions")
        row.button("+ page", class_="button--quiet").dataController(func="addPage")
        row.button("+ folder", class_="button--quiet").dataController(func="addFolder")
        assign = pages.div(class_="slot-assign", hidden="^site.assign_hidden")
        assign.span("^site.assign_slot")
        menu = assign.select(value="^site.assign_content", aria_label="Content for the slot")
        menu.option("Choose a content…", value="")
        for content in contents:
            menu.option(content["name"], value=content["id"])
        assign.button("Assign").dataController(func="assignChosen")
        assign.button("Edit", class_="button--secondary").dataController(func="openSlot")
        contents = trees.contentPane(title="Contents", pageName="contents", padding="8px")
        contents.tree(
            storepath="site.contents_tree",
            hideValues=True,
            labelAttribute="caption",
            draggable=True,
            dragTags="content",
            effectAllowed="copy",
            onDrag="prepareContent",
            getLabelClass="contentClass",
            id="contents-tree",
        )
        add = contents.div(class_="drawer-actions")
        add.input(value="^site.new_content_name", placeholder="New content name")
        add.button("+ content", class_="button--quiet").dataController(func="addContent")
        stage = layout.contentPane(region="center", class_="site-stage")
        bar = stage.div(class_="stage-bar")
        bar.span("^site.status", class_="muted")
        bar.html_label("Show slots", for_="show-slots")
        bar.input(id="show-slots", type="checkbox", value="^site.show_slots")
        stage.iframe(
            srcdoc="^site.preview",
            sandbox="allow-scripts",
            title="Page preview",
            class_="site-preview",
        )
        editor = layout.contentPane(
            region="right",
            width="400px",
            splitter=True,
            overflow="auto",
            class_="block-editor",
            hidden="^site.editor_hidden",
        )
        head = editor.div(class_="editor-head")
        head.strong("^site.editor_title")
        head.button("Close", class_="button--quiet").dataController(func="closeEditor")
        views = editor.tabContainer(height="300px", tabMode="underline")
        views.contentPane(title="CodeMirror", pageName="code").codeMirror(
            value="^site.editor_text", language="html", height="100%"
        )
        views.contentPane(title="Jodit", pageName="rich").htmlEditor(
            value="^site.editor_text", height="100%"
        )
        views.contentPane(title="Preview", pageName="preview").htmlPreview(
            value="^site.editor_text", height="100%"
        )
        editor.button("Save", disabled="^site.busy").dataController(func="saveContent")
        editor.div(class_="update-plan").remote("plan_view", plan="^site.plan_json")

    @source(auth="editor")
    async def plan_view(self, pane, plan=""):
        if not plan:
            return
        items = json.loads(plan)
        pane.strong("Update copies")
        for index, item in enumerate(items):
            pane.dataSetter(f"site.plan.i{index}", item["selected"])
            label = item["page_name"] + (
                " · changed in the page" if item["locally_changed"] else ""
            )
            pane.html_label(label, for_=f"plan-{index}")
            pane.input(id=f"plan-{index}", type="checkbox", value=f"^site.plan.i{index}")
        pane.button("Update and render").dataController(func="applyUpdate")

    def new_site(self, pane):
        pane.dataSetter("site.new_name", "")
        pane.dataSetter("site.message", "")
        form = pane.main(class_="new-site")
        form.h1("New site")
        form.html_label("Name", for_="new-site-name")
        form.input(id="new-site-name", value="^site.new_name")
        form.button("Create site").dataController(func="createSite")
        form.p("^site.message", role="status")

    @endpoint(auth="editor")
    async def command(self, operation, arguments):
        if operation not in COMMANDS:
            raise DomainError("invalid_operation", "Command unavailable in the site tab")
        if not isinstance(arguments, dict):
            raise DomainError("invalid_input", "Command arguments must be an object")
        try:
            return {"ok": True, "result": await execute_service(operation, arguments)}
        except DomainError as error:
            return {"ok": False, "error": error.as_dict()}
