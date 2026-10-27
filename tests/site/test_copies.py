"""Copies in pages, use counts and Update (N2 Phase 4)."""

import pytest
from site_support import template_source

from kajenn_press.domain import DomainError
from kajenn_press.site.model import Site, value_digest
from kajenn_press.site.storage import WorkingCopy


def site_with_pages():
    site = Site.create("S")
    template = site.add_template("Landing", "gramlot", template_source("hero", "body"))
    footer = site.add_content("Footer", "html", "<p>© Genro</p>\n")
    welcome = site.add_content("Welcome", "html", "<p>Welcome</p>\n")
    unused = site.add_content("Old banner", "html", "<p>Old</p>\n")
    pages = [site.add_page(name, template) for name in ("Home", "About", "Contacts")]
    for page_id in pages:
        site.assign_content(page_id, "body", footer)
    site.assign_content(pages[0], "hero", welcome)
    return site, pages, {"footer": footer, "welcome": welcome, "unused": unused}


def test_use_counts_zero_one_and_many():
    site, _pages, ids = site_with_pages()
    assert site.use_count(ids["unused"]) == 0
    assert site.use_count(ids["welcome"]) == 1
    assert site.use_count(ids["footer"]) == 3


def test_copy_records_origin_and_is_independent():
    site, pages, ids = site_with_pages()
    path = next(p for page_id, p in site.uses(ids["welcome"]) if page_id == pages[0])
    copy = site.page(pages[0]).bag.get_node(path)
    assert copy.attr["slot"] == "hero"
    assert copy.attr["original_id"] == ids["welcome"]
    assert copy.attr["original_digest"] == value_digest("<p>Welcome</p>\n")
    site.node("contents", ids["welcome"]).value = "<p>Welcome back</p>\n"
    assert copy.value == "<p>Welcome</p>\n"


def test_assigning_an_occupied_slot_keeps_the_previous_copy_unplaced():
    site, pages, ids = site_with_pages()
    site.assign_content(pages[0], "hero", ids["unused"])
    page = site.page(pages[0])
    assert [n.attr["original_id"] for n in page.unplaced.nodes] == [ids["welcome"]]
    assert "slot" not in page.unplaced.nodes[0].attr
    assert site.use_count(ids["welcome"]) == 1


def test_update_plan_selects_outdated_copies_and_leaves_local_changes_unselected():
    site, pages, ids = site_with_pages()
    site.node("contents", ids["footer"]).value = "<p>© Genro 2026</p>\n"
    about_path = next(p for page_id, p in site.uses(ids["footer"]) if page_id == pages[1])
    site.page(pages[1]).bag.get_node(about_path).value = "<p>© Genro, about</p>\n"

    plan = {item.page_id: item for item in site.update_plan(ids["footer"])}

    assert [plan[p].selected for p in pages] == [True, False, True]
    assert plan[pages[1]].locally_changed is True
    assert plan[pages[0]].locally_changed is False
    assert "+<p>© Genro 2026</p>" in plan[pages[0]].difference
    assert "-<p>© Genro, about</p>" in plan[pages[1]].difference


def test_apply_replaces_only_selected_copies_and_is_idempotent():
    site, pages, ids = site_with_pages()
    site.node("contents", ids["footer"]).value = "<p>© Genro 2026</p>\n"
    about_path = next(p for page_id, p in site.uses(ids["footer"]) if page_id == pages[1])
    site.page(pages[1]).bag.get_node(about_path).value = "<p>© Genro, about</p>\n"
    selected = [(i.page_id, i.path) for i in site.update_plan(ids["footer"]) if i.selected]

    site.apply_update(ids["footer"], selected)
    after = site.bag.to_tytx(transport="json")
    site.apply_update(ids["footer"], selected)

    assert site.bag.to_tytx(transport="json") == after
    plan = {item.page_id: item for item in site.update_plan(ids["footer"])}
    assert [plan[p].up_to_date for p in pages] == [True, False, True]
    assert [plan[p].selected for p in pages] == [False, False, False]
    assert site.page(pages[1]).bag.get_node(about_path).value == "<p>© Genro, about</p>\n"


def test_assets_are_copied_and_counted():
    site, pages, _ids = site_with_pages()
    css = site.add_asset("site", "css", b"body{}", "text/css")
    site.add_page_asset(pages[0], css)
    site.add_page_asset(pages[2], css)
    site.node("assets", css).value = b"body{color:red}"

    plan = site.update_plan(css)

    assert site.use_count(css) == 2
    assert [i.selected for i in plan] == [True, True]
    assert plan[0].difference is None


def test_copies_survive_the_working_copy(tmp_path):
    site, _pages, ids = site_with_pages()
    WorkingCopy(tmp_path / "w").save(site)
    loaded = WorkingCopy(tmp_path / "w").load()
    assert loaded.use_count(ids["footer"]) == 3
    assert loaded.uses(ids["footer"]) == site.uses(ids["footer"])


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda s, p, i: s.assign_content(p[0], "aside", i["welcome"]), "no slot aside"),
        (lambda s, p, i: s.assign_content(p[0], "body", "missing"), "No content"),
        (lambda s, p, i: s.update_plan("missing"), "No original"),
        (lambda s, p, i: s.apply_update(i["welcome"], [(p[1], "slots.x")]), "No copy"),
    ],
)
def test_invalid_requests_are_refused(call, message):
    site, pages, ids = site_with_pages()
    with pytest.raises(DomainError, match=message):
        call(site, pages, ids)
