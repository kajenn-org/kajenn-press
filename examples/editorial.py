"""Exercise both real ASGI faces locally; rerun to verify exact idempotent results."""

import argparse
import asyncio
import json
import secrets

import httpx

from kajenn_public_site.application import create_server


async def run(root):
    token = secrets.token_urlsafe(32)
    server = create_server(
        root,
        auth={"bearer": {"demo": {"token": token, "tags": "editor"}}},
        grants={"demo": {"*": ["read", "write", "use", "create_site"]}},
    )
    # Public Kajenn lifecycle hooks; the automated API tests also drive the
    # complete ASGI lifespan message exchange and shutdown/ownership release.
    await server.lifespan.startup()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server),
            base_url="http://demo",
            headers={"Authorization": "Bearer " + token},
        ) as http:

            async def call(operation, channel="rest", **arguments):
                if channel == "rest":
                    response = await http.post("/" + operation, json=arguments)
                    result = response.json()
                else:
                    response = await http.post(
                        "/mcp",
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/call",
                            "params": {"name": operation, "arguments": arguments},
                        },
                    )
                    result = response.json()["result"]["structuredContent"]
                response.raise_for_status()
                assert result["ok"], result
                return result["result"]

            site = (
                await call("site_create", key="demo-site", name="Demo", languages=["it", "en"])
            )["records"][0]
            other = (
                await call(
                    "site_create",
                    channel="mcp",
                    key="demo-other",
                    name="Second site",
                    languages=["it"],
                )
            )["records"][0]
            template = (
                await call(
                    "resource_save",
                    key="demo-template",
                    scope="library",
                    kind="template",
                    name="page",
                    engine="gramlot",
                    source="# Template source: stored, never executed.\r\n",
                    blocks={
                        "intro": {"format": "html", "required": True},
                        "body": {"format": "markdown", "required": False},
                    },
                )
            )["records"][0]
            content = (
                await call(
                    "content_create",
                    channel="mcp",
                    key="demo-content",
                    site_id=site["record_id"],
                    title="Article",
                )
            )["records"][0]
            italian = (
                await call(
                    "variant_create",
                    key="demo-it",
                    content_id=content["record_id"],
                    language="it",
                    template_revision=template["revision_id"],
                    blocks={
                        "intro": {"format": "html", "source": "<p>Ciao!</p>\r\n"},
                        "body": {"format": "markdown", "source": "# Titolo\n\nTesto **esatto**.\n"},
                    },
                )
            )["records"][0]
            english = (
                await call(
                    "variant_create",
                    channel="mcp",
                    key="demo-en",
                    content_id=content["record_id"],
                    language="en",
                    template_revision=template["revision_id"],
                    translated_from=italian["revision_id"],
                    blocks={},
                )
            )["records"][0]
            readiness = await call("readiness", channel="mcp", record_id=english["record_id"])
            copied = (
                await call(
                    "resource_copy",
                    channel="mcp",
                    key="demo-copy",
                    source_revision=template["revision_id"],
                    site_id=site["record_id"],
                    name="local-page",
                )
            )["records"][0]
            saved = (
                await call(
                    "draft_save",
                    channel="mcp",
                    key="demo-save",
                    variant_id=italian["record_id"],
                    expected_generation=1,
                    template_revision=template["revision_id"],
                    blocks={"intro": {"format": "html", "source": "<p>Aggiornato!</p>"}},
                )
            )["records"][0]
            original = await call(
                "record_read", record_id=italian["record_id"], revision_id=italian["revision_id"]
            )
            assert original == italian and not readiness["ready"]
            assert (
                await call("record_read", channel="mcp", record_id=english["record_id"])
            ) == english
            return {
                "site_ids": [site["record_id"], other["record_id"]],
                "italian_revisions": [italian["revision_id"], saved["revision_id"]],
                "english_revision": english["revision_id"],
                "missing_block": readiness["diagnostics"][0]["block"],
                "generic_revision": template["revision_id"],
                "copy_id": copied["record_id"],
                "historical_html": original["sources"]["block.intro"]["text"],
                "historical_markdown": original["sources"]["block.body"]["text"],
            }
    finally:
        await server.lifespan.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Dedicated private data directory outside the checkout")
    args = parser.parse_args()
    first = asyncio.run(run(args.root))
    second = asyncio.run(run(args.root))
    assert first == second
    print(json.dumps({"restart_and_retry": "verified", **second}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
