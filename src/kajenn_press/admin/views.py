"""Multisite browsing through Gramlot Source and request-authorized service reads."""

import asyncio
import json
from uuid import uuid4

from gramlot import Page as GramlotPage
from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, LOGO_SRC, execute_read
from kajenn_press.domain import DomainError

SECTIONS = {"content": "Content", "resource": "Resources", "library": "Library"}
KINDS = {
    "content": {"content", "variant"},
    "resource": {"template", "css", "javascript", "media"},
    "library": {"template", "css", "javascript", "media"},
}


def caption(record):
    attrs = record["attributes"]
    return attrs.get("title") or attrs.get("name") or attrs.get("language") or record["record_id"]


PREVIEW_HEIGHT = 1000  # px of page shown in the scaled preview


def scaled_preview(pane, prefix, status):
    """Width and scale selectors over a rendered page kept at its real width and scaled down.

    The HTML comes from ``<prefix>.preview``; ``status`` points to the line beside the selectors.
    """
    pane.dataSetter(prefix + ".preview_width", "1280")
    pane.dataSetter(prefix + ".preview_scale", "0.5")
    controls = pane.div(class_="preview-controls")
    controls.html_label("Width", for_=prefix + "-preview-width")
    width = controls.select(id=prefix + "-preview-width", value=f"^{prefix}.preview_width")
    width.option("Desktop · 1280 px", value="1280")
    width.option("Phone · 375 px", value="375")
    controls.html_label("Scale", for_=prefix + "-preview-scale")
    scale = controls.select(id=prefix + "-preview-scale", value=f"^{prefix}.preview_scale")
    for value in ("0.5", "0.75", "1"):
        scale.option(value, value=value)
    controls.span("^" + status, role="status", class_="muted")
    # _init computes them once before the first change of width or scale.
    pane.dataFormula(
        prefix + ".box_width",
        "(+w*+s)+'px'",
        w=f"^{prefix}.preview_width",
        s=f"^{prefix}.preview_scale",
        _init=True,
    )
    pane.dataFormula(
        prefix + ".box_height",
        "(h*+s)+'px'",
        s=f"^{prefix}.preview_scale",
        h=PREVIEW_HEIGHT,
        _init=True,
    )
    pane.dataFormula(
        prefix + ".frame_width", "w+'px'", w=f"^{prefix}.preview_width", _init=True
    )
    pane.dataFormula(
        prefix + ".frame_scale", "'scale('+s+')'", s=f"^{prefix}.preview_scale", _init=True
    )
    box = pane.div(
        class_="preview-viewport",
        width=f"^{prefix}.box_width",
        height=f"^{prefix}.box_height",
    )
    box.div(
        class_="preview-frame",
        width=f"^{prefix}.frame_width",
        height=f"{PREVIEW_HEIGHT}px",
        transform=f"^{prefix}.frame_scale",
    ).htmlPreview(value=f"^{prefix}.preview", height="100%")


def literal_text(pane, tag, text, **attributes):
    """Saved text is Data, never a Source expression (even when it starts with == or ^)."""
    path = "display_text." + uuid4().hex
    pane.dataSetter(path, text)
    return getattr(pane, tag)("^" + path, **attributes)


class AdminPage(GramlotPage):
    css = ("/index.css",)

    async def scope_records(self, site, section):
        if section not in KINDS:
            raise DomainError("invalid_input", "Section unavailable")
        scope = "library" if section == "library" else "site:" + site
        records = await execute_read("records_index", scope=scope)
        return scope, [r for r in records if r["kind"] in KINDS[section]]

    @source(auth="editor")
    async def permissions(self, pane, site="", section="content"):
        try:
            scope = "library" if section == "library" else "site:" + site
            rights = await execute_read("scope_capabilities", scope=scope)
            labels = {
                "read": "Read",
                "write": "Write",
                "use": "Use",
                "build": "Build",
                "preview_grant": "Preview",
                "publish": "Publishing",
            }
            pane.p("Permissions in the current scope")
            pane.span(" · ".join(labels[k] for k in rights["permissions"]))
        except DomainError:
            pane.span("Scope not accessible")

    @source(auth="editor")
    async def workspace(
        self, pane, site="", section="content", search="", refresh=0
    ):
        try:
            _scope, records = await self.scope_records(site, section)
            site_label = (
                "Shared library"
                if section == "library"
                else (await execute_read("record_read", record_id=site))["attributes"]["name"]
            )
            literal_text(pane, "p", site_label, class_="breadcrumb")
            heading = pane.div(class_="heading")
            heading.h1("Shared library" if section == "library" else SECTIONS[section])
            heading.span("Browse mode", class_="status")
            visible = [
                r
                for r in records
                if r["kind"] != "variant" and (search or "").casefold() in caption(r).casefold()
            ]
            layout = pane.div(class_="workspace")
            listing = layout.section(class_="record-list", aria_label="Items")
            listing.div("Title / latest revision", class_="list-heading")
            if not visible:
                listing.p("No items available.", class_="empty")
            for record in visible:
                button = listing.button(class_="record-row")
                text = button.div(class_="record-row-text")
                literal_text(text, "strong", caption(record))
                language = " · ".join(
                    r["attributes"]["language"]
                    for r in records
                    if r["kind"] == "variant"
                    and r["attributes"]["content_id"] == record["record_id"]
                )
                text.span(language or record["kind"], class_="muted")
                text.small(f"Revision {record['generation']}")
                button.dataController(
                    "this.SET('admin.selected', record); this.SET('admin.revision','');",
                    record=record["record_id"],
                )
            layout.section(class_="record-detail", aria_label="Selected item details").remote(
                "detail",
                site=site,
                section=section,
                selected="^admin.selected",
                fallback=visible[0]["record_id"] if visible else "",
                revision="^admin.revision",
                _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
            )
        except DomainError as error:
            pane.h1("Scope unavailable")
            pane.p(str(error), role="status")

    @source(auth="editor")
    async def detail(
        self, pane, site="", section="content", selected="", fallback="", revision=""
    ):
        try:
            scope, records = await self.scope_records(site, section)
            record_id = selected or fallback
            allowed = {r["record_id"] for r in records}
            if not record_id:
                pane.p("Select an item.")
                return
            if record_id not in allowed:
                raise DomainError("not_found", "Selection unavailable in this scope")
            record = await execute_read(
                "record_read", record_id=record_id, revision_id=revision or None
            )
            history = await execute_read("revision_index", record_id=record_id)
            pane.span("Read-only", class_="status")
            literal_text(pane, "h2", caption(record))
            tabs = pane.tabContainer(selectedPage="^admin.tab", height="420px")
            info = tabs.contentPane(title="Information", pageName="info", padding="12px")
            attributes = info.dl()
            for label, value in [
                ("Scope", "Shared library" if scope == "library" else "Current site"),
                ("Identifier", record_id),
                ("Revision", record["revision_id"]),
                ("Generation", str(record["generation"])),
            ]:
                attributes.dt(label)
                attributes.dd(value)
            if record["kind"] == "content":
                info.h3("Language variants")
                for variant in records:
                    if (
                        variant["kind"] == "variant"
                        and variant["attributes"]["content_id"] == record_id
                    ):
                        info.button(
                            variant["attributes"]["language"], class_="button--secondary"
                        ).dataController(
                            "this.SET('admin.selected',record);this.SET('admin.revision','')",
                            record=variant["record_id"],
                        )
            else:
                info.pre(json.dumps(record["attributes"], ensure_ascii=False, indent=2))
            source_pane = tabs.contentPane(
                title="Source", pageName="source", padding="12px", overflow="auto"
            )
            if not record["sources"]:
                source_pane.p("This record has no source files. Select a language variant.")
            for name, payload in record["sources"].items():
                source_pane.h3(name)
                literal_text(
                    source_pane,
                    "pre",
                    payload.get("text", "Binary content; original file preserved."),
                )
            revisions = tabs.contentPane(
                title="Revisions", pageName="history", padding="12px", overflow="auto"
            )
            for item in history:
                revisions.button(
                    f"Revision {item['generation']}", class_="button--secondary"
                ).dataController(
                    "this.SET('admin.revision', revision)", revision=item["revision_id"]
                )
        except DomainError as error:
            pane.p(str(error), role="status")

    def login_view(self, root):
        root.dataSetter("login.username", "")
        root.dataSetter("login.password", "")
        root.dataSetter("login.error", "")
        box = root.main(class_="login-shell").section(class_="login-card")
        box.img(src=LOGO_SRC, width="160", height="160", alt="Kajenn Press", class_="login-logo")
        box.h1("Sign in to your sites")
        box.textbox(
            value="^login.username",
            lbl="Username",
            lbl_position="TL",
            live=True,
            width="100%",
            box_margin_bottom="16px",
        )
        box.passwordbox(
            value="^login.password",
            lbl="Password",
            lbl_position="TL",
            live=True,
            width="100%",
            box_margin_bottom="16px",
        )
        box.button("Sign in").dataRpc(
            "sign_in",
            username="=login.username",
            password="=login.password",
            _onResult="this.SET('login.password',''); if(!result){window.location.reload();}else{this.SET('login.error',result)}",
            _onError="this.SET('login.password','');this.SET('login.error','Sign-in unavailable')",
        )
        box.p("^login.error", role="status")

    @endpoint
    async def sign_in(self, username="", password=""):
        request = CURRENT_REQUEST.get()
        server_app = request.server.application_at("_server")
        result = await asyncio.to_thread(
            server_app.login, identity=username, password=password, _request=request
        )
        return "Sign-in failed" if "error" in result else ""

    @endpoint(auth="editor")
    def sign_out(self):
        request = CURRENT_REQUEST.get()
        request.server.session_store.delete(request.session.id)
        return True

    @endpoint(auth="editor")
    async def read(self, operation, arguments=None):
        return await execute_read(operation, **(arguments or {}))


class WorkspacePage(AdminPage):
    section = "content"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {
            "site": "",
            "selected": "",
            "search": "",
            "refresh": 0,
            "revision": "",
            "tab": "info",
        }.items():
            root.dataSetter(f"admin.{name}", value)
        root.dataController(
            "this.SET('admin.site', new URLSearchParams(window.location.search).get('site') || '');",
            _onStart=True,
        )
        root.dataController(
            "this.SET('admin.selected','');this.SET('admin.revision','');", site="^admin.site"
        )
        toolbar = root.div(class_="toolbar")
        toolbar.input(
            value="^admin.search",
            placeholder="Search by title…",
            aria_label="Search by title",
            type="search",
            live=True,
        )
        toolbar.button("Refresh").dataController(
            "this.SET('admin.refresh', (this.GET('admin.refresh')||0)+1)"
        )
        root.div(class_="workspace-host").remote(
            "workspace",
            site="^admin.site",
            section=self.section,
            search="^admin.search",
            refresh="^admin.refresh",
            _delay=150,
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )
