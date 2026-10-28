"""Export, import and starting sites (N3 Phase 6)."""

import base64
import os

import pytest
from publication.storage_support import versioned_bucket

from kajenn_press.catalog.errors import IntegrityError
from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    doc.body().div(node_label="body", kpress_slot="body")
"""
GRANTS = {
    "anna": {"*": ["read", "write", "create_site", "build"]},
    "bruno": {"*": ["read", "write"]},
}


@pytest.fixture
def service(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    return SiteService(
        tmp_path / "s", SourceStore(versioned_bucket()), AccessPolicy(GRANTS), worker=worker
    )


def run(service, identity, operation, **arguments):
    return service.execute(identity, operation, **arguments)


def saved_site(service):
    site_id = run(service, "anna", "site_new", key="n", name="Original")["site_id"]
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
    page = run(
        service, "anna", "page_add", site_id=site_id, key="p", name="Home", template_id=template
    )["page_id"]
    content = run(
        service,
        "anna",
        "content_add",
        site_id=site_id,
        key="c",
        name="Body",
        format="html",
        text="<p>Body</p>",
    )["content_id"]
    run(
        service,
        "anna",
        "slot_assign",
        site_id=site_id,
        key="a",
        page_id=page,
        slot="body",
        content_id=content,
    )
    run(service, "anna", "site_save", site_id=site_id)
    return site_id


def shape(read):
    return (
        [t["name"] for t in read["templates"]],
        [(c["name"], c["uses"]) for c in read["contents"]],
        [(p["name"], sorted(p["slots"])) for p in read["pages"]],
    )


def test_export_then_import_gives_a_new_site_with_the_same_content(service):
    original = saved_site(service)
    exported = run(service, "anna", "site_export", site_id=original)

    imported = run(
        service, "anna", "site_import", key="i", data_base64=exported["data_base64"], name="Copy"
    )["site_id"]

    assert imported != original
    copy, source = (run(service, "anna", "site_read", site_id=s) for s in (imported, original))
    assert copy["name"] == "Copy"
    assert shape(copy) == shape(source)
    operations = [n.attr["operation"] for n in service.store.open(imported).audit.nodes]
    assert operations[-1] == "site_import"


def test_a_new_site_from_a_starting_site(service):
    original = saved_site(service)
    starter = run(service, "anna", "starter_save", key="st", site_id=original, name="Landing")[
        "starter_id"
    ]
    assert run(service, "anna", "starters_list") == [{"starter_id": starter, "name": "Landing"}]

    started = run(service, "anna", "site_new", key="n2", name="Acme", starter_id=starter)

    read = run(service, "anna", "site_read", site_id=started["site_id"])
    assert read["name"] == "Acme"
    assert shape(read) == shape(run(service, "anna", "site_read", site_id=original))


def test_retried_import_creates_one_site(service):
    data = run(service, "anna", "site_export", site_id=saved_site(service))["data_base64"]
    first = run(service, "anna", "site_import", key="same", data_base64=data)
    again = run(service, "anna", "site_import", key="same", data_base64=data)
    assert first == again


def test_invalid_imports_and_missing_grants_are_refused(service):
    with pytest.raises(DomainError, match="base64"):
        run(service, "anna", "site_import", key="x", data_base64="***")
    with pytest.raises(IntegrityError, match="zip"):
        run(service, "anna", "site_import", key="y", data_base64=base64.b64encode(b"x").decode())
    with pytest.raises(DomainError, match="create_site"):
        run(service, "bruno", "site_import", key="z", data_base64="")
    with pytest.raises(DomainError, match="No starting site"):
        run(service, "anna", "site_new", key="w", name="W", starter_id="missing")
