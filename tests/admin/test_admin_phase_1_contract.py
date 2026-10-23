"""Plan-owned behavior contracts; implement only the copied test bodies."""

import asyncio
import hashlib
import importlib.metadata
import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest

pytest.importorskip("gramlot", reason="Run the admin contract suite in the qualified admin profile")

from api.support import call, seed_http

from admin.support import admin_client, login, open_page, rpc
from kajenn_public_site.admin.host import CURRENT_REQUEST


def test_admin_is_optional_and_installs_from_reproducible_artifacts(tmp_path):  # wf:phase-1:new
    # wf:contract: The editorial-only installation starts without Gramlot or the admin adapter; the
    # wf:contract: optional admin installation uses recorded reproducible artifacts.
    # wf:contract: The installed admin artifact exposes CodeMirror, HTML and Markdown editors,
    # wf:contract: allowHtml in the Python grammar and browser bundle, and compatible adapter APIs.
    headless = os.environ["KAJENN_APP_PYTHON"]
    probe = subprocess.run(
        [
            headless,
            "-I",
            "-c",
            "import importlib.util; import kajenn_public_site.application; assert importlib.util.find_spec('gramlot') is None; assert importlib.util.find_spec('gramlot_py_server') is None",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr
    manifest = json.loads(Path("docs/admin-artifacts.json").read_text())
    for item in manifest["artifacts"]:
        assert importlib.metadata.version(item["distribution"]) == item["version"]
        wheel = (
            Path(os.environ.get("KAJENN_ADMIN_WHEELS", "/tmp/kajenn-macro3-wheels"))
            / item["filename"]
        )
        assert hashlib.sha256(wheel.read_bytes()).hexdigest() == item["sha256"]
    core = Path(importlib.metadata.distribution("gramlot").locate_file("gramlot"))
    grammar = (core / "collections/editors.json").read_text()
    bundle = (core / "resources/components/editors.js").read_text()
    for name in ("codeMirror", "htmlEditor", "markdownEditor", "markdownPreview", "allowHtml"):
        assert name in grammar and name in bundle
    assert (
        "identity"
        in __import__("inspect")
        .signature(__import__("gramlot.server", fromlist=["GramlotServer"]).GramlotServer.call)
        .parameters
    )

    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, _server):
            for asset in ("editors.js", "layout.js", "inputs.js", "tree.js"):
                response = await http.get("/admin/assets/" + asset)
                assert (
                    response.status_code == 200 and "javascript" in response.headers["content-type"]
                )
            assert (await http.get("/admin/themes/gramlot-base/theme.css")).status_code == 200

    asyncio.run(check())


def test_request_identity_is_current_isolated_and_not_client_supplied(tmp_path):  # wf:phase-1:new
    # wf:contract: Concurrent admin RPC requests execute common services under their own
    # wf:contract: authenticated server identity.
    # wf:contract: Client Data and page-owner cookies cannot supply or replace service identity;
    # wf:contract: request context is cleared on success and failure.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            _site, other, _template, content, _variant = await seed_http(http)
            service = server.applications["public_site"].service
            service.policy.grants["writer"] = {"site:" + other["record_id"]: ["read"]}
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=server),
                base_url=str(http.base_url),
                headers={"Origin": str(http.base_url).rstrip("/")},
            ) as writer:
                writer_page = await login(writer, "writer")
                requests = [
                    rpc(http, page, "read", operation="sites_list"),
                    rpc(writer, writer_page, "read", operation="sites_list"),
                ] * 5
                results = await asyncio.gather(*requests)
                for result in results[::2]:
                    assert len(result["value"]) == 2
                for result in results[1::2]:
                    assert [r["record_id"] for r in result["value"]] == [other["record_id"]]
                for args in ({"identity": "admin"}, {"principal": "admin"}, {"_request": "admin"}):
                    assert "error" in await rpc(
                        writer, writer_page, "read", operation="sites_list", arguments=args
                    )
                assert "error" in await rpc(
                    writer,
                    writer_page,
                    "read",
                    operation="record_read",
                    arguments={"record_id": content["record_id"]},
                )
                assert "error" in await rpc(writer, page, "read", operation="sites_list")
            with pytest.raises(LookupError):
                CURRENT_REQUEST.get()

    asyncio.run(check())


def test_logout_and_grant_revocation_apply_to_open_pages(tmp_path):  # wf:phase-1:new
    # wf:contract: A previously opened administration page cannot continue protected reads or
    # wf:contract: writes after logout or relevant grant revocation.
    # wf:contract: A page-owner cookie alone does not authenticate an operator.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            site, _other, _template, content, _variant = await seed_http(http)
            assert "value" in await rpc(
                http,
                page,
                "detail",
                "source",
                site=site["record_id"],
                selected=content["record_id"],
            )
            service = server.applications["public_site"].service
            rights = service.policy.grants.pop("admin")
            refused = await rpc(
                http,
                page,
                "read",
                operation="record_read",
                arguments={"record_id": content["record_id"]},
            )
            assert "error" in refused
            _, mutation = await call(
                http,
                "rest",
                "content_create",
                key="revoked",
                site_id=site["record_id"],
                title="denied",
            )
            assert not mutation["ok"]
            service.policy.grants["admin"] = rights
            assert (await rpc(http, page, "sign_out"))["value"] is True
            assert "gramlot_owner" in http.cookies
            for name, args in (("read", {"operation": "sites_list"}), ("sign_out", {})):
                assert "error" in await rpc(http, page, name, **args)
            denied = await http.post(
                "/content_create",
                json={"key": "out", "site_id": site["record_id"], "title": "denied"},
            )
            assert denied.status_code in {401, 403}

    asyncio.run(check())


def test_admin_session_mutations_require_the_authorized_origin(tmp_path):  # wf:phase-1:new
    # wf:contract: Session-authenticated mutation requests from an unauthorized origin are rejected
    # wf:contract: without changing catalog state.
    # wf:contract: The supported same-origin admin flow succeeds without exposing permanent API
    # wf:contract: credentials in Data.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            site, *_ = await seed_http(http)
            catalog = server.applications["public_site"].service.catalog
            generation = catalog.read().generation
            for path, payload in (
                (
                    "/content_create",
                    {"key": "csrf", "site_id": site["record_id"], "title": "injected"},
                ),
                (
                    "/mcp",
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "content_create",
                            "arguments": {
                                "key": "csrf",
                                "site_id": site["record_id"],
                                "title": "injected",
                            },
                        },
                    },
                ),
                (
                    "/admin/gramlot/rpc",
                    {
                        "id": "x",
                        "pageId": page,
                        "name": "sign_out",
                        "contentType": "data",
                        "params": {},
                    },
                ),
                ("/_server/logout", {}),
                ("/_server/login", {"identity": "admin", "password": "fixture-only"}),
            ):
                response = await http.post(
                    path, json=payload, headers={"Origin": "https://evil.test"}
                )
                assert response.status_code == 403
            http.headers.pop("Origin")
            response = await http.post(
                "/content_create", json={}, headers={"Authorization": "Bearer invalid"}
            )
            assert response.status_code in {401, 403}
            http.headers["Origin"] = str(http.base_url).rstrip("/")
            assert catalog.read().generation == generation
            assert (await http.get("/_server/logout")).status_code == 405
            _, created = await call(
                http,
                "rest",
                "content_create",
                key="allowed",
                site_id=site["record_id"],
                title="Allowed",
            )
            assert created["ok"]
            main = (await rpc(http, page, "main", "source"))["value"]
            assert (
                "fixture-only" not in main
                and "test-admin-token" not in main
                and "session_id" not in main
            )
            assert all(
                "HttpOnly" in cookie
                for cookie in (await http.get("/admin/")).headers.get_list("set-cookie")
                if cookie.startswith("session_id")
            )

    asyncio.run(check())


def test_site_and_library_navigation_has_explicit_record_boundaries(tmp_path):  # wf:phase-1:new
    # wf:contract: The browser shows the selected site and keeps the shared library separate;
    # wf:contract: content and resource lists contain only their declared kinds and readable
    # wf:contract: scopes.
    # wf:contract: Operational publication records remain excluded from generic editorial read,
    # wf:contract: list and history operations.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            site, other, _template, content, _variant = await seed_http(http)
            for section, expected, excluded in (
                ("content", "Article", "source only"),
                ("resource", "No items", "Article"),
                ("library", "Shared library", "Article"),
            ):
                view = await rpc(
                    http, page, "workspace", "source", site=site["record_id"], section=section
                )
                assert expected in view["value"] and excluded not in view["value"]
            view = await rpc(
                http,
                page,
                "detail",
                "source",
                site=other["record_id"],
                selected=content["record_id"],
            )
            assert "Selection unavailable" in view["value"] and "Article" not in view["value"]
            service = server.applications["public_site"].service
            from kajenn_public_site.catalog.local import Change

            # A genuine operational catalog record, never an editorial record.
            service.catalog.commit(
                changes=[
                    Change(
                        scope="site:" + site["record_id"],
                        data={
                            "kind": "publication_settings",
                            "attributes": {"secret": "operational"},
                        },
                    )
                ],
                key="operational",
                principal="admin",
                scope="site:" + site["record_id"],
                authorize=lambda *_: None,
            )
            snapshot = service.catalog.read()
            operation = next(
                r
                for r in snapshot.revisions.values()
                if r["data"]["kind"] == "publication_settings"
            )
            for name in ("record_read", "revision_history", "revision_index"):
                denied = (await call(http, "rest", name, record_id=operation["record_id"]))[1]
                assert not denied["ok"]
                if name != "revision_history":
                    assert "error" in await rpc(
                        http,
                        page,
                        "read",
                        operation=name,
                        arguments={"record_id": operation["record_id"]},
                    )
            listing = (
                await rpc(
                    http,
                    page,
                    "read",
                    operation="records_index",
                    arguments={"scope": "site:" + site["record_id"]},
                )
            )["value"]
            assert all(not item["kind"].startswith("publication_") for item in listing)

    asyncio.run(check())


def test_lightweight_lists_do_not_eagerly_load_private_payloads(
    tmp_path, monkeypatch
):  # wf:phase-1:new
    # wf:contract: Administration list projections omit source/media payloads and return stable
    # wf:contract: record identifiers; selecting an authorized detail loads only the requested
    # wf:contract: data.
    # wf:contract: Unauthorized details and exact revisions cannot be obtained by altering client
    # wf:contract: identifiers.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            site, _other, template, _content, variant = await seed_http(http)
            catalog = server.applications["public_site"].service.catalog
            calls = []
            original = catalog.read_payload

            def tracked(*args, **kwargs):  # wf:phase-1:new
                calls.append(args)
                return original(*args, **kwargs)

            monkeypatch.setattr(catalog, "read_payload", tracked)
            for operation, arguments in (
                ("records_index", {"scope": "library"}),
                ("records_index", {"scope": "site:" + site["record_id"]}),
                ("revision_index", {"record_id": template["record_id"]}),
            ):
                records = (await rpc(http, page, "read", operation=operation, arguments=arguments))[
                    "value"
                ]
                assert records and all("sources" not in r and "payloads" not in r for r in records)
            assert calls == []
            detail = await rpc(
                http,
                page,
                "read",
                operation="record_read",
                arguments={"record_id": template["record_id"]},
            )
            assert detail["value"]["sources"] and len(calls) == 1
            assert calls[0][0] == template["revision_id"]
            assert "error" in await rpc(
                http,
                page,
                "read",
                operation="record_read",
                arguments={
                    "record_id": template["record_id"],
                    "revision_id": variant["revision_id"],
                },
            )
            server.applications["public_site"].service.policy.grants["admin"].pop("*")
            assert "error" in await rpc(
                http,
                page,
                "read",
                operation="record_read",
                arguments={
                    "record_id": template["record_id"],
                    "revision_id": template["revision_id"],
                },
            )

    asyncio.run(check())


def test_effective_capabilities_and_new_reads_are_shared(tmp_path):  # wf:phase-1:new
    # wf:contract: Effective capabilities are computed for the authenticated identity and scope,
    # wf:contract: not inferred from a global permission vocabulary.
    # wf:contract: New application reads and capability projections return equivalent authorized
    # wf:contract: outcomes through UI, REST and MCP; commands independently recheck permissions.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, server):
            page = await login(http)
            site, _other, template, _content, _variant = await seed_http(http)
            service = server.applications["public_site"].service
            service.policy.grants["admin"] = {
                "site:" + site["record_id"]: ["read"],
                "library": ["read", "use"],
            }
            for operation, arguments in (
                ("scope_capabilities", {"scope": "site:" + site["record_id"]}),
                ("records_index", {"scope": "library"}),
                ("revision_index", {"record_id": template["record_id"]}),
            ):
                ui = await rpc(http, page, "read", operation=operation, arguments=arguments)
                rest = (await call(http, "rest", operation, **arguments))[1]
                mcp = (await call(http, "mcp", operation, **arguments))[1]
                assert ui["value"] == rest["result"] == mcp["result"]
                if operation == "scope_capabilities":
                    assert ui["value"]["permissions"] == ["read"]
            _, denied = await call(
                http,
                "mcp",
                "content_create",
                key="no-write",
                site_id=site["record_id"],
                title="denied",
            )
            assert not denied["ok"] and denied["error"]["code"] == "forbidden"
            assert "error" in await rpc(
                http, page, "read", operation="content_create", arguments={}
            )

    asyncio.run(check())


def test_workspace_refresh_restores_context_from_authorized_services(tmp_path):  # wf:phase-1:new
    # wf:contract: After browser refresh an authenticated operator can select a readable site or
    # wf:contract: library and inspect a record without private filesystem access or remembered
    # wf:contract: object handles.
    # wf:contract: Unknown, stale and inaccessible selections produce clear outcomes without
    # wf:contract: disclosing another scope.
    async def check():  # wf:phase-1:new
        async with admin_client(tmp_path) as (http, _server):
            await login(http)
            site, other, template, content, _variant = await seed_http(http)
            for _ in range(2):
                page = await open_page(http)
                main = await rpc(http, page, "main", "source")
                assert "Current site" in main["value"] and "site_selector" in main["value"]
                selector = await rpc(http, page, "site_selector", "source")
                assert site["record_id"] in selector["value"]
                for section, selected in (
                    ("content", content["record_id"]),
                    ("library", template["record_id"]),
                ):
                    view = await rpc(
                        http,
                        page,
                        "detail",
                        "source",
                        site=site["record_id"],
                        section=section,
                        selected=selected,
                    )
                    assert selected in view["value"] and "Read-only" in view["value"]
                for params in (
                    {"site": other["record_id"], "selected": content["record_id"]},
                    {"site": site["record_id"], "selected": "missing"},
                    {
                        "site": site["record_id"],
                        "selected": content["record_id"],
                        "revision": "missing",
                    },
                ):
                    view = await rpc(http, page, "detail", "source", **params)
                    assert "Article" not in view["value"] and "status" in view["value"]

    asyncio.run(check())


def test_admin_preview_and_public_origins_remain_separate(tmp_path):  # wf:phase-1:new
    # wf:contract: Mounting administration on the management origin preserves Macro 2 private-
    # wf:contract: preview and public-host routing.
    # wf:contract: Admin-only routes and session credentials are not exposed by preview or public
    # wf:contract: origins.
    from publication.support import CONFIG, site_fixture
    from publication.test_gateway import exchange
    from publication.test_release_api import RELEASE_GRANTS, build_http, command

    async def check():  # wf:phase-1:new
        config = {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
        async with admin_client(tmp_path, grants=RELEASE_GRANTS, publication=config) as (
            http,
            server,
        ):
            await login(http)
            app = server.applications["public_site"]
            fixture = await asyncio.to_thread(site_fixture, app.service, app.publication)
            app.publication.public_origins["https://one.test"] = fixture["settings"]["record_id"]
            build = await build_http(http, fixture, "admin-separation")
            grant = await command(
                http,
                "rest",
                "preview_grant_create",
                build_id=build["record_id"],
                lifetime_seconds=300,
                key="admin-preview",
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=server), base_url=CONFIG["preview_origin"]
            ) as preview:
                url = await exchange(preview, grant)
                assert (await preview.get(url + "it/")).status_code == 200
                for origin in (CONFIG["preview_origin"], "https://one.test"):
                    for path in ("/admin/", "/admin/gramlot/rpc", "/_server/login"):
                        response = await preview.get(
                            origin + path,
                            headers={"Cookie": "session_id=" + http.cookies["session_id"]},
                        )
                        assert response.status_code == 404 and "set-cookie" not in response.headers
                assert "session_id" not in preview.cookies

    asyncio.run(check())
