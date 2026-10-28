"""Site operations through the shared service (N3 Phase 5)."""

import base64
import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.service import OPERATIONS, SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    body = doc.body()
    body.div(node_label="hero", kpress_slot="hero")
    body.div(node_label="body", kpress_slot="body")
"""

GRANTS = {
    "anna": {"*": ["read", "write", "create_site", "build"]},
    "bruno": {"*": ["read", "write", "build"]},
    "carla": {"*": ["read"]},
}


@pytest.fixture
def service(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    return SiteService(
        tmp_path / "sites", SourceStore(versioned_bucket()), AccessPolicy(GRANTS), worker=worker
    )


def run(service, identity, operation, **arguments):
    return service.execute(identity, operation, **arguments)


def build_site(service):
    site_id = run(service, "anna", "site_new", key="new", name="Kajenn Press")["site_id"]
    template = run(
        service,
        "anna",
        "template_add",
        site_id=site_id,
        key="t",
        name="Layout",
        engine="gramlot",
        python_source=LAYOUT,
    )["template_id"]
    pages = [
        run(
            service,
            "anna",
            "page_add",
            site_id=site_id,
            key=f"p{i}",
            name=name,
            template_id=template,
        )["page_id"]
        for i, name in enumerate(("Home", "About"))
    ]
    footer = run(
        service,
        "anna",
        "content_add",
        site_id=site_id,
        key="c1",
        name="Footer",
        format="html",
        text="<p>© Genro</p>",
    )["content_id"]
    for i, page in enumerate(pages):
        run(
            service,
            "anna",
            "slot_assign",
            site_id=site_id,
            key=f"s{i}",
            page_id=page,
            slot="body",
            content_id=footer,
        )
    return site_id, template, pages, footer


def test_a_full_cycle_creates_fills_saves_restores_and_renders(service):
    site_id, _template, pages, footer = build_site(service)
    first = run(service, "anna", "site_save", site_id=site_id)["version_id"]
    run(
        service,
        "anna",
        "content_save",
        site_id=site_id,
        key="e1",
        content_id=footer,
        text="<p>© Genro 2026</p>",
    )
    run(service, "anna", "site_save", site_id=site_id)

    read = run(service, "anna", "site_read", site_id=site_id)
    assert [c["uses"] for c in read["contents"]] == [2]
    assert read["holder"] == "anna"
    plan = run(service, "anna", "copies_update_plan", site_id=site_id, original_id=footer)
    assert [item["selected"] for item in plan] == [True, True]

    run(service, "anna", "site_restore", site_id=site_id, version_id=first)
    versions = run(service, "anna", "site_versions", site_id=site_id)
    assert len(versions) == 4

    rendered = run(service, "anna", "page_render", site_id=site_id, page_id=pages[0])
    assert rendered["status"] == "succeeded", rendered
    assert "<p>© Genro</p>" in rendered["html"]
    assert run(service, "anna", "page_check", site_id=site_id, page_id=pages[0]) == {
        "empty_slots": ["hero"],
        "unplaced": [],
    }


def test_a_retried_change_applies_once(service):
    site_id, *_ = build_site(service)
    for _ in range(2):
        run(
            service,
            "anna",
            "content_add",
            site_id=site_id,
            key="dup",
            name="X",
            format="html",
            text="<p>x</p>",
        )
    names = [c["name"] for c in run(service, "anna", "site_read", site_id=site_id)["contents"]]
    assert names == ["Footer", "X"]


def test_changes_need_the_lock_and_grants(service):
    site_id, *_ = build_site(service)
    with pytest.raises(DomainError, match="edited by anna"):
        run(
            service,
            "bruno",
            "content_add",
            site_id=site_id,
            key="b",
            name="B",
            format="html",
            text="b",
        )
    with pytest.raises(DomainError, match="Missing write"):
        run(service, "carla", "site_open", site_id=site_id)
    with pytest.raises(DomainError, match="Missing create_site"):
        run(service, "bruno", "site_new", key="n", name="N")
    assert run(service, "carla", "site_read", site_id=site_id)["name"] == "Kajenn Press"


def test_others_read_the_saved_version_and_take_with_force(service):
    site_id, *_ = build_site(service)
    run(service, "anna", "site_save", site_id=site_id)
    run(
        service,
        "anna",
        "content_add",
        site_id=site_id,
        key="u",
        name="Unsaved",
        format="html",
        text="<p>u</p>",
    )

    assert len(run(service, "bruno", "site_read", site_id=site_id)["contents"]) == 1
    assert run(service, "bruno", "site_open", site_id=site_id, force=True) == {
        "holder": "bruno",
        "taken_from": "anna",
    }
    assert len(run(service, "bruno", "site_read", site_id=site_id)["contents"]) == 1


def test_assets_and_the_audit_log(service):
    site_id, _template, pages, _footer = build_site(service)
    asset = run(
        service,
        "anna",
        "asset_add",
        site_id=site_id,
        key="a",
        name="logo",
        kind="media",
        data_base64=base64.b64encode(b"\x89PNG").decode(),
        mime_type="image/png",
    )["asset_id"]
    run(
        service,
        "anna",
        "page_asset_add",
        site_id=site_id,
        key="pa",
        page_id=pages[0],
        asset_id=asset,
    )
    run(service, "anna", "site_save", site_id=site_id)

    site = service.store.open(site_id)
    operations = [n.attr["operation"] for n in site.audit.nodes]
    assert operations[0] == "site_new"
    assert operations[-3:] == ["asset_add", "page_asset_add", "site_save"]
    assert {n.attr["identity"] for n in site.audit.nodes} == {"anna"}


def test_invalid_input_is_a_domain_error(service):
    site_id, *_ = build_site(service)
    with pytest.raises(DomainError, match="either source or python_source"):
        run(service, "anna", "template_add", site_id=site_id, key="x", name="T", engine="gramlot")
    with pytest.raises(DomainError, match="base64"):
        run(
            service,
            "anna",
            "asset_add",
            site_id=site_id,
            key="y",
            name="a",
            kind="media",
            data_base64="***",
            mime_type="image/png",
        )
    with pytest.raises(DomainError, match="Unknown site operation"):
        run(service, "anna", "site_delete", site_id=site_id)
    with pytest.raises(DomainError, match="unexpected keyword"):
        run(service, "anna", "site_read", site_id=site_id, extra=1)


def test_operation_names_do_not_collide_with_the_editorial_ones():
    from kajenn_press.domain import OPERATIONS as EDITORIAL
    from kajenn_press.publication.service import OPERATIONS as PUBLICATION

    assert not OPERATIONS & (EDITORIAL | PUBLICATION | {"render_preview", "render_draft"})
