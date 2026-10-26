"""Resource editor: one editor per kind, sample pages through exact dependencies, site boundaries."""

import asyncio
import base64
import os
import re

import pytest

pytest.importorskip("gramlot", reason="Requires the optional admin profile")

from api.support import record
from publication.support import CONFIG

from admin.support import admin_client, login, rpc

STYLED = """def build(source, data):
    page = source.html(lang="^language")
    head = page.head()
    for asset in data.get_item("resources").values():
        if asset.get_item("kind") == "css":
            head.link(rel="stylesheet", href=asset.get_item("url"))
    page.body().main("^blocks.body")
"""
BLOCKS = {"body": {"format": "html", "required": True}}
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="


async def seed(http):
    """A site whose page uses a template that links a site stylesheet, and a second site."""
    site = await record(http, "rest", "site_create", key="site", name="Styled", languages=["en"])
    other = await record(http, "rest", "site_create", key="other", name="Other", languages=["en"])
    scope = "site:" + site["record_id"]
    css = await record(
        http,
        "rest",
        "resource_save",
        key="css",
        scope=scope,
        kind="css",
        name="Styles",
        source="main { color: #123; }",
    )
    template = await record(
        http,
        "rest",
        "resource_save",
        key="template",
        scope=scope,
        kind="template",
        name="Styled page",
        source=STYLED,
        engine="gramlot",
        blocks=BLOCKS,
        dependencies=[css["revision_id"]],
    )
    media = await record(
        http,
        "rest",
        "media_save",
        key="media",
        scope=scope,
        name="Pixel",
        data_base64=PNG,
        mime_type="image/png",
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
        blocks={"body": {"format": "html", "source": "<p>Saved</p>"}},
    )
    return site, other, css, template, media, content, variant


async def open_editor(http, path, **query):
    response = await http.get("/admin/" + path, params=query)
    assert response.status_code == 200, response.text
    return re.search(r'"pageId":"([a-f0-9]+)"', response.text)[1]


def test_each_kind_gets_its_editor_and_sample_pages_follow_dependencies(tmp_path):
    async def scenario():
        async with admin_client(tmp_path) as (http, _server):
            await login(http)
            http.headers["Authorization"] = "Bearer test-admin-token"
            site, other, css, template, media, _content, _variant = await seed(http)
            http.headers.pop("Authorization")
            page = await open_editor(
                http, "resource", site=site["record_id"], record=css["record_id"]
            )

            async def view(record_id, site_id=site["record_id"]):
                result = await rpc(http, page, "editor", "source", site=site_id, record=record_id)
                return result["value"]

            styles = await view(css["record_id"])
            assert "codeMirror" in styles and "main { color: #123; }" in styles
            # The page reaches the stylesheet through its template: it is a sample page.
            assert "Home · en" in styles and css["revision_id"] in styles
            layout = await view(template["record_id"])
            assert "Blocks" in layout and "Dependencies" in layout and "python" in layout
            assert "blocks_form" in layout and "Revision 1 · latest" in layout
            image = await view(media["record_id"])
            assert "mediaFile" in image and "image/png" in image
            foreign = await view(css["record_id"], other["record_id"])
            assert "Resource does not belong to this site" in foreign
            assert "main { color" not in foreign
            refused = await rpc(
                http, page, "command", operation="draft_save", arguments={"key": "x"}
            )
            assert "Command unavailable" in str(refused)

    asyncio.run(scenario())


def test_save_conflict_draft_render_and_latest_template(tmp_path):
    async def scenario():
        grants = {"admin": {"*": ["read", "write", "use", "create_site", "build"]}}
        async with admin_client(
            tmp_path, grants, {**CONFIG, "render_python": os.environ["KAJENN_RENDER_PYTHON"]}
        ) as (http, _server):
            await login(http)
            http.headers["Authorization"] = "Bearer test-admin-token"
            site, _other, css, template, _media, content, variant = await seed(http)
            http.headers.pop("Authorization")
            page = await open_editor(
                http, "resource", site=site["record_id"], record=css["record_id"]
            )

            async def command(operation, **arguments):
                return (await rpc(http, page, "command", operation=operation, arguments=arguments))[
                    "value"
                ]

            unsaved = "main { color: red; }"
            rendered = await command(
                "render_draft",
                variant_id=variant["record_id"],
                revision_id=variant["revision_id"],
                blocks={},
                resources={css["revision_id"]: unsaved},
            )
            assert rendered["result"]["status"] == "succeeded", rendered
            encoded = base64.b64encode(unsaved.encode()).decode()
            assert "data:text/css;base64," + encoded in rendered["result"]["html"]
            arguments = {
                "scope": "site:" + site["record_id"],
                "kind": "css",
                "name": "Styles",
                "source": unsaved,
                "record_id": css["record_id"],
                "expected_generation": css["generation"],
                "dependencies": [],
            }
            saved = await command("resource_save", key="save", **arguments)
            assert saved["ok"], saved
            stale = await command("resource_save", key="stale", **arguments)
            assert stale["error"]["code"] == "conflict"
            newer = await command(
                "resource_save",
                key="template-revision-2",
                scope="site:" + site["record_id"],
                kind="template",
                name="Styled page",
                source=STYLED,
                engine="gramlot",
                blocks=BLOCKS,
                dependencies=[saved["result"]["records"][0]["revision_id"]],
                record_id=template["record_id"],
                expected_generation=template["generation"],
            )
            assert newer["ok"], newer
            editor = await open_editor(
                http, "page", site=site["record_id"], content=content["record_id"]
            )
            view = (
                await rpc(
                    http,
                    editor,
                    "editor",
                    "source",
                    site=site["record_id"],
                    content=content["record_id"],
                )
            )["value"]
            assert "Use latest template" in view and "latest 2" in view
            moved = await rpc(
                http,
                editor,
                "command",
                operation="draft_save",
                arguments={
                    "key": "latest",
                    "variant_id": variant["record_id"],
                    "expected_generation": variant["generation"],
                    "template_revision": newer["result"]["records"][0]["revision_id"],
                    "blocks": {"body": {"format": "html", "source": "<p>Saved</p>"}},
                },
            )
            assert moved["value"]["ok"], moved
            view = (
                await rpc(
                    http,
                    editor,
                    "editor",
                    "source",
                    site=site["record_id"],
                    content=content["record_id"],
                    version=1,
                )
            )["value"]
            assert "Use latest template" not in view

    asyncio.run(scenario())
