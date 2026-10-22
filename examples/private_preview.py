"""Local two-site preview demo. Credentials stay in a private file, never console logs."""

import argparse
import base64
import json
import os
import secrets
import struct
import time
import urllib.request
import zlib
from pathlib import Path

import uvicorn

from kajenn_public_site.application import create_server
from kajenn_public_site.catalog.filesystem import private_directory
from kajenn_public_site.catalog.local import LocalCatalog
from kajenn_public_site.domain import AccessPolicy
from kajenn_public_site.publication.service import PublicationService
from kajenn_public_site.rendering.process import RenderWorker
from kajenn_public_site.services.editorial import EditorialService

PERMISSIONS = ["read", "write", "use", "create_site", "build", "preview_grant"]
TEMPLATE = """def build(source, data):
    doc = source.html(lang="^language")
    head = doc.head()
    head.title("^page.title")
    body = doc.body()
    body.h1("^page.title")
    body.div("^blocks.body")
    body.a("Italiano", href="/it/")
    body.a("English", href="/en/about/")
    for asset in data.get_item("resources").values():
        if asset.get_item("kind") == "css":
            head.link(rel="stylesheet", href=asset.get_item("url"))
        elif asset.get_item("kind") == "media":
            body.img(src=asset.get_item("url"), alt="Immagine della release")
"""


def pixel():
    def chunk(kind, raw):
        return struct.pack(">I", len(raw)) + kind + raw + struct.pack(">I", zlib.crc32(kind + raw))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\x21\x76\x84\xff"))
        + chunk(b"IEND", b"")
    )


def prepare(root, python, port, public_origins=None):
    root = private_directory(root)
    config_path = root / "demo-credentials.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    config = {
        "management_origin": f"http://127.0.0.1:{port}",
        "preview_origin": f"http://localhost:{port}",
        "preview_secret": secrets.token_hex(32),
        "render_python": str(Path(python).absolute()),
        "admin_token": secrets.token_urlsafe(32),
        "port": port,
        "grants": [],
        "public_origins": {},
    }
    catalog = LocalCatalog(root / "catalog")
    policy = AccessPolicy({"demo": {"*": PERMISSIONS}})
    editorial = EditorialService(catalog, policy)
    pub = PublicationService(
        catalog,
        policy,
        RenderWorker(config["render_python"]),
        management_origin=config["management_origin"],
        preview_origin=config["preview_origin"],
        preview_secret=bytes.fromhex(config["preview_secret"]),
    )
    try:

        def save(operation, **args):
            return editorial.execute("demo", operation, **args)["records"][0]

        for label, engine in (("Primo sito", "gramlot"), ("Secondo sito", "htmlbuilder")):
            site = save("site_create", key=label, name=label, languages=["it", "en"])
            scope = "site:" + site["record_id"]
            css = save(
                "resource_save",
                key=label + "css",
                scope=scope,
                kind="css",
                name="style",
                source="body {max-width:56rem;margin:4rem auto;font:18px system-ui;color:#19353a} h1 {color:#217684} a {margin-right:1rem} td,th {padding:.5rem;border:1px solid #bbb} img {display:block;width:64px;height:64px;margin-top:2rem}",
            )
            media = save(
                "media_save",
                key=label + "media",
                scope=scope,
                name="pixel",
                mime_type="image/png",
                data_base64=base64.b64encode(pixel()).decode(),
            )
            template = save(
                "resource_save",
                key=label + "template",
                scope=scope,
                kind="template",
                name="page",
                engine=engine,
                source=TEMPLATE,
                dependencies=[css["revision_id"], media["revision_id"]],
                blocks={"body": {"format": "markdown", "required": True}},
            )
            content = save(
                "content_create", key=label + "content", site_id=site["record_id"], title=label
            )
            variants = []
            for language, path in (("it", ""), ("en", "about")):
                variant = save(
                    "variant_create",
                    key=label + language,
                    content_id=content["record_id"],
                    language=language,
                    template_revision=template["revision_id"],
                    blocks={
                        "body": {
                            "format": "markdown",
                            "source": "## Contenuti statici\n\nHTML nel Markdown: <strong>già renderizzato</strong>.\n\n| Motore | Lingua |\n|---|---|\n| "
                            + engine
                            + " | "
                            + language
                            + " |",
                        }
                    },
                )
                variants.append(variant)
                pub.execute(
                    "demo",
                    "publication_route_save",
                    variant_id=variant["record_id"],
                    path=path,
                    title=label + " · " + language,
                    description="Anteprima privata della release",
                    key=label + language + "route",
                )
            settings = pub.execute(
                "demo",
                "publication_settings_save",
                site_id=site["record_id"],
                channel="main",
                public_origin=(public_origins or {}).get(engine, "https://" + engine + ".example"),
                primary_language="it",
                landing_variant=variants[0]["record_id"],
                key=label + "settings",
            )
            config["public_origins"][settings["attributes"]["public_origin"]] = settings[
                "record_id"
            ]
            selection = pub.execute(
                "demo",
                "candidate_create",
                settings_id=settings["record_id"],
                variant_revisions=[v["revision_id"] for v in variants],
                key=label + "candidate",
            )
            job = pub.execute(
                "demo", "build_start", candidate_id=selection["record_id"], key=label + "build"
            )
            # Poll the public service contract; do not depend on executor internals.
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                status = pub.execute("demo", "build_status", build_id=job["record_id"])
                if status["attributes"]["state"] in {"succeeded", "failed", "interrupted"}:
                    break
                time.sleep(0.1)
            if status["attributes"]["state"] != "succeeded":
                raise RuntimeError(status["attributes"]["diagnostics"])
            grant = pub.execute(
                "demo",
                "preview_grant_create",
                build_id=job["record_id"],
                lifetime_seconds=3600,
                key=label + "grant",
            )
            config["grants"].append(grant)
        fd = os.open(config_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(config, stream, indent=2)
        return config
    finally:
        pub.close()
        catalog.close()


def serve(root, config):
    publication = {k: config[k] for k in ("management_origin", "preview_origin", "render_python")}
    publication["preview_secret"] = bytes.fromhex(config["preview_secret"])
    app = create_server(
        Path(root) / "catalog",
        auth={"bearer": {"demo": {"token": config["admin_token"], "tags": "editor"}}},
        grants={"demo": {"*": PERMISSIONS}},
        publication=publication,
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=config["port"],
        access_log=False,
        proxy_headers=False,
        log_level="warning",
    )


def revoke(config):
    for grant in config["grants"]:
        body = json.dumps(
            {
                "grant_id": grant["record_id"],
                "expected_generation": grant["generation"],
                "key": "demo-revoke-" + grant["record_id"],
            }
        ).encode()
        request = urllib.request.Request(
            config["management_origin"] + "/preview_grant_revoke",
            data=body,
            headers={
                "Authorization": "Bearer " + config["admin_token"],
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request) as response:
            assert json.load(response)["ok"]
    print("Anteprime revocate tramite REST.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", default=os.sys.executable)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    configuration = prepare(args.root, args.python, args.port)
    if args.revoke:
        revoke(configuration)
    else:
        print(
            "Demo pronta; URL e credenziali nel file privato:",
            args.root / "demo-credentials.json",
            flush=True,
        )
        if not args.prepare_only:
            serve(args.root, configuration)
