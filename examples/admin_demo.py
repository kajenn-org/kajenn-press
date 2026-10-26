"""Loopback-only disposable administration demo; never a production identity store."""

import argparse
import copy
import os
import secrets
import tempfile

import uvicorn
from kajenn.auth.user_store import UserStore

from kajenn_press.admin.pages.author import BLOCKS, TEMPLATE
from kajenn_press.application import create_server
from kajenn_press.catalog.local import LocalCatalog
from kajenn_press.domain import AccessPolicy
from kajenn_press.services.editorial import EditorialService

LANDING = """def build(source, data):
    page = source.html(lang="^language")
    head = page.head()
    head.meta(charset="utf-8")
    head.title("^page.title")
    head.style("body {font: 18px system-ui; margin: 0;} .hero {background: #172c43; color: #fff;"
               " padding: 48px;} .notes {padding: 24px 48px;}")
    body = page.body()
    body.section("^blocks.hero", class_="hero")
    body.section("^blocks.notes", class_="notes")
"""
LANDING_BLOCKS = {
    "hero": {"format": "html", "required": True},
    "notes": {"format": "markdown", "required": False},
}


class DemoUsers(UserStore):
    def __init__(self, storage):
        self.record = {
            "identity": "demo",
            "password_hash": self.hash_password("demo"),
            "tags": ["editor"],
            "enabled": True,
        }

    def load_all(self):
        return [copy.deepcopy(self.record)] if self.record else []

    def get(self, identity):
        return copy.deepcopy(self.record) if self.record and identity == "demo" else None

    def save(self, record):
        self.record = copy.deepcopy(record)

    def delete(self, identity):
        found = self.get(identity) is not None
        if found:
            self.record = None
        return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8874)
    parser.add_argument("--render-python", default=os.environ.get("KAJENN_RENDER_PYTHON"))
    args = parser.parse_args()
    root = tempfile.mkdtemp(prefix="kajenn-admin-demo-")
    grants = {"demo": {"*": ["read", "write", "use", "create_site", "build"]}}
    service = EditorialService(LocalCatalog(root), AccessPolicy(grants))
    template = service.execute(
        "demo",
        "resource_save",
        key="template",
        scope="library",
        kind="template",
        name="Standard page",
        source=TEMPLATE,
        engine="gramlot",
        blocks=BLOCKS,
    )["records"][0]
    for index, name in enumerate(("Kajenn", "Gramlot")):
        site = service.execute(
            "demo", "site_create", key=f"site-{index}", name=name, languages=["it", "en"]
        )["records"][0]
        local_template = service.execute(
            "demo",
            "resource_copy",
            source_revision=template["revision_id"],
            site_id=site["record_id"],
            name="Standard page",
            key=f"copy-{index}",
        )["records"][0]
        for title in ("About us", "The project", "Contact"):
            content = service.execute(
                "demo",
                "content_create",
                key=f"{index}-{title}",
                site_id=site["record_id"],
                title=title,
            )["records"][0]
            for language in ("it", "en"):
                service.execute(
                    "demo",
                    "variant_create",
                    key=f"{index}-{title}-{language}",
                    content_id=content["record_id"],
                    language=language,
                    template_revision=local_template["revision_id"],
                    blocks={
                        "body": {
                            "format": "html",
                            "source": f"<p>Welcome to {title}. Replace this sample with your own content.</p>",
                        }
                    },
                )
        # A two-block page shows the page editor with an HTML and a Markdown block.
        landing_template = service.execute(
            "demo",
            "resource_save",
            key=f"landing-template-{index}",
            scope="site:" + site["record_id"],
            kind="template",
            name="Landing page",
            source=LANDING,
            engine="gramlot",
            blocks=LANDING_BLOCKS,
        )["records"][0]
        landing = service.execute(
            "demo",
            "content_create",
            key=f"{index}-landing",
            site_id=site["record_id"],
            title="Landing",
        )["records"][0]
        service.execute(
            "demo",
            "variant_create",
            key=f"{index}-landing-en",
            content_id=landing["record_id"],
            language="en",
            template_revision=landing_template["revision_id"],
            blocks={
                "hero": {"format": "html", "source": f"<h1>{name}</h1><p>A landing page.</p>"},
                "notes": {
                    "format": "markdown",
                    "source": "## Notes\n\n- written in **Markdown**\n",
                },
            },
        )
        service.execute(
            "demo",
            "resource_save",
            key=f"css-{index}",
            scope="site:" + site["record_id"],
            kind="css",
            name="Site styles",
            source="h1 { color: #192e42; }\n",
        )
    service.catalog.close()
    server = create_server(
        root,
        auth={},
        publication={
            "render_python": args.render_python,
            "management_origin": f"http://127.0.0.1:{args.port}",
            "preview_origin": f"http://localhost:{args.port}",
            "preview_secret": secrets.token_bytes(32),
        }
        if args.render_python
        else None,
        grants=grants,
        administration={
            "origin": f"http://127.0.0.1:{args.port}",
            "users": {"store_class": DemoUsers},
        },
    )
    print(
        f"Local demo: http://127.0.0.1:{args.port}/admin/ — username demo, password demo",
        flush=True,
    )
    uvicorn.run(server, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
