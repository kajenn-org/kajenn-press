"""A complete first authoring path over common editorial and rendering services."""

from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, execute_read, execute_service
from kajenn_press.admin.views import AdminPage, literal_text
from kajenn_press.domain import DomainError

BLOCKS = {"body": {"format": "html", "required": True}}
TEMPLATE = """def build(source, data):
    page = source.html(lang="^language")
    head = page.head()
    head.meta(charset="utf-8")
    head.title("^page.title")
    head.style("body {font: 18px system-ui; max-width: 850px; margin: 48px auto; padding: 24px; color: #24334b;} h1 {color: #315f85;}")
    body = page.body()
    body.h1("^page.title")
    body.main("^blocks.body")
"""
COMMANDS = frozenset(
    {"resource_save", "content_create", "variant_create", "draft_save", "render_preview"}
)


class Page(AdminPage):
    title = "New page"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        root.dataController(
            "var q=new URLSearchParams(window.location.search);"
            "this.SET('author.site',q.get('site')||'');"
            "this.SET('author.open',q.get('variant')||'');"
            "this.SET('author.template',q.get('template')||'');",
            _onStart=True,
        )
        root.div().remote(
            "editor", site="^author.site", variant="^author.open", template_id="^author.template"
        )

    @source(auth="editor")
    async def editor(self, pane, site="", variant="", template_id=""):
        if not site:
            pane.p("Choose a site to start.")
            return
        try:
            site_record = await execute_read("record_read", record_id=site)
            if site_record["kind"] != "site":
                raise DomainError("invalid_input", "Expected a site")
            rights = await execute_read("scope_capabilities", scope="site:" + site)
            writable = all(p in rights["permissions"] for p in ("write", "use"))
            draft = {
                "site": site,
                "template_name": "New page template",
                "source": TEMPLATE,
                "template_id": "",
                "template_generation": 0,
                "template_revision": "",
                "title": "New page",
                "language": site_record["attributes"]["languages"][0],
                "body": "<p>Write your page content here.</p>",
                "content_id": "",
                "variant_id": "",
                "variant_generation": 0,
                "variant_revision": "",
                "dependencies": [],
                "template_scope": "site:" + site,
            }
            template = None
            if variant:
                record = await execute_read("record_read", record_id=variant)
                if record["kind"] != "variant" or record["scope"] != "site:" + site:
                    raise DomainError("forbidden", "Page does not belong to this site")
                attrs = record["attributes"]
                content = await execute_read("record_read", record_id=attrs["content_id"])
                dependencies = await execute_service("dependencies", {"record_id": variant})
                template = next(
                    (
                        r
                        for r in dependencies["dependencies"]
                        if r["revision_id"] == attrs["template_revision"]
                    ),
                    None,
                )
                draft.update(
                    title=content["attributes"]["title"],
                    language=attrs["language"],
                    body=record["sources"].get("block.body", {"text": ""})["text"],
                    content_id=content["record_id"],
                    variant_id=variant,
                    variant_generation=record["generation"],
                    variant_revision=record["revision_id"],
                )
            elif template_id:
                template = await execute_read("record_read", record_id=template_id)
            if variant or template_id:
                if (
                    template is None
                    or template["attributes"].get("blocks") != BLOCKS
                    or template["attributes"].get("engine") != "gramlot"
                ):
                    raise DomainError(
                        "invalid_input",
                        "This first editor supports Gramlot templates with one required HTML block named body. Other templates remain available in the browser.",
                    )
                if template["scope"] != "site:" + site:
                    raise DomainError(
                        "invalid_input",
                        "Copy this shared template into the site before editing it here.",
                    )
                draft.update(
                    template_name=template["attributes"]["name"],
                    source=template["sources"]["source"]["text"],
                    template_id=template["record_id"],
                    template_generation=template["generation"],
                    template_revision=template["revision_id"],
                    dependencies=template["attributes"]["dependencies"],
                )
            for name, value in draft.items():
                pane.dataSetter("draft." + name, value)
            for name, value in {
                "busy": False,
                "message": "",
                "dirty": False,
                "preview": "",
                "refresh": 0,
            }.items():
                pane.dataSetter("author." + name, value)
            # _onBuilt: the parent pane is mounted, so initialize can register its dispose.
            pane.dataController(func="initialize", _onBuilt=True)
            pane.dataController(
                func="changed",
                template_name="^draft.template_name",
                source="^draft.source",
                title="^draft.title",
                language="^draft.language",
                body="^draft.body",
                template_revision="^draft.template_revision",
            )
            page = pane.main(class_="author-page")
            literal_text(page, "p", site_record["attributes"]["name"], class_="breadcrumb")
            page.h1("Create a template. Write your page.")
            page.p(
                "Start with this working Gramlot template, replace the sample text in Jodit, then save and render your page. Nothing is published automatically."
            )
            page.p(
                "This first workspace uses one HTML content block named body. Full multi-block and Markdown editing will follow.",
                class_="muted",
            )
            if not writable:
                page.p("Your current permissions allow viewing only.", role="status")
            actions = page.div(class_="author-actions")
            actions.button(
                "Save template", disabled=("^author.busy" if writable else True)
            ).dataController(func="saveTemplate")
            actions.button(
                "Save page", disabled=("^author.busy" if writable else True)
            ).dataController(func="savePage")
            actions.button("Render saved page", disabled="^author.busy").dataController(
                func="preview"
            )
            page.dataFormula(
                "author.new_url",
                "'author?site='+site+(template ? '&template='+template : '')",
                site="^draft.site",
                template="^draft.template_id",
            )
            actions.a("Start another page", href="^author.new_url")
            page.p("^author.message", role="status", class_="author-message")
            page.dataFormula(
                "author.status", "dirty ? 'Unsaved changes' : 'Saved'", dirty="^author.dirty"
            )
            page.p("^author.status", class_="muted")
            page.dataFormula(
                "author.title_locked",
                "busy || !!saved",
                busy="^author.busy",
                saved="^draft.content_id",
            )
            page.dataFormula(
                "author.language_locked",
                "busy || !!saved",
                busy="^author.busy",
                saved="^draft.variant_id",
            )
            tabs = page.tabContainer(selectedPage="^author.tab", height="670px")
            page.dataSetter("author.tab", "template")
            template_pane = tabs.contentPane(
                title="1 · Gramlot template", pageName="template", padding="18px", overflow="auto"
            )
            template_pane.html_label("Template name", for_="template-name")
            template_pane.input(
                id="template-name", value="^draft.template_name", live=True, readonly=not writable
            )
            template_pane.p(
                "The template controls the layout. ^page.title inserts the page title; ^blocks.body inserts the HTML written in the Content tab.",
                class_="muted",
            )
            template_pane.codeMirror(
                value="^draft.source", language="python", height="450px", readonly=not writable
            )
            content_pane = tabs.contentPane(
                title="2 · Content", pageName="content", padding="18px", overflow="auto"
            )
            content_pane.html_label("Page title", for_="page-title")
            content_pane.input(
                id="page-title",
                value="^draft.title",
                live=True,
                readonly=(True if not writable else "^author.title_locked"),
            )
            content_pane.html_label("Language", for_="page-language")
            select = content_pane.select(
                id="page-language",
                value="^draft.language",
                disabled=(True if not writable else "^author.language_locked"),
            )
            for language in site_record["attributes"]["languages"]:
                select.option(language, value=language)
            content_pane.p("Content block: body · HTML", class_="muted")
            content_pane.dataSetter("author.content_view", "rich")
            editors = content_pane.tabContainer(selectedPage="^author.content_view", height="440px")
            editors.contentPane(title="Rich text · Jodit", pageName="rich").htmlEditor(
                value="^draft.body", height="380px", readonly=not writable
            )
            editors.contentPane(title="HTML source", pageName="code").codeMirror(
                value="^draft.body", language="html", height="380px", readonly=not writable
            )
            preview = tabs.contentPane(
                title="3 · Rendered page", pageName="preview", padding="18px", overflow="auto"
            )
            preview.p(
                "Render uses the saved template and content revisions. Scripts and external resources are restricted in this quick preview; publication preview is a separate step.",
                class_="muted",
            )
            preview.htmlPreview(value="^author.preview", height="550px")
            page.h2("Your templates and pages")
            page.div().remote("saved_pages", site=site, refresh="^author.refresh")
        except DomainError as error:
            pane.p(str(error), role="status")

    @source(auth="editor")
    async def saved_pages(self, pane, site, refresh=0):
        records = await execute_read("records_index", scope="site:" + site)
        titles = {
            r["record_id"]: r["attributes"].get("title", "Page")
            for r in records
            if r["kind"] == "content"
        }
        pane.h3("Use a saved template for a new page")
        templates = pane.ul()
        for record in records:
            if (
                record["kind"] == "template"
                and record["attributes"].get("engine") == "gramlot"
                and record["attributes"].get("blocks") == BLOCKS
            ):
                literal_text(
                    templates.li(),
                    "a",
                    record["attributes"]["name"],
                    href="author?site=" + site + "&template=" + record["record_id"],
                )
        pane.a("Create another template", href="author?site=" + site)
        pane.h3("Reopen a saved page")
        links = pane.ul()
        for record in records:
            if record["kind"] == "variant":
                attrs = record["attributes"]
                literal_text(
                    links.li(),
                    "a",
                    titles.get(attrs["content_id"], "Page") + " · " + attrs["language"],
                    href="author?site=" + site + "&variant=" + record["record_id"],
                )

    @endpoint(auth="editor")
    async def command(self, operation, arguments):
        if operation not in COMMANDS:
            raise DomainError("invalid_operation", "Command unavailable in this workspace")
        if not isinstance(arguments, dict):
            raise DomainError("invalid_input", "Command arguments must be an object")
        try:
            return {"ok": True, "result": await execute_service(operation, arguments)}
        except DomainError as error:
            return {"ok": False, "error": error.as_dict()}
