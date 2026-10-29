"""Putting a site online on its server (N7b Phase 5)."""

import os
import socket
import threading
import time

import pytest
import uvicorn
from publication.storage_support import versioned_bucket

from kajenn_press.agent.app import create_agent_server
from kajenn_press.agent.drivers import TraefikDriver
from kajenn_press.domain import AccessPolicy
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.publish import Publisher
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    doc.body().div(node_label="body", kpress_slot="body")
"""


@pytest.fixture
def agent(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    dynamic = tmp_path / "dynamic"
    dynamic.mkdir()
    app = create_agent_server(
        token="agent-secret",
        driver=TraefikDriver(dynamic, "http://127.0.0.1:8877"),
        allowed=["127.0.0.1"],
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", dynamic
    server.should_exit = True
    thread.join(10)


def test_a_site_goes_live_step_by_step(tmp_path, agent):
    agent_url, dynamic = agent
    tokens = tmp_path / "tokens"
    tokens.mkdir()
    (tokens / "web-1.token").write_text("agent-secret\n")
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    service = SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy(
            {"anna": {"*": ["read", "write", "create_site", "build", "publish", "servers"]}}
        ),
        worker=worker,
        publisher=Publisher(versioned_bucket(), worker),
        agent_tokens=tokens,
    )

    def run(operation, **arguments):
        return service.execute("anna", operation, **arguments)

    run("server_add", key="w", name="web-1", ipv4=["157.90.1.20"], ipv6=[], agent_url=agent_url)
    site = run("site_new", key="n", name="Bottega")["site_id"]
    template = run(
        "template_add", site_id=site, key="t", name="L", engine="gramlot", python_source=LAYOUT
    )
    page = run("page_add", site_id=site, key="p", name="Home", template_id=template["template_id"])
    run(
        "page_seo_set",
        site_id=site,
        key="o",
        page_id=page["page_id"],
        fields={"origin": "https://bottega.example"},
    )
    run("site_server_set", site_id=site, key="s", server="web-1", alias=True)

    service.dns_lookup = lambda name, kind, resolver: []
    stopped = run("site_go_live", site_id=site, key="g1")
    assert [s["step"] for s in stopped["steps"]] == ["dns"] and stopped["ok"] is False

    service.dns_lookup = lambda name, kind, resolver: ["157.90.1.20"]
    service.address_answers = lambda address: address == "https://bottega.example"
    live = run("site_go_live", site_id=site, key="g2")
    assert live["ok"] is True, live
    assert [(s["step"], s["ok"]) for s in live["steps"]] == [
        ("dns", True), ("publish", True), ("certificate", True), ("online", True)
    ]  # fmt: skip
    assert live["steps"][2]["detail"]["proxy"] == "traefik"
    routers = (dynamic / "kpress-bottega.example.yml").read_text()
    assert "Host(`bottega.example`) || Host(`www.bottega.example`)" in routers
    assert service.publisher.binding(site)[0] == "https://bottega.example"
