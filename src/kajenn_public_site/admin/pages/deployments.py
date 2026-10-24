"""Deployments: children serving channels from release storage, catalog beside storage."""

from uuid import uuid4

from gramlot import endpoint, source

from kajenn_public_site.admin.host import CURRENT_REQUEST, execute_read, execute_service
from kajenn_public_site.admin.views import AdminPage, literal_text
from kajenn_public_site.domain import DomainError

STATES = {
    "up_to_date": ("Up to date", "badge badge--ok"),
    "storage_differs": ("Storage differs from catalog", "badge badge--warn"),
    "not_exported": ("Not in storage", "badge badge--warn"),
    "nothing_to_serve": ("Nothing to serve", "badge badge--error"),
    "storage_unconfigured": ("No release storage", "badge badge--error"),
}
NOTES = {
    "storage_differs": "Storage names a different release than the catalog. The child keeps "
    "serving the release in storage until it is exported again.",
    "not_exported": "The catalog has an active release that storage does not contain yet. "
    "The child has nothing new to serve until it is exported.",
    "nothing_to_serve": "No release is active for this channel and storage holds no pointer.",
    "storage_unconfigured": "This installation has no release storage configured.",
}
REFRESH = "this.SET('deploy.refresh', (this.GET('deploy.refresh') || 0) + 1)"


def release_cell(row, release):
    cell = row.td()
    if release and release.get("build_id"):
        literal_text(cell, "code", release["build_id"][:8])
        cell.small(f"channel generation {release['channel_generation']}")
    else:
        cell.code("—")
        cell.small("none")


class Page(AdminPage):
    title = "Deployments"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {
            "refresh": 0,
            "selected": "",
            "message": "",
            "channel": "",
            "name": "",
            "serving": "",
            "key": uuid4().hex,
        }.items():
            root.dataSetter("deploy." + name, value)
        root.div(class_="workspace-host deploy-page").remote(
            "view",
            refresh="^deploy.refresh",
            selected="^deploy.selected",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    @source(auth="editor")
    async def view(self, pane, refresh=0, selected=""):
        try:
            children = await execute_read("child_list")
            channels = await execute_read("child_channels")
        except DomainError as error:
            pane.h1("Deployments unavailable")
            literal_text(pane, "p", str(error), role="status")
            return
        sites = {channel["site_id"]: channel["site_name"] for channel in channels}
        pane.p("This installation", class_="breadcrumb")
        pane.div(class_="heading").h1("Deployments")
        pane.p(
            "Children are servers that serve a site from release storage. For each child: the "
            "release the catalog has active, and the release found in storage, read back now. "
            "A difference is shown here and never corrected automatically.",
            class_="lead",
        )
        pane.p("^deploy.message", role="status", class_="author-message")
        current = next((c for c in children if c["record_id"] == selected), None) or (
            children[0] if children else None
        )
        if children:
            table = pane.table(class_="deploy-table")
            head = table.thead().tr()
            for title in ("Child", "Site", "Catalog release", "Release in storage", "State", ""):
                head.th(title)
            body = table.tbody()
            for child in children:
                attrs, deployment = child["attributes"], child["deployment"]
                row = body.tr(class_="selected" if child is current else "")
                name = row.td()
                pick = name.button(class_="button--quiet")
                literal_text(pick, "strong", attrs["name"])
                pick.dataController("this.SET('deploy.selected', record)", record=child["record_id"])
                literal_text(name, "small", attrs["public_origin"])
                literal_text(row.td(), "span", sites.get(attrs["site_id"], attrs["site_id"]))
                release_cell(row, deployment["catalog"])
                release_cell(row, deployment["storage"])
                label, css = STATES[deployment["state"]]
                row.td().span(label, class_=css)
                self.reexport_button(row.td(), child)
        else:
            pane.p("No children registered yet.", class_="empty")
        cards = pane.div(class_="deploy-cards")
        if current:
            self.child_detail(cards.section(class_="record-detail"), current, sites)
        self.register_form(cards.section(class_="record-detail"), channels)

    def reexport_button(self, pane, child, label="Re-export", class_=""):
        pane.button(
            label,
            class_=class_,
            disabled=child["deployment"]["catalog"]["build_id"] is None,
        ).dataRpc(
            "reexport",
            settings_id=child["attributes"]["settings_id"],
            _onResult="this.SET('deploy.message', result);" + REFRESH,
            _onError="this.SET('deploy.message', 'No response received. Retry.')",
        )

    def child_detail(self, pane, child, sites):
        attrs, deployment = child["attributes"], child["deployment"]
        literal_text(pane, "h2", attrs["name"])
        facts = pane.dl()
        for label, value in (
            ("Bound site", sites.get(attrs["site_id"], attrs["site_id"])),
            ("Channel settings", attrs["settings_id"]),
            ("Public origin", attrs["public_origin"]),
            ("Serving address", attrs["serving_address"] + " (declared)"),
            ("Release storage", attrs["mount"]),
            ("Registry record", f"generation {child['generation']} · revision {child['revision_id'][:8]}"),
        ):
            facts.dt(label)
            literal_text(facts, "dd", value)
        compare = pane.div(class_="deploy-compare")
        for title, release in (
            ("Catalog", deployment["catalog"]),
            ("Storage (read back now)", deployment["storage"]),
        ):
            box = compare.div()
            box.h3(title)
            if release and release.get("build_id"):
                literal_text(box, "code", release["build_id"][:8])
                box.p(f"channel generation {release['channel_generation']}")
            else:
                box.p("none")
        if deployment["state"] in NOTES:
            pane.p(NOTES[deployment["state"]], class_="deploy-note")
        self.reexport_button(pane.div(class_="author-actions"), child, "Re-export to storage")

    def register_form(self, pane, channels):
        pane.h2("Register child")
        if not channels:
            pane.p("No channel settings yet: save publication settings for a site first.")
            return
        pane.html_label("Channel", for_="deploy-channel")
        select = pane.select(id="deploy-channel", value="^deploy.channel")
        select.option("Choose a channel", value="")
        for channel in channels:
            literal_text(
                select,
                "option",
                f"{channel['site_name']} · {channel['channel']} · {channel['public_origin']}",
                value=channel["settings_id"],
            )
        pane.html_label("Name", for_="deploy-name")
        pane.input(id="deploy-name", value="^deploy.name", live=True)
        pane.html_label("Serving address (declared)", for_="deploy-serving")
        pane.input(id="deploy-serving", value="^deploy.serving", live=True)
        pane.div(class_="author-actions").button("Register").dataRpc(
            "register",
            settings_id="=deploy.channel",
            name="=deploy.name",
            serving_address="=deploy.serving",
            key="=deploy.key",
            _onResult="this.SET('deploy.message', result.message);"
            "if(result.ok){this.SET('deploy.key', crypto.randomUUID());"
            "this.SET('deploy.name', '');this.SET('deploy.serving', '');" + REFRESH + "}",
            _onError="this.SET('deploy.message', 'No response received. Retry without changing your input.')",
        )

    @endpoint(auth="editor")
    async def reexport(self, settings_id):
        try:
            result = await execute_service("release_export", {"settings_id": settings_id})
        except DomainError as error:
            return "Export failed: " + str(error)
        return f"Exported release {result['pointer']['build_id'][:8]} to storage."

    @endpoint(auth="editor")
    async def register(self, settings_id, name, serving_address, key):
        channels = await execute_read("child_channels")
        channel = next((c for c in channels if c["settings_id"] == settings_id), None)
        if channel is None:
            return {"ok": False, "message": "Choose a channel."}
        try:
            child = await execute_service(
                "child_save",
                {
                    "settings_id": settings_id,
                    "name": name,
                    "public_origin": channel["public_origin"],
                    "serving_address": serving_address,
                    "key": key,
                },
            )
        except DomainError as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "message": f"Registered {child['attributes']['name']}."}
