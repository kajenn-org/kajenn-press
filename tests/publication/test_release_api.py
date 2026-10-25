import asyncio
import os

import httpx
from api.support import call, client
from publication.release_support import publisher
from publication.support import CONFIG, site_fixture
from publication.test_gateway import exchange

RELEASE_GRANTS = {
    "admin": {"*": ["read", "write", "use", "create_site", "build", "preview_grant", "publish"]},
    "writer": {"*": ["read", "use", "publish"]},
}


async def command(http, channel, operation, **arguments):
    status, response = await call(http, channel, operation, **arguments)
    assert status == 200 and response.get("ok"), response
    return response["result"]


async def build_http(http, fixture, key, *, revisions=None, base=None):
    selection = await command(
        http,
        "rest",
        "candidate_create",
        settings_id=fixture["settings"]["record_id"],
        variant_revisions=revisions or [v["revision_id"] for v in fixture["variants"].values()],
        base_build_id=base,
        key=key + "candidate",
    )
    started = await command(
        http, "mcp", "build_start", candidate_id=selection["record_id"], key=key + "build"
    )
    for _ in range(300):
        status = await command(http, "rest", "build_status", build_id=started["record_id"])
        if status["attributes"]["state"] not in {"queued", "running"}:
            assert status["attributes"]["state"] == "succeeded", status
            return status
        await asyncio.sleep(0.05)
    raise AssertionError("Build did not complete within bounded test deadline")


async def full_api_cycle(root):
    editorial, pub = await asyncio.to_thread(publisher, root)
    try:
        fixture = await asyncio.to_thread(site_fixture, editorial, pub)
        other = await asyncio.to_thread(site_fixture, editorial, pub, "other")
        sources = {
            (rid, name): pub.catalog.read_payload(rid, name)
            for rid, rev in pub.catalog.read().revisions.items()
            for name in rev["payloads"]
        }
    finally:
        pub.close()
        editorial.catalog.close()
    config = {
        **CONFIG,
        "render_python": os.environ["KAJENN_RENDER_PYTHON"],
        "public_origins": {"https://one.test": fixture["settings"]["record_id"]},
    }
    async with client(root, grants=RELEASE_GRANTS, publication=config) as (http, server):
        pub = server.applications["press"].publication
        other_channel = await command(
            http,
            "rest",
            "channel_create",
            settings_id=other["settings"]["record_id"],
            key="create-channel",
        )
        assert (
            await command(
                http,
                "mcp",
                "channel_create",
                settings_id=other["settings"]["record_id"],
                key="create-channel",
            )
            == other_channel
        )
        assert (
            await command(http, "mcp", "channel_read", settings_id=fixture["settings"]["record_id"])
        )["generation"] == 0
        first = await build_http(http, fixture, "first")
        grant = await command(
            http,
            "mcp",
            "preview_grant_create",
            build_id=first["record_id"],
            lifetime_seconds=300,
            key="preview",
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server), base_url=CONFIG["preview_origin"]
        ) as preview:
            path = await exchange(preview, grant)
            preview_html = await preview.get(path + "it/")
            assert preview_html.status_code == 200
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server), base_url="https://one.test"
        ) as public:
            assert (await public.get("/it/")).status_code == 404
            http.headers["authorization"] = "Bearer test-writer-token"
            _, no_build = await call(
                http,
                "mcp",
                "build_start",
                candidate_id=first["attributes"]["candidate_id"],
                key="denied-build",
            )
            assert no_build["error"]["code"] == "forbidden"
            pub.policy.grants["writer"]["*"].remove("use")
            for channel in ("rest", "mcp"):
                _, denied = await call(
                    http,
                    channel,
                    "release_activate",
                    settings_id=fixture["settings"]["record_id"],
                    build_id=first["record_id"],
                    expected_generation=0,
                    key="denied-use",
                )
                assert denied["error"]["code"] == "forbidden"
            pub.policy.grants["writer"]["*"].append("use")
            http.headers["authorization"] = "Bearer test-admin-token"
            await command(
                http,
                "rest",
                "site_configure",
                site_id=fixture["site"]["record_id"],
                expected_generation=1,
                key="require-review",
                name="one",
                languages=["it", "en"],
                review_required=True,
            )
            for channel in ("rest", "mcp"):
                _, denied = await call(
                    http,
                    channel,
                    "release_activate",
                    settings_id=fixture["settings"]["record_id"],
                    build_id=first["record_id"],
                    expected_generation=0,
                    key="denied-review",
                )
                assert denied["error"]["code"] == "review_required"
            await command(
                http,
                "mcp",
                "site_configure",
                site_id=fixture["site"]["record_id"],
                expected_generation=2,
                key="direct-publication",
                name="one",
                languages=["it", "en"],
                review_required=False,
            )
            http.headers["authorization"] = "Bearer test-writer-token"
            activated = await command(
                http,
                "mcp",
                "release_activate",
                settings_id=fixture["settings"]["record_id"],
                build_id=first["record_id"],
                expected_generation=0,
                key="first-activate",
            )
            old_html = (await public.get("/it/")).content
            assert b"<strong>Static</strong>" in old_html and b"<table>" in old_html
            assert b'href="https://one.test/it/"' in old_html
            read = await command(http, "rest", "release_read", build_id=first["record_id"])
            assert read["manifest"]["routes"].keys() == {"/it/", "/en/about/"}
            http.headers["authorization"] = "Bearer test-admin-token"
            for language, text in (("it", "ITALIAN UPDATE"), ("en", "UNFINISHED ENGLISH")):
                saved = await command(
                    http,
                    "rest",
                    "draft_save",
                    variant_id=fixture["variants"][language]["record_id"],
                    expected_generation=1,
                    key="edit-" + language,
                    template_revision=fixture["template"]["revision_id"],
                    blocks={"body": {"format": "markdown", "source": text}},
                )
                if language == "it":
                    italian = saved["records"][0]
            second = await build_http(
                http, fixture, "second", revisions=[italian["revision_id"]], base=first["record_id"]
            )
            assert (await public.get("/it/")).content == old_html
            next_activation = await command(
                http,
                "rest",
                "release_activate",
                settings_id=fixture["settings"]["record_id"],
                build_id=second["record_id"],
                expected_generation=activated["generation"],
                key="second-activate",
            )
            assert "ITALIAN UPDATE" in (await public.get("/it/")).text
            assert "UNFINISHED ENGLISH" not in (await public.get("/en/about/")).text
            for channel in ("rest", "mcp"):
                _, stale = await call(
                    http,
                    channel,
                    "release_rollback",
                    settings_id=fixture["settings"]["record_id"],
                    build_id=first["record_id"],
                    expected_generation=1,
                    key="stale-" + channel,
                )
                assert stale["error"]["code"] == "conflict"
            pub.worker.python = str(root / "absent-worker")
            rollback = await command(
                http,
                "mcp",
                "release_rollback",
                settings_id=fixture["settings"]["record_id"],
                build_id=first["record_id"],
                expected_generation=next_activation["generation"],
                key="rollback",
            )
            assert (await public.get("/it/")).content == old_html
            assert (
                len(
                    await command(
                        http,
                        "rest",
                        "release_history",
                        settings_id=fixture["settings"]["record_id"],
                    )
                )
                == 3
            )
    async with client(root, grants=RELEASE_GRANTS, publication=config) as (http, server):
        current = await command(
            http, "mcp", "channel_read", settings_id=fixture["settings"]["record_id"]
        )
        assert current == rollback
        for (rid, name), source in sources.items():
            assert (
                server.applications["press"].service.catalog.read_payload(rid, name) == source
            )
        response = await http.get("https://one.test/it/")
        assert response.status_code == 200 and response.content == old_html


def test_full_cycle_through_real_rest_mcp_and_http(tmp_path):
    asyncio.run(full_api_cycle(tmp_path))
