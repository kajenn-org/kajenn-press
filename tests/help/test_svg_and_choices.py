"""SVG cleaning, choices and asset tools of Help me (N8 Phase 2)."""

import base64
import json

import pytest

from kajenn_press.domain import DomainError
from kajenn_press.help.svg import clean_svg
from kajenn_press.help.tools import FONT_STACKS, HelpTools, checked_choices

NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
SKETCH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><defs><linearGradient id="g">'
    '<stop offset="0" stop-color="#7a3e1d"/></linearGradient></defs><rect x="6" y="6" '
    'width="28" height="28" rx="4" fill="url(#g)"/><text x="20" y="26" text-anchor="middle">'
    'B<tspan fill="#fff">R</tspan> 1962</text></svg>'
)


def test_a_clean_sketch_keeps_every_element_and_attribute():
    assert clean_svg(SKETCH) == SKETCH
    assert clean_svg(clean_svg(SKETCH)) == clean_svg(SKETCH)


@pytest.mark.parametrize(
    "hostile",
    [
        "<script>alert(1)</script>",
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject>',
        '<rect width="1" height="1" onclick="alert(1)"/>',
        '<use xlink:href="https://evil.example/x.svg#a"/>',
        '<use href="javascript:alert(1)"/>',
        '<rect width="1" height="1" fill="url(https://evil.example/p)"/>',
        '<rect width="1" height="1" style="fill:url(https://evil.example/p)"/>',
        '<image href="https://evil.example/i.png"/>',
    ],
)
def test_nothing_that_runs_or_loads_survives(hostile):
    cleaned = clean_svg(f'<svg {NS} viewBox="0 0 9 9"><circle r="2"/>{hostile}</svg>')
    for word in ("script", "foreignObject", "onclick", "evil", "javascript", "style"):
        assert word not in cleaned


@pytest.mark.parametrize(
    "refused",
    [
        '<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>',
        '<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        "<svg><circle r='2'/></svg>",
        "not xml",
    ],
)
def test_a_document_with_nothing_to_draw_is_refused(refused):
    with pytest.raises(DomainError):
        clean_svg(refused)


def test_choices_are_checked_and_resolved():
    palette = checked_choices(
        "palette",
        [
            {"label": "Walnut", "colors": ["#7a3e1d", "#e9d8c4"]},
            {"label": "Olive", "colors": ["#3d5a40", "#f1ede4"]},
        ],
    )
    assert palette[0] == {"label": "Walnut", "colors": ["#7a3e1d", "#e9d8c4"]}
    fonts = checked_choices(
        "fonts",
        [
            {"label": "Serif", "heading": "serif", "body": "sans"},
            {"label": "Mono", "heading": "mono", "body": "sans"},
        ],
    )
    assert fonts[0]["heading"] == FONT_STACKS["serif"]
    for kind, options in (
        (
            "palette",
            [
                {"label": "A", "colors": ["red", "#fff"]},
                {"label": "B", "colors": ["#000000", "#111111"]},
            ],
        ),
        (
            "fonts",
            [
                {"label": "A", "heading": "Comic Sans", "body": "sans"},
                {"label": "B", "heading": "serif", "body": "sans"},
            ],
        ),
        ("palette", [{"label": "only one", "colors": ["#000000", "#111111"]}]),
    ):
        with pytest.raises(DomainError):
            checked_choices(kind, options)


class Recorder:
    """Stands for SiteService: records what Help me asks it to run."""

    def __init__(self):
        self.calls = []

    def execute(self, identity, operation, *, via=None, **arguments):
        self.calls.append((identity, operation, via, arguments))
        return {"asset_id": "a1"}


def test_svg_and_css_assets_go_through_asset_add_cleaned():
    service = Recorder()
    tools = HelpTools(service, "anna", "s1")
    hostile = SKETCH.replace("<rect", '<rect onload="alert(1)"')
    assert not tools.run("svg_asset_add", {"name": "logo", "svg": hostile}, "t1")[1]
    assert not tools.run("css_asset_add", {"name": "site", "css": "body{color:#222}"}, "t2")[1]
    (_i, operation, via, svg), (_j, _o, _v, css) = service.calls
    assert (operation, via, svg["key"], svg["mime_type"]) == (
        "asset_add",
        "help_me",
        "help-t1",
        "image/svg+xml",
    )
    assert base64.b64decode(svg["data_base64"]).decode() == SKETCH
    assert (css["kind"], css["mime_type"]) == ("css", "text/css")
    content, error = tools.run(
        "offer_choices",
        {
            "question": "Q",
            "kind": "svg",
            "options": [{"label": "A", "svg": hostile}, {"label": "B", "svg": SKETCH}],
        },
        "t3",
    )
    assert not error and json.loads(content)["choices"][0]["svg"] == SKETCH
