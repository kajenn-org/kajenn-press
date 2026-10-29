"""Help me against the Claude API: real tokens, run only on request (N8 Phase 4).

KAJENN_HELP_LIVE=1 enables it; the Anthropic SDK finds the credentials in its usual
places (ANTHROPIC_API_KEY or an `ant auth login` profile).
"""

import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy
from kajenn_press.help.chat import HelpService, HelpStore
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_HELP_LIVE") != "1", reason="Set KAJENN_HELP_LIVE=1: costs real tokens"
)
REQUEST = (
    "Build a small site for Bottega Rossi, a furniture workshop in Bologna since 1962: "
    "two pages, Home and Contacts, with a layout, a stylesheet in warm colours and two "
    "contents per page. Do not ask me anything and do not offer choices: decide yourself, "
    "then save."
)


def test_one_request_builds_a_two_page_site(tmp_path):
    import anthropic

    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=60)
    service = SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy({"anna": {"*": ["read", "write", "create_site", "build"]}}),
        worker=worker,
    )
    site = service.execute("anna", "site_new", key="n", name="Bottega Rossi")["site_id"]
    help_me = HelpService(service, HelpStore(service.store), anthropic.Anthropic())

    shown = help_me.send("anna", site, REQUEST)
    print(f"\nstop {shown['stop']} · usage {shown['usage']} · cost ${shown['cost']:.4f}")
    built = service.working_copy(site).load()
    pages = [built.page(n.label) for n in built.section("pages").nodes]
    assert len(pages) >= 2
    assert all(len(page.slots) >= 1 for page in pages)
    for page in pages:
        rendered = service.execute("anna", "page_render", site_id=site, page_id=page.page_id)
        assert rendered["status"] == "succeeded", rendered
    assert len(service.store.versions(site)) >= 2


def test_one_request_translates_a_page(tmp_path):
    import anthropic

    service = SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy({"anna": {"*": ["read", "write", "create_site", "build"]}}),
        worker=RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=60),
    )
    site = service.execute("anna", "site_new", key="n", name="Bottega Rossi")["site_id"]
    contents = [
        service.execute(
            "anna", "content_add", site_id=site, key=f"c{i}", name=name, format="html", text=text
        )["content_id"]
        for i, (name, text) in enumerate(
            (
                ("Welcome", "<h1>Benvenuti in bottega</h1>"),
                ("Intro", "<p>Mobili fatti a mano dal 1962.</p>"),
            )
        )
    ]
    service.execute("anna", "site_languages_set", site_id=site, key="l", languages=["it", "en"])
    help_me = HelpService(service, HelpStore(service.store), anthropic.Anthropic())

    shown = help_me.send("anna", site, "Translate every content into English.")
    print(f"\nstop {shown['stop']} · usage {shown['usage']} · cost ${shown['cost']:.4f}")
    read = service.execute("anna", "site_read", site_id=site)
    states = {c["id"]: c["translations"]["en"] for c in read["contents"]}
    assert set(states) == set(contents)
    assert all(state["state"] == "to_review" and state["text"] for state in states.values())
