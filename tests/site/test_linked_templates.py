"""Linked site templates and per-node conflicts with the Library (N2 Phase 5)."""

import pytest
from genro_bag import Bag

from kajenn_press.domain import DomainError
from kajenn_press.site.model import Library, Site, value_digest
from kajenn_press.site.storage import WorkingCopy


def layout():
    """html > body > header(nav) + main(hero, body slots) + footer."""
    source = Bag()
    source.set_item("html_0", Bag(), node_tag="html")
    source.set_item("html_0.body", Bag(), node_tag="body")
    body = "html_0.body"
    source.set_item(f"{body}.header", Bag(), node_tag="header", _attributes={"class": "top"})
    source.set_item(f"{body}.header.nav", "Menu", node_tag="nav")
    source.set_item(f"{body}.main", Bag(), node_tag="main")
    source.set_item(f"{body}.main.hero", None, node_tag="div", _attributes={"kpress_slot": "hero"})
    source.set_item(f"{body}.main.body", None, node_tag="div", _attributes={"kpress_slot": "body"})
    source.set_item(f"{body}.footer", "© Genro", node_tag="footer")
    return source


def linked_pair():
    library = Library.create("Library")
    generic = library.add_template("Generic", "gramlot", layout())
    site = Site.create("S")
    template = site.import_template(library, generic, linked=True)
    return library, generic, site, template


def library_source(library, generic):
    return library.node("templates", generic).value


def site_source(site, template):
    return site.node("templates", template).value


def test_independent_copy_does_not_follow_the_library():
    library = Library.create("Library")
    generic = library.add_template("Generic", "gramlot", layout())
    site = Site.create("S")
    template = site.import_template(library, generic, linked=False)
    assert site.node("templates", template).attr["linked"] is False
    with pytest.raises(DomainError, match="linked"):
        site.rebase_template(template, library)


def test_clean_rebase_keeps_site_changes_and_takes_library_changes():
    library, generic, site, template = linked_pair()
    site_source(site, template).set_item("html_0.body.footer", "© Kajenn Press", node_tag="footer")
    site_source(site, template).set_item(
        "html_0.body.main.aside", None, node_tag="aside", _attributes={"kpress_slot": "aside"}
    )
    library_source(library, generic).set_item("html_0.body.header.nav", "Main menu", node_tag="nav")

    assert site.rebase_template(template, library) == []

    merged = site_source(site, template)
    assert merged.get_item("html_0.body.header.nav") == "Main menu"
    assert merged.get_item("html_0.body.footer") == "© Kajenn Press"
    assert list(merged.get_item("html_0.body.main").keys()) == ["hero", "body", "aside"]
    attributes = site.node("templates", template).attr
    assert attributes["library_digest"] == value_digest(library_source(library, generic))
    assert site.rebase_template(template, library) == []


def test_a_node_changed_on_both_sides_is_a_conflict_and_nothing_changes():
    library, generic, site, template = linked_pair()
    site_source(site, template).set_item("html_0.body.footer", "© Site", node_tag="footer")
    library_source(library, generic).set_item("html_0.body.footer", "© Library", node_tag="footer")
    before = site_source(site, template).to_tytx(transport="json")

    (conflict,) = site.rebase_template(template, library)

    assert conflict.path == "html_0.body.footer"
    assert (conflict.base[1], conflict.site[1], conflict.library[1]) == (
        "© Genro",
        "© Site",
        "© Library",
    )
    assert site_source(site, template).to_tytx(transport="json") == before


def test_a_site_change_under_a_node_the_library_removed_is_a_conflict():
    library, generic, site, template = linked_pair()
    site_source(site, template).set_item("html_0.body.header.nav", "Site menu", node_tag="nav")
    library_source(library, generic).get_item("html_0.body").pop("header")

    conflicts = site.rebase_template(template, library)

    assert [c.path for c in conflicts] == ["html_0.body.header"]
    assert conflicts[0].library is None


def test_a_renamed_label_conflicts_with_site_changes_under_the_old_label():
    library, generic, site, template = linked_pair()
    site_source(site, template).set_item(
        "html_0.body.main.hero",
        "x",
        node_tag="div",
        _attributes={"kpress_slot": "hero", "class": "big"},
    )
    body = library_source(library, generic).get_item("html_0.body")
    main = body.pop("main")
    body.set_item("content", main, node_tag="main")

    conflicts = site.rebase_template(template, library)

    assert [c.path for c in conflicts] == ["html_0.body.main"]


def test_resolutions_apply_per_node_and_to_the_subtree():
    library, generic, site, template = linked_pair()
    site_source(site, template).set_item("html_0.body.footer", "© Site", node_tag="footer")
    site_source(site, template).set_item("html_0.body.header.nav", "Site menu", node_tag="nav")
    library_source(library, generic).set_item("html_0.body.footer", "© Library", node_tag="footer")
    library_source(library, generic).get_item("html_0.body").pop("header")

    conflicts = site.rebase_template(
        template, library, {"html_0.body.footer": "library", "html_0.body.header": "site"}
    )

    assert conflicts == []
    merged = site_source(site, template)
    assert merged.get_item("html_0.body.footer") == "© Library"
    assert merged.get_item("html_0.body.header.nav") == "Site menu"


def test_linked_template_and_its_base_survive_the_working_copy(tmp_path):
    library, generic, site, template = linked_pair()
    site_source(site, template).set_item("html_0.body.footer", "© Site", node_tag="footer")
    WorkingCopy(tmp_path / "w").save(site)
    loaded = WorkingCopy(tmp_path / "w").load()
    library_source(library, generic).set_item("html_0.body.header.nav", "Main menu", node_tag="nav")

    assert loaded.rebase_template(template, library) == []
    assert site_source(loaded, template).get_item("html_0.body.footer") == "© Site"


def test_invalid_resolution_and_library_pages_are_refused():
    library, _generic, site, template = linked_pair()
    with pytest.raises(DomainError, match="keeps site or takes library"):
        site.rebase_template(template, library, {"html_0.body.footer": "mine"})
    with pytest.raises(DomainError, match="no pages"):
        library.add_page("P", "x")
