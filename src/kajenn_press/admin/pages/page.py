"""Page editor: every block the template declares, beside a scaled live preview."""

import json

from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, execute_read, execute_service
from kajenn_press.admin.views import AdminPage, literal_text, scaled_preview
from kajenn_press.domain import DomainError

LIVE_DELAY = 800  # ms after the last edit before a draft render
COMMANDS = frozenset({"draft_save", "variant_create", "render_draft", "readiness"})
EDITORS = {
    "html": (("Rich text · Jodit", "htmlEditor"), ("HTML source", "codeMirror")),
    "markdown": (("Markdown", "markdownEditor"), ("Markdown source", "codeMirror")),
}


class Page(AdminPage):
    title = "Page"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {"site": "", "content": "", "language": "", "version": 0}.items():
            root.dataSetter(f"page.{name}", value)
        root.dataController(
            "var q=new URLSearchParams(window.location.search);"
            "this.SET('page.site',q.get('site')||'');"
            "this.SET('page.content',q.get('content')||'');",
            _onStart=True,
        )
        root.div(class_="page-editor-host").remote(
            "editor",
            site="^page.site",
            content="^page.content",
            language="^page.language",
            version="^page.version",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    async def page_records(self, site, content):
        """The content and its language variants, refused when they are not in the site."""
        record = await execute_read("record_read", record_id=content)
        if record["kind"] != "content" or record["scope"] != "site:" + site:
            raise DomainError("forbidden", "Page does not belong to this site")
        records = await execute_read("records_index", scope="site:" + site)
        variants = {
            r["attributes"]["language"]: r
            for r in records
            if r["kind"] == "variant" and r["attributes"]["content_id"] == content
        }
        return record, variants

    @source(auth="editor")
    async def editor(self, pane, site="", content="", language="", version=0):
        if not site or not content:
            pane.p("Select a page in the navigation.")
            return
        try:
            record, variants = await self.page_records(site, content)
            if not variants:
                raise DomainError("not_found", "This page has no language variant yet")
            site_record = await execute_read("record_read", record_id=site)
            language = language if language in variants else min(variants)
            variant = await execute_read("record_read", record_id=variants[language]["record_id"])
            attrs = variant["attributes"]
            dependencies = await execute_service(
                "dependencies", {"record_id": variant["record_id"]}
            )
            template = next(
                r
                for r in dependencies["dependencies"]
                if r["revision_id"] == attrs["template_revision"]
            )
            declarations = template["attributes"]["blocks"]
            # The page keeps its exact template revision until it is saved against a newer one.
            latest = await execute_read("record_read", record_id=template["record_id"])
            history = await execute_read("revision_index", record_id=variant["record_id"])
            rights = await execute_read("scope_capabilities", scope="site:" + site)
        except DomainError as error:
            pane.p(str(error), role="status")
            return
        writable = all(p in rights["permissions"] for p in ("write", "use"))
        for name, value in {
            "language": language,
            "variant_id": variant["record_id"],
            "variant_generation": variant["generation"],
            "variant_revision": variant["revision_id"],
            "template_revision": attrs["template_revision"],
            "template_id": template["record_id"],
            "latest_template": latest["revision_id"],
            "latest_declarations": json.dumps(latest["attributes"]["blocks"]),
            "content_id": content,
            "declarations": json.dumps(declarations),
            "writable": writable,
            "busy": False,
            "dirty": False,
            "message": "",
            "preview": "",
            "live_status": "The preview follows your edits after a short pause.",
            "load_revision": "",
            "new_language": "",
            "block_tab": next(iter(declarations), ""),
        }.items():
            pane.dataSetter("page." + name, value)
        for name in declarations:
            pane.dataSetter(
                "draft.blocks." + name,
                variant["sources"].get("block." + name, {"text": ""})["text"],
            )
        blocks = {f"b{index}": "^draft.blocks." + name for index, name in enumerate(declarations)}
        # _onBuilt: the parent pane is mounted, so initialize can register its dispose.
        pane.dataController(func="initialize", _onBuilt=True)
        pane.dataController(func="changed", **blocks)
        pane.dataController(func="livePreview", _delay=LIVE_DELAY, **blocks)
        layout = pane.borderContainer(height="100vh", class_="page-editor")
        top = layout.contentPane(region="top", class_="page-toolbar")
        heading = top.div(class_="page-heading")
        literal_text(heading, "p", site_record["attributes"]["name"], class_="breadcrumb")
        literal_text(heading, "h1", record["attributes"]["title"])
        heading.html_label("Language", for_="page-language")
        select = heading.select(id="page-language", value="^page.language", disabled="^page.dirty")
        for code in sorted(variants):
            select.option(code, value=code)
        actions = top.div(class_="page-actions")
        locked = "^page.busy" if writable else True
        actions.button("Save", disabled=locked).dataController(func="save")
        actions.button("Revert", disabled="^page.busy", class_="button--secondary").dataController(
            func="revert"
        )
        revisions = actions.select(value="^page.load_revision", aria_label="Revisions")
        revisions.option("Revisions…", value="")
        for item in history:
            revisions.option(f"Revision {item['generation']}", value=item["revision_id"])
        actions.button(
            "Load revision", disabled="^page.busy", class_="button--secondary"
        ).dataController(func="loadRevision")
        actions.button(
            "Open template",
            disabled=template["scope"] != "site:" + site,
            class_="button--secondary",
        ).dataController(func="openTemplate")
        actions.button(
            "Readiness", disabled="^page.busy", class_="button--secondary"
        ).dataController(func="readiness")
        if latest["revision_id"] != attrs["template_revision"]:
            actions.span(
                f"Template revision {template['generation']} · latest {latest['generation']}",
                class_="status",
            )
            if writable:
                actions.button(
                    "Use latest template", disabled="^page.busy", class_="button--secondary"
                ).dataController(func="useLatestTemplate")
        missing = [code for code in site_record["attributes"]["languages"] if code not in variants]
        if missing and writable:
            pane.dataSetter("page.new_language", missing[0])
            add = actions.select(value="^page.new_language", aria_label="New language")
            for code in missing:
                add.option(code, value=code)
            actions.button(
                "Add language", disabled="^page.busy", class_="button--secondary"
            ).dataController(func="addLanguage")
        pane.dataFormula(
            "page.status", "dirty ? 'Unsaved changes' : 'Saved'", dirty="^page.dirty", _init=True
        )
        status = top.div(class_="page-status")
        status.span("^page.status", class_="status")
        status.span("^page.message", role="status", class_="page-message")
        if not writable:
            status.span("Your current permissions allow viewing only.", class_="muted")
        center = layout.contentPane(region="center", class_="page-blocks")
        tabs = center.tabContainer(selectedPage="^page.block_tab", height="100%")
        for name, declaration in declarations.items():
            fmt = declaration["format"]
            label = name + (" · required" if declaration["required"] else "") + " · " + fmt
            block = tabs.contentPane(title=label, pageName=name, padding="12px")
            views = block.tabContainer(height="100%", tabMode="underline")
            for title, editor in EDITORS[fmt]:
                view = views.contentPane(title=title, pageName=editor)
                options = {"language": fmt} if editor == "codeMirror" else {}
                getattr(view, editor)(
                    value="^draft.blocks." + name,
                    height="100%",
                    readonly=not writable,
                    **options,
                )
        right = layout.contentPane(
            region="right", splitter=True, width="50%", minSize=320, class_="page-preview"
        )
        scaled_preview(right, "page", "page.live_status")

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
