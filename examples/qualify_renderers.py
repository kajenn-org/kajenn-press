"""Run with the installed [render] profile: python examples/qualify_renderers.py."""

import importlib.util
import json

from kajenn_public_site.rendering.contract import PreparedHTML, RenderProblem
from kajenn_public_site.rendering.engines import installed_profile, render_template

SOURCE = """def build(source, data):
    doc = source.html(lang="^language")
    doc.head().title("^page.title")
    body = doc.body()
    body.h1("^page.title", title="^page.title")
    body.div("^blocks.body")
    body.a("Approfondisci", href="/it/dettagli/")
"""


def main():
    for engine in ("gramlot", "htmlbuilder"):
        html = render_template(
            engine,
            SOURCE,
            {
                "language": "it",
                "page": {"title": '<b>"Test"</b>::HTML'},
                "blocks": {"body": PreparedHTML("<p>HTML preparato</p>")},
            },
        )
        assert html.startswith('<!doctype html><html lang="it">')
        assert '<h1 title="&lt;b&gt;&quot;Test&quot;&lt;/b&gt;::HTML">' in html
        assert '&lt;b&gt;"Test"&lt;/b&gt;::HTML</h1>' in html
        assert "<div><p>HTML preparato</p></div>" in html
        assert '<a href="/it/dettagli/">Approfondisci</a>' in html
        try:
            render_template(engine, SOURCE.replace('"^page.title"', '"==browser.title"'), {})
        except RenderProblem:
            pass
        else:
            raise AssertionError("Browser binding accepted")
    print(
        json.dumps(
            {
                "qualified": ["gramlot", "htmlbuilder"],
                "profile": installed_profile(),
                "paths": {
                    name: importlib.util.find_spec(name).origin
                    for name in ("gramlot", "genro_builders", "nh3", "markdown_it")
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
