"""Rendering a page Bag in the installed worker (N2 Phase 7)."""

import json
import os
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from kajenn_press.rendering.process import RenderWorker
from kajenn_press.rendering.resolvers import ConfigValueResolver
from kajenn_press.site.model import Site
from kajenn_press.site.render import page_request

EXAMPLE = Path(__file__).parents[2] / "examples" / "kajenn_press_site"
PAGES = (
    ("home", "Kajenn Press · Editorial publishing with releases"),
    ("features", "Features · Kajenn Press"),
    ("start", "Get started · Kajenn Press"),
)


def render_python():
    python = os.environ.get("KAJENN_RENDER_PYTHON")
    if not python or not Path(python).is_file():
        raise AssertionError("Set KAJENN_RENDER_PYTHON to an installed .[render] interpreter")
    return python


class BodyText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside, self.parts = False, []

    def handle_starttag(self, tag, _attrs):
        self.inside = self.inside or tag == "body"

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def body_text(html):
    parser = BodyText()
    parser.feed(html)
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def example_site(worker):
    site = Site.create("Kajenn Press")
    layout = worker.plain_template("gramlot", (EXAMPLE / "layout.py").read_text())
    template = site.add_template("Layout", "gramlot", layout)
    css = site.add_asset("site", "css", (EXAMPLE / "site.css").read_bytes(), "text/css")
    logo = site.add_asset(
        "logo", "media", (EXAMPLE / "kajenn-press-logo.png").read_bytes(), "image/png"
    )
    pages = {}
    for key, title in PAGES:
        page = site.add_page(title, template)
        for slot in ("hero", "body"):
            text = (EXAMPLE / "pages" / f"{key}.{slot}.html").read_text()
            site.assign_content(page, slot, site.add_content(f"{key} {slot}", "html", text))
        site.add_page_asset(page, css)
        site.add_page_asset(page, logo)
        pages[key] = page
    return site, pages


OLD_PATH = """
import json, sys
from kajenn_press.rendering.engines import render_template
from kajenn_press.rendering.preparation import prepare_blocks
request = json.loads(sys.stdin.read())
blocks, _ = prepare_blocks(
    request["blocks"], {k: {"format": "html", "required": True} for k in request["blocks"]}, "x"
)
data = {"page": {"title": request["title"]}, "language": "en", "blocks": blocks,
        "resources": {"css": {"kind": "css", "url": "site.css"},
                      "logo": {"kind": "media", "url": "logo.png"}}}
print(json.dumps(render_template("gramlot", request["source"], data)))
"""


def old_template_html(key, title):
    blocks = {
        slot: {"format": "html", "source": (EXAMPLE / "pages" / f"{key}.{slot}.html").read_text()}
        for slot in ("hero", "body")
    }
    request = {"source": (EXAMPLE / "template.py").read_text(), "title": title, "blocks": blocks}
    completed = subprocess.run(
        [render_python(), "-I", "-c", OLD_PATH],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def worker():
    return RenderWorker(render_python(), timeout=30)


def test_example_pages_render_the_same_visible_text_as_the_previous_template(worker):
    site, pages = example_site(worker)
    for key, title in PAGES:
        result = worker.render_page(page_request(site, pages[key], {}))
        assert result["status"] == "succeeded", result
        html = result["html"]
        assert f"<title>{title}</title>" in html
        assert 'href="data:text/css;base64,' in html
        assert body_text(html) == body_text(old_template_html(key, title))


def small_site(worker, layout):
    site = Site.create("S")
    template = site.add_template("T", "gramlot", worker.plain_template("gramlot", layout))
    page = site.add_page("P", template)
    data = site.page(page).bag.get_item("data")
    data.set_item("news", None, resolver=ConfigValueResolver(connection="site", key="headline"))
    data.set_item(
        "notice",
        None,
        resolver=ConfigValueResolver(connection="site", key="notice", html=True),
    )
    return site, page


LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.div("^news", node_label="news")
    body.div("^notice", node_label="notice")
    body.div(node_label="map", kpress_slot="map", kpress_iframe="/app/map")
"""


def test_resolvers_use_named_connections_and_their_output_is_text_or_filtered_html(worker):
    site, page = small_site(worker, LAYOUT)
    site.assign_content(page, "map", site.add_content("Map", "html", "<p>Our office</p>"))
    connections = {
        "site": {"headline": "Hello <b>all</b>", "notice": "<p>Open</p><script>x()</script>"}
    }

    result = worker.render_page(page_request(site, page, connections))

    assert result["status"] == "succeeded", result
    html = result["html"]
    assert "Hello &lt;b&gt;all&lt;/b&gt;" in html
    assert "<p>Open</p>" in html and "<script" not in html
    assert '<div kpress_slot="map" kpress_iframe="/app/map"><p>Our office</p></div>' in html


def test_a_missing_connection_is_a_diagnostic(worker):
    site, page = small_site(worker, LAYOUT)
    result = worker.render_page(page_request(site, page, {}))
    assert result["status"] == "failed"
    assert result["diagnostics"][0]["code"] == "missing_connection"
    assert result["diagnostics"][0]["name"] == "site"
