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

import base64
import json
import re

from genro_bag import Bag
from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, execute_help, execute_service
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
        "content_translate",
        "translation_confirm",
        "site_languages_set",
        "site_server_set",
        "site_go_live",
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


TRANSLATION_MARKS = {
    "missing": "  ○ missing",
    "to_update": "  ↻ to update",
    "to_review": "  ◐ to review",
}


def translation_mark(content, language):
    """The mark of a content's translation in the language shown; none for the main one."""
    state = content["translations"].get(language)
    return TRANSLATION_MARKS.get(state["state"], "") if state else ""


def toolbar(frame):
    """The toolbar on top of a tab's frame: a Gramlot menu bar (d-gramlot-shell)."""
    return frame.top.menu(presentation="bar", iconSize=18, class_="tab-toolbar")


def language_select(parent, languages):
    """The language shown, when the site has more than one."""
    if len(languages) > 1:
        menu = parent.select(value="^site.language", aria_label="Language shown")
        for code in languages:
            menu.option(code.upper() + (" · main" if code == languages[0] else ""), value=code)


def pages_bag(read, language):
    """The Pages tree for the tree component: folders, pages, and slots under each page."""
    pages = {page["id"]: page for page in read["pages"]}
    contents = {content["id"]: content for content in read["contents"]}

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
                caption = (
                    f"{name} ← {contents[assigned]['name']}"
                    + translation_mark(contents[assigned], language)
                    if assigned
                    else f"{name} · empty"
                )
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


def contents_bag(read, language):
    bag = Bag()
    for content in read["contents"]:
        uses = content["uses"]
        caption = content["name"] + (f"  ({uses})" if uses > 1 else "")
        caption += translation_mark(content, language)
        bag.set_item(
            content["id"],
            None,
            caption=caption,
            kind="content",
            content=content["id"],
            unused=uses == 0,
        )
    return bag


def localized(item, languages, language):
    """The SEO tab's view of a page in a language: its own fields, URL without prefix."""
    base = {**item, "language": None, "languages": languages}
    if language in ("", languages[0]) or language not in languages:
        return base
    own = item["seo_languages"][language]
    return {
        **base,
        "language": language,
        "seo": own["seo"],
        "seo_effective": own["seo_effective"],
        "seo_inherited": own["seo_inherited"],
        "url": item["urls"][language].removeprefix("/" + language),
    }


def cost_line(chat, site_cost):
    """Tokens and cost of the chat and of the site, for information only (d-help-budget)."""
    site = f"site total ${site_cost:.2f}"
    if chat is None:
        return site
    usage = chat["usage"]
    tokens = (
        f"{(usage['input'] + usage['cache_write'] + usage['cache_read']) / 1000:.1f}k in"
        f" · {usage['output'] / 1000:.1f}k out"
    )
    cost = "cost unknown" if chat["cost"] is None else f"${chat['cost']:.2f}"
    return f"this chat {tokens} · {cost} · {site}"


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
        # Help me state lives here, so a refresh of the workspace keeps the chat open.
        for name, value in {
            "id": "",
            "version": 0,
            "help_open": False,
            "help_chat": "",
            "help_version": 0,
            "help_text": "",
            "help_busy": False,
            "help_message": "",
            "language": "",
            # The tab shown is page state too: a refresh keeps it.
            "tab": "visual",
        }.items():
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
            language="^site.language",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    @source(auth="editor")
    async def site_workspace(self, pane, site="", version=0, language=""):
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
        languages = read["languages"]
        if language not in languages:
            # The language shown is page state: set once, kept across refreshes.
            pane.dataSetter("site.language", languages[0])
            language = languages[0]
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
                {
                    c["id"]: {
                        "name": c["name"],
                        "text": c["text"],
                        "translations": c["translations"],
                    }
                    for c in read["contents"]
                }
            ),
            "main_language": languages[0],
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
            "editor_original": "",
            "editor_tab": "rich",
            "block_preview": "",
            "plan_json": "",
            "assign_slot": "",
            "assign_page": "",
            "assign_content": "",
            "new_content_name": "",
        }.items():
            pane.dataSetter("site." + name, value)
        pane.dataFormula("site.assign_hidden", "!slot", slot="^site.assign_slot", _init=True)
        pane.dataFormula(
            "site.editor_change",
            "text === original ? 'No changes' : 'Changed, not saved'",
            text="^site.editor_text",
            original="^site.editor_original",
            _init=True,
        )
        pane.dataSetter("site.pages_tree", pages_bag(read, language))
        pane.dataSetter("site.contents_tree", contents_bag(read, language))
        pane.dataController(func="initialize", _onBuilt=True)
        pane.dataController(
            func="renderPage", page="^site.page", slots="^site.show_slots", _onBuilt=True
        )
        layout = pane.borderContainer(height="100vh", class_="site-tab")
        pane.dataFormula("site.help_hidden", "!open", open="^site.help_open", _init=True)
        chat = layout.contentPane(
            region="right",
            width="380px",
            splitter=True,
            class_="help-pane",
            hidden="^site.help_hidden",
        )
        self.help_pane(chat, site)
        # Three tabs, each a frame with its own toolbar (d-gramlot-shell).
        tabs = layout.contentPane(region="center").tabContainer(
            height="100%", selectedPage="^site.tab", class_="site-tabs"
        )
        visual = tabs.contentPane(title="Visual editor", pageName="visual")
        frame = visual.framePane(height="100%", class_="tab-frame")
        bar = toolbar(frame)
        group = bar.menuline(group=True, overflowable=False)
        language_select(group, languages)
        group.html_label("Show slots", for_="show-slots")
        group.input(id="show-slots", type="checkbox", value="^site.show_slots")
        group.span("^site.status", class_="tab-crumb")
        group.span("^site.message", role="status", class_="tab-message")
        bar.spacer(flex=1)
        bar.menuline(caption="Help me", action="toggleHelp", overflowable=False)
        bar.menuline(
            caption="Take the site", action="takeSite", hidden="^site.editing", overflowable=False
        )
        bar.menuline(caption="Save", action="save", disabled="^site.busy", overflowable=False)
        self.visual_editor(frame.center, read["contents"])
        root = [p["id"] for p in read["pages"] if p["url"] == "/"]
        pane.dataSetter("site.seo_page", (root or [first_page])[0])
        pane.dataSetter("site.seo_version", 0)
        tabs.contentPane(title="SEO", pageName="seo", overflow="hidden").remote(
            "seo_panel",
            site=site,
            page_id="^site.seo_page",
            version="^site.seo_version",
            language=language,
        )
        pane.dataSetter("site.pub_version", 0)
        pane.dataSetter("site.pub_panel", "")
        pane.dataSetter("site.pub_message", "")
        # Outside the stage: a go live rebuilds the stage and its result must stay.
        pane.dataSetter("site.gl_result", "")
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
        center = layout.contentPane(region="center", class_="site-stage")
        stage = center.div(class_="stage-box")
        stage.iframe(
            srcdoc="^site.preview",
            sandbox="allow-scripts",
            title="Page preview",
            class_="site-preview",
        )
        self.block_window(pane, center)

    def block_window(self, pane, center):
        """The block in Gramlot's floating window (d-block-editing, d-gramlot-shell): a title
        bar, and a frame with the tabs Preview, Jodit, HTML and CSS and a footer bar."""
        window = pane.floatingPane(
            title="^site.editor_title",
            open="^site.editor_open",
            beforeClose="blockBeforeClose",
            movable=True,
            resizable=True,
            collapsible=True,
            maximizable=True,
            width="760px",
            height="86vh",
            top="48px",
            left="calc(100vw - 800px)",
            minWidth="460px",
            minHeight="320px",
        )
        frame = window.frame
        pane.dataFormula("site.editor_main_hidden", "!main", main="^site.editor_main", _init=True)
        original = frame.top.div(class_="editor-main", hidden="^site.editor_main_hidden")
        original.span("Main language", class_="muted")
        original.htmlPreview(value="^site.editor_main", height="96px")
        tabs = frame.center.tabContainer(height="100%", selectedPage="^site.editor_tab")
        # Preview: the block inside the chain of elements that holds its slot, with the
        # page's style sheets; built in Logic (blockPreviewHtml).
        tabs.contentPane(title="Preview", pageName="preview", overflow="hidden").iframe(
            srcdoc="^site.block_preview",
            sandbox="allow-scripts",
            title="Block preview",
            class_="block-preview",
        )
        tabs.contentPane(
            title="Jodit", pageName="rich", overflow="hidden", class_="block-editor-pane"
        ).htmlEditor(value="^site.editor_text", height="100%", class_="block-rich")
        tabs.contentPane(
            title="HTML", pageName="html", overflow="hidden", class_="block-editor-pane"
        ).codeMirror(value="^site.editor_text", language="html", height="100%")
        tabs.contentPane(title="CSS", pageName="css", class_="block-css").p(
            "The rules acting on this block come here.", class_="muted"
        )
        frame.bottom.div(class_="update-plan").remote("plan_view", plan="^site.plan_json")
        bar = frame.bottom.menu(presentation="bar", class_="tab-toolbar block-footer")
        group = bar.menuline(group=True, overflowable=False)
        group.span("^site.editor_change", class_="tab-crumb")
        group.span("^site.editor_note", class_="tab-crumb")
        bar.spacer(flex=1)
        pane.dataFormula(
            "site.confirm_hidden", "state !== 'to_review'", state="^site.editor_state", _init=True
        )
        bar.menuline(
            caption="Confirm translation",
            action="confirmTranslation",
            hidden="^site.confirm_hidden",
            overflowable=False,
        )
        bar.menuline(caption="Cancel", action="closeEditor", overflowable=False)
        bar.menuline(
            caption="Save", action="saveContent", disabled="^site.busy", overflowable=False
        )
        pane.dataController(func="styleBlockEditor", tab="^site.editor_tab")

    @source(auth="editor")
    async def seo_panel(self, pane, site="", page_id="", version=0, language=""):
        read = await execute_service("site_read", {"site_id": site})
        problems = await execute_service("seo_check", {"site_id": site})
        pages = {item["id"]: item for item in read["pages"]}
        if page_id not in pages:
            pane.p("This site has no page yet.", class_="muted seo-empty")
            return
        item = localized(pages[page_id], read["languages"], language)
        images = {a["id"]: a["name"] for a in read["assets"] if a["mime_type"].startswith("image/")}
        frame = pane.framePane(height="100%", class_="tab-frame seo-tab")
        bar = toolbar(frame)
        group = bar.menuline(group=True, overflowable=False)
        language_select(group, read["languages"])
        self.seo_summary(group, problems)
        bar.spacer(flex=1)
        layout = frame.center.borderContainer(height="100%")
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
        main = item["language"] is None
        root_fields = ROOT_FIELDS if main else tuple(f for f in ROOT_FIELDS if f != "origin")
        fields = [*root_fields, *PAGE_FIELDS] if is_root else list(PAGE_FIELDS)
        initial = {
            "page": item["id"],
            "language": item["language"],
            "languages": ", ".join(item["languages"]),
            "url": item["url"],
            "fields": {name: stored.get(name, "") for name in dict.fromkeys(fields)},
            "images": [{"image": i["image"], "alt": i["alt"] or ""} for i in item["images"]],
        }
        pane.dataSetter("site.seo_initial", json.dumps(initial))
        pane.dataSetter("site.seo_message", "")
        pane.dataSetter("site.seo.url", item["url"])
        pane.dataSetter("site.seo.languages", initial["languages"])
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
            if main:
                hint = "Main language first, such as it, en, de"
                row(box, "Languages", "languages", hint)
            row(box, "Site name", "site_name", "Empty: " + inherited["site_name"])
            if main:
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

    def help_pane(self, pane, site):
        layout = pane.borderContainer(height="100%")
        layout.contentPane(region="center", overflow="auto").remote(
            "help_panel", site=site, chat_id="^site.help_chat", version="^site.help_version"
        )
        footer = layout.contentPane(region="bottom", class_="help-footer")
        footer.textarea(
            value="^site.help_text",
            placeholder="Tell Help me what to do…",
            aria_label="Message to Help me",
        )
        row = footer.div(class_="help-row")
        row.button("Send", disabled="^site.help_busy").dataController(func="helpSend")
        row.span("^site.help_message", role="status", class_="muted help-status")

    @source(auth="editor")
    async def help_panel(self, pane, site="", chat_id="", version=0):
        try:
            listing = await execute_help("chats", {"site_id": site})
            chat = (
                await execute_help("chat", {"site_id": site, "chat_id": chat_id})
                if chat_id
                else None
            )
        except DomainError as error:
            literal_text(pane, "p", str(error), class_="muted help-empty")
            return
        head = pane.div(class_="help-head")
        head.strong("Help me")
        menu = head.select(value="^site.help_chat", aria_label="Chat")
        menu.option("New chat", value="")
        for item in reversed(listing["chats"]):
            menu.option(item["title"], value=item["chat_id"])
        head.button("Close", class_="button--quiet").dataController(func="toggleHelp")
        log = pane.div(class_="help-log")
        if chat is None:
            log.p(
                "Say what the site is for, or what to change. Help me builds it with you;"
                " publishing stays with you.",
                class_="muted",
            )
        else:
            self.help_items(log, chat["items"])
        literal_text(pane, "div", cost_line(chat, listing["site_cost"]), class_="help-cost")

    def help_items(self, log, items):
        actions = []
        for item in [*items, {"kind": "end"}]:
            if item["kind"] == "action":
                actions.append(("✓ " if item["ok"] else "✗ ") + item["name"])
                continue
            if actions:
                literal_text(log, "div", " · ".join(actions), class_="help-actions")
                actions = []
            if item["kind"] in ("user", "assistant"):
                literal_text(log, "div", item["text"], class_="help-msg help-" + item["kind"])
            elif item["kind"] == "choices":
                box = log.div(class_="help-msg help-assistant")
                literal_text(box, "div", item["question"])
                cards = box.div(class_="help-choices")
                for choice in item["choices"]:
                    self.choice_card(cards, item["kind_of_choice"], choice)

    def choice_card(self, cards, kind, choice):
        # A native button holds the drawing (gramlot-button shows its text only); the click
        # sends the label, read from `title`, as the next message.
        card = cards.html_button(
            class_="help-choice", title=choice["label"], type="button", connect_onclick="helpPick"
        )
        if kind == "palette":
            strip = card.span(class_="help-swatches")
            for color in choice["colors"]:
                strip.span(style=f"background:{color}")
        elif kind == "fonts":
            literal_text(card, "span", "Aa Title", style=f"font-family:{choice['heading']}")
            literal_text(card, "span", "Body text", style=f"font-family:{choice['body']}")
        else:
            encoded = base64.b64encode(choice["svg"].encode("utf-8")).decode("ascii")
            card.img(src="data:image/svg+xml;base64," + encoded, alt=choice["label"])
        literal_text(card, "span", choice["label"], class_="muted")

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
            "pub_plan": json.dumps([item["entry"] for item in plan]),
            "pub_link": "",
            "pub_hours": "8",
            "pub_target": "site",
            "pub_rollback_version": "",
        }.items():
            pane.dataSetter("site." + name, value)
        for name in ("publish", "rollback", "private", "golive"):
            pane.dataFormula(
                f"site.pub_hide_{name}", f"p !== '{name}'", p="^site.pub_panel", _init=True
            )
        frame = pane.framePane(height="100%", class_="tab-frame pub-tab")
        bar = toolbar(frame)
        group = bar.menuline(group=True, overflowable=False)
        label, kind = publication_label(state)
        group.span(label, class_="pub-chip pub-" + kind)
        if state["address"]:
            literal_text(
                group, "a", state["address"] + "/", href=state["address"] + "/", target="_blank"
            )
        else:
            group.span("No address yet", class_="tab-crumb")
        group.span(publication_summary(state), class_="tab-crumb")
        group.span("^site.pub_message", role="status", class_="tab-message")
        bar.spacer(flex=1)
        for caption, action in (
            ("Publish…", "showPublish"),
            ("Rollback…", "showRollback"),
            ("Maintenance off" if state["maintenance"] else "Maintenance on", "toggleMaintenance"),
            ("Private link", "showPrivate"),
            ("Go live…", "showGoLive"),
        ):
            bar.menuline(caption=caption, action=action, overflowable=False)
        layout = frame.center.borderContainer(height="100%")
        if state["next_address"] or state["address_problem"]:
            note = layout.contentPane(region="bottom").div(class_="pub-note")
            literal_text(note, "span", address_note(state))
        stage = layout.contentPane(region="center", class_="pub-stage")
        self.publish_panel(stage, plan)
        self.rollback_panel(stage, read["pages"], site, read["languages"])
        self.private_panel(stage, state)
        servers = await execute_service("server_list", {})
        self.golive_panel(pane, stage, site, read, servers)
        if state["address"] and not hidden:
            stage.div(class_="stage-box").iframe(
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
            else:
                box.button("Go live…").dataController(func="showGoLive")

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

    def rollback_panel(self, stage, pages, site, languages):
        panel = stage.div(class_="pub-panel", hidden="^site.pub_hide_rollback")
        head = panel.div(class_="pub-panel-head")
        head.strong("Rollback")
        head.button("Close", class_="button--quiet").dataController(func="closePanel")
        menu = panel.select(value="^site.pub_target", aria_label="What to roll back")
        menu.option("Whole site", value="site")
        for page in pages:
            for code in languages:
                # The main language's entry is the page id; the others add their code.
                entry = page["id"] if code == languages[0] else f"{page['id']}.{code}"
                suffix = f" · {code.upper()}" if len(languages) > 1 else ""
                menu.option("Page: " + page["name"] + suffix, value=entry)
        panel.div(class_="pub-versions").remote(
            "rollback_view", site=site, target="^site.pub_target"
        )
        panel.div(
            "Whole site: restores a saved source version and republishes its pages.",
            class_="muted pub-small",
        )

    def golive_panel(self, pane, stage, site, read, servers):
        """The first publication, or a move, step by step (proposal, First publication)."""
        root = next((p for p in read["pages"] if p["url"] == "/"), None)
        origin = (root or {}).get("seo_effective", {}).get("origin", "")
        host = origin.partition("://")[2]
        bare = host.removeprefix("www.")
        current = read.get("server", "")
        for name, value in {
            "gl_root": root["id"] if root else "",
            "gl_server": current or (servers[0]["name"] if servers else ""),
            "gl_domain": bare,
            "gl_canonical": "www" if host.startswith("www.") else "bare",
            "gl_dns_version": 0,
        }.items():
            pane.dataSetter("site." + name, value)
        panel = stage.div(class_="pub-panel golive", hidden="^site.pub_hide_golive")
        head = panel.div(class_="pub-panel-head")
        head.strong("Go live")
        head.button("Close", class_="button--quiet").dataController(func="closePanel")
        one = panel.fieldset(class_="gl-step")
        one.legend("1 · Server")
        if not servers:
            one.p("No server is registered: register one with server_add.", class_="muted")
        menu = one.select(value="^site.gl_server", aria_label="Server")
        for server in servers:
            addresses = ", ".join(server["ipv4"] + server["ipv6"])
            menu.option(f"{server['name']} · {addresses}", value=server["name"])
        two = panel.fieldset(class_="gl-step")
        two.legend("2 · Address")
        two.input(value="^site.gl_domain", placeholder="bottega.example", aria_label="Domain")
        choice = two.select(value="^site.gl_canonical", aria_label="Address")
        choice.option("the domain; www answers 301", value="bare")
        choice.option("www.; the domain answers 301", value="www")
        two.button("Save server and address").dataController(func="goLiveSave")
        three = panel.fieldset(class_="gl-step")
        three.legend("3 · DNS records")
        three.div().remote("dns_view", site=site, version="^site.gl_dns_version")
        three.button("Check again", class_="button--secondary").dataController(func="goLiveCheck")
        four = panel.fieldset(class_="gl-step")
        four.legend("4 · Publish and certificate")
        four.button("Publish and go live").dataController(func="goLiveRun")
        four.div("^site.gl_result", class_="gl-result")

    @source(auth="editor")
    async def dns_view(self, pane, site="", version=0):
        try:
            checked = await execute_service("dns_check", {"site_id": site})
        except DomainError as error:
            literal_text(pane, "p", str(error), class_="muted")
            return
        table = pane.table(class_="gl-dns")
        head = table.tr()
        for title in ("Name", "Type", "Value", "Seen"):
            head.th(title)
        marks = {"ok": "✓", "missing": "✗ not found", "unknown": "? no answer"}
        for record in checked["records"]:
            row = table.tr()
            literal_text(row, "td", record["name"])
            row.td(record["type"])
            literal_text(row, "td", ", ".join(record["expected"]))
            seen = marks.get(record["state"])
            if seen is None:
                found = sorted({v for vs in record["answers"].values() for v in vs or []})
                seen = "✗ " + ", ".join(found)
            literal_text(row, "td", seen, class_="gl-" + record["state"])

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
    async def help_call(self, call, arguments):
        if call not in ("chats", "chat", "send"):
            raise DomainError("invalid_operation", "Unknown Help me call")
        if not isinstance(arguments, dict):
            raise DomainError("invalid_input", "Help me arguments must be an object")
        try:
            return {"ok": True, "result": await execute_help(call, arguments)}
        except DomainError as error:
            return {"ok": False, "error": error.as_dict()}

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
