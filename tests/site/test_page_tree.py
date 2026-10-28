"""Pages tree and marks (N5 Phase 1)."""

import os

import pytest
from publication.storage_support import versioned_bucket
from site_support import template_source

from kajenn_press.domain import AccessPolicy, DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.model import Site
from kajenn_press.site.publish import Publisher
from kajenn_press.site.service import SiteService
from kajenn_press.site.store import SourceStore, pack, unpack

LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    doc.head().title("^page.title")
    doc.body().div(node_label="body", kpress_slot="body")
"""


def site_with_pages(*names):
    site = Site.create("S")
    template = site.add_template("T", "gramlot", template_source("body"))
    return site, [site.add_page(name, template) for name in names]


def names(items):
    return [
        (item["name"], names(item["children"])) if item["type"] == "folder" else item["name"]
        for item in items
    ]


def test_folders_and_moves_keep_positions_dense():
    site, (_home, team, history) = site_with_pages("Home", "Team", "History")
    about = site.add_folder("About")
    site.move(team, about)
    site.move(history, about, 0)
    site.move(about, None, 1)

    assert names(site.tree()) == ["Home", ("About", ["History", "Team"])]
    positions = sorted(n.attr["position"] for n in site.children(None))
    assert positions == [0, 1]
    assert names(unpack(pack(site)).tree()) == names(site.tree())


def test_a_folder_cannot_move_into_itself_or_a_descendant():
    site, _pages = site_with_pages("Home")
    outer = site.add_folder("Outer")
    inner = site.add_folder("Inner", outer)
    for target in (outer, inner):
        with pytest.raises(DomainError, match="into itself"):
            site.move(outer, target)


def test_moving_does_not_change_urls():
    site, (_home, team) = site_with_pages("Home", "Team")
    site.move(team, site.add_folder("About"))
    assert site.page_urls() == {"/": _home, "/team/": team}


def test_outdated_copies_are_reported():
    site, (home,) = site_with_pages("Home")
    content = site.add_content("Intro", "html", "<p>a</p>")
    site.assign_content(home, "body", content)
    assert site.outdated_copies(home) == []
    site.node("contents", content).value = "<p>b</p>"
    assert [o["original_id"] for o in site.outdated_copies(home)] == [content]


def test_site_read_returns_the_tree_and_the_marks(tmp_path):
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    grants = {"anna": {"*": ["read", "write", "create_site", "build", "publish"]}}
    service = SiteService(
        tmp_path / "s",
        SourceStore(versioned_bucket()),
        AccessPolicy(grants),
        worker=worker,
        publisher=Publisher(versioned_bucket(), worker),
    )

    def run(operation, **arguments):
        return service.execute("anna", operation, **arguments)

    site = run("site_new", key="n", name="S")["site_id"]
    template = run(
        "template_add",
        site_id=site,
        key="t",
        name="T",
        engine="gramlot",
        python_source=LAYOUT,
    )["template_id"]
    home = run("page_add", site_id=site, key="h", name="Home", template_id=template)["page_id"]
    folder = run("folder_add", site_id=site, key="f", name="About")["folder_id"]
    team = run("page_add", site_id=site, key="tm", name="Team", template_id=template)["page_id"]
    run("tree_move", site_id=site, key="m", item_id=team, parent=folder)
    content = run("content_add", site_id=site, key="c", name="C", format="html", text="<p>c</p>")[
        "content_id"
    ]
    run("slot_assign", site_id=site, key="s", page_id=home, slot="body", content_id=content)
    assert run("publish", site_id=site, key="p", selected=[home, team])["failed"] == []
    run("content_save", site_id=site, key="e", content_id=content, text="<p>new</p>")

    read = run("site_read", site_id=site)
    assert names(read["tree"]) == ["Home", ("About", ["Team"])]
    marks = {p["name"]: (p["changed"], p["outdated"], p["slot_names"]) for p in read["pages"]}
    assert marks == {"Home": (False, True, ["body"]), "Team": (False, False, ["body"])}
