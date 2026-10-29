"""Publish the Kajenn Press example site page by page through MCP (N4).

Run against a websites installation with site sources and a versioned release bucket.
The public origin becomes the site's address: Publish binds it in the release bucket,
where site servers read it. Rerunning with the same keys returns the first results
(idempotency receipts are kept 24 hours).
"""

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = (
    ("home", "Kajenn Press · Website editing, page by page", "/"),
    ("features", "Features · Kajenn Press", "/features/"),
    ("start", "Get started · Kajenn Press", "/get-started/"),
)
# Site texts of the layout: English (main) and Italian.
TEXTS = {
    "skip": ("Skip to content", "Vai al contenuto"),
    "nav_overview": ("Overview", "Panoramica"),
    "nav_features": ("Features", "Funzioni"),
    "nav_start": ("Get started", "Per iniziare"),
    "href_overview": ("/", "/it/"),
    "href_features": ("/features/", "/it/features/"),
    "href_start": ("/get-started/", "/it/get-started/"),
    "footer_about": (
        "Build, translate and publish sites page by page, with S3 versions and rollback.",
        "Costruisci, traduci e pubblica siti pagina per pagina, con versioni S3 e rollback.",
    ),
    "footer_family": ("Part of the Genro family.", "Parte della famiglia Genro."),
    "footer_learn": ("Learn", "Scopri"),
    "footer_links": ("Family", "Famiglia"),
}
DESCRIPTIONS = {
    "home": "Kajenn Press builds a website page by page and publishes each page as a versioned object.",
    "features": "What Kajenn Press does today.",
    "start": "Run Kajenn Press locally with Docker and call it through REST and MCP.",
}


class Mcp:
    """JSON-RPC tools/call with the Host the management origin expects."""

    def __init__(self, endpoint, host, token):
        self.endpoint, self.host, self.token = endpoint, host, token

    def __call__(self, operation, **arguments):
        envelope = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": operation, "arguments": arguments},
        }
        request = urllib.request.Request(
            self.endpoint + "/mcp",
            data=json.dumps(envelope).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "Host": self.host,
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)["result"]["structuredContent"]
        if not result.get("ok"):
            raise RuntimeError(f"{operation}: {json.dumps(result.get('error'), indent=2)}")
        return result["result"]


def wait_until_ready(mcp, seconds=300):
    """The manager answers MCP once its lifespan has opened the site store."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            if mcp("capabilities")["sites"]:
                return
        except (OSError, urllib.error.URLError, RuntimeError):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("The manager did not become ready")
        time.sleep(2)


def publish(mcp, origin):
    site = mcp("site_new", key="press-site", name="Kajenn Press")["site_id"]
    mcp("site_languages_set", site_id=site, key="press-languages", languages=["en", "it"])
    for name, (english, italian) in TEXTS.items():
        mcp("site_text_set", site_id=site, key=f"press-text-{name}", name=name, text=english)
        mcp("site_text_set", site_id=site, key=f"press-text-{name}-it", name=name, text=italian,
            language="it")
    template = mcp(
        "template_add", site_id=site, key="press-layout", name="Layout", engine="gramlot",
        python_source=(HERE / "layout.py").read_text(),
    )["template_id"]
    assets = [
        mcp(
            "asset_add", site_id=site, key="press-file-" + name, name=name, kind=kind,
            data_base64=base64.b64encode((HERE / path).read_bytes()).decode(), mime_type=mime,
        )["asset_id"]
        for name, kind, path, mime in (
            ("site", "css", "site.css", "text/css"),
            ("logo", "media", "kajenn-press-logo.png", "image/png"),
        )
    ]
    for key, title, url in PAGES:
        page = mcp(
            "page_add", site_id=site, key=f"press-page-{key}", name=title, template_id=template
        )["page_id"]
        mcp("page_url_set", site_id=site, key=f"press-url-{key}", page_id=page, url=url)
        fields = {"description": DESCRIPTIONS[key]}
        if url == "/":
            fields.update(site_name="Kajenn Press", origin=origin)
        mcp("page_seo_set", site_id=site, key=f"press-seo-{key}", page_id=page, fields=fields)
        for index, asset in enumerate(assets):
            mcp("page_asset_add", site_id=site, key=f"press-asset-{key}-{index}", page_id=page,
                asset_id=asset)
        for slot in ("hero", "body"):
            content = mcp(
                "content_add", site_id=site, key=f"press-{key}-{slot}", name=f"{key} {slot}",
                format="html", text=(HERE / "pages" / f"{key}.{slot}.html").read_text(),
            )["content_id"]
            italian = HERE / "pages" / f"{key}.{slot}.it.html"
            if italian.exists():
                mcp("content_translate", site_id=site, key=f"press-it-{key}-{slot}",
                    content_id=content, language="it", text=italian.read_text())
            mcp("slot_assign", site_id=site, key=f"press-slot-{key}-{slot}", page_id=page,
                slot=slot, content_id=content)
    plan = mcp("publish_plan", site_id=site)
    result = mcp("publish", site_id=site, key="press-publish",
                 selected=[p["entry"] for p in plan if p["selected"]])
    if result["failed"]:
        raise RuntimeError(json.dumps(result["failed"], indent=2))
    return site


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--public-origin", required=True)
    arguments = parser.parse_args()
    mcp = Mcp(arguments.endpoint, arguments.host, Path(arguments.token_file).read_text().strip())
    wait_until_ready(mcp)
    site = publish(mcp, arguments.public_origin)
    print("published site", site, "for", arguments.public_origin, flush=True)


if __name__ == "__main__":
    main()
