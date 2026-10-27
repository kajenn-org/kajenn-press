"""Unplaced contents, template updates in pages and template switch (N2 Phase 6)."""

import pytest
from site_support import template_source

from kajenn_press.domain import DomainError
from kajenn_press.site.model import Site
from kajenn_press.site.storage import WorkingCopy


def site_with_page():
    site = Site.create("S")
    landing = site.add_template("Landing", "gramlot", template_source("hero", "body", "aside"))
    article = site.add_template("Article", "gramlot", template_source("hero", "main"))
    contents = {
        name: site.add_content(name, "html", f"<p>{name}</p>") for name in ("Hero", "Body", "Aside")
    }
    page = site.add_page("Home", landing)
    for slot, name in (("hero", "Hero"), ("body", "Body"), ("aside", "Aside")):
        site.assign_content(page, slot, contents[name])
    return site, page, landing, article, contents


def placed(site, page):
    return {n.attr["slot"]: n.attr["name"] for n in site.page(page).slots.nodes}


def unplaced(site, page):
    return sorted(n.attr["name"] for n in site.page(page).unplaced.nodes)


def test_a_template_update_that_removes_a_slot_keeps_its_content_unplaced():
    site, page, landing, *_ = site_with_page()
    site.node("templates", landing).value.get_item("html_0.body").pop("aside")

    plan = site.update_plan(landing)
    site.apply_update(landing, [(i.page_id, i.path) for i in plan if i.selected])

    assert placed(site, page) == {"hero": "Hero", "body": "Body"}
    assert unplaced(site, page) == ["Aside"]
    assert site.page_check(page) == {
        "empty_slots": [],
        "unplaced": [n.label for n in site.page(page).unplaced.nodes],
    }


def test_a_page_with_a_changed_template_copy_is_not_selected():
    site, page, landing, *_ = site_with_page()
    site.page(page).template.value.set_item("html_0.head.title", "Mine", node_tag="title")
    site.node("templates", landing).value.get_item("html_0.body").pop("aside")

    (item,) = site.update_plan(landing)

    assert (item.locally_changed, item.selected) == (True, False)


def test_switch_plan_matches_by_name():
    site, page, _landing, article, _contents = site_with_page()
    assert site.switch_plan(page, article) == {"hero": "hero", "body": None, "aside": None}


def test_switch_follows_the_corrected_mapping_and_unplaces_the_rest():
    site, page, _landing, article, _contents = site_with_page()

    site.switch_template(page, article, {"hero": "hero", "body": "main", "aside": None})

    assert site.page(page).template.attr["original_id"] == article
    assert placed(site, page) == {"hero": "Hero", "main": "Body"}
    assert unplaced(site, page) == ["Aside"]
    assert site.page_check(page)["empty_slots"] == []


def test_unplaced_content_can_be_placed_in_a_free_slot():
    site, page, _landing, article, _contents = site_with_page()
    site.switch_template(page, article, {"hero": "hero", "body": None, "aside": None})
    assert site.page_check(page)["empty_slots"] == ["main"]
    key = next(n.label for n in site.page(page).unplaced.nodes if n.attr["name"] == "Body")

    site.place_unplaced(page, key, "main")

    assert placed(site, page) == {"hero": "Hero", "main": "Body"}
    assert unplaced(site, page) == ["Aside"]


def test_every_content_copy_survives_and_is_counted(tmp_path):
    site, page, _landing, article, contents = site_with_page()
    site.switch_template(page, article, {"hero": None, "body": None, "aside": None})
    WorkingCopy(tmp_path / "w").save(site)
    loaded = WorkingCopy(tmp_path / "w").load()
    assert [loaded.use_count(contents[n]) for n in ("Hero", "Body", "Aside")] == [1, 1, 1]
    assert loaded.page_check(page)["empty_slots"] == ["hero", "main"]


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ({"hero": "footer"}, "lacks"),
        ({"hero": "main", "body": "main"}, "same slot"),
    ],
)
def test_invalid_mappings_are_refused(mapping, message):
    site, page, _landing, article, _contents = site_with_page()
    with pytest.raises(DomainError, match=message):
        site.switch_template(page, article, mapping)


def test_placing_into_an_occupied_or_missing_slot_is_refused():
    site, page, _landing, article, _contents = site_with_page()
    site.switch_template(page, article, {"hero": "hero", "body": None, "aside": None})
    key = next(n.label for n in site.page(page).unplaced.nodes)
    with pytest.raises(DomainError, match="already holds"):
        site.place_unplaced(page, key, "hero")
    with pytest.raises(DomainError, match="no slot"):
        site.place_unplaced(page, key, "footer")
