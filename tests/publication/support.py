"""Real publication fixtures using installed renderers and private filesystem storage."""

import base64
import struct
import zlib

from rendering.support import configured_worker
from services.scenarios import create_service, record

from kajenn_press.publication.service import PublicationService

CONFIG = {
    "management_origin": "https://admin.test",
    "preview_origin": "https://preview.test",
    "preview_secret": b"private-test-deployment-key-32bytes",
}
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
            body.img(src=asset.get_item("url"), alt="Pixel")
"""


def png():
    def chunk(kind, raw):
        return struct.pack(">I", len(raw)) + kind + raw + struct.pack(">I", zlib.crc32(kind + raw))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\xff"))
        + chunk(b"IEND", b"")
    )


def services(root, **config):
    editorial = create_service(root)
    editorial.policy.grants["admin"]["*"] += ["build", "preview_grant"]
    publication = PublicationService(
        editorial.catalog, editorial.policy, configured_worker(), **(CONFIG | config)
    )
    return editorial, publication


def site_fixture(editorial, publication, prefix="one", source=TEMPLATE):
    site = record(
        editorial, "site_create", key=prefix + "site", name=prefix, languages=["it", "en"]
    )
    scope = "site:" + site["record_id"]
    css = record(
        editorial,
        "resource_save",
        key=prefix + "css",
        scope="library",
        kind="css",
        name=prefix + "css",
        source="h1 {color: #345}",
    )
    media = record(
        editorial,
        "media_save",
        key=prefix + "media",
        scope=scope,
        name="pixel",
        data_base64=base64.b64encode(png()).decode(),
        mime_type="image/png",
    )
    template = record(
        editorial,
        "resource_save",
        key=prefix + "template",
        scope=scope,
        kind="template",
        name="template",
        engine="gramlot",
        source=source,
        dependencies=[css["revision_id"], media["revision_id"]],
        blocks={"body": {"format": "markdown", "required": True}},
    )
    content = record(
        editorial, "content_create", key=prefix + "content", site_id=site["record_id"], title="Page"
    )
    variants, routes = {}, {}
    for language, path in (("it", ""), ("en", "about")):
        variants[language] = record(
            editorial,
            "variant_create",
            key=prefix + language,
            content_id=content["record_id"],
            language=language,
            template_revision=template["revision_id"],
            blocks={
                "body": {
                    "format": "markdown",
                    "source": f"# {language}\n\n<strong>Static</strong>\n\n| A | B |\n|---|---|\n| 1 | 2 |",
                }
            },
        )
        routes[language] = publication.execute(
            "admin",
            "publication_route_save",
            key=prefix + language + "route",
            variant_id=variants[language]["record_id"],
            path=path,
            title=language + " title",
            description=language + " description",
        )
    settings = publication.execute(
        "admin",
        "publication_settings_save",
        key=prefix + "settings",
        site_id=site["record_id"],
        channel="main",
        public_origin=f"https://{prefix}.test",
        primary_language="it",
        landing_variant=variants["it"]["record_id"],
    )
    return {
        "site": site,
        "css": css,
        "media": media,
        "template": template,
        "content": content,
        "variants": variants,
        "routes": routes,
        "settings": settings,
    }


def candidate(publication, fixture, key="candidate", **kwargs):
    return publication.execute(
        "admin",
        "candidate_create",
        key=key,
        settings_id=fixture["settings"]["record_id"],
        variant_revisions=[v["revision_id"] for v in fixture["variants"].values()],
        **kwargs,
    )


def built(publication, selection, key="build"):
    started = publication.execute(
        "admin", "build_start", candidate_id=selection["record_id"], key=key
    )
    publication._futures[started["record_id"]].result(timeout=40)
    status = publication.execute("admin", "build_status", build_id=started["record_id"])
    assert status["attributes"]["state"] == "succeeded", status
    return status
