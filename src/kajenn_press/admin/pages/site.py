"""The site tab (N5, N6): Visual editor, SEO and Published site, over the site operations.

The Visual editor shows the working copy rendered page by page in a sandboxed iframe
(scripts allowed, never the administration's origin). A drawer holds the Pages tree, with
the slots of each page, and the Contents tree; a content is assigned to a slot by dropping
it on the slot, or by choosing it from the slot's menu. A slot opens in the block editor,
docked at the right (N5-D1), which edits the original content and then offers the Update
plan of its copies (N5-D2).

The SEO tab (N6) lists the pages with the state of their checks; the selected page shows
its fields, with the value an empty field takes beside it, its images with their alt texts,
its search and social previews and its checks. The root page also holds the site defaults.
"""

import json
import re

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
        "page_seo_set",
        "page_url_set",
        "page_alt_set",
        "publish",
        "page_rollback",
        "site_rollback",
        "maintenance_set",
        "site_visibility_set",
        "private_link",
    }
)
ROBOTS = ("index, follow", "noindex, follow", "index, nofollow", "noindex, nofollow")
CHECK_LABELS = {
    "broken_link": "broken links",
    "missing_description": "missing descriptions",
    "missing_alt": "images without alt",
    "duplicate_title": "duplicate titles",
    "missing_origin": "no public origin",
    "iframe_without_fallback": "iframe slots without fallback",
}
ROOT_FIELDS = ("site_name", "origin", "organisation", "social_image", "robots", "description")
PAGE_FIELDS = (
    "title",
    "description",
    "canonical",
    "robots",
    "social_title",
    "social_description",
    "social_image",
    "json_ld",
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


def publication_label(state):
    """Text and kind of the state chip of the Published site tab."""
    if not state["published"] and state["state"] is None:
        return "Not published", "none"
    if state["maintenance"]:
        return "Maintenance", "maintenance"
    if state["state"] == "private":
        return "Private", "private"
    return "Public", "public"


def publication_summary(state):
    parts = []
    if state["last_publish"]:
        parts.append("published " + state["last_publish"][:16])
    changed = state["changed"]
    parts.append(
        f"{changed} page{'s' if changed != 1 else ''} changed since"
        if state["published"]
        else f"{changed} page{'s' if changed != 1 else ''} to publish"
    )
    return " · ".join(parts)


def address_note(state):
    if state["address_problem"]:
        return "The root page's public origin cannot be an address: " + state["address_problem"]
    if state["address"] is None:
        return "The next Publish puts the site at " + state["next_address"]
    return "The next Publish moves the site to " + state["next_address"]


def stage_message(state):
    if not state["address"]:
        return "Give the root page a public origin in the SEO tab, then publish."
    if state["state"] == "private":
        return "The site is private: visitors get 404. Open it with a private link."
    return "The site is in maintenance: visitors get 503. Open it with a private link."


def image_source(src):
    """An image source for people: a bound page asset shows as its asset name."""
    match = re.fullmatch(r"\^assets\.([^.]+)\.url", src)
    return "asset " + match[1] if match else src


def level(problem):
    return "error" if problem["code"] == "broken_link" else "warning"


def seo_pages_bag(pages, problems):
    """The SEO page list: each page with its URL and the worst state of its checks."""
    bag = Bag()
    for page in pages:
        found = {level(p) for p in problems if p["page_id"] == page["id"]}
        state = "error" if "error" in found else "warning" if found else "ok"
        bag.set_item(
            page["id"], None, caption=f"{page['name']}  {page['url']}", state=state, page=page["id"]
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
        root = [p["id"] for p in read["pages"] if p["url"] == "/"]
        pane.dataSetter("site.seo_page", (root or [first_page])[0])
        pane.dataSetter("site.seo_version", 0)
        tabs.contentPane(title="SEO", pageName="seo", overflow="hidden").remote(
            "seo_panel", site=site, page_id="^site.seo_page", version="^site.seo_version"
        )
        pane.dataSetter("site.pub_version", 0)
        pane.dataSetter("site.pub_panel", "")
        pane.dataSetter("site.pub_message", "")
        tabs.contentPane(title="Published site", pageName="published", overflow="hidden").remote(
            "published_panel", site=site, version="^site.pub_version"
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
    async def seo_panel(self, pane, site="", page_id="", version=0):
        read = await execute_service("site_read", {"site_id": site})
        problems = await execute_service("seo_check", {"site_id": site})
        pages = {item["id"]: item for item in read["pages"]}
        if page_id not in pages:
            pane.p("This site has no page yet.", class_="muted seo-empty")
            return
        item = pages[page_id]
        images = {a["id"]: a["name"] for a in read["assets"] if a["mime_type"].startswith("image/")}
        layout = pane.borderContainer(height="100%", class_="seo-tab")
        self.seo_summary(layout.contentPane(region="top").div(class_="seo-checks"), problems)
        listing = layout.contentPane(region="left", width="240px", splitter=True, class_="seo-list")
        pane.dataSetter("site.seo_pages", seo_pages_bag(read["pages"], problems))
        listing.tree(
            storepath="site.seo_pages",
            hideValues=True,
            labelAttribute="caption",
            selectedPath="^site.seo_page",
            getLabelClass="seoClass",
            id="seo-pages",
        )
        form = layout.contentPane(region="center", overflow="auto", class_="seo-form")
        self.seo_form(pane, form, item, images)
        side = layout.contentPane(
            region="right", width="340px", splitter=True, overflow="auto", class_="seo-side"
        )
        self.seo_previews(pane, side, item, images, read["name"])
        side.h4("Checks for this page")
        mine = [p for p in problems if p["page_id"] == page_id]
        checks = side.div(class_="seo-page-checks")
        for problem in mine:
            literal_text(checks, "div", "▲ " + problem["message"], class_="seo-" + level(problem))
        if not mine:
            checks.div("✓ No problem on this page", class_="seo-ok")

    def seo_summary(self, top, problems):
        top.span("Site checks:", class_="muted")
        counts = {}
        for problem in problems:
            counts[problem["code"]] = counts.get(problem["code"], 0) + 1
        for code, count in counts.items():
            top.span(f"{count} {CHECK_LABELS[code]}", class_="seo-" + level({"code": code}))
        if not counts:
            top.span("No problem found", class_="seo-ok")
        top.span("Publish shows the same list", class_="muted seo-note")

    def seo_form(self, pane, form, item, images):
        stored, inherited = item["seo"], item["seo_inherited"]
        is_root, is_missing = item["url"] == "/", item["url"] == "/404/"
        fields = [*ROOT_FIELDS, *PAGE_FIELDS] if is_root else list(PAGE_FIELDS)
        initial = {
            "page": item["id"],
            "url": item["url"],
            "fields": {name: stored.get(name, "") for name in dict.fromkeys(fields)},
            "images": [{"image": i["image"], "alt": i["alt"] or ""} for i in item["images"]],
        }
        pane.dataSetter("site.seo_initial", json.dumps(initial))
        pane.dataSetter("site.seo_message", "")
        pane.dataSetter("site.seo.url", item["url"])
        for name, value in initial["fields"].items():
            pane.dataSetter("site.seo." + name, value)
        for index, image in enumerate(initial["images"]):
            pane.dataSetter(f"site.seo.alt.i{index}", image["alt"])

        def row(box, label, field, hint=None, kind="input", options=None):
            line = box.div(class_="seo-row")
            line.html_label(label, for_="seo-" + field)
            cell = line.div()
            value = "^site.seo." + field
            if kind == "textarea":
                cell.textarea(id="seo-" + field, value=value, placeholder="empty")
            elif kind == "select":
                menu = cell.select(id="seo-" + field, value=value)
                for option_value, option_label in options:
                    menu.option(option_label, value=option_value)
            else:
                cell.input(id="seo-" + field, value=value, placeholder="empty")
            if hint:
                literal_text(cell, "div", hint, class_="seo-hint")

        def image_options(inherited_id):
            first = "— none —"
            if inherited_id:
                first = "— root: " + images.get(inherited_id, inherited_id) + " —"
            return [("", first), *images.items()]

        if is_root:
            box = form.fieldset(class_="seo-box")
            box.legend("Site defaults · root page only")
            row(box, "Site name", "site_name", "Empty: " + inherited["site_name"])
            row(box, "Public origin", "origin", "Scheme and host, such as https://example.org")
            row(box, "Organisation", "organisation")
            row(box, "Sharing image", "social_image", kind="select", options=image_options(""))
            robots = [("", "— default: index, follow —"), *((r, r) for r in ROBOTS)]
            row(box, "Robots", "robots", "noindex closes the whole site", "select", robots)
        box = form.fieldset(class_="seo-box")
        literal_text(box, "legend", item["name"])
        row(box, "Public URL", "url", "Changing the URL adds a 301 redirect from the old one.")
        row(box, "Title", "title", "Empty: " + inherited["title"])
        description = inherited["description"] or "no root value"
        row(box, "Description", "description", "Empty: " + description, "textarea")
        canonical = inherited["canonical"] or "none (no public origin)"
        row(box, "Canonical", "canonical", "Empty: " + canonical)
        if is_missing:
            box.div("The 404 page is always noindex.", class_="seo-hint")
        elif not is_root:
            root_robots = [("", "— root: " + inherited["robots"] + " —")]
            row(
                box,
                "Robots",
                "robots",
                kind="select",
                options=[*root_robots, *((r, r) for r in ROBOTS)],
            )
        box = form.fieldset(class_="seo-box")
        box.legend("Social share")
        row(box, "Title", "social_title", "Empty: the page title")
        row(box, "Description", "social_description", "Empty: the page description", "textarea")
        if not is_root:
            options = image_options(inherited["social_image"])
            row(box, "Image", "social_image", kind="select", options=options)
        box = form.fieldset(class_="seo-box")
        box.legend("Images and structured data")
        for index, image in enumerate(item["images"]):
            line = box.div(class_="seo-row")
            source_name = image_source(image["src"])
            literal_text(line, "span", source_name + " · " + image["where"], class_="seo-image")
            line.input(
                value=f"^site.seo.alt.i{index}",
                placeholder="decorative (empty alt)" if image["alt"] == "" else "missing",
                aria_label="Alt text of " + source_name,
            )
        if item["images"]:
            box.div(
                "Editing an alt text changes this page's copy of the content.", class_="seo-hint"
            )
        else:
            box.div("No image on this page.", class_="seo-hint")
        row(box, "JSON-LD", "json_ld", "Empty: " + (inherited["json_ld"] or "none"), "textarea")
        actions = form.div(class_="seo-actions")
        actions.button("Save SEO", disabled="^site.busy").dataController(func="saveSeo")
        actions.span("^site.seo_message", role="status")

    def seo_previews(self, pane, side, item, images, site_name):
        inherited = item["seo_inherited"]
        origin = "^site.seo.origin" if item["url"] == "/" else None
        pane.dataFormula(
            "site.seo_shown.title", "t || f", t="^site.seo.title", f=inherited["title"], _init=True
        )
        pane.dataFormula(
            "site.seo_shown.description",
            "d || f",
            d="^site.seo.description",
            f=inherited["description"],
            _init=True,
        )
        pane.dataFormula(
            "site.seo_shown.url",
            "(o || f) + u",
            o=origin or item["seo_effective"]["origin"],
            f=item["seo_effective"]["origin"],
            u="^site.seo.url",
            _init=True,
        )
        pane.dataFormula(
            "site.seo_shown.social_title",
            "s || t",
            s="^site.seo.social_title",
            t="^site.seo_shown.title",
            _init=True,
        )
        pane.dataFormula(
            "site.seo_shown.social_description",
            "(s || d) || 'No description'",
            s="^site.seo.social_description",
            d="^site.seo_shown.description",
            _init=True,
        )
        pane.dataFormula(
            "site.seo_shown.search_description",
            "d || 'No description: the search engine picks text from the page'",
            d="^site.seo_shown.description",
            _init=True,
        )
        pane.dataFormula(
            "site.seo_shown.image",
            "JSON.parse(names)[i || f] || 'No sharing image'",
            names=json.dumps(images),
            i="^site.seo.social_image",
            f=inherited["social_image"],
            _init=True,
        )
        side.h4("Search result")
        serp = side.div(class_="seo-serp")
        serp.div("^site.seo_shown.url", class_="seo-serp-url")
        serp.div("^site.seo_shown.title", class_="seo-serp-title")
        serp.div("^site.seo_shown.search_description", class_="seo-serp-text")
        side.h4("Social share")
        card = side.div(class_="seo-card")
        card.div("^site.seo_shown.image", class_="seo-card-image")
        body = card.div(class_="seo-card-body")
        literal_text(body, "div", inherited["site_name"] or site_name, class_="seo-card-site")
        body.div("^site.seo_shown.social_title", class_="seo-card-title")
        body.div("^site.seo_shown.social_description", class_="seo-card-text")

    @source(auth="editor")
    async def published_panel(self, pane, site="", version=0):
        try:
            state = await execute_service("publication_state", {"site_id": site})
            plan = await execute_service("publish_plan", {"site_id": site})
        except DomainError as error:
            literal_text(pane, "p", str(error), class_="muted pub-empty")
            return
        read = await execute_service("site_read", {"site_id": site})
        hidden = state["state"] == "private" or state["maintenance"]
        for name, value in {
            "pub_maintenance": state["maintenance"],
            "pub_state": state["state"] or "",
            "pub_plan": json.dumps([item["page_id"] for item in plan]),
            "pub_link": "",
            "pub_hours": "8",
            "pub_target": "site",
            "pub_rollback_version": "",
        }.items():
            pane.dataSetter("site." + name, value)
        for name in ("publish", "rollback", "private"):
            pane.dataFormula(
                f"site.pub_hide_{name}", f"p !== '{name}'", p="^site.pub_panel", _init=True
            )
        layout = pane.borderContainer(height="100%", class_="pub-tab")
        bar = layout.contentPane(region="top").div(class_="pub-bar")
        label, kind = publication_label(state)
        bar.span(label, class_="pub-chip pub-" + kind)
        if state["address"]:
            literal_text(
                bar, "a", state["address"] + "/", href=state["address"] + "/", target="_blank"
            )
        else:
            bar.span("No address yet", class_="muted")
        bar.span(publication_summary(state), class_="muted")
        actions = bar.div(class_="pub-actions")
        actions.button("Publish…").dataController(func="showPublish")
        actions.button("Rollback…", class_="button--secondary").dataController(func="showRollback")
        actions.button(
            "Maintenance off" if state["maintenance"] else "Maintenance on",
            class_="button--secondary",
        ).dataController(func="toggleMaintenance")
        actions.button("Private link", class_="button--secondary").dataController(
            func="showPrivate"
        )
        bar.span("^site.pub_message", role="status", class_="pub-message")
        if state["next_address"] or state["address_problem"]:
            note = layout.contentPane(region="bottom").div(class_="pub-note")
            literal_text(note, "span", address_note(state))
        stage = layout.contentPane(region="center", class_="pub-stage")
        self.publish_panel(stage, plan)
        self.rollback_panel(stage, read["pages"], site)
        self.private_panel(stage, state)
        if state["address"] and not hidden:
            stage.iframe(
                src=state["address"] + "/",
                sandbox="allow-scripts allow-same-origin allow-popups",
                title="Published site",
                class_="pub-frame",
            )
        else:
            box = stage.div(class_="pub-empty")
            literal_text(box, "p", stage_message(state))
            if state["address"]:
                box.button("Open with a private link").dataController(func="openPrivate")

    def publish_panel(self, stage, plan):
        panel = stage.div(class_="pub-panel", hidden="^site.pub_hide_publish")
        head = panel.div(class_="pub-panel-head")
        head.strong("Publish")
        head.button("Close", class_="button--quiet").dataController(func="closePanel")
        for index, item in enumerate(plan):
            stage.dataSetter(f"site.pub_sel.i{index}", item["selected"])
            row = panel.div(class_="pub-row")
            row.input(id=f"pub-{index}", type="checkbox", value=f"^site.pub_sel.i{index}")
            text = row.div()
            name = item["name"] or "(removed page)"
            text.html_label(f"{name} · {item['url']} · {item['state']}", for_=f"pub-{index}")
            for warning in item["warnings"]:
                literal_text(text, "div", "▲ " + warning, class_="pub-warning")
        panel.button("Publish selected pages").dataController(func="publishSelected")
        panel.div("Warnings never block Publish.", class_="muted pub-small")

    def rollback_panel(self, stage, pages, site):
        panel = stage.div(class_="pub-panel", hidden="^site.pub_hide_rollback")
        head = panel.div(class_="pub-panel-head")
        head.strong("Rollback")
        head.button("Close", class_="button--quiet").dataController(func="closePanel")
        menu = panel.select(value="^site.pub_target", aria_label="What to roll back")
        menu.option("Whole site", value="site")
        for page in pages:
            menu.option("Page: " + page["name"], value=page["id"])
        panel.div(class_="pub-versions").remote(
            "rollback_view", site=site, target="^site.pub_target"
        )
        panel.div(
            "Whole site: restores a saved source version and republishes its pages.",
            class_="muted pub-small",
        )

    @source(auth="editor")
    async def rollback_view(self, pane, site="", target="site"):
        try:
            if target == "site":
                versions = await execute_service("site_versions", {"site_id": site})
                online = {v["version_id"] for v in versions if v["is_latest"]}
            else:
                versions = await execute_service(
                    "page_versions", {"site_id": site, "page_id": target}
                )
                online = {v["version_id"] for v in versions if v["online"]}
        except DomainError as error:
            literal_text(pane, "p", str(error), class_="muted")
            return
        pane.dataSetter("site.pub_rollback_version", "")
        menu = pane.select(value="^site.pub_rollback_version", aria_label="Version")
        menu.option("Choose a version…", value="")
        for item in reversed(versions):
            mark = " · online" if item["version_id"] in online else ""
            menu.option(item["last_modified"][:19] + mark, value=item["version_id"])
        pane.button("Put online").dataController(func="rollbackChosen")

    def private_panel(self, stage, state):
        panel = stage.div(class_="pub-panel", hidden="^site.pub_hide_private")
        head = panel.div(class_="pub-panel-head")
        head.strong("Private link")
        head.button("Close", class_="button--quiet").dataController(func="closePanel")
        row = panel.div(class_="pub-row")
        menu = row.select(value="^site.pub_hours", aria_label="Validity")
        menu.option("valid 8 hours", value="8")
        menu.option("valid 7 days", value="168")
        row.button("Create link").dataController(func="createPrivateLink")
        panel.input(value="^site.pub_link", readonly=True, aria_label="Private link")
        panel.button("Copy", class_="button--secondary").dataController(func="copyPrivateLink")
        panel.div(
            "Shows the real site during maintenance or while the site is private."
            " Anyone with the link can open it until it expires.",
            class_="muted pub-small",
        )
        if state["state"] == "private":
            panel.button("Make public").dataController(func="makePublic")
        else:
            panel.button("Make private", class_="button--secondary").dataController(
                func="makePrivate"
            )

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
