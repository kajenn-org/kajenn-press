import asyncio
from threading import Event

import httpx
from publication.release_support import activate, initial_release, publisher, updated_release
from publication.scenarios import FixtureHost
from publication.support import CONFIG, built, candidate, site_fixture

from kajenn_public_site.publication.gateway import PreviewGateway


async def serving_scenario(root):
    editorial, pub = await asyncio.to_thread(publisher, root)
    release_read = Event()
    continue_read = Event()
    original_artifact = pub.artifact
    try:
        fixture, _selected, first, channel = await asyncio.to_thread(
            initial_release, editorial, pub
        )
        _, second, _, _ = await asyncio.to_thread(updated_release, editorial, pub, fixture, first)
        other = await asyncio.to_thread(site_fixture, editorial, pub, "other")
        hidden = await asyncio.to_thread(
            built, pub, candidate(pub, other, key="hidden"), "hidden-build"
        )
        pub.public_origins = {
            "https://one.test": fixture["settings"]["record_id"],
            "https://other.test": other["settings"]["record_id"],
        }
        gateway = PreviewGateway(
            FixtureHost(pub), CONFIG["management_origin"], CONFIG["preview_origin"]
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=gateway), base_url="https://one.test"
        ) as browser:
            captured = []

            def pause_after_selection(revision, context, path):
                captured.append(revision["id"])
                release_read.set()
                assert continue_read.wait(10)
                return original_artifact(revision, context, path)

            pub.artifact = pause_after_selection
            request = asyncio.create_task(browser.get("/it/"))
            assert await asyncio.to_thread(release_read.wait, 10)
            changed = await asyncio.to_thread(
                activate, pub, fixture, second, channel["generation"], "during-request"
            )
            continue_read.set()
            old_response = await request
            pub.artifact = original_artifact
            assert captured == [first["revision_id"]]
            assert (
                old_response.status_code == 200 and "Italiano aggiornato" not in old_response.text
            )
            assert old_response.headers["cache-control"] == "no-store"
            new_response = await browser.get("/it/")
            assert "Italiano aggiornato" in new_response.text
            assert "UNFINISHED ENGLISH" not in (await browser.get("/en/about/")).text
            first_revision = pub.catalog.read().revisions[first["revision_id"]]
            old_manifest = pub.sealed_manifest(first_revision)
            second_manifest = pub.sealed_manifest(
                pub.catalog.read().revisions[second["revision_id"]]
            )
            assert (
                old_manifest["release_key"] in old_response.text
                and second_manifest["release_key"] not in old_response.text
            )
            assert (
                second_manifest["release_key"] in new_response.text
                and old_manifest["release_key"] not in new_response.text
            )
            for path, descriptor in old_manifest["artifacts"]["public"].items():
                if not path.startswith("/_releases/"):
                    continue
                for method in ("GET", "HEAD"):
                    response = await browser.request(method, path)
                    assert response.status_code == 200
                    assert "immutable" in response.headers["cache-control"]
                    assert response.headers["x-content-type-options"] == "nosniff"
                    assert response.headers["content-type"] == descriptor["media_type"]
                    if method == "HEAD":
                        assert (
                            response.content == b""
                            and int(response.headers["content-length"]) == descriptor["size"]
                        )
            redirect = await browser.get("/")
            assert redirect.status_code == 307 and redirect.headers["location"] == "/it/"
            assert (await browser.post("/it/")).status_code == 405
            hidden_manifest = pub.sealed_manifest(
                pub.catalog.read().revisions[hidden["revision_id"]]
            )
            hidden_asset = next(
                p for p in hidden_manifest["artifacts"]["public"] if p.startswith("/_releases/")
            )
            forbidden = [
                "/missing/",
                "/mcp",
                "/site_create",
                "/preview/" + first["record_id"] + "/it/",
                hidden_asset,
                "/it/%2e%2e/private",
                "/it/%2Fprivate",
                "/it/%5cprivate",
                "/it/%69/",
                "/it//",
            ]
            for path in forbidden:
                for method in ("GET", "HEAD"):
                    assert (await browser.request(method, path)).status_code == 404, path
            assert (await browser.get("https://other.test/it/")).status_code == 404
            assert (
                await browser.get(
                    "https://unknown.test/it/", headers={"x-forwarded-host": "one.test"}
                )
            ).status_code == 404
            assert (
                await browser.post(
                    "/release_activate", headers={"authorization": "Bearer test-admin-token"}
                )
            ).status_code == 405
            assert (
                await browser.get("/it/", headers=[("host", "one.test"), ("host", "admin.test")])
            ).status_code == 404
            assert (
                pub.execute("admin", "channel_read", settings_id=fixture["settings"]["record_id"])[
                    "revision_id"
                ]
                == changed["revision_id"]
            )
    finally:
        continue_read.set()
        pub.artifact = original_artifact
        pub.close()
        editorial.catalog.close()


def test_public_selection_pinning_retained_assets_and_private_denials(tmp_path):
    asyncio.run(serving_scenario(tmp_path))
