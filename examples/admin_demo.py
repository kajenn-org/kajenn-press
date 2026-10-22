"""Loopback-only disposable administration demo; never a production identity store."""

import argparse
import copy
import tempfile

import uvicorn
from kajenn.auth.user_store import UserStore

from kajenn_public_site.application import create_server
from kajenn_public_site.catalog.local import LocalCatalog
from kajenn_public_site.domain import AccessPolicy
from kajenn_public_site.services.editorial import EditorialService


class DemoUsers(UserStore):
    def __init__(self, storage):  # wf:phase-1:new
        self.record = {
            "identity": "demo",
            "password_hash": self.hash_password("demo"),
            "tags": ["editor"],
            "enabled": True,
        }

    def load_all(self):  # wf:phase-1:new
        return [copy.deepcopy(self.record)] if self.record else []

    def get(self, identity):  # wf:phase-1:new
        return copy.deepcopy(self.record) if self.record and identity == "demo" else None

    def save(self, record):  # wf:phase-1:new
        self.record = copy.deepcopy(record)

    def delete(self, identity):  # wf:phase-1:new
        found = self.get(identity) is not None
        if found:
            self.record = None
        return found


def main():  # wf:phase-1:new
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8874)
    args = parser.parse_args()
    root = tempfile.mkdtemp(prefix="kajenn-admin-demo-")
    grants = {"demo": {"*": ["read", "write", "use", "create_site"]}}
    service = EditorialService(LocalCatalog(root), AccessPolicy(grants))
    template = service.execute(
        "demo",
        "resource_save",
        key="template",
        scope="library",
        kind="template",
        name="Standard page",
        source="def build(source, data):\n    source.h1('^page.title')\n",
        engine="gramlot",
        blocks={"body": {"format": "markdown", "required": True}},
    )["records"][0]
    for index, name in enumerate(("Kajenn", "Gramlot")):
        site = service.execute(
            "demo", "site_create", key=f"site-{index}", name=name, languages=["it", "en"]
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
                    template_revision=template["revision_id"],
                    blocks={
                        "body": {
                            "format": "markdown",
                            "source": f"# {title}\n\nSample content.",
                        }
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
