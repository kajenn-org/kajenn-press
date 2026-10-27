"""Qualification of the Source Bag path on the installed render profile (N2 Phase 1).

The engines live only in the render interpreter, so each check runs there as a script
and reports JSON. Set KAJENN_RENDER_PYTHON to an installed .[render] interpreter.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

PRELUDE = """
import json
from genro_bag import Bag
from genro_bag.resolver import BagCbResolver
from kajenn_press.rendering.engines import make_builder, validate_static_source


def author(source):
    doc = source.html(lang="en")
    doc.head().title("Title")
    body = doc.body()
    hero = body.div(node_label="hero", kpress_slot="hero", class_="hero")
    hero.p("Hello & <b>")
    body.section(node_label="main").div(node_label="info", kpress_slot=True)
    body.table().tr().td(kpress_slot="cell")


def replay(target, loaded):
    # Rebuild a loaded Source through the target builder's grammar: loaded nodes carry
    # tag, label and attributes but no builder, so they cannot be rendered directly.
    for node in loaded:
        value = node.value
        attributes = dict(node.attr)
        if node.label != node.node_tag:
            attributes["node_label"] = node.label
        args = () if value is None or isinstance(value, Bag) else (value,)
        child = getattr(target, node.node_tag)(*args, **attributes)
        if isinstance(value, Bag):
            replay(child, value)


def render(builder):
    return builder.render(mode="html", target=False, doctype=True)
"""

ROUND_TRIP = """
original = make_builder(ENGINE)
author(original.source)
before = render(original)
loaded = Bag.from_tytx(original.source.to_tytx(transport="json"))
rebuilt = make_builder(ENGINE)
replay(rebuilt.source, loaded)
print(json.dumps({
    "same_html": render(rebuilt) == before,
    "named_slot": rebuilt.source.findNodeByAttr("kpress_slot", "cell").label,
    "path_slot": rebuilt.source.get_node("html_0.body.main.info").attr,
    "emitted": '<td kpress_slot="cell">' in before,
}))
"""

RESOLVER = """
calls = [0]


def latest():
    calls[0] += 1
    return "Value <b>%d</b>" % calls[0]


builder = make_builder(ENGINE)
builder.data.set_item("news.latest", BagCbResolver(latest, cache_time=60))
doc = builder.source.html(lang="en")
doc.head().title("Title")
doc.body().div("^news.latest", kpress_slot="news")
validate_static_source(builder)
first, second = render(builder), render(builder)
print(json.dumps({
    "calls": calls[0],
    "escaped": "Value &lt;b&gt;1&lt;/b&gt;" in first,
    "stable": first == second,
}))
"""


def run_in_render_profile(engine, body):
    python = os.environ.get("KAJENN_RENDER_PYTHON")
    if not python or not Path(python).is_file():
        raise AssertionError("Set KAJENN_RENDER_PYTHON to an installed .[render] interpreter")
    script = PRELUDE + f"\nENGINE = {engine!r}\n" + body
    completed = subprocess.run(
        [python, "-I", "-c", script], capture_output=True, text=True, timeout=60, check=False
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("engine", ["gramlot", "htmlbuilder"])
def test_loaded_source_renders_the_same_html_after_replay(engine):
    result = run_in_render_profile(engine, ROUND_TRIP)
    assert result["same_html"] is True
    assert result["named_slot"] == "td_0"
    assert result["path_slot"] == {"kpress_slot": True}
    assert result["emitted"] is True


@pytest.mark.parametrize("engine", ["gramlot", "htmlbuilder"])
def test_cached_resolver_fills_a_slot_as_escaped_text(engine):
    result = run_in_render_profile(engine, RESOLVER)
    assert result == {"calls": 1, "escaped": True, "stable": True}
