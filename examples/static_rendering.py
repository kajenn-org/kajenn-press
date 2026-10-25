"""Two real engines, local derived files. No preview/publication server is started."""

import argparse
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from kajenn_press.catalog.local import LocalCatalog
from kajenn_press.domain import AccessPolicy
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.rendering.service import RenderService
from kajenn_press.services.editorial import EditorialService


def demonstrate(python, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    template_source = Path(__file__).with_name("static_template.py").read_text()
    report = {}
    with (
        TemporaryDirectory(prefix="kajenn-render-demo-") as directory,
        LocalCatalog(directory) as cat,
    ):
        policy = AccessPolicy({"demo": {"*": ["read", "write", "use", "create_site", "build"]}})
        editorial = EditorialService(cat, policy)
        renderer = RenderService(cat, policy, RenderWorker(python))

        def save(operation, **arguments):
            return editorial.execute("demo", operation, **arguments)["records"][0]

        site = save("site_create", key="site", name="Demo statica", languages=["it"])
        scope = "site:" + site["record_id"]
        css = save(
            "resource_save",
            key="css",
            scope=scope,
            kind="css",
            name="style",
            source="body {max-width:60rem;margin:3rem auto;font-family:system-ui} "
            "td,th {border:1px solid #aaa;padding:.4rem} .accent {color:#256}",
        )
        javascript = save(
            "resource_save",
            key="js",
            scope=scope,
            kind="javascript",
            name="optional",
            source="document.documentElement.dataset.enhanced='true';",
        )
        media = save(
            "media_save",
            key="media",
            scope=scope,
            name="pixel",
            mime_type="image/png",
            data_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=",
        )
        dependencies = [item["revision_id"] for item in (css, javascript, media)]
        for engine in ("gramlot", "htmlbuilder"):
            template = save(
                "resource_save",
                key=engine + "template",
                scope=scope,
                kind="template",
                name=engine,
                source=template_source,
                engine=engine,
                dependencies=dependencies,
                blocks={
                    "intro": {"format": "html", "required": True},
                    "body": {"format": "markdown", "required": True},
                },
            )
            content = save(
                "content_create",
                key=engine + "content",
                site_id=site["record_id"],
                title='<Testo ordinario> & "citazione"::HTML',
            )
            variant = save(
                "variant_create",
                key=engine + "variant",
                content_id=content["record_id"],
                language="it",
                template_revision=template["revision_id"],
                blocks={
                    "intro": {
                        "format": "html",
                        "source": '<p class="accent">HTML <b>preparato</b>.</p><script>removed()</script>',
                    },
                    "body": {
                        "format": "markdown",
                        "source": '## Contenuti statici\n\n| Formato | Esito |\n|---|---|\n| HTML | pronto |\n| Markdown | pronto |\n\n```python\nx < 2\n```\n\n<span style="color:green">HTML nel Markdown</span>',
                    },
                },
            )
            first_input = renderer.freeze("demo", variant["record_id"])
            urls = {
                rid: asset["url"].lstrip("/")
                for rid, asset in first_input.unpack()["data"]["resources"].items()
            }
            frozen = renderer.freeze("demo", variant["record_id"], resource_urls=urls)
            result = renderer.render("demo", frozen)
            repeated = renderer.render("demo", frozen)
            if result["status"] != "succeeded" or repeated["status"] != "succeeded":
                raise RuntimeError((result, repeated))
            assert result["html"] == repeated["html"]
            assert result["attempt_id"] != repeated["attempt_id"]
            (output / (engine + ".html")).write_text(result["html"])
            for rid, url in urls.items():
                asset = frozen.unpack()["references"][rid]
                raw = base64.b64decode(next(iter(asset["sources"].values())))
                target = output / url
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            report[engine] = {
                "digest": result["digest"],
                "diagnostics": result["diagnostics"],
                "profile": result["profile"],
                "output": str(output / (engine + ".html")),
            }
    (output / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, help="Interpreter with installed .[render]")
    parser.add_argument("output", help="Dedicated derived demo directory")
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.python, args.output), indent=2))
