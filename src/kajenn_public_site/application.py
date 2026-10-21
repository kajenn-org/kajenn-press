"""Authenticated Kajenn REST/MCP adapter; business rules live in services."""

from pathlib import Path
from typing import ClassVar

from genro_routes import route
from kajenn import AsgiServer, HTTPException, McpOpenApiApplication
from kajenn.lifespan import FatalBootError

from .catalog.errors import CommitUncertain
from .catalog.filesystem import private_directory
from .catalog.local import LocalCatalog
from .domain import MUTATIONS, AccessPolicy, DomainError
from .services.editorial import EditorialService


class PublicSiteApplication(McpOpenApiApplication):
    openapi_info: ClassVar[dict] = {
        "title": "kajenn-public-site",
        "version": "0.1.0",
        "description": "Private editorial services; exact revisions and named sources",
    }
    mcp_name = "kajenn-public-site"

    def __init__(self, catalog_root, grants, **kwargs):
        self.catalog_root = Path(catalog_root)
        self.policy = AccessPolicy(grants)
        self.service = None
        super().__init__(**kwargs)

    def on_startup(self):
        try:
            self.service = EditorialService(LocalCatalog(self.catalog_root), self.policy)
        except Exception as exc:
            # Ordinary hook exceptions are only logged by Kajenn. Ownership or
            # integrity failure must prevent serving an uninitialized backend.
            raise FatalBootError("Cannot open the private editorial catalog") from exc

    def on_shutdown(self):
        if self.service is not None:
            self.service.catalog.close()
            self.service = None

    def _execute(self, request, operation, arguments):
        if request is None or request.avatar() is None:
            raise HTTPException(401, "Authentication required")
        is_rest = request.scope.get("kajenn.channel") != "mcp"
        if is_rest and operation in MUTATIONS and request.scope["method"] != "POST":
            raise HTTPException(405, "Mutations require POST")
        if self.service is None:
            raise HTTPException(503, "Editorial service is not started")
        try:
            result = self.service.execute(request.avatar().identity, operation, **arguments)
            return {"ok": True, "result": result}
        except DomainError as exc:
            if is_rest:
                request.response.status_code = {
                    "unauthenticated": 401,
                    "forbidden": 403,
                    "not_found": 404,
                    "conflict": 409,
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
    def records_list(
        self, scope: str, kind: str | None = None, _request=None
    ) -> dict:
        """Records list. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(_request, "records_list", {"scope": scope, "kind": kind})

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def content_create(
        self, site_id: str, key: str, title: str, _request=None
    ) -> dict:
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
    def record_read(
        self, record_id: str, revision_id: str | None = None, _request=None
    ) -> dict:
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
    def dependencies(
        self, record_id: str, revision_id: str | None = None, _request=None
    ) -> dict:
        """Dependencies. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request, "dependencies", {"record_id": record_id, "revision_id": revision_id}
        )

    @route(channel_channels="mcp,rest", auth_rule="editor", openapi_method="post")
    def readiness(
        self, record_id: str, revision_id: str | None = None, _request=None
    ) -> dict:
        """Readiness. See capabilities for domain schemas and exact-source semantics."""
        return self._execute(
            _request, "readiness", {"record_id": record_id, "revision_id": revision_id}
        )


def create_server(catalog_root, *, auth, grants):
    """Build a host with explicit credentials/policy and private local storage.

    Authentication configuration belongs to the deployment; API clients cannot
    supply it. The `editor` Kajenn tag admits transport access, scope grants
    decide every domain action. Missing grants deny access by default.
    """
    root = private_directory(catalog_root)
    private_directory(root / "host")
    return AsgiServer(
        applications=[
            (
                PublicSiteApplication,
                {"code": "public_site", "mount": "", "catalog_root": str(root), "grants": grants},
            )
        ],
        auth=auth,
        plugins={"openapi": True},
        credential_cache_ttl=0,
        storage=[
            {"name": "site", "protocol": "local", "base_path": str(root / "host")},
            {"name": "home", "protocol": "local", "base_path": str(root / "host")},
        ],
    )
