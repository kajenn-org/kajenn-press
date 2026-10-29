"""DNS records of a site and their check (N7b Phase 4)."""

import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.dns import dns_check, dns_plan
from kajenn_press.site.publish import Publisher
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

SERVER = {"ipv4": ["157.90.1.20"], "ipv6": ["2a01:4f8::20"], "agent_url": "https://web-1.example"}
LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.body().div(node_label="body", kpress_slot="body")
"""


def fake(answers):
    """A lookup answering from a table; `None` stands for a resolver that timed out."""

    def lookup(name, kind, resolver):
        return answers.get((name, kind, resolver), answers.get((name, kind), []))

    return lookup


def test_the_plan_lists_a_and_aaaa_for_both_names():
    plan = dns_plan(["https://www.bottega.example", "https://bottega.example"], SERVER)
    assert plan == [
        {"name": "www.bottega.example", "type": "A", "value": "157.90.1.20"},
        {"name": "www.bottega.example", "type": "AAAA", "value": "2a01:4f8::20"},
        {"name": "bottega.example", "type": "A", "value": "157.90.1.20"},
        {"name": "bottega.example", "type": "AAAA", "value": "2a01:4f8::20"},
    ]


def test_the_check_tells_ok_missing_wrong_and_unknown():
    plan = dns_plan(["https://bottega.example"], {**SERVER, "ipv6": []})
    assert dns_check(plan, fake({("bottega.example", "A"): ["157.90.1.20"]}))["ok"] is True
    assert dns_check(plan, fake({}))["records"][0]["state"] == "missing"
    wrong = dns_check(plan, fake({("bottega.example", "A"): ["1.2.3.4"]}))
    assert wrong["records"][0]["state"] == "wrong" and wrong["ok"] is False
    half = fake(
        {
            ("bottega.example", "A", "1.1.1.1"): ["157.90.1.20"],
            ("bottega.example", "A", "8.8.8.8"): [],
        }
    )
    assert dns_check(plan, half)["records"][0]["state"] == "wrong"
    timeout = fake(
        {("bottega.example", "A", "8.8.8.8"): None, ("bottega.example", "A"): ["157.90.1.20"]}
    )
    assert dns_check(plan, timeout)["records"][0]["state"] == "unknown"


def test_the_site_plan_follows_its_server_and_address(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    grants = {"anna": {"*": ["read", "write", "create_site", "build", "publish", "servers"]}}
    service = SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy(grants),
        worker=worker,
        publisher=Publisher(versioned_bucket(), worker),
    )

    def run(operation, **arguments):
        return service.execute("anna", operation, **arguments)

    run("server_add", key="w", name="web-1", **SERVER)
    site = run("site_new", key="n", name="S")["site_id"]
    template = run(
        "template_add", site_id=site, key="t", name="L", engine="gramlot", python_source=LAYOUT
    )
    page = run("page_add", site_id=site, key="p", name="Home", template_id=template["template_id"])
    with pytest.raises(DomainError, match="public origin"):
        run("dns_plan", site_id=site)
    run(
        "page_seo_set",
        site_id=site,
        key="o",
        page_id=page["page_id"],
        fields={"origin": "https://bottega.example"},
    )
    with pytest.raises(DomainError, match="registered server"):
        run("dns_plan", site_id=site)
    run("site_server_set", site_id=site, key="s", server="web-1", alias=True)
    assert {r["name"] for r in run("dns_plan", site_id=site)} == {
        "bottega.example",
        "www.bottega.example",
    }

    service.dns_lookup = fake({
        ("bottega.example", "A"): ["157.90.1.20"], ("bottega.example", "AAAA"): ["2a01:4f8::20"],
        ("www.bottega.example", "A"): ["157.90.1.20"], ("www.bottega.example", "AAAA"): ["2a01:4f8::20"],
    })  # fmt: skip
    assert run("dns_check", site_id=site)["ok"] is True
