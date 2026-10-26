"""One site object per tab: its details, sources and revisions, read-only until its editor exists."""

from gramlot import source

from kajenn_press.admin.host import CURRENT_REQUEST
from kajenn_press.admin.views import AdminPage
from kajenn_press.domain import DomainError


class Page(AdminPage):
    title = "Object"

    async def main(self, root):
        avatar = CURRENT_REQUEST.get().avatar()
        if avatar is None or "editor" not in avatar.tags:
            self.login_view(root)
            return
        for name, value in {
            "site": "",
            "record": "",
            "selected": "",
            "revision": "",
            "tab": "info",
        }.items():
            root.dataSetter(f"admin.{name}", value)
        root.dataController(
            "var q=new URLSearchParams(window.location.search);"
            "this.SET('admin.site',q.get('site')||'');"
            "this.SET('admin.record',q.get('record')||'');"
            "this.SET('admin.selected',q.get('record')||'');",
            _onStart=True,
        )
        root.div(class_="workspace-host record-host").remote(
            "object_view",
            site="^admin.site",
            record="^admin.record",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )

    @source(auth="editor")
    async def object_view(self, pane, site="", record=""):
        if not site or not record:
            pane.p("Select an object in the navigation.")
            return
        try:
            # The record must belong to the site; detail checks it again against its kinds.
            _scope, contents = await self.scope_records(site, "content")
            section = "content" if any(r["record_id"] == record for r in contents) else "resource"
        except DomainError as error:
            pane.p(str(error), role="status")
            return
        # Language variant buttons in detail select another record of the same content.
        pane.div(class_="record-detail").remote(
            "detail",
            site=site,
            section=section,
            selected="^admin.selected",
            revision="^admin.revision",
            _onCalling="if(this.requests.inflight)this.requests.inflight.cancel()",
        )
