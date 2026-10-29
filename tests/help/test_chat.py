"""The Help me chat loop and its store, with a scripted client in place of the API (N8 Phase 3)."""

import copy
import json
import os
from types import SimpleNamespace

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.help.chat import MODEL, HelpService, HelpStore
from kajenn_press.help.tools import tool_definitions
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.div(node_label="hero", kpress_slot="hero")
    body.div(node_label="body", kpress_slot="body")
"""
USAGE = {
    "input_tokens": 1000,
    "output_tokens": 200,
    "cache_creation_input_tokens": 400,
    "cache_read_input_tokens": 3000,
}
# 1000 x 2 + 200 x 10 + 400 x 2.5 + 3000 x 0.2 = 5600 dollars per million tokens.
STEP_COST = 0.0056


class ScriptedClient:
    """Stands for the Anthropic client: each create() answers with the next scripted step."""

    def __init__(self, steps):
        self.steps, self.requests = list(steps), []
        self.beta = SimpleNamespace(messages=self)

    def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        content, stop = self.steps.pop(0)(request["messages"])
        return SimpleNamespace(
            content=content,
            stop_reason=stop,
            usage=SimpleNamespace(**USAGE),
            model=MODEL,
        )


def tool_use(call_id, tool, **arguments):
    return {"type": "tool_use", "id": call_id, "name": tool, "input": arguments}


def results(messages):
    """Tool results of the last user message, by tool use id, decoded."""
    return {b["tool_use_id"]: json.loads(b["content"]) for b in messages[-1]["content"]}


def build_home(messages):
    return [
        {"type": "thinking", "thinking": "", "signature": "sig-1"},
        {"type": "text", "text": "I add a layout and two contents."},
        tool_use("t1", "template_add", name="Layout", engine="gramlot", python_source=LAYOUT),
        tool_use("t2", "content_add", name="Welcome", format="html", text="<h1>Welcome</h1>"),
        tool_use("t3", "content_add", name="Intro", format="markdown", text="We make tables."),
    ], "tool_use"


def add_page(messages):
    found = results(messages)
    return [
        tool_use("t4", "page_add", name="Home", template_id=found["t1"]["template_id"])
    ], "tool_use"


def fill_slots(messages):
    page = results(messages)["t4"]["page_id"]
    contents = [
        m for m in messages if m["role"] == "user" and m["content"][0]["type"] == "tool_result"
    ]
    first = {b["tool_use_id"]: json.loads(b["content"]) for b in contents[0]["content"]}
    return [
        tool_use(
            "t5", "slot_assign", page_id=page, slot="hero", content_id=first["t2"]["content_id"]
        ),
        tool_use(
            "t6", "slot_assign", page_id=page, slot="body", content_id=first["t3"]["content_id"]
        ),
        tool_use("t7", "site_save"),
    ], "tool_use"


def done(messages):
    return [{"type": "text", "text": "Home is ready."}], "end_turn"


@pytest.fixture
def setup(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    grants = {"anna": {"*": ["read", "write", "create_site"]}, "carla": {"*": ["read"]}}
    service = SiteService(
        tmp_path / "s", SourceStore(versioned_bucket()), AccessPolicy(grants), worker=worker
    )
    site = service.execute("anna", "site_new", key="n", name="Bottega")["site_id"]
    return service, site


def test_a_turn_builds_a_page_and_keeps_an_append_only_history(setup):
    service, site = setup
    client = ScriptedClient([build_home, add_page, fill_slots, done, done])
    help_me = HelpService(service, HelpStore(service.store), client)

    shown = help_me.send("anna", site, "A home page for my workshop")
    assert shown["stop"] == "end_turn" and shown["title"] == "A home page for my workshop"
    assert shown["usage"]["input"] == 4000 and shown["cost"] == pytest.approx(4 * STEP_COST)
    assert [i["kind"] for i in shown["items"]] == [
        "user", "assistant", "action", "action", "action", "action", "action", "action",
        "action", "assistant",
    ]  # fmt: skip
    assert all(i["ok"] for i in shown["items"] if i["kind"] == "action")

    site_bag = service.working_copy(site).load()
    (page,) = [n.label for n in site_bag.section("pages").nodes]
    assert {n.attr["slot"] for n in site_bag.page(page).slots.nodes} == {"hero", "body"}
    assert len(service.store.versions(site)) == 2
    assert {
        a.attr.get("via") for a in site_bag.audit.nodes if a.attr["operation"] != "site_new"
    } == {"help_me"}

    first = client.requests[0]
    assert first["model"] == MODEL and first["tools"] == tool_definitions()
    assert first["fallbacks"] == "default" and first["thinking"] == {"type": "adaptive"}
    assert all(
        r["tools"] == first["tools"] and r["system"] == first["system"] for r in client.requests
    )
    # Each request extends the previous one: nothing earlier is edited (preserved thinking).
    for before, after in zip(client.requests, client.requests[1:], strict=False):
        assert after["messages"][: len(before["messages"])] == before["messages"]

    again = HelpService(service, HelpStore(service.store), client)
    resumed = again.send("anna", site, "Thanks", chat_id=shown["chat_id"])
    assert client.requests[-1]["messages"][: len(client.requests[3]["messages"]) + 1] == (
        client.requests[3]["messages"]
        + [client.requests[-1]["messages"][len(client.requests[3]["messages"])]]
    )
    assert resumed["cost"] == pytest.approx(5 * STEP_COST)
    listing = again.chats("anna", site)
    assert [c["chat_id"] for c in listing["chats"]] == [shown["chat_id"]]
    assert listing["site_cost"] == pytest.approx(5 * STEP_COST)
    assert again.chat("carla", site, shown["chat_id"])["items"][-1]["text"] == "Home is ready."


def test_offered_choices_end_the_turn_and_the_pick_is_the_next_message(setup):
    service, site = setup
    palette = [
        {"label": "Walnut", "colors": ["#7a3e1d", "#e9d8c4"]},
        {"label": "Olive", "colors": ["#3d5a40", "#f1ede4"]},
    ]

    def offer(messages):
        return [
            tool_use("c1", "offer_choices", question="Palette?", kind="palette", options=palette)
        ], "tool_use"

    client = ScriptedClient([offer, done])
    help_me = HelpService(service, HelpStore(service.store), client)
    shown = help_me.send("anna", site, "Choose colours")
    assert shown["stop"] == "choices" and len(client.requests) == 1
    assert shown["items"][-1] == {
        "kind": "choices",
        "question": "Palette?",
        "kind_of_choice": "palette",
        "choices": palette,
    }
    help_me.send("anna", site, "Walnut", chat_id=shown["chat_id"])
    last = client.requests[-1]["messages"][-1]
    assert last["role"] == "user" and last["content"][0]["type"] == "text"
    assert client.requests[-1]["messages"][-2]["content"][0]["type"] == "tool_result"


def test_only_the_holder_with_write_grants_uses_help_me(setup):
    service, site = setup
    help_me = HelpService(service, HelpStore(service.store), ScriptedClient([done]))
    with pytest.raises(DomainError):
        help_me.send("carla", site, "Hello")
    with pytest.raises(DomainError, match="Write a message"):
        help_me.send("anna", site, "  ")
    with pytest.raises(DomainError):
        help_me.chats("bruno", site)
