"""Authenticated Kajenn REST/MCP adapter; business rules live in services."""

import asyncio
from pathlib import Path
from typing import ClassVar

from genro_routes import route
from kajenn import AsgiServer, HTTPException, McpOpenApiApplication
from kajenn.config import ConfigurationHandler, DefaultConfiguration
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
from .site.service import OPERATIONS as SITE_OPERATIONS
from .site.service import SiteService

RENDERS = frozenset({"render_preview", "render_draft"})


class PressApplication(McpOpenApiApplication):
    openapi_info: ClassVar[dict] = {
        "title": "kajenn-press",
        "version": "0.1.0",
        "description": "Private editorial services; exact revisions and named sources",
    }
    mcp_name = "kajenn-press"

    def __init__(self, catalog_root, grants, publication_config=None, sites_config=None, **kwargs):
        self.catalog_root = Path(catalog_root)
        self.policy = AccessPolicy(grants)
        self.service = None
        self.publication = None
        self.publication_config = publication_config
        self.sites_config = sites_config
        self.sites = None
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
            if self.sites_config is not None:
                # s3fs comes with the optional release-s3 extra; an installation without
                # site sources keeps working without it, as the administration does.
                from .site.publish import Publisher
                from .site.store import SourceStore

                config = dict(self.sites_config)
                worker = self.publication.worker if self.publication is not None else None
                if "render_python" in config:
                    worker = RenderWorker(config.pop("render_python"))
                self.sites = SiteService(
                    config.pop("root"),
                    SourceStore(config.pop("sources")),
                    self.policy,
                    worker=worker,
                    connections=config.get("connections", {}),
                    publisher=(
                        Publisher(config.pop("releases"), worker, config.get("connections", {}))
                        if "releases" in config
                        else None
                    ),
                )
                config.pop("connections", None)
                if config:
                    raise ValueError("Unknown site configuration")
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
            in (MUTATIONS | (PUBLICATION_OPERATIONS - READS) | EXPORTS | RENDERS | SITE_OPERATIONS)
            and request.scope["method"] != "POST"
        ):
            raise HTTPException(405, "Mutations require POST")
        if self.service is None:
            raise HTTPException(503, "Editorial service is not started")
        try:
            if operation in SITE_OPERATIONS:
                if self.sites is None:
                    raise DomainError("unavailable", "Configure the site source store first")
                return {"ok": True, "result": self.sites.execute(request.avatar().identity, operation, **arguments)}
            if operation in RENDERS:
                names = {"variant_id", "revision_id"}
                if operation == "render_draft":
                    names |= {"blocks", "resources"}
                if set(arguments) != names:
                    raise DomainError("invalid_input", "Expected " + ", ".join(sorted(names)))
                exact = {"variant_id": arguments["variant_id"], "revision_id": arguments["revision_id"]}
                if any(not isinstance(value, str) or not value for value in exact.values()):
                    raise DomainError("invalid_input", "An exact variant ID and revision ID are required")
                draft = {}
                if operation == "render_draft":
                    draft = {
                        "block_sources": self._sources(arguments["blocks"], "blocks"),
                        "resource_sources": self._sources(arguments["resources"], "resources"),
                        "data_urls": True,
                    }
                if self.publication is None:
                    raise DomainError("unavailable", "Configure the optional rendering worker first")
                renderer = RenderService(self.service.catalog, self.policy, self.publication.worker)
                identity = request.avatar().identity
                try:
                    frozen = renderer.freeze(identity, **exact, **draft)
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
                    operations=sorted(set(result["operations"]) | PUBLICATION_OPERATIONS | RENDERS),
                    permissions=result["permissions"] + ["build", "preview_grant", "publish"],
                )
            if operation == "capabilities" and self.sites is not None:
                result.update(sites=True, operations=sorted(set(result["operations"]) | SITE_OPERATIONS))
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
    def records_index(self, scope: str, kind: str | None = None, _request=None) -> dict:
        """List authorized editorial metadata without source or media payloads."""
        return self._execute(_request, "records_index", {"scope": scope, "kind": kind})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def revision_index(self, record_id: str, _request=None) -> dict:
        """List exact revision metadata without reading historical payloads."""
        return self._execute(_request, "revision_index", {"record_id": record_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def scope_capabilities(self, scope: str, _request=None) -> dict:
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
    def render_preview(self, variant_id: str, revision_id: str, _request=None) -> dict:
        """Render an exact saved variant in the configured worker, without publishing it."""
        return self._execute(_request, "render_preview", {"variant_id": variant_id, "revision_id": revision_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def render_draft(
        self,
        variant_id: str,
        revision_id: str,
        blocks: dict | None = None,
        resources: dict | None = None,
        _request=None,
    ) -> dict:
        """Render unsaved block and resource sources over an exact saved variant; writes nothing.

        blocks maps declared block names to source text; resources maps revision IDs of the
        page's template, CSS or JavaScript to source text and needs write in their scope.
        Resources are referenced as data: URLs.
        """
        return self._execute(
            _request,
            "render_draft",
            {
                "variant_id": variant_id,
                "revision_id": revision_id,
                "blocks": blocks or {},
                "resources": resources or {},
            },
        )

    @staticmethod
    def _sources(mapping, label):
        if not isinstance(mapping, dict) or any(
            not isinstance(key, str) or not key or not isinstance(value, str)
            for key, value in mapping.items()
        ):
            raise DomainError("invalid_input", f"{label} must map names to source text")
        return mapping

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
    def publication_overview(self, site_id: str, _request=None) -> dict:
        """Publication overview: channel settings, routes per variant, channel state and recent builds."""
        return self._execute(_request, "publication_overview", {"site_id": site_id})

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

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def child_save(
        self,
        settings_id: str,
        name: str,
        public_origin: str,
        serving_address: str,
        key: str,
        mount: str = "releases",
        record_id: str | None = None,
        expected_generation: int = 0,
        _request=None,
    ) -> dict:
        """Child save. Register or update a server that serves a channel from release storage."""
        return self._execute(
            _request,
            "child_save",
            {
                "settings_id": settings_id,
                "name": name,
                "public_origin": public_origin,
                "serving_address": serving_address,
                "key": key,
                "mount": mount,
                "record_id": record_id,
                "expected_generation": expected_generation,
            },
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def child_read(self, record_id: str, _request=None) -> dict:
        """Child read. Registry record with catalog and storage releases side by side."""
        return self._execute(_request, "child_read", {"record_id": record_id})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def child_list(self, _request=None) -> dict:
        """Child list. Every registered child readable by the caller, with its releases."""
        return self._execute(_request, "child_list", {})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def child_channels(self, _request=None) -> dict:
        """Child channels. Channel settings a child can be registered for."""
        return self._execute(_request, "child_channels", {})

    # Site operations (N3): the site source model, see kajenn_press.site.service.

    def _site(self, request, operation, **arguments):
        return self._execute(request, operation, arguments)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def site_new(
        self, key: str, name: str, starter_id: str | None = None, _request=None
    ) -> dict:
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
            _request, "template_add", site_id=site_id, key=key, name=name, engine=engine,
            source=source, python_source=python_source,
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
    def content_save(self, site_id: str, key: str, content_id: str, text: str, _request=None) -> dict:
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
            _request, "asset_add", site_id=site_id, key=key, name=name, kind=kind,
            data_base64=data_base64, mime_type=mime_type,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_add(self, site_id: str, key: str, name: str, template_id: str, _request=None) -> dict:
        """Add a page with a copy of a site template."""
        return self._site(
            _request, "page_add", site_id=site_id, key=key, name=name, template_id=template_id
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_url_set(self, site_id: str, key: str, page_id: str, url: str, _request=None) -> dict:
        """Move a page to a new URL path; the old path redirects to it."""
        return self._site(
            _request, "page_url_set", site_id=site_id, key=key, page_id=page_id, url=url
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
            _request, "slot_assign", site_id=site_id, key=key, page_id=page_id, slot=slot,
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
            _request, "copies_update", site_id=site_id, key=key, original_id=original_id,
            selected=selected,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def template_switch_plan(
        self, site_id: str, page_id: str, template_id: str, _request=None
    ) -> dict:
        """Proposed slot mapping, by name, for a page switching template."""
        return self._site(
            _request, "template_switch_plan", site_id=site_id, page_id=page_id,
            template_id=template_id,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def template_switch(
        self, site_id: str, key: str, page_id: str, template_id: str, mapping: dict, _request=None
    ) -> dict:
        """Switch a page's template with the confirmed slot mapping."""
        return self._site(
            _request, "template_switch", site_id=site_id, key=key, page_id=page_id,
            template_id=template_id, mapping=mapping,
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def unplaced_place(
        self, site_id: str, key: str, page_id: str, copy_id: str, slot: str, _request=None
    ) -> dict:
        """Move an unplaced content copy into a free slot."""
        return self._site(
            _request, "unplaced_place", site_id=site_id, key=key, page_id=page_id,
            copy_id=copy_id, slot=slot,
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
    def page_check(self, site_id: str, page_id: str, _request=None) -> dict:
        """Empty slots and unplaced contents of a page."""
        return self._site(_request, "page_check", site_id=site_id, page_id=page_id)

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def page_render(self, site_id: str, page_id: str, _request=None) -> dict:
        """Static HTML of a page, rendered in the worker."""
        return self._site(_request, "page_render", site_id=site_id, page_id=page_id)


def create_server(
    catalog_root, *, auth, grants, publication=None, administration=None, sites=None
):
    """Build a host with explicit credentials/policy and private local storage.

    Authentication configuration belongs to the deployment; API clients cannot
    supply it. The `editor` Kajenn tag admits transport access, scope grants
    decide every domain action. Missing grants deny access by default.
    """
    root = private_directory(catalog_root)
    private_directory(root / "host")
    applications = [
            (
                PressApplication,
                {
                    "code": "press",
                    "mount": "",
                    "catalog_root": str(root),
                    "grants": grants,
                    "publication_config": publication,
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
