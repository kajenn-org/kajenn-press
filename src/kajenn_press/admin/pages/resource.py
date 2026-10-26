"""Resource editor: templates, CSS, JavaScript and media, beside a sample page that uses them."""

import json

from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, execute_read, execute_service
from kajenn_press.admin.views import AdminPage, caption, literal_text, scaled_preview
from kajenn_press.domain import DomainError

LIVE_DELAY = 800  # ms after the last edit before a draft render
COMMANDS = frozenset({"resource_save", "media_save", "render_draft"})
LANGUAGES = {"template": "python", "css": "css", "javascript": "javascript"}
RESOURCE_KINDS = frozenset({"template", "css", "javascript", "media"})
DEPENDENCY_KINDS = ("css", "javascript", "media")
SAMPLE_LIMIT = 50  # variants examined when looking for sample pages


class Page(AdminPage):
    title = "Resource"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {"site": "", "record": ""}.items():
            root.dataSetter(f"res.{name}", value)
        root.dataController(
            "var q=new URLSearchParams(window.location.search);"
            "this.SET('res.site',q.get('site')||'');"
            "this.SET('res.record',q.get('record')||'');",
            _onStart=True,
        )
        root.div(class_="page-editor-host").remote(
            "editor",
            site="^res.site",
            record="^res.record",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    async def revisions_by_id(self, scopes):
        """Revision ID -> (record ID, dependencies) for every resource revision in the scopes."""
        revisions = {}
        for scope in scopes:
            for record in await execute_read("records_index", scope=scope):
                if record["kind"] in RESOURCE_KINDS:
                    for item in await execute_read("revision_index", record_id=record["record_id"]):
                        revisions[item["revision_id"]] = (
                            record["record_id"],
                            item["attributes"].get("dependencies", []),
                        )
        return revisions

    async def sample_pages(self, site, record_id, records):
        """Variants whose exact dependency closure contains a revision of the resource."""
        revisions = await self.revisions_by_id(("site:" + site, "library"))
        titles = {r["record_id"]: caption(r) for r in records if r["kind"] == "content"}
        samples = []
        variants = [r for r in records if r["kind"] == "variant"][:SAMPLE_LIMIT]
        for variant in variants:
            pending, seen, used = [variant["attributes"]["template_revision"]], set(), None
            while pending and used is None:
                revision = pending.pop()
                if revision in seen or revision not in revisions:
                    continue
                seen.add(revision)
                owner, dependencies = revisions[revision]
                if owner == record_id:
                    used = revision
                pending.extend(dependencies)
            if used:
                attrs = variant["attributes"]
                samples.append(
                    {
                        "label": titles.get(attrs["content_id"], "Page")
                        + " · "
                        + attrs["language"],
                        "variant_id": variant["record_id"],
                        "variant_revision": variant["revision_id"],
                        "resource_revision": used,
                    }
                )
        return sorted(samples, key=lambda item: item["label"].casefold())

    @source(auth="editor")
    async def editor(self, pane, site="", record=""):
        if not site or not record:
            pane.p("Select a resource in the navigation.")
            return
        try:
            resource = await execute_read("record_read", record_id=record)
            if resource["kind"] not in RESOURCE_KINDS or resource["scope"] != "site:" + site:
                raise DomainError("forbidden", "Resource does not belong to this site")
            site_record = await execute_read("record_read", record_id=site)
            records = await execute_read("records_index", scope="site:" + site)
            samples = await self.sample_pages(site, record, records)
            history = await execute_read("revision_index", record_id=record)
            rights = await execute_read("scope_capabilities", scope="site:" + site)
            choices = []
            if resource["kind"] == "template":
                library = await execute_read("records_index", scope="library")
                choices = await self.dependency_choices(
                    [r for r in records + library if r["kind"] in DEPENDENCY_KINDS]
                )
        except DomainError as error:
            pane.p(str(error), role="status")
            return
        kind, attrs = resource["kind"], resource["attributes"]
        writable = all(p in rights["permissions"] for p in ("write", "use"))
        for name, value in {
            "kind": kind,
            "scope": resource["scope"],
            "record_id": record,
            "generation": resource["generation"],
            "revision_id": resource["revision_id"],
            "engine": attrs.get("engine", ""),
            "mime_type": attrs.get("mime_type", ""),
            "samples": json.dumps(samples),
            "sample": "0" if samples else "",
            "writable": writable,
            "busy": False,
            "dirty": False,
            "message": "",
            "preview": "",
            "live_status": "Choose a sample page to see this resource rendered."
            if samples
            else "No page of this site uses this resource yet.",
            "load_revision": "",
            "tab": "source",
        }.items():
            pane.dataSetter("res." + name, value)
        pane.dataSetter("draft.name", attrs["name"])
        # Dependencies this editor does not list (all of them outside templates) are kept as they are.
        listed = set().union(*(choice["revision_ids"] for choice in choices))
        pane.dataSetter(
            "res.other_deps", json.dumps([r for r in attrs["dependencies"] if r not in listed])
        )
        if kind == "media":
            pane.dataSetter("draft.data_base64", resource["sources"]["binary"]["base64"])
        else:
            pane.dataSetter("draft.source", resource["sources"]["source"]["text"])
        tracked = {"name": "^draft.name"}
        if kind == "template":
            tracked.update(rows="^draft.row_keys")
            self.template_data(pane, attrs, choices, tracked)
        tracked.update(
            {"source": "^draft.source"} if kind != "media" else {"media": "^draft.data_base64"}
        )
        # _onBuilt: the parent pane is mounted, so initialize can register its dispose.
        pane.dataController(func="initialize", _onBuilt=True)
        pane.dataController(func="changed", **tracked)
        pane.dataController(
            func="livePreview",
            _delay=LIVE_DELAY,
            sample="^res.sample",
            **({"source": "^draft.source"} if kind != "media" else {}),
        )
        layout = pane.borderContainer(height="100vh", class_="page-editor")
        top = layout.contentPane(region="top", class_="page-toolbar")
        heading = top.div(class_="page-heading")
        literal_text(heading, "p", site_record["attributes"]["name"], class_="breadcrumb")
        literal_text(heading, "h1", attrs["name"])
        heading.span(kind, class_="status")
        actions = top.div(class_="page-actions")
        actions.html_label("Name", for_="resource-name")
        actions.input(id="resource-name", value="^draft.name", live=True, readonly=not writable)
        actions.button("Save", disabled="^res.busy" if writable else True).dataController(
            func="save"
        )
        actions.button("Revert", disabled="^res.busy", class_="button--secondary").dataController(
            func="revert"
        )
        revisions = actions.select(value="^res.load_revision", aria_label="Revisions")
        revisions.option("Revisions…", value="")
        for item in history:
            revisions.option(f"Revision {item['generation']}", value=item["revision_id"])
        actions.button(
            "Load revision", disabled="^res.busy", class_="button--secondary"
        ).dataController(func="loadRevision")
        if samples:
            actions.html_label("Sample page", for_="resource-sample")
            select = actions.select(id="resource-sample", value="^res.sample")
            for index, sample in enumerate(samples):
                select.option(sample["label"], value=str(index))
        pane.dataFormula(
            "res.status", "dirty ? 'Unsaved changes' : 'Saved'", dirty="^res.dirty", _init=True
        )
        status = top.div(class_="page-status")
        status.span("^res.status", class_="status")
        status.span("^res.message", role="status", class_="page-message")
        if not writable:
            status.span("Your current permissions allow viewing only.", class_="muted")
        center = layout.contentPane(region="center", class_="page-blocks")
        if kind == "media":
            self.media_view(center, writable)
        else:
            tabs = center.tabContainer(selectedPage="^res.tab", height="100%")
            code = tabs.contentPane(title="Source", pageName="source", padding="8px")
            code.codeMirror(
                value="^draft.source",
                language=LANGUAGES[kind],
                height="100%",
                readonly=not writable,
            )
            if kind == "template":
                blocks = tabs.contentPane(
                    title="Blocks", pageName="blocks", padding="12px", overflow="auto"
                )
                blocks.p(
                    "Each block is a named area that pages fill. Changing blocks creates a new "
                    "template revision; pages adopt it from their editor.",
                    class_="muted",
                )
                blocks.div().remote("blocks_form", keys="^draft.row_keys", writable=writable)
                if writable:
                    blocks.button("Add block", class_="button--secondary").dataController(
                        func="addBlock"
                    )
                self.dependencies_view(
                    tabs.contentPane(
                        title="Dependencies",
                        pageName="dependencies",
                        padding="12px",
                        overflow="auto",
                    ),
                    choices,
                    writable,
                )
        right = layout.contentPane(
            region="right", splitter=True, width="50%", minSize=320, class_="page-preview"
        )
        scaled_preview(right, "res", "res.live_status")

    def template_data(self, pane, attrs, choices, tracked):
        """Block rows and dependency choices of a template, as Data the Logic collects on save."""
        keys = []
        for index, (name, declaration) in enumerate(attrs["blocks"].items()):
            key = f"r{index}"
            keys.append(key)
            pane.dataSetter(f"draft.block_rows.{key}.name", name)
            pane.dataSetter(f"draft.block_rows.{key}.format", declaration["format"])
            pane.dataSetter(f"draft.block_rows.{key}.required", declaration["required"])
            tracked.update(
                {
                    f"{key}_name": f"^draft.block_rows.{key}.name",
                    f"{key}_format": f"^draft.block_rows.{key}.format",
                    f"{key}_required": f"^draft.block_rows.{key}.required",
                }
            )
        pane.dataSetter("draft.row_keys", ",".join(keys))
        used = set(attrs["dependencies"])
        order = []
        for choice in choices:
            key = "d_" + choice["record_id"]
            order.append(key)
            current = next((r for r in used if r in choice.get("revision_ids", ())), None)
            pane.dataSetter(f"draft.deps.{key}.record_id", choice["record_id"])
            pane.dataSetter(f"draft.deps.{key}.revision", current or choice["revision_id"])
            pane.dataSetter(f"draft.deps.{key}.on", current is not None)
            tracked.update(
                {f"{key}_on": f"^draft.deps.{key}.on", f"{key}_rev": f"^draft.deps.{key}.revision"}
            )
        pane.dataSetter("draft.dep_keys", ",".join(order))

    def dependencies_view(self, pane, choices, writable):
        pane.p(
            "A template references exact revisions of styles, scripts and media. Choose which "
            "ones it uses and whether to move to the latest revision.",
            class_="muted",
        )
        if not choices:
            pane.p("This site and the shared library have no styles, scripts or media yet.")
        table = pane.table(class_="deploy-table")
        head = table.thead().tr()
        for label in ("Use", "Resource", "Revision"):
            head.th(label)
        body = table.tbody()
        for choice in choices:
            key = "d_" + choice["record_id"]
            row = body.tr()
            row.td().checkbox(value=f"^draft.deps.{key}.on", disabled=not writable)
            cell = row.td()
            literal_text(cell, "strong", caption(choice))
            cell.small(
                choice["kind"] + (" · shared library" if choice["scope"] == "library" else "")
            )
            select = row.td().select(value=f"^draft.deps.{key}.revision", disabled=not writable)
            for revision_id, label in choice["options"]:
                select.option(label, value=revision_id)

    @source(auth="editor")
    async def blocks_form(self, pane, keys="", writable=False):
        table = pane.table(class_="deploy-table")
        head = table.thead().tr()
        for label in ("Name", "Format", "Required", ""):
            head.th(label)
        body = table.tbody()
        for key in filter(None, keys.split(",")):
            row = body.tr()
            row.td().input(
                value=f"^draft.block_rows.{key}.name",
                live=True,
                readonly=not writable,
                aria_label="Block name",
            )
            select = row.td().select(value=f"^draft.block_rows.{key}.format", disabled=not writable)
            select.option("HTML", value="html")
            select.option("Markdown", value="markdown")
            row.td().checkbox(value=f"^draft.block_rows.{key}.required", disabled=not writable)
            if writable:
                row.td().button("Remove", class_="button--quiet").dataController(
                    func="removeBlock", key=key
                )

    def media_view(self, pane, writable):
        pane.p("^res.mime_type", class_="muted")
        pane.dataFormula(
            "res.media_src",
            "'data:'+mime+';base64,'+data",
            mime="^res.mime_type",
            data="^draft.data_base64",
            _init=True,
        )
        pane.img(src="^res.media_src", alt="", class_="media-view")
        if writable:
            pane.html_label("Replace the file", for_="media-file")
            pane.input(id="media-file", type="file", connect_onchange="mediaFile")

    async def dependency_choices(self, records):
        """Each resource a template may use, with its revisions, latest first."""
        choices = []
        for record in sorted(records, key=lambda r: (r["kind"], caption(r).casefold())):
            history = await execute_read("revision_index", record_id=record["record_id"])
            options = [
                (
                    item["revision_id"],
                    f"Revision {item['generation']}" + (" · latest" if not i else ""),
                )
                for i, item in enumerate(history)
            ]
            choices.append(
                {
                    **record,
                    "revision_ids": {item["revision_id"] for item in history},
                    "options": options,
                }
            )
        return choices

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
