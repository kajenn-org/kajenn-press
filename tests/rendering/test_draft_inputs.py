"""Draft render inputs: unsaved sources and data: URLs, without writing the catalog."""

import base64

import pytest
from rendering.support import make_page
from services.scenarios import create_service

from kajenn_press.domain import DomainError
from kajenn_press.rendering.contract import CONTRACT
from kajenn_press.rendering.inputs import RenderInputs

PROFILE = {"contract": CONTRACT}


def draft_service(tmp_path):
    service = create_service(tmp_path)
    service.policy.grants["admin"]["*"] += ["build"]
    return service, RenderInputs(service.catalog, service.policy)


def test_draft_sources_replace_saved_ones_and_leave_the_catalog_unchanged(tmp_path):
    service, inputs = draft_service(tmp_path)
    try:
        page = make_page(service)
        generation = service.catalog.read().generation
        frozen = inputs.freeze(
            "admin",
            page["variant"]["record_id"],
            PROFILE,
            block_sources={"intro": "<p>Unsaved intro</p>"},
            resource_sources={
                page["template"]["revision_id"]: "def build(source, data):\n    pass\n",
                page["css"]["revision_id"]: "p { color: red; }",
            },
            data_urls=True,
        )
        data = frozen.unpack()
        assert data["blocks"]["intro"]["source"] == "<p>Unsaved intro</p>"
        # Blocks without a draft keep their saved source.
        assert data["blocks"]["body"]["source"].startswith("# Testo")
        template = data["references"][page["template"]["revision_id"]]
        assert base64.b64decode(template["sources"]["source"]).startswith(b"def build")
        assert template["draft"] is True
        assert "draft" not in data["references"][page["media"]["revision_id"]]
        resources = data["data"]["resources"]
        css_url = resources[page["css"]["revision_id"]]["url"]
        assert css_url == "data:text/css;base64," + base64.b64encode(b"p { color: red; }").decode(
            "ascii"
        )
        assert resources[page["media"]["revision_id"]]["url"].startswith("data:image/png;base64,")
        assert resources[page["javascript"]["revision_id"]]["url"].startswith(
            "data:text/javascript;base64,"
        )
        assert service.catalog.read().generation == generation
        saved = inputs.freeze("admin", page["variant"]["record_id"], PROFILE).unpack()
        assert saved["data"]["resources"][page["css"]["revision_id"]]["url"].startswith(
            "/_resources/"
        )
        assert not any("draft" in reference for reference in saved["references"].values())
    finally:
        service.catalog.close()


def test_draft_rejects_undeclared_blocks_foreign_and_binary_resources(tmp_path):
    service, inputs = draft_service(tmp_path)
    try:
        page = make_page(service)
        other = make_page(service)
        variant = page["variant"]["record_id"]
        with pytest.raises(DomainError, match="Undeclared block"):
            inputs.freeze("admin", variant, PROFILE, block_sources={"sidebar": "<p>x</p>"})
        with pytest.raises(DomainError, match="outside the page closure"):
            inputs.freeze(
                "admin",
                variant,
                PROFILE,
                resource_sources={other["template"]["revision_id"]: "def build(s, d): pass"},
            )
        with pytest.raises(DomainError, match="Only template, CSS and JavaScript"):
            inputs.freeze(
                "admin", variant, PROFILE, resource_sources={page["media"]["revision_id"]: "x"}
            )
    finally:
        service.catalog.close()


def test_drafting_a_resource_requires_write_in_its_scope(tmp_path):
    service, inputs = draft_service(tmp_path)
    try:
        page = make_page(service)
        variant = page["variant"]["record_id"]
        frozen = inputs.freeze(
            "admin",
            variant,
            PROFILE,
            resource_sources={page["template"]["revision_id"]: "def build(s, d): pass"},
        )
        service.policy.grants["admin"]["*"].remove("write")
        # Saved sources still render; drafted ones need write when frozen and when rendered.
        inputs.freeze("admin", variant, PROFILE, block_sources={"intro": "<p>ok</p>"})
        with pytest.raises(DomainError, match="Missing write"):
            inputs.freeze(
                "admin",
                variant,
                PROFILE,
                resource_sources={page["template"]["revision_id"]: "def build(s, d): pass"},
            )
        with pytest.raises(DomainError, match="Missing write"):
            inputs.authorize("admin", frozen)
    finally:
        service.catalog.close()
