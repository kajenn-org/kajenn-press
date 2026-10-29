"""Authenticated Kajenn REST/MCP adapter of the site operations; rules live in the services."""

import asyncio
from pathlib import Path
from typing import ClassVar

from genro_routes import route
from kajenn import AsgiServer, HTTPException, McpOpenApiApplication
from kajenn.config import ConfigurationHandler, DefaultConfiguration
from kajenn.lifespan import FatalBootError

from .catalog.filesystem import private_directory
from .domain import AccessPolicy, DomainError
from .rendering.process import RenderWorker
from .site.service import OPERATIONS as SITE_OPERATIONS
from .site.service import SiteService

ERROR_STATUS = {
    "unauthenticated": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "unavailable": 503,
}


class PressApplication(McpOpenApiApplication):
    openapi_info: ClassVar[dict] = {
        "title": "kajenn-press",
        "version": "0.1.0",
        "description": "Site sources, pages and per-page publication",
    }
    mcp_name = "kajenn-press"

    def __init__(self, root, grants, sites_config=None, **kwargs):
        self.root = Path(root)
        self.policy = AccessPolicy(grants)
        self.sites_config = sites_config
        self.sites = None
        super().__init__(**kwargs)

    async def on_startup(self):
        await asyncio.to_thread(self._open_services)

    def _open_services(self):
        if self.sites_config is None:
            return
        try:
            # s3fs comes with the optional release-s3 extra; an installation without site
            # sources keeps starting without it.
            from .site.publish import Publisher
            from .site.store import SourceStore

            config = dict(self.sites_config)
            render_python = config.pop("render_python", None)
            worker = RenderWorker(render_python) if render_python else None
            connections = config.pop("connections", {})
            releases = config.pop("releases", None)
            private_secret = config.pop("private_secret", None)
            self.sites = SiteService(
                config.pop("root", self.root / "sites"),
                SourceStore(config.pop("sources")),
                self.policy,
                worker=worker,
                connections=connections,
                publisher=Publisher(releases, worker, connections, private_secret)
                if releases
                else None,
            )
            if config:
                raise ValueError("Unknown site configuration")
        except Exception as exc:
            self.sites = None
            # Ordinary hook exceptions are only logged by Kajenn; a misconfigured store must
            # prevent serving.
            raise FatalBootError("Cannot open the site source store") from exc

    def _execute(self, request, operation, arguments):
        if request is None or request.avatar() is None:
            raise HTTPException(401, "Authentication required")
        is_rest = request.scope.get("kajenn.channel") != "mcp"
        if is_rest and request.scope["method"] != "POST":
            raise HTTPException(405, "Operations require POST")
        try:
            if operation == "capabilities":
                return {"ok": True, "result": self._capabilities(request.avatar().identity)}
            if self.sites is None:
                raise DomainError("unavailable", "Configure the site source store first")
            result = self.sites.execute(request.avatar().identity, operation, **arguments)
            return {"ok": True, "result": result}
        except DomainError as exc:
            if is_rest:
                request.response.status_code = ERROR_STATUS.get(exc.code, 422)
            return {"ok": False, "error": exc.as_dict()}

    def _capabilities(self, identity):
        return {
            "sites": self.sites is not None,
            "publishing": self.sites is not None and self.sites.publisher is not None,
            "rendering": self.sites is not None and self.sites.worker is not None,
            "operations": sorted(SITE_OPERATIONS) if self.sites is not None else [],
        }

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def capabilities(self, _request=None) -> dict:
        """Which site operations this installation offers."""
        return self._execute(_request, "capabilities", {})

    # Site operations (N3): the site source model, see kajenn_press.site.service.

    def _site(self, request, operation, **arguments):
        return self._execute(request, operation, arguments)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_new(self, key: str, name: str, starter_id: str | None = None, _request=None) -> dict:
        """Create a site source, empty or from a starting site; the creator holds it."""
        return self._site(_request, "site_new", key=key, name=name, starter_id=starter_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_export(self, site_id: str, version_id: str | None = None, _request=None) -> dict:
        """A saved version of the site as one zip, in base64."""
        return self._site(_request, "site_export", site_id=site_id, version_id=version_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_import(
        self, key: str, data_base64: str, name: str | None = None, _request=None
    ) -> dict:
        """A new site from an exported zip; the importer holds it."""
        return self._site(_request, "site_import", key=key, data_base64=data_base64, name=name)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def starter_save(self, key: str, site_id: str, name: str, _request=None) -> dict:
        """Keep the latest saved version of a site in the Library as a starting site."""
        return self._site(_request, "starter_save", key=key, site_id=site_id, name=name)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_list(self, _request=None) -> dict:
        """Sites with a source the caller can read, and who holds each."""
        return self._site(_request, "site_list")

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def starters_list(self, _request=None) -> dict:
        """Starting sites in the Library."""
        return self._site(_request, "starters_list")

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_open(self, site_id: str, force: bool = False, _request=None) -> dict:
        """Take the site for editing; force takes it from another holder."""
        return self._site(_request, "site_open", site_id=site_id, force=force)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_close(self, site_id: str, _request=None) -> dict:
        """Release the site."""
        return self._site(_request, "site_close", site_id=site_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_save(self, site_id: str, _request=None) -> dict:
        """Save the working copy as a new S3 version."""
        return self._site(_request, "site_save", site_id=site_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_restore(self, site_id: str, version_id: str, _request=None) -> dict:
        """Make an older version current again, as a new version."""
        return self._site(_request, "site_restore", site_id=site_id, version_id=version_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_read(self, site_id: str, _request=None) -> dict:
        """Templates, contents with use counts, assets, pages and the holder."""
        return self._site(_request, "site_read", site_id=site_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_versions(self, site_id: str, _request=None) -> dict:
        """S3 versions of the site source, oldest first."""
        return self._site(_request, "site_versions", site_id=site_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def template_add(
        self,
        site_id: str,
        key: str,
        name: str,
        engine: str,
        source: str | None = None,
        python_source: str | None = None,
        _request=None,
    ) -> dict:
        """Add a template: a plain Source in TYTX JSON, or Python build code."""
        return self._site(
            _request,
            "template_add",
            site_id=site_id,
            key=key,
            name=name,
            engine=engine,
            source=source,
            python_source=python_source,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def content_add(
        self, site_id: str, key: str, name: str, format: str, text: str, _request=None
    ) -> dict:
        """Add an HTML or Markdown content."""
        return self._site(
            _request, "content_add", site_id=site_id, key=key, name=name, format=format, text=text
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def content_save(
        self, site_id: str, key: str, content_id: str, text: str, _request=None
    ) -> dict:
        """Replace the text of a content; page copies change only through copies_update."""
        return self._site(
            _request, "content_save", site_id=site_id, key=key, content_id=content_id, text=text
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def asset_add(
        self,
        site_id: str,
        key: str,
        name: str,
        kind: str,
        data_base64: str,
        mime_type: str,
        _request=None,
    ) -> dict:
        """Add a CSS, JavaScript or media asset."""
        return self._site(
            _request,
            "asset_add",
            site_id=site_id,
            key=key,
            name=name,
            kind=kind,
            data_base64=data_base64,
            mime_type=mime_type,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_add(self, site_id: str, key: str, name: str, template_id: str, _request=None) -> dict:
        """Add a page with a copy of a site template."""
        return self._site(
            _request, "page_add", site_id=site_id, key=key, name=name, template_id=template_id
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def folder_add(
        self, site_id: str, key: str, name: str, parent: str | None = None, _request=None
    ) -> dict:
        """Add a logical folder to the Pages tree."""
        return self._site(
            _request, "folder_add", site_id=site_id, key=key, name=name, parent=parent
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def tree_move(
        self,
        site_id: str,
        key: str,
        item_id: str,
        parent: str | None = None,
        position: int | None = None,
        _request=None,
    ) -> dict:
        """Move a page or folder in the Pages tree (drag and drop)."""
        return self._site(
            _request,
            "tree_move",
            site_id=site_id,
            key=key,
            item_id=item_id,
            parent=parent,
            position=position,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_url_set(self, site_id: str, key: str, page_id: str, url: str, _request=None) -> dict:
        """Move a page to a new URL path; the old path redirects to it."""
        return self._site(
            _request, "page_url_set", site_id=site_id, key=key, page_id=page_id, url=url
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_seo_set(
        self, site_id: str, key: str, page_id: str, fields: dict, _request=None
    ) -> dict:
        """Set SEO fields of a page; an empty value clears the field (root page: site defaults)."""
        return self._site(
            _request, "page_seo_set", site_id=site_id, key=key, page_id=page_id, fields=fields
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_alt_set(
        self, site_id: str, key: str, page_id: str, image: str, alt: str, _request=None
    ) -> dict:
        """Set the alt text of one image in this page's copy (a local change of the copy)."""
        return self._site(
            _request,
            "page_alt_set",
            site_id=site_id,
            key=key,
            page_id=page_id,
            image=image,
            alt=alt,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_asset_add(
        self, site_id: str, key: str, page_id: str, asset_id: str, _request=None
    ) -> dict:
        """Copy an asset into a page."""
        return self._site(
            _request, "page_asset_add", site_id=site_id, key=key, page_id=page_id, asset_id=asset_id
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def slot_assign(
        self, site_id: str, key: str, page_id: str, slot: str, content_id: str, _request=None
    ) -> dict:
        """Copy a content into a slot of a page."""
        return self._site(
            _request,
            "slot_assign",
            site_id=site_id,
            key=key,
            page_id=page_id,
            slot=slot,
            content_id=content_id,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def copies_update_plan(self, site_id: str, original_id: str, _request=None) -> dict:
        """Copies of an original, with differences and what Update would select."""
        return self._site(_request, "copies_update_plan", site_id=site_id, original_id=original_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def copies_update(
        self, site_id: str, key: str, original_id: str, selected: list, _request=None
    ) -> dict:
        """Replace the selected copies, given as [page_id, path], with the original."""
        return self._site(
            _request,
            "copies_update",
            site_id=site_id,
            key=key,
            original_id=original_id,
            selected=selected,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def template_switch_plan(
        self, site_id: str, page_id: str, template_id: str, _request=None
    ) -> dict:
        """Proposed slot mapping, by name, for a page switching template."""
        return self._site(
            _request,
            "template_switch_plan",
            site_id=site_id,
            page_id=page_id,
            template_id=template_id,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def template_switch(
        self, site_id: str, key: str, page_id: str, template_id: str, mapping: dict, _request=None
    ) -> dict:
        """Switch a page's template with the confirmed slot mapping."""
        return self._site(
            _request,
            "template_switch",
            site_id=site_id,
            key=key,
            page_id=page_id,
            template_id=template_id,
            mapping=mapping,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def unplaced_place(
        self, site_id: str, key: str, page_id: str, copy_id: str, slot: str, _request=None
    ) -> dict:
        """Move an unplaced content copy into a free slot."""
        return self._site(
            _request,
            "unplaced_place",
            site_id=site_id,
            key=key,
            page_id=page_id,
            copy_id=copy_id,
            slot=slot,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def publish_plan(self, site_id: str, _request=None) -> dict:
        """Pages changed since the last publication, selected, with their warnings."""
        return self._site(_request, "publish_plan", site_id=site_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def publish(self, site_id: str, key: str, selected: list[str], _request=None) -> dict:
        """Save the source and publish the selected pages; the site index is written last."""
        return self._site(_request, "publish", site_id=site_id, key=key, selected=selected)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_versions(self, site_id: str, page_id: str, _request=None) -> dict:
        """Published versions of a page, oldest first, with the one online marked."""
        return self._site(_request, "page_versions", site_id=site_id, page_id=page_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_rollback(
        self, site_id: str, key: str, page_id: str, version_id: str, _request=None
    ) -> dict:
        """Put an earlier published version of a page online."""
        return self._site(
            _request,
            "page_rollback",
            site_id=site_id,
            key=key,
            page_id=page_id,
            version_id=version_id,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_rollback(self, site_id: str, key: str, version_id: str, _request=None) -> dict:
        """Restore a source version and publish the whole site from it."""
        return self._site(
            _request, "site_rollback", site_id=site_id, key=key, version_id=version_id
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def maintenance_set(self, site_id: str, key: str, on: bool, _request=None) -> dict:
        """Put the published site in maintenance (503) or take it out."""
        return self._site(_request, "maintenance_set", site_id=site_id, key=key, on=on)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_visibility_set(self, site_id: str, key: str, state: str, _request=None) -> dict:
        """Make the site public or private at its address (the root page's public origin)."""
        return self._site(_request, "site_visibility_set", site_id=site_id, key=key, state=state)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def private_link(self, site_id: str, hours: int = 8, _request=None) -> dict:
        """A link that shows the real site while private or in maintenance (8 or 168 hours)."""
        return self._site(_request, "private_link", site_id=site_id, hours=hours)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_check(self, site_id: str, page_id: str, _request=None) -> dict:
        """Empty slots and unplaced contents of a page."""
        return self._site(_request, "page_check", site_id=site_id, page_id=page_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def seo_check(self, site_id: str, page_id: str | None = None, _request=None) -> dict:
        """SEO problems of one page or of the whole site: titles, descriptions, alt, links."""
        return self._site(_request, "seo_check", site_id=site_id, page_id=page_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_render(self, site_id: str, page_id: str, _request=None) -> dict:
        """Static HTML of a page, rendered in the worker."""
        return self._site(_request, "page_render", site_id=site_id, page_id=page_id)


def create_server(root, *, auth, grants, administration=None, sites=None):
    """Build a host with explicit credentials, policy and private local storage.

    Authentication configuration belongs to the deployment; API clients cannot supply it.
    The `editor` Kajenn tag admits transport access, scope grants decide every action.
    """
    root = private_directory(root)
    private_directory(root / "host")
    applications = [
        (
            PressApplication,
            {
                "code": "press",
                "mount": "",
                "root": str(root),
                "grants": grants,
                "sites_config": sites,
            },
        )
    ]
    options = {}
    if administration is not None:
        from .admin.host import AdminApplication, AdminConfiguration

        admin = dict(administration)
        management_origin = admin.pop("origin")
        users = admin.pop("users")
        if admin:
            raise ValueError("Unknown administration configuration")
        applications.append((AdminApplication, {"code": "admin", "mount": "admin"}))
        options.update(
            users=users,
            middleware={"session": {"secure": management_origin.startswith("https:")}},
        )
    server_options = dict(
        applications=applications,
        auth=auth,
        plugins={"openapi": True},
        credential_cache_ttl=0,
        storage=[
            {"name": "site", "protocol": "local", "base_path": str(root / "host")},
            {"name": "home", "protocol": "local", "base_path": str(root / "host")},
        ],
        **options,
    )
    if administration is None:
        return AsgiServer(**server_options)
    config = ConfigurationHandler(
        AdminConfiguration(server_options), parents=[DefaultConfiguration]
    )
    from .admin.host import ManagementGuard

    return ManagementGuard(AsgiServer(config=config, **server_options), management_origin)
