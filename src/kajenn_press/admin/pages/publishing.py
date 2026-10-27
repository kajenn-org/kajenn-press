"""Publishing panel: channel settings, routes, builds, private previews, activation and rollback."""

import json

from gramlot import endpoint, source

from kajenn_press.admin.host import CURRENT_REQUEST, execute_read, execute_service
from kajenn_press.admin.views import AdminPage, caption, literal_text
from kajenn_press.domain import DomainError

COMMANDS = frozenset(
    {
        "publication_settings_save",
        "publication_route_save",
        "candidate_create",
        "build_start",
        "build_status",
        "preview_grant_create",
        "release_activate",
        "release_rollback",
        "release_history",
    }
)


class Page(AdminPage):
    title = "Publishing"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        # Set once: the panel is rebuilt after each command and must keep these.
        for name, value in {
            "site": "",
            "version": 0,
            "busy": False,
            "message": "",
            "preview_url": "",
        }.items():
            root.dataSetter(f"pub.{name}", value)
        root.dataController(
            "this.SET('pub.site',new URLSearchParams(window.location.search).get('site')||'');",
            _onStart=True,
        )
        root.div(class_="workspace-host publish-page").remote(
            "panel",
            site="^pub.site",
            version="^pub.version",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    @source(auth="editor")
    async def panel(self, pane, site="", version=0):
        if not site:
            pane.p("Choose a site to publish.")
            return
        try:
            site_record = await execute_read("record_read", record_id=site)
            if site_record["kind"] != "site":
                raise DomainError("invalid_input", "Expected a site")
            overview = await execute_read("publication_overview", site_id=site)
            records = await execute_read("records_index", scope="site:" + site)
            rights = set(
                (await execute_read("scope_capabilities", scope="site:" + site))["permissions"]
            )
        except DomainError as error:
            pane.p(str(error), role="status")
            return
        titles = {r["record_id"]: caption(r) for r in records if r["kind"] == "content"}
        variants = sorted(
            (r for r in records if r["kind"] == "variant"),
            key=lambda r: (
                titles.get(r["attributes"]["content_id"], ""),
                r["attributes"]["language"],
            ),
        )
        labels = {
            v["record_id"]: titles.get(v["attributes"]["content_id"], "Page")
            + " · "
            + v["attributes"]["language"]
            for v in variants
        }
        channels = overview["channels"]
        routes = overview["routes"]
        for name, value in {
            "channels": json.dumps(channels),
            "routes_meta": json.dumps(routes),
            "revisions": json.dumps({v["record_id"]: v["revision_id"] for v in variants}),
            "languages": json.dumps(
                {v["record_id"]: v["attributes"]["language"] for v in variants}
            ),
            "channel_index": "0" if channels else "new",
        }.items():
            pane.dataSetter("pub." + name, value)
        literal_text(pane, "p", site_record["attributes"]["name"], class_="breadcrumb")
        heading = pane.div(class_="heading")
        heading.h1("Publishing")
        heading.span("Nothing is public until you activate a release.", class_="status")
        pane.p("^pub.message", role="status", class_="page-message")
        pane.a("^pub.preview_url", href="^pub.preview_url", target="_blank", rel="noopener")
        self.channel_section(pane, site_record, channels, variants, labels, "write" in rights)
        self.routes_section(pane, variants, labels, routes, "write" in rights)
        self.build_section(pane, variants, labels, routes, channels, rights)

    def channel_section(self, pane, site_record, channels, variants, labels, writable):
        section = pane.section(class_="publish-section")
        section.h2("1 · Channel")
        section.p(
            "A channel publishes the site at one public origin. The landing page answers / and "
            "must be in the primary language.",
            class_="muted",
        )
        select = section.select(value="^pub.channel_index", aria_label="Channel")
        for index, channel in enumerate(channels):
            literal_text(select, "option", channel["channel"], value=str(index))
        select.option("New channel…", value="new")
        # A new channel starts from the first language and its first page.
        first = site_record["attributes"]["languages"][0]
        pane.dataSetter("pub.form.primary_language", first)
        pane.dataSetter(
            "pub.form.landing_variant",
            next((v["record_id"] for v in variants if v["attributes"]["language"] == first), ""),
        )
        pane.dataController(func="fillChannel", index="^pub.channel_index", _onBuilt=True)
        form = section.div(class_="publish-form")
        form.html_label("Channel name", for_="pub-channel")
        form.input(id="pub-channel", value="^pub.form.channel", live=True, readonly=not writable)
        form.html_label("Public origin", for_="pub-origin")
        form.input(
            id="pub-origin",
            value="^pub.form.public_origin",
            live=True,
            placeholder="https://www.example.org",
            readonly=not writable,
        )
        form.html_label("Primary language", for_="pub-language")
        languages = form.select(
            id="pub-language", value="^pub.form.primary_language", disabled=not writable
        )
        for code in site_record["attributes"]["languages"]:
            languages.option(code, value=code)
        form.html_label("Landing page", for_="pub-landing")
        landing = form.select(
            id="pub-landing", value="^pub.form.landing_variant", disabled=not writable
        )
        for variant in variants:
            literal_text(
                landing, "option", labels[variant["record_id"]], value=variant["record_id"]
            )
        section.button("Save channel", disabled="^pub.busy" if writable else True).dataController(
            func="saveChannel"
        )

    def routes_section(self, pane, variants, labels, routes, writable):
        section = pane.section(class_="publish-section")
        section.h2("2 · Routes")
        section.p(
            "Each page needs a path in its language: about in English becomes /en/about/.",
            class_="muted",
        )
        table = section.table(class_="deploy-table")
        head = table.thead().tr()
        for label in ("Page", "Path", "Title", "Description", ""):
            head.th(label)
        body = table.tbody()
        for variant in variants:
            vid = variant["record_id"]
            route = routes.get(vid, {})
            language = variant["attributes"]["language"]
            # The stored path is localized; the form edits the part after /<language>/.
            path = route.get("path", "").removeprefix(f"/{language}/").removesuffix("/")
            for name, value in {
                "path": path,
                "title": route.get("title", labels[vid]),
                "description": route.get("description", ""),
            }.items():
                pane.dataSetter(f"pub.routes.{vid}.{name}", value)
            row = body.tr()
            literal_text(row.td(), "strong", labels[vid])
            for name in ("path", "title", "description"):
                row.td().input(
                    value=f"^pub.routes.{vid}.{name}",
                    live=True,
                    readonly=not writable,
                    aria_label=name.capitalize(),
                )
            row.td().button(
                "Save route" if route else "Add route",
                disabled="^pub.busy" if writable else True,
                class_="button--secondary",
            ).dataController(func="saveRoute", variant=vid)

    def build_section(self, pane, variants, labels, routes, channels, rights):
        section = pane.section(class_="publish-section")
        section.h2("3 · Build, preview and activate")
        if not channels:
            section.p("Save a channel first.")
            return
        section.p(
            "A build renders the latest saved revision of each selected page. Preview it "
            "privately, then activate it: the channel switches to the whole release at once.",
            class_="muted",
        )
        choices = section.div(class_="publish-choices")
        for variant in variants:
            vid = variant["record_id"]
            pane.dataSetter(f"pub.select.{vid}", vid in routes)
            choices.checkbox(
                value=f"^pub.select.{vid}",
                label=labels[vid] + ("" if vid in routes else " · no route"),
                disabled=vid not in routes,
            )
        section.button("Build", disabled="^pub.busy" if "build" in rights else True).dataController(
            func="build"
        )
        pane.dataFormula(
            "pub.settings_id",
            "index==='new'||!channels?'':JSON.parse(channels)[+index].record_id",
            index="^pub.channel_index",
            channels="=pub.channels",
            _init=True,
        )
        section.div().remote(
            "channel_view",
            site="=pub.site",
            settings_id="^pub.settings_id",
            version="^pub.version",
            preview="preview_grant" in rights,
            publish="publish" in rights,
        )

    @source(auth="editor")
    async def channel_view(
        self, pane, site="", settings_id="", version=0, preview=False, publish=False
    ):
        if not site or not settings_id:
            return
        try:
            overview = await execute_read("publication_overview", site_id=site)
            channel = next((c for c in overview["channels"] if c["record_id"] == settings_id), None)
            if channel is None:
                raise DomainError("not_found", "Channel unavailable in this site")
            history = (
                await execute_service("release_history", {"settings_id": settings_id})
                if publish
                else []
            )
        except DomainError as error:
            pane.p(str(error), role="status")
            return
        active = channel["active_build"]
        pane.dataSetter("pub.channel_generation", channel["channel_generation"])
        pane.h3("Builds")
        if not channel["builds"]:
            pane.p("No builds yet.", class_="muted")
        table = pane.table(class_="deploy-table")
        head = table.thead().tr()
        for label in ("Build", "State", "Details", ""):
            head.th(label)
        body = table.tbody()
        for job in channel["builds"]:
            row = body.tr(class_="selected" if job["build_id"] == active else None)
            row.td().code(job["build_id"][:12])
            state = row.td()
            state.span(
                "Active" if job["build_id"] == active else job["state"],
                class_="badge "
                + (
                    "badge--ok"
                    if job["state"] == "succeeded"
                    else "badge--error"
                    if job["state"] in {"failed", "interrupted"}
                    else "badge--warn"
                ),
            )
            literal_text(
                row.td(), "small", " · ".join(d["message"] for d in job["diagnostics"]) or "—"
            )
            actions = row.td()
            if job["state"] == "succeeded":
                if preview:
                    actions.button("Preview link", class_="button--secondary").dataController(
                        func="previewLink", build=job["build_id"]
                    )
                if publish and job["build_id"] != active:
                    actions.button("Activate").dataController(
                        func="activate",
                        build=job["build_id"],
                        _ask={
                            "title": "Activate this release?",
                            "msg": "The public channel switches to this build at once.",
                        },
                    )
        pane.h3("History")
        if not publish:
            pane.p("The history needs the publish permission.", class_="muted")
            return
        if not history:
            pane.p("No release has been activated yet.", class_="muted")
        table = pane.table(class_="deploy-table")
        head = table.thead().tr()
        for label in ("Channel generation", "Action", "Build", ""):
            head.th(label)
        body = table.tbody()
        for entry in reversed(history):
            attrs = entry["attributes"]
            row = body.tr(class_="selected" if attrs["build_id"] == active else None)
            row.td(str(attrs["channel_generation"]))
            row.td(attrs["action"])
            row.td().code(attrs["build_id"][:12])
            cell = row.td()
            if attrs["build_id"] != active:
                cell.button("Roll back", class_="button--secondary").dataController(
                    func="rollback",
                    build=attrs["build_id"],
                    _ask={
                        "title": "Roll back to this release?",
                        "msg": "The public channel switches back to this build at once.",
                    },
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
