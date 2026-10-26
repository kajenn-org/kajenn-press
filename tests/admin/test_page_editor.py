"""Page editor: one tab per declared block, site boundaries and the editing round trip."""

import asyncio
import os
import re

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from api.support import seed_http
from genro_bag import Bag
from publication.support import CONFIG

from admin.support import admin_client, login, rpc


async def panel(http, page, selection):
    """index_panel takes a Bag: the payload travels as TYTX, as the browser sends it."""
    from genro_tytx import to_tytx

    payload = to_tytx(
        {
            "id": "panel",
            "pageId": page,
            "name": "index_panel",
            "contentType": "source",
            "params": {"selection": selection},
        }
    )
    response = await http.post(
        "/admin/gramlot/rpc", content=payload, headers={"Content-Type": "application/json"}
    )
    return response.text


async def open_page_editor(http, site, content):
    response = await http.get(f"/admin/page?site={site}&content={content}")
    assert response.status_code == 200, response.text
    return re.search(r'"pageId":"([a-f0-9]+)"', response.text)[1]


def test_editor_shows_every_declared_block_inside_its_site(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            shell = await login(http)
            site, other, _template, content, _variant = await seed_http(http)
            page = await open_page_editor(http, site["record_id"], content["record_id"])
            view = (
                await rpc(
                    http,
                    page,
                    "editor",
                    "source",
                    site=site["record_id"],
                    content=content["record_id"],
                )
            )["value"]
            # The seeded template declares a required HTML intro and an optional Markdown body.
            assert "intro · required · html" in view and "body · markdown" in view
            assert "htmlEditor" in view and "markdownEditor" in view
            assert "Esatto" in view and "Article" in view
            foreign = (
                await rpc(
                    http,
                    page,
                    "editor",
                    "source",
                    site=other["record_id"],
                    content=content["record_id"],
                )
            )["value"]
            assert "Page does not belong to this site" in foreign and "Esatto" not in foreign
            refused = await rpc(
                http, page, "command", operation="resource_save", arguments={"key": "x"}
            )
            assert "Command unavailable" in str(refused)
            nav = (await rpc(http, shell, "navigation_for_site", site=site["record_id"]))["value"]
            entry = nav.get_node("site.pages").value.get_node("r_" + content["record_id"])
            assert entry.attr["section"] == "page"
            selection = Bag()
            selection.set_item(
                "chosen", None, site=site["record_id"], section="page", record=content["record_id"]
            )
            assert "page?site=" + site["record_id"] in await panel(http, shell, selection)
            # A record that is not a page cannot open the page editor.
            selection = Bag()
            selection.set_item(
                "chosen", None, site=site["record_id"], section="page", record=site["record_id"]
            )
            assert "page?site=" not in await panel(http, shell, selection)
            main = (await rpc(http, shell, "main", "source"))["value"]
            assert "subscribe_open_object" in main

    asyncio.run(scenario())


def test_save_conflict_language_and_draft_render_round_trip(tmp_path):
    async def scenario():
        grants = {"admin": {"*": ["read", "write", "use", "create_site", "build"]}}
        async with admin_client(
            tmp_path, grants, {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
        ) as (http, _server):
            await login(http)
            site, _other, template, content, variant = await seed_http(http)
            page = await open_page_editor(http, site["record_id"], content["record_id"])

            async def command(operation, **arguments):
                return (await rpc(http, page, "command", operation=operation, arguments=arguments))[
                    "value"
                ]

            blocks = {
                "intro": {"format": "html", "source": "<p>Edited intro</p>"},
                "body": {"format": "markdown", "source": "# Edited\n"},
            }
            saved = await command(
                "draft_save",
                key="save",
                variant_id=variant["record_id"],
                expected_generation=variant["generation"],
                template_revision=template["revision_id"],
                blocks=blocks,
            )
            assert saved["ok"], saved
            revision = saved["result"]["records"][0]
            stale = await command(
                "draft_save",
                key="stale",
                variant_id=variant["record_id"],
                expected_generation=variant["generation"],
                template_revision=template["revision_id"],
                blocks=blocks,
            )
            assert stale["error"]["code"] == "conflict"
            added = await command(
                "variant_create",
                key="english",
                content_id=content["record_id"],
                language="en",
                template_revision=template["revision_id"],
                translated_from=revision["revision_id"],
                blocks=blocks,
            )
            assert added["ok"], added
            english = added["result"]["records"][0]
            assert english["attributes"]["translated_from"] == revision["revision_id"]
            view = (
                await rpc(
                    http,
                    page,
                    "editor",
                    "source",
                    site=site["record_id"],
                    content=content["record_id"],
                    language="en",
                )
            )["value"]
            assert english["record_id"] in view
            ready = await command(
                "readiness", record_id=variant["record_id"], revision_id=revision["revision_id"]
            )
            assert ready["ok"] and ready["result"]["ready"]
            # The seeded library template raises: the draft render reports it as a diagnostic.
            rendered = await command(
                "render_draft",
                variant_id=variant["record_id"],
                revision_id=revision["revision_id"],
                blocks={"intro": "<p>Unsaved</p>"},
                resources={},
            )
            assert rendered["ok"] and rendered["result"]["status"] == "failed"

    asyncio.run(scenario())
