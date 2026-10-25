"""Real storage and installed-worker fixtures, shared by behavioral contracts."""

import os
from pathlib import Path
from uuid import uuid4

from services.scenarios import create_service, record

from kajenn_press.rendering.process import RenderWorker
from kajenn_press.rendering.service import RenderService

TEMPLATE = """def build(source, data):
    doc = source.html(lang="^language")
    head = doc.head()
    head.title("^page.title")
    body = doc.body()
    body.h1("^page.title", title="^page.title")
    body.div("^blocks.intro", title="^blocks.intro")
    body.div("^blocks.body")
    body.a("Dettagli", href="/it/dettagli/")
    for revision, asset in data.get_item("resources").items():
        kind, url = asset.get_item("kind"), asset.get_item("url")
        if kind == "css":
            head.link(rel="stylesheet", href=url)
        elif kind == "javascript":
            body.script(src=url)
        elif kind == "media":
            body.img(src=url, alt="Immagine")
"""
DECLARATIONS = {
    "intro": {"format": "html", "required": True},
    "body": {"format": "markdown", "required": False},
}
BLOCKS = {
    "intro": {"format": "html", "source": "<p>Caffè &amp; tè</p>\r\n"},
    "body": {"format": "markdown", "source": "# Testo\n\n**importante**\n"},
}
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="


def configured_worker(**limits):
    python = os.environ.get("KAJENN_RENDER_PYTHON")
    if not python or not Path(python).is_file():
        raise AssertionError("Set KAJENN_RENDER_PYTHON to an installed .[render] interpreter")
    return RenderWorker(python, **limits)


def render_service(root, **limits):
    editorial = create_service(root)
    editorial.policy.grants["admin"]["*"].append("build")
    renderer = RenderService(editorial.catalog, editorial.policy, configured_worker(**limits))
    return editorial, renderer


def make_page(
    service,
    engine="gramlot",
    *,
    source=TEMPLATE,
    title="Una pagina",
    blocks=None,
    declarations=None,
):
    prefix = uuid4().hex
    site = record(service, "site_create", key=prefix + "site", name=prefix, languages=["it", "en"])
    scope = "site:" + site["record_id"]
    media = record(
        service,
        "media_save",
        key=prefix + "media",
        scope=scope,
        name="pixel",
        data_base64=PNG,
        mime_type="image/png",
    )
    css = record(
        service,
        "resource_save",
        key=prefix + "css",
        scope="library",
        kind="css",
        name=prefix + "style",
        source="p { color: #345; }\r\n",
    )
    javascript = record(
        service,
        "resource_save",
        key=prefix + "js",
        scope=scope,
        kind="javascript",
        name="interaction",
        source='console.log("trusted");\r\n',
        dependencies=[css["revision_id"], media["revision_id"]],
    )
    template = record(
        service,
        "resource_save",
        key=prefix + "template",
        scope=scope,
        kind="template",
        name="page",
        source=source,
        engine=engine,
        blocks=declarations if declarations is not None else DECLARATIONS,
        dependencies=[javascript["revision_id"]],
    )
    content = record(
        service, "content_create", key=prefix + "content", site_id=site["record_id"], title=title
    )
    variant = record(
        service,
        "variant_create",
        key=prefix + "variant",
        content_id=content["record_id"],
        language="it",
        template_revision=template["revision_id"],
        blocks=blocks if blocks is not None else BLOCKS,
    )
    return {
        "site": site,
        "template": template,
        "content": content,
        "variant": variant,
        "css": css,
        "javascript": javascript,
        "media": media,
    }


def render_page(renderer, page):
    frozen = renderer.freeze("admin", page["variant"]["record_id"])
    return frozen, renderer.render("admin", frozen)
