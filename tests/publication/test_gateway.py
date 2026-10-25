import asyncio
import os
from urllib.parse import urlsplit

import httpx
from api.support import call, client
from publication.support import CONFIG, site_fixture

GRANTS = {
    "admin": {"*": ["read", "write", "use", "create_site", "build", "preview_grant"]},
    "writer": {"*": ["read", "write", "use"]},
}


async def exchange(browser, grant):
    parsed = urlsplit(grant["url"])
    opened = await browser.get(parsed.path)
    assert opened.status_code == 200 and parsed.fragment not in opened.text
    assert "history.replaceState" in opened.text
    result = await browser.post(
        parsed.path.replace("/open/", "/access/"),
        content=parsed.fragment,
        headers={"origin": CONFIG["preview_origin"]},
    )
    assert result.status_code == 200, result.text
    assert "HttpOnly" in result.headers["set-cookie"] and "Secure" in result.headers["set-cookie"]
    return result.text


async def preview_scenario(root):
    config = {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
    async with client(root, grants=GRANTS, publication=config) as (http, server):
        app = server.applications["press"]
        fixture = await asyncio.to_thread(site_fixture, app.service, app.publication)
        args = {
            "settings_id": fixture["settings"]["record_id"],
            "variant_revisions": [v["revision_id"] for v in fixture["variants"].values()],
            "key": "api-candidate",
        }
        _, first = await call(http, "rest", "candidate_create", **args)
        _, repeated = await call(http, "mcp", "candidate_create", **args)
        assert first == repeated and first["ok"], first
        start_args = {"candidate_id": first["result"]["record_id"], "key": "api-build"}
        _, started = await call(http, "rest", "build_start", **start_args)
        _, retried = await call(http, "mcp", "build_start", **start_args)
        assert started == retried and started["ok"], started
        build_id = started["result"]["record_id"]
        await asyncio.to_thread(app.publication._futures[build_id].result, 30)
        job = app.publication.execute("admin", "build_status", build_id=build_id)
        assert job["attributes"]["state"] == "succeeded", job
        _, caps = await call(http, "rest", "capabilities")
        assert caps["result"]["preview"] and caps["result"]["rendering"]
        assert caps["result"]["publication"]
        assert "preview_grant_create" in caps["result"]["operations"]
        for channel in ("rest", "mcp"):
            _, result = await call(http, channel, "build_status", build_id=job["record_id"])
            assert result["result"] == job
        grant_args = {"build_id": job["record_id"], "lifetime_seconds": 300, "key": "grant"}
        _, granted = await call(http, "rest", "preview_grant_create", **grant_args)
        _, repeated = await call(http, "mcp", "preview_grant_create", **grant_args)
        assert granted == repeated and granted["ok"], granted
        grant = granted["result"]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server),
            base_url=CONFIG["preview_origin"],
            follow_redirects=True,
        ) as browser:
            root_url = await exchange(browser, grant)
            page = await browser.get(root_url)
            assert page.status_code == 200 and "<h1>it title</h1>" in page.text
            assert 'href="https://one.test/it/"' in page.text
            manifest = app.publication.sealed_manifest(
                app.service.catalog.read().revisions[job["revision_id"]]
            )
            asset = next(p for p in manifest["artifacts"]["preview"] if p.endswith(".css"))
            for path in ("/it/", "/en/about/", asset):
                for method in ("GET", "HEAD"):
                    response = await browser.request(method, root_url.rstrip("/") + path)
                    assert response.status_code == 200
                    assert response.headers["cache-control"] == "no-store, private"
                    assert response.headers["referrer-policy"] == "no-referrer"
                    if method == "HEAD":
                        assert (
                            response.content == b"" and int(response.headers["content-length"]) > 0
                        )
            for path in ("/mcp", "/site_create", asset, "/preview/unknown/it/"):
                response = await browser.post(
                    path, json={}, headers={"authorization": "Bearer test-admin-token"}
                )
                assert response.status_code == 404
            for host in ("https://one.test", "https://forged.test"):
                response = await browser.get(host + root_url)
                assert response.status_code == 404
            _, revoked = await call(
                http,
                "mcp",
                "preview_grant_revoke",
                grant_id=grant["record_id"],
                expected_generation=grant["generation"],
                key="revoke",
            )
            assert revoked["ok"]
            cookies = browser.cookies
            for path in ("/it/", asset):
                for method in ("GET", "HEAD"):
                    assert (
                        await browser.request(method, root_url.rstrip("/") + path)
                    ).status_code == 404
        http.headers["authorization"] = "Bearer test-writer-token"
        for channel in ("rest", "mcp"):
            for operation, arguments in (
                ("build_start", {"candidate_id": first["result"]["record_id"], "key": "denied"}),
                ("preview_grant_create", grant_args),
            ):
                _, denied = await call(http, channel, operation, **arguments)
                assert denied["error"]["code"] == "forbidden", denied
        http.headers["authorization"] = "Bearer test-admin-token"
        interpreter = app.publication.worker.python
        app.publication.worker.python = str(root / "absent-interpreter")
        try:
            for channel in ("rest", "mcp"):
                _, unavailable = await call(
                    http, channel, "candidate_create", **{**args, "key": "unavailable"}
                )
                assert unavailable["error"]["code"] == "render_profile_unavailable", unavailable
        finally:
            app.publication.worker.python = interpreter
    async with (
        client(root, grants=GRANTS, publication=config) as (_, server),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server),
            base_url=CONFIG["preview_origin"],
            cookies=cookies,
        ) as browser,
    ):
        for method in ("GET", "HEAD"):
            assert (await browser.request(method, root_url + "it/")).status_code == 404


def test_real_gateway_rest_mcp_and_revoke_restart(tmp_path):
    asyncio.run(preview_scenario(tmp_path))
