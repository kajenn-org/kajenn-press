"""Authenticated Kajenn REST/MCP adapter; business rules live in services."""

import asyncio
from pathlib import Path
from typing import ClassVar

from genro_routes import route
from kajenn import AsgiServer, HTTPException, McpOpenApiApplication
from kajenn.lifespan import FatalBootError

from .catalog.errors import CommitUncertain
from .catalog.filesystem import private_directory
from .catalog.local import LocalCatalog
from .domain import MUTATIONS, AccessPolicy, DomainError
from .publication.gateway import PreviewGateway
from .publication.service import EXPORTS, READS, PublicationService
from .publication.service import OPERATIONS as PUBLICATION_OPERATIONS
from .rendering.contract import RenderProblem
from .rendering.process import RenderWorker
from .rendering.service import RenderService
from .services.editorial import EditorialService


class PublicSiteApplication(McpOpenApiApplication):
    openapi_info: ClassVar[dict] = {
        "title": "kajenn-public-site",
        "version": "0.1.0",
        "description": "Private editorial services; exact revisions and named sources",
    }
    mcp_name = "kajenn-public-site"

    def __init__(self, catalog_root, grants, publication_config=None, **kwargs):
        self.catalog_root = Path(catalog_root)
        self.policy = AccessPolicy(grants)
        self.service = None
        self.publication = None
        self.publication_config = publication_config
        super().__init__(**kwargs)

    async def on_startup(self):
        await asyncio.to_thread(self._open_services)

    def _open_services(self):
        try:
            self.service = EditorialService(LocalCatalog(self.catalog_root), self.policy)
            if self.publication_config is not None:
                config = dict(self.publication_config)
                worker = RenderWorker(
                    config.pop("render_python"),
                    timeout=config.pop("worker_timeout", 15),
                    output_limit=config.pop("worker_output_limit", 8 * 1024 * 1024),
                )
                self.publication = PublicationService(
                    self.service.catalog, self.policy, worker, **config
                )
        except Exception as exc:
            self._close_services()
            # Ordinary hook exceptions are only logged by Kajenn. Ownership or
            # integrity failure must prevent serving an uninitialized backend.
            raise FatalBootError("Cannot open the private editorial catalog") from exc

    async def on_shutdown(self):
        await asyncio.to_thread(self._close_services)

    def _close_services(self):
        if self.publication is not None:
            self.publication.close()
            self.publication = None
        if self.service is not None:
            self.service.catalog.close()
            self.service = None

    def _execute(self, request, operation, arguments):
        if request is None or request.avatar() is None:
            raise HTTPException(401, "Authentication required")
        is_rest = request.scope.get("kajenn.channel") != "mcp"
        if (
            is_rest
            and operation
            in (MUTATIONS | (PUBLICATION_OPERATIONS - READS) | EXPORTS | {"render_preview"})
            and request.scope["method"] != "POST"
        ):
            raise HTTPException(405, "Mutations require POST")
        if self.service is None:
            raise HTTPException(503, "Editorial service is not started")
        try:
            if operation == "render_preview":
                if set(arguments) != {"variant_id", "revision_id"} or any(
                    not isinstance(value, str) or not value for value in arguments.values()
                ):
                    raise DomainError("invalid_input", "An exact variant ID and revision ID are required")
                if self.publication is None:
                    raise DomainError("unavailable", "Configure the optional rendering worker first")
                renderer = RenderService(self.service.catalog, self.policy, self.publication.worker)
                identity = request.avatar().identity
                try:
                    frozen = renderer.freeze(identity, **arguments)
                    result = renderer.render(identity, frozen)
                except RenderProblem as error:
                    result = {"status": "failed", "diagnostics": [error.diagnostic]}
                return {"ok": True, "result": result}
            service = self.publication if operation in PUBLICATION_OPERATIONS else self.service
            if service is None:
                raise DomainError("unavailable", "Configure the optional publication worker first")
            result = service.execute(request.avatar().identity, operation, **arguments)
            if operation == "capabilities" and self.publication is not None:
                result.update(
                    rendering=True,
                    preview=True,
                    publication=True,
                    operations=sorted(set(result["operations"]) | PUBLICATION_OPERATIONS | {"render_preview"}),
                    permissions=result["permissions"] + ["build", "preview_grant", "publish"],
                )
            return {"ok": True, "result": result}
        except DomainError as exc:
            if is_rest:
                request.response.status_code = {
                    "unauthenticated": 401,
                    "forbidden": 403,
                    "not_found": 404,
                    "conflict": 409,
                    "unavailable": 503,
                }.get(exc.code, 422)
            return {"ok": False, "error": exc.as_dict()}
        except CommitUncertain:
            if is_rest:
                request.response.status_code = 503
            return {
                "ok": False,
                "error": {
                    "code": "commit_uncertain",
                    "message": "Reopen and reconcile; retry the same key and input.",
                    "resource_id": None,
                    "block": None,
                    "details": None,
                },
            }

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def capabilities(self, _request=None) -> dict:
        """Capabilities. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(_request, "capabilities", {})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_create(
        self,
        key: str,
        name: str,
        languages: list[str],
        review_required: bool = False,
        _request=None,
    ) -> dict:
        """Site create. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "site_create",
            {"key": key, "name": name, "languages": languages, "review_required": review_required},
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def sites_list(self, _request=None) -> dict:
        """Sites list. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(_request, "sites_list", {})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_configure(
        self,
        site_id: str,
        expected_generation: int,
        key: str,
        name: str,
        languages: list[str],
        review_required: bool = False,
        _request=None,
    ) -> dict:
        """Site configure. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "site_configure",
            {
                "site_id": site_id,
                "expected_generation": expected_generation,
                "key": key,
                "name": name,
                "languages": languages,
                "review_required": review_required,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def records_list(self, scope: str, kind: str | None = None, _request=None) -> dict:
        """Records list. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(_request, "records_list", {"scope": scope, "kind": kind})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def records_index(self, scope: str, kind: str | None = None, _request=None) -> dict:  # wf:phase-1:new
        """List authorized editorial metadata without source or media payloads."""
        return self._execute(_request, "records_index", {"scope": scope, "kind": kind})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def revision_index(self, record_id: str, _request=None) -> dict:  # wf:phase-1:new
        """List exact revision metadata without reading historical payloads."""
        return self._execute(_request, "revision_index", {"record_id": record_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def scope_capabilities(self, scope: str, _request=None) -> dict:  # wf:phase-1:new
        """Read the current principal's actual permissions in a readable scope."""
        return self._execute(_request, "scope_capabilities", {"scope": scope})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def content_create(self, site_id: str, key: str, title: str, _request=None) -> dict:
        """Content create. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request, "content_create", {"site_id": site_id, "key": key, "title": title}
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def variant_create(
        self,
        content_id: str,
        language: str,
        template_revision: str,
        key: str,
        blocks: dict | None = None,
        translated_from: str | None = None,
        _request=None,
    ) -> dict:
        """Variant create. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "variant_create",
            {
                "content_id": content_id,
                "language": language,
                "template_revision": template_revision,
                "key": key,
                "blocks": blocks,
                "translated_from": translated_from,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def draft_save(
        self,
        variant_id: str,
        expected_generation: int,
        template_revision: str,
        blocks: dict,
        key: str,
        _request=None,
    ) -> dict:
        """Draft save. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "draft_save",
            {
                "variant_id": variant_id,
                "expected_generation": expected_generation,
                "template_revision": template_revision,
                "blocks": blocks,
                "key": key,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def resource_save(
        self,
        scope: str,
        kind: str,
        name: str,
        source: str,
        key: str,
        record_id: str | None = None,
        expected_generation: int = 0,
        engine: str | None = None,
        blocks: dict | None = None,
        dependencies: list[str] | None = None,
        _request=None,
    ) -> dict:
        """Resource save. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "resource_save",
            {
                "scope": scope,
                "kind": kind,
                "name": name,
                "source": source,
                "key": key,
                "record_id": record_id,
                "expected_generation": expected_generation,
                "engine": engine,
                "blocks": blocks,
                "dependencies": dependencies,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def media_save(
        self,
        scope: str,
        name: str,
        data_base64: str,
        mime_type: str,
        key: str,
        record_id: str | None = None,
        expected_generation: int = 0,
        _request=None,
    ) -> dict:
        """Media save. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "media_save",
            {
                "scope": scope,
                "name": name,
                "data_base64": data_base64,
                "mime_type": mime_type,
                "key": key,
                "record_id": record_id,
                "expected_generation": expected_generation,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def resource_copy(
        self, source_revision: str, site_id: str, name: str, key: str, _request=None
    ) -> dict:
        """Resource copy. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "resource_copy",
            {"source_revision": source_revision, "site_id": site_id, "name": name, "key": key},
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def record_read(self, record_id: str, revision_id: str | None = None, _request=None) -> dict:
        """Record read. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request, "record_read", {"record_id": record_id, "revision_id": revision_id}
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def revision_history(self, record_id: str, _request=None) -> dict:
        """Revision history. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(_request, "revision_history", {"record_id": record_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def revision_compare(
        self, record_id: str, left_revision: str, right_revision: str, _request=None
    ) -> dict:
        """Revision compare. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "revision_compare",
            {
                "record_id": record_id,
                "left_revision": left_revision,
                "right_revision": right_revision,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def revision_checkpoint(
        self, record_id: str, expected_generation: int, key: str, message: str, _request=None
    ) -> dict:
        """Revision checkpoint. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "revision_checkpoint",
            {
                "record_id": record_id,
                "expected_generation": expected_generation,
                "key": key,
                "message": message,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def revision_restore(
        self,
        record_id: str,
        source_revision: str,
        expected_generation: int,
        key: str,
        _request=None,
    ) -> dict:
        """Revision restore. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request,
            "revision_restore",
            {
                "record_id": record_id,
                "source_revision": source_revision,
                "expected_generation": expected_generation,
                "key": key,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def dependencies(self, record_id: str, revision_id: str | None = None, _request=None) -> dict:
        """Dependencies. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request, "dependencies", {"record_id": record_id, "revision_id": revision_id}
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def readiness(self, record_id: str, revision_id: str | None = None, _request=None) -> dict:
        """Readiness. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request, "readiness", {"record_id": record_id, "revision_id": revision_id}
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def render_preview(self, variant_id: str, revision_id: str, _request=None) -> dict:  # wf:phase-1:new
        """Render an exact saved variant in the configured worker, without publishing it."""
        return self._execute(_request, "render_preview", {"variant_id": variant_id, "revision_id": revision_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def publication_settings_save(
        self,
        site_id: str,
        channel: str,
        public_origin: str,
        primary_language: str,
        landing_variant: str,
        key: str,
        record_id: str | None = None,
        expected_generation: int = 0,
        _request=None,
    ) -> dict:
        """Publication settings save. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(
            _request,
            "publication_settings_save",
            {
                "site_id": site_id,
                "channel": channel,
                "public_origin": public_origin,
                "primary_language": primary_language,
                "landing_variant": landing_variant,
                "key": key,
                "record_id": record_id,
                "expected_generation": expected_generation,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def publication_route_save(
        self,
        variant_id: str,
        path: str,
        title: str,
        description: str,
        key: str,
        record_id: str | None = None,
        expected_generation: int = 0,
        _request=None,
    ) -> dict:
        """Publication route save. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(
            _request,
            "publication_route_save",
            {
                "variant_id": variant_id,
                "path": path,
                "title": title,
                "description": description,
                "key": key,
                "record_id": record_id,
                "expected_generation": expected_generation,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def candidate_create(
        self,
        settings_id: str,
        variant_revisions: list[str],
        key: str,
        base_build_id: str | None = None,
        _request=None,
    ) -> dict:
        """Candidate create. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(
            _request,
            "candidate_create",
            {
                "settings_id": settings_id,
                "variant_revisions": variant_revisions,
                "key": key,
                "base_build_id": base_build_id,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def candidate_read(self, candidate_id: str, _request=None) -> dict:
        """Candidate read. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(_request, "candidate_read", {"candidate_id": candidate_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def build_start(self, candidate_id: str, key: str, _request=None) -> dict:
        """Build start. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(_request, "build_start", {"candidate_id": candidate_id, "key": key})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def build_retry(self, build_id: str, expected_generation: int, key: str, _request=None) -> dict:
        """Build retry. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(
            _request,
            "build_retry",
            {"build_id": build_id, "expected_generation": expected_generation, "key": key},
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def build_status(self, build_id: str, _request=None) -> dict:
        """Build status. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(_request, "build_status", {"build_id": build_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def preview_grant_create(
        self, build_id: str, lifetime_seconds: int, key: str, _request=None
    ) -> dict:
        """Preview grant create. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(
            _request,
            "preview_grant_create",
            {"build_id": build_id, "lifetime_seconds": lifetime_seconds, "key": key},
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def preview_grant_revoke(
        self, grant_id: str, expected_generation: int, key: str, _request=None
    ) -> dict:
        """Preview grant revoke. Exact revisions, explicit grants and idempotent mutation keys."""
        return self._execute(
            _request,
            "preview_grant_revoke",
            {"grant_id": grant_id, "expected_generation": expected_generation, "key": key},
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def channel_create(self, settings_id: str, key: str, _request=None) -> dict:
        """Channel create. Conditional transitions, current publish policy and exact releases."""
        return self._execute(_request, "channel_create", {"settings_id": settings_id, "key": key})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def channel_read(self, settings_id: str, _request=None) -> dict:
        """Channel read. Conditional transitions, current publish policy and exact releases."""
        return self._execute(_request, "channel_read", {"settings_id": settings_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def release_activate(
        self, settings_id: str, build_id: str, expected_generation: int, key: str, _request=None
    ) -> dict:
        """Release activate. Conditional transitions, current publish policy and exact releases."""
        return self._execute(
            _request,
            "release_activate",
            {
                "settings_id": settings_id,
                "build_id": build_id,
                "expected_generation": expected_generation,
                "key": key,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def release_rollback(
        self, settings_id: str, build_id: str, expected_generation: int, key: str, _request=None
    ) -> dict:
        """Release rollback. Conditional transitions, current publish policy and exact releases."""
        return self._execute(
            _request,
            "release_rollback",
            {
                "settings_id": settings_id,
                "build_id": build_id,
                "expected_generation": expected_generation,
                "key": key,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def release_read(self, build_id: str, _request=None) -> dict:
        """Release read. Conditional transitions, current publish policy and exact releases."""
        return self._execute(_request, "release_read", {"build_id": build_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def release_history(self, settings_id: str, _request=None) -> dict:
        """Release history. Conditional transitions, current publish policy and exact releases."""
        return self._execute(_request, "release_history", {"settings_id": settings_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def release_export(self, settings_id: str, _request=None) -> dict:
        """Release export. Copy the active release and its pointer to release storage."""
        return self._execute(_request, "release_export", {"settings_id": settings_id})


def create_server(catalog_root, *, auth, grants, publication=None, administration=None):
    """Build a host with explicit credentials/policy and private local storage.

    Authentication configuration belongs to the deployment; API clients cannot
    supply it. The `editor` Kajenn tag admits transport access, scope grants
    decide every domain action. Missing grants deny access by default.
    """
    root = private_directory(catalog_root)
    private_directory(root / "host")
    applications = [
            (
                PublicSiteApplication,
                {
                    "code": "public_site",
                    "mount": "",
                    "catalog_root": str(root),
                    "grants": grants,
                    "publication_config": publication,
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
        if publication is not None and management_origin != publication["management_origin"]:
            raise ValueError("Administration and publication management origins must match")
        applications.append((AdminApplication, {"code": "admin", "mount": "admin"}))
        options.update(users=users, middleware={"session": {"secure": management_origin.startswith("https:")}})
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
    if administration is not None:
        from kajenn.config import ConfigurationHandler, DefaultConfiguration

        config = ConfigurationHandler(AdminConfiguration(server_options), parents=[DefaultConfiguration])
        server = AsgiServer(config=config, **server_options)
    else:
        server = AsgiServer(**server_options)
    if administration is not None:
        from .admin.host import ManagementGuard

        server = ManagementGuard(server, management_origin)

    if publication is not None:
        return PreviewGateway(
            server, publication["management_origin"], publication["preview_origin"]
        )
    return server
