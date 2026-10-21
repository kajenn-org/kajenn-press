"""Plan-time contract skeletons; intentionally pending implementation."""

import asyncio
import importlib.util

import pytest
from api.support import call, client, seed_http
from api.support import record as api_record
from catalog.support import workspace
from services.scenarios import BLOCKS, DECLARATIONS, create_service, record, seed

from kajenn_public_site.domain import DomainError


def test_rest_and_mcp_share_domain_results():
    # wf:contract: Execute creation, draft save, exact revision read and conflicting save through both REST and MCP.
    # wf:contract: Both channels enforce the same application rules and expose equivalent IDs, generations and error codes.
    async def scenario(root):
        async with client(root) as (http, _server):
            _, _, template, _, variant = await seed_http(http)
            saved = await api_record(
                http,
                "mcp",
                "draft_save",
                key="save",
                variant_id=variant["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks={},
            )
            replay = await api_record(
                http,
                "rest",
                "draft_save",
                key="save",
                variant_id=variant["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks={},
            )
            assert replay == saved
            results = []
            for channel in ("rest", "mcp"):
                _, read = await call(
                    http,
                    channel,
                    "record_read",
                    record_id=variant["record_id"],
                    revision_id=variant["revision_id"],
                )
                assert read["result"] == variant
                status, error = await call(
                    http,
                    channel,
                    "draft_save",
                    key="conflict-" + channel,
                    variant_id=variant["record_id"],
                    expected_generation=1,
                    template_revision=template["revision_id"],
                    blocks=BLOCKS,
                )
                assert status == (409 if channel == "rest" else 200)
                results.append(error["error"])
            assert results[0] == results[1]
            assert results[0]["code"] == "conflict"
        async with client(root) as (http, _server):
            _, read = await call(http, "mcp", "record_read", record_id=saved["record_id"])
            assert read["result"] == saved

    with workspace() as root:
        asyncio.run(scenario(root))


def test_authorization_is_shared_and_scoped():
    # wf:contract: A caller without the required site or generic-library grant cannot read or modify protected records through REST or MCP.
    # wf:contract: Payload role declarations cannot grant authority.
    async def scenario(root):
        async with client(root) as (http, server):
            site, other, template, _, _ = await seed_http(http)
            policy = server.applications["public_site"].policy
            policy.grants["writer"] = {
                "site:" + site["record_id"]: ["read", "write", "use"],
                "library": ["read", "use"],
            }
            http.headers["Authorization"] = "Bearer test-writer-token"
            for channel in ("rest", "mcp"):
                _, denied = await call(http, channel, "record_read", record_id=other["record_id"])
                assert denied["error"]["code"] == "forbidden"
                _, denied = await call(
                    http,
                    channel,
                    "resource_save",
                    key=channel,
                    scope="library",
                    kind="css",
                    name="x",
                    source="x",
                    roles=["admin"],
                    principal="admin",
                )
                assert not denied.get("ok", False)
                _, allowed = await call(
                    http,
                    channel,
                    "resource_copy",
                    key="copy",
                    source_revision=template["revision_id"],
                    site_id=site["record_id"],
                    name="local",
                )
                assert allowed["ok"]
            http.headers["Authorization"] = "Bearer test-outsider-token"
            for channel in ("rest", "mcp"):
                _, denied = await call(
                    http, channel, "record_read", record_id=template["record_id"]
                )
                assert denied["error"]["code"] == "forbidden"

    with workspace() as root:
        asyncio.run(scenario(root))


def test_named_blocks_preserve_format_and_source():
    # wf:contract: A template declares named HTML and Markdown blocks and their required status.
    # wf:contract: Saving and reopening a draft preserves names, source formats and exact source text without converting the canonical source.
    with workspace() as root:
        service = create_service(root)
        try:
            _, _, template, _, variant = seed(service)
            assert template["attributes"]["blocks"] == DECLARATIONS
            assert variant["attributes"]["blocks"] == {
                name: {"format": value["format"]} for name, value in BLOCKS.items()
            }
            for name, value in BLOCKS.items():
                assert variant["sources"]["block." + name]["text"] == value["source"]
        finally:
            service.catalog.close()
        service = create_service(root)
        try:
            assert (
                service.execute("admin", "record_read", record_id=variant["record_id"]) == variant
            )
        finally:
            service.catalog.close()


def test_incomplete_draft_can_be_saved():
    # wf:contract: A draft missing a required template block can be saved and reopened.
    # wf:contract: Publication-readiness validation reports the missing block by name; an empty optional block is not a blocking error.
    with workspace() as root:
        service = create_service(root)
        try:
            _, _, template, _, variant = seed(service)
            saved = record(
                service,
                "draft_save",
                key="empty",
                variant_id=variant["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks={},
            )
            report = service.execute("admin", "readiness", record_id=saved["record_id"])
            assert not report["ready"]
            assert [(d["resource_id"], d["block"]) for d in report["diagnostics"]] == [
                (variant["record_id"], "intro")
            ]
            filled = record(
                service,
                "draft_save",
                key="filled",
                variant_id=variant["record_id"],
                expected_generation=2,
                template_revision=template["revision_id"],
                blocks={"intro": BLOCKS["intro"], "body": {"format": "markdown", "source": ""}},
            )
            assert service.execute("admin", "readiness", record_id=filled["record_id"])["ready"]
        finally:
            service.catalog.close()


def test_shared_draft_conflict_preserves_history():
    # wf:contract: Each content and language has one shared draft.
    # wf:contract: A stale edit is rejected without altering the accepted head or losing its preceding immutable revisions.
    with workspace() as root:
        service = create_service(root)
        try:
            _, _, template, _, variant = seed(service)
            saved = record(
                service,
                "draft_save",
                key="saved",
                variant_id=variant["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks={},
            )
            before = service.catalog.read()
            with pytest.raises(DomainError) as error:
                record(
                    service,
                    "draft_save",
                    key="stale",
                    variant_id=variant["record_id"],
                    expected_generation=1,
                    template_revision=template["revision_id"],
                    blocks=BLOCKS,
                )
            assert error.value.code == "conflict"
            assert service.catalog.read() == before
            assert service.execute("admin", "record_read", record_id=variant["record_id"]) == saved
            assert (
                service.execute(
                    "admin",
                    "record_read",
                    record_id=variant["record_id"],
                    revision_id=variant["revision_id"],
                )
                == variant
            )
        finally:
            service.catalog.close()


def test_generic_resource_copy_is_independent():
    # wf:contract: Copying a selected generic resource revision into a site creates a new resource identity and revision history.
    # wf:contract: Subsequent changes to either resource do not alter the other; exact dependency references and provenance are retained.
    with workspace() as root:
        service = create_service(root)
        try:
            site, _, template, _, _ = seed(service)
            copied = record(
                service,
                "resource_copy",
                key="copy",
                source_revision=template["revision_id"],
                site_id=site["record_id"],
                name="local",
            )
            assert copied["record_id"] != template["record_id"]
            assert copied["attributes"]["copied_from"] == template["revision_id"]
            record(
                service,
                "resource_save",
                key="original-change",
                scope="library",
                kind="template",
                name="page",
                source="original changed",
                engine="gramlot",
                blocks=DECLARATIONS,
                record_id=template["record_id"],
                expected_generation=1,
            )
            assert service.execute("admin", "record_read", record_id=copied["record_id"]) == copied
            updated = record(
                service,
                "resource_save",
                key="copy-change",
                scope="site:" + site["record_id"],
                kind="template",
                name="local",
                source="local changed",
                engine="gramlot",
                blocks=DECLARATIONS,
                record_id=copied["record_id"],
                expected_generation=1,
            )
            assert updated["attributes"]["copied_from"] == template["revision_id"]
            assert (
                service.execute("admin", "record_read", record_id=template["record_id"])["sources"][
                    "source"
                ]["text"]
                == "original changed"
            )
            assert (
                service.execute(
                    "admin",
                    "record_read",
                    record_id=template["record_id"],
                    revision_id=template["revision_id"],
                )
                == template
            )
        finally:
            service.catalog.close()


def test_languages_have_independent_draft_heads():
    # wf:contract: Saving one language variant does not modify another language draft head or its revisions.
    # wf:contract: Translation provenance does not create an implicit requirement to save other variants together.
    with workspace() as root:
        service = create_service(root)
        try:
            _, _, template, content, italian = seed(service)
            english = record(
                service,
                "variant_create",
                key="english",
                content_id=content["record_id"],
                language="en",
                template_revision=template["revision_id"],
                translated_from=italian["revision_id"],
                blocks={},
            )
            record(
                service,
                "draft_save",
                key="it-save",
                variant_id=italian["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks={},
            )
            assert (
                service.execute("admin", "record_read", record_id=english["record_id"]) == english
            )
            updated = record(
                service,
                "draft_save",
                key="en-save",
                variant_id=english["record_id"],
                expected_generation=1,
                template_revision=template["revision_id"],
                blocks=BLOCKS,
            )
            assert updated["generation"] == 2
            assert updated["attributes"]["translated_from"] == italian["revision_id"]
        finally:
            service.catalog.close()


def test_filesystem_backend_has_no_asqueel_dependency():
    # wf:contract: The application starts and completes the site, draft, source and resource-copy scenarios without Asqueel or a PostgreSQL driver installed.
    # wf:contract: Restart preserves IDs, revisions, generations and storage references required by later rendering and a future catalog migration.
    async def scenario(root):
        async with client(root) as (http, _server):
            site, _, template, _, variant = await seed_http(http, "mcp")
            copied = await api_record(
                http,
                "rest",
                "resource_copy",
                key="copy",
                source_revision=template["revision_id"],
                site_id=site["record_id"],
                name="local",
            )
        async with client(root) as (http, _server):
            for expected in (site, template, variant, copied):
                _, result = await call(
                    http,
                    "mcp",
                    "record_read",
                    record_id=expected["record_id"],
                    revision_id=expected["revision_id"],
                )
                assert result["result"] == expected

    for module in ("asqueel", "psycopg", "psycopg2", "asyncpg", "sqlalchemy", "gramlot"):
        assert importlib.util.find_spec(module) is None
    with workspace() as root:
        asyncio.run(scenario(root))


def test_clients_can_discover_templates_and_read_sources():
    # wf:contract: REST and MCP expose template block declarations and exact readable source revisions for authorized clients.
    # wf:contract: Validation errors identify the relevant resource and block so an LLM can correct the input without browser automation.
    async def scenario(root):
        async with client(root) as (http, _server):
            _, _, template, _, variant = await seed_http(http)
            schema = (await http.get("/_meta/schema_json")).json()
            assert {"/resource_save", "/record_read", "/capabilities", "/readiness"} <= set(
                schema["paths"]
            )
            tools = (
                await http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            ).json()["result"]["tools"]
            assert {"resource_save", "record_read", "capabilities", "readiness"} <= {
                tool["name"] for tool in tools
            }
            for channel in ("rest", "mcp"):
                _, read = await call(
                    http,
                    channel,
                    "record_read",
                    record_id=template["record_id"],
                    revision_id=template["revision_id"],
                )
                assert read["result"]["attributes"]["blocks"] == DECLARATIONS
                assert read["result"]["sources"] == template["sources"]
                _, error = await call(
                    http,
                    channel,
                    "draft_save",
                    key="bad-" + channel,
                    variant_id=variant["record_id"],
                    expected_generation=1,
                    template_revision=template["revision_id"],
                    blocks={"intro": {"format": "markdown", "source": "wrong"}},
                )
                assert error["error"]["resource_id"] == variant["record_id"]
                assert error["error"]["block"] == "intro"

    with workspace() as root:
        asyncio.run(scenario(root))
