"""Publishing panel: settings, routes, build, private preview, activation and rollback."""

import asyncio
import os
import re

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from api.support import record
from publication.support import CONFIG

from admin.support import admin_client, login, rpc
from kajenn_press.admin.pages.author import BLOCKS, TEMPLATE


def test_publishing_cycle_from_the_panel(tmp_path):
    async def scenario():
        grants = {
            "admin": {
                "*": ["read", "write", "use", "create_site", "build", "preview_grant", "publish"]
            }
        }
        async with admin_client(
            tmp_path, grants, {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
        ) as (http, _server):
            await login(http)
            http.headers["Authorization"] = "Bearer test-admin-token"
            site = await record(
                http, "rest", "site_create", key="site", name="Published", languages=["en"]
            )
            template = await record(
                http,
                "rest",
                "resource_save",
                key="template",
                scope="site:" + site["record_id"],
                kind="template",
                name="Page",
                source=TEMPLATE,
                engine="gramlot",
                blocks=BLOCKS,
            )
            content = await record(
                http, "rest", "content_create", key="page", site_id=site["record_id"], title="Home"
            )
            variant = await record(
                http,
                "rest",
                "variant_create",
                key="variant",
                content_id=content["record_id"],
                language="en",
                template_revision=template["revision_id"],
                blocks={"body": {"format": "html", "source": "<p>Hello</p>"}},
            )
            http.headers.pop("Authorization")
            response = await http.get("/admin/publishing", params={"site": site["record_id"]})
            page = re.search(r'"pageId":"([a-f0-9]+)"', response.text)[1]

            async def panel():
                return (await rpc(http, page, "panel", "source", site=site["record_id"]))["value"]

            async def command(operation, **arguments):
                reply = await rpc(http, page, "command", operation=operation, arguments=arguments)
                assert reply["value"]["ok"], reply
                return reply["value"]["result"]

            async def build():
                selection = await command(
                    "candidate_create",
                    key="candidate-" + os.urandom(4).hex(),
                    settings_id=settings["record_id"],
                    variant_revisions=[variant["revision_id"]],
                )
                job = await command(
                    "build_start",
                    key="build-" + os.urandom(4).hex(),
                    candidate_id=selection["record_id"],
                )
                for _poll in range(120):
                    status = await command("build_status", build_id=job["record_id"])
                    if status["attributes"]["state"] not in {"queued", "running"}:
                        break
                    await asyncio.sleep(0.25)
                assert status["attributes"]["state"] == "succeeded", status
                return job["record_id"]

            async def channel_view():
                return (
                    await rpc(
                        http,
                        page,
                        "channel_view",
                        "source",
                        site=site["record_id"],
                        settings_id=settings["record_id"],
                        preview=True,
                        publish=True,
                    )
                )["value"]

            view = await panel()
            assert (
                "1 · Channel" in view and "2 · Routes" in view and "Save a channel first." in view
            )
            assert "Add route" in view
            settings = await command(
                "publication_settings_save",
                key="settings",
                site_id=site["record_id"],
                channel="main",
                public_origin="https://published.test",
                primary_language="en",
                landing_variant=variant["record_id"],
            )
            await command(
                "publication_route_save",
                key="route",
                variant_id=variant["record_id"],
                path="",
                title="Home",
                description="The home page",
            )
            view = await panel()
            assert "https://published.test" in view and "Save route" in view
            assert "Save a channel first." not in view
            first = await build()
            builds = await channel_view()
            assert "Activate" in builds and "Preview link" in builds
            grant = await command(
                "preview_grant_create", key="grant", build_id=first, lifetime_seconds=3600
            )
            assert grant["url"]
            await command(
                "release_activate",
                key="activate-1",
                settings_id=settings["record_id"],
                build_id=first,
                expected_generation=0,
            )
            assert "Active" in await channel_view()
            second = await build()
            await command(
                "release_activate",
                key="activate-2",
                settings_id=settings["record_id"],
                build_id=second,
                expected_generation=1,
            )
            history = await channel_view()
            assert "Roll back" in history
            await command(
                "release_rollback",
                key="rollback",
                settings_id=settings["record_id"],
                build_id=first,
                expected_generation=2,
            )
            overview = (
                await rpc(
                    http,
                    page,
                    "read",
                    operation="publication_overview",
                    arguments={"site_id": site["record_id"]},
                )
            )["value"]
            assert overview["channels"][0]["active_build"] == first
            refused = await rpc(
                http, page, "command", operation="draft_save", arguments={"key": "x"}
            )
            assert "Command unavailable" in str(refused)

    asyncio.run(scenario())
