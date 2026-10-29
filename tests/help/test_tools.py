"""Help me tools from the site operations (N8 Phase 1)."""

import inspect
import json
import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.application import PressApplication
from kajenn_press.domain import AccessPolicy
from kajenn_press.help.tools import ALLOWED, EXTRA, FILLED, HelpTools, tool_definitions
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.service import OPERATIONS, PUBLISHING, SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    doc.body().div(node_label="body", kpress_slot="body")
"""


@pytest.fixture
def service(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    grants = {"anna": {"*": ["read", "write", "create_site", "build"]}}
    return SiteService(
        tmp_path / "sites", SourceStore(versioned_bucket()), AccessPolicy(grants), worker=worker
    )


def test_tools_match_the_routes_and_leave_publishing_out():
    tools = {tool["name"]: tool for tool in tool_definitions()}
    assert list(tools) == [*ALLOWED, *EXTRA]
    tools = {name: tools[name] for name in ALLOWED}
    assert set(ALLOWED) <= OPERATIONS
    # publish_plan only reads which pages changed; every other publishing operation stays out.
    refused = (PUBLISHING - {"publish_plan"}) | {"site_new", "site_import", "site_restore"}
    assert not set(ALLOWED) & refused
    for name, tool in tools.items():
        route = inspect.signature(getattr(PressApplication, name)).parameters
        expected = {p for p in route if p != "self" and p not in FILLED}
        assert set(tool["input_schema"]["properties"]) == expected, name
        assert tool["description"], name


def test_a_tool_call_changes_the_site_as_the_user_through_help_me(service):
    site = service.execute("anna", "site_new", key="n", name="S")["site_id"]
    tools = HelpTools(service, "anna", site)

    content, error = tools.run(
        "template_add",
        {"name": "Layout", "engine": "gramlot", "python_source": LAYOUT},
        "toolu_1",
    )
    assert not error
    template = json.loads(content)["template_id"]
    again, _ = tools.run(
        "template_add",
        {"name": "Layout", "engine": "gramlot", "python_source": LAYOUT},
        "toolu_1",
    )
    assert json.loads(again)["template_id"] == template
    _page, error = tools.run("page_add", {"name": "Home", "template_id": template}, "toolu_2")
    assert not error
    assert not tools.run("site_save", {}, "toolu_3")[1]

    entries = [n.attr for n in service.working_copy(site).load().audit.nodes]
    made = [e for e in entries if e["operation"] in ("template_add", "page_add", "site_save")]
    assert [e["operation"] for e in made] == ["template_add", "page_add", "site_save"]
    assert {(e["identity"], e.get("via")) for e in made} == {("anna", "help_me")}


def test_refused_and_invalid_calls_come_back_as_tool_errors(service):
    site = service.execute("anna", "site_new", key="n", name="S")["site_id"]
    tools = HelpTools(service, "anna", site)

    content, error = tools.run("publish", {"selected": []}, "toolu_1")
    assert error and "cannot use publish" in content
    content, error = tools.run("content_add", {"name": "X"}, "toolu_2")
    assert error and json.loads(content)["code"] == "invalid_input"
    content, error = tools.run("content_add", {"name": "X", "format": "pdf", "text": ""}, "toolu_3")
    assert error and "html or markdown" in json.loads(content)["message"]


def test_a_template_that_does_not_build_comes_back_to_the_model(service):
    site = service.execute("anna", "site_new", key="n", name="S")["site_id"]
    tools = HelpTools(service, "anna", site)
    content, error = tools.run(
        "template_add", {"name": "L", "engine": "python", "python_source": LAYOUT}, "t1"
    )
    assert error and "gramlot or htmlbuilder" in content
    broken = "def build(source, data):\n    source.html().no_such_tag()\n"
    content, error = tools.run(
        "template_add", {"name": "L", "engine": "gramlot", "python_source": broken}, "t2"
    )
    assert error and json.loads(content)["code"] == "invalid_template"
