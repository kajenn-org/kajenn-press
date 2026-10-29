"""Languages and translated texts in the site model (N9 Phase 1)."""

import json

import pytest
from site_support import template_source

from kajenn_press.domain import DomainError
from kajenn_press.site.languages import (
    confirm_translation,
    set_languages,
    set_site_text,
    set_translation,
    site_languages,
    translation_states,
)
from kajenn_press.site.model import Site
from kajenn_press.site.storage import site_envelope, site_from_envelope


def two_language_site():
    site = Site.create("Bottega")
    template = site.add_template("T", "gramlot", template_source("body"))
    home = site.add_page("Home", template)
    content = site.add_content("Intro", "html", "<p>Mobili fatti a mano.</p>")
    set_languages(site, ["it", "en"])
    return site, home, content


def test_an_existing_site_has_one_language_from_the_root_template_or_english():
    site = Site.create("S")
    assert site_languages(site) == ["en"]
    source = template_source("body")
    source.get_node("html_0").attr["lang"] = "it"
    site.add_page("Home", site.add_template("T", "gramlot", source))
    assert site_languages(site) == ["it"]


@pytest.mark.parametrize(
    "languages",
    [[], ["it", "it"], ["IT"], ["italian"], ["it", "en", "de", "fr", "es", "pt", "nl", "pl", "sv"]],
)
def test_invalid_language_lists_are_refused(languages):
    site = Site.create("S")
    with pytest.raises(DomainError):
        set_languages(site, languages)


def test_translation_states_follow_the_main_text_and_review():
    site, _home, content = two_language_site()
    key = "content_" + content
    assert translation_states(site, key) == {"en": {"state": "missing", "text": None}}

    set_translation(site, key, "en", "<p>Hand-made furniture.</p>", proposed=True)
    assert translation_states(site, key)["en"]["state"] == "to_review"
    confirm_translation(site, key, "en")
    assert translation_states(site, key)["en"] == {
        "state": "done",
        "text": "<p>Hand-made furniture.</p>",
    }

    site.node("contents", content).value = "<p>Mobili fatti a mano dal 1962.</p>"
    assert translation_states(site, key)["en"]["state"] == "to_update"
    with pytest.raises(DomainError, match="other languages"):
        set_translation(site, key, "it", "x")
    with pytest.raises(DomainError, match="other languages"):
        set_translation(site, key, "de", "x")


def test_copies_carry_translations_and_update_brings_new_ones():
    site, home, content = two_language_site()
    key = "content_" + content
    set_translation(site, key, "en", "<p>Hand-made.</p>")
    copy = site.assign_content(home, "body", content)
    page = site.page(home)
    assert page.bag.get_item("translations").get_item(copy).get_item("en") == "<p>Hand-made.</p>"
    assert site.outdated_copies(home) == []

    set_translation(site, key, "en", "<p>Hand-made furniture.</p>")
    assert site.outdated_copies(home) == [{"path": "slots." + copy, "original_id": content}]
    (item,) = site.update_plan(content)
    assert item.selected and not item.up_to_date and not item.locally_changed
    site.apply_update(content, [(home, "slots." + copy)])
    assert (
        page.bag.get_item("translations").get_item(copy).get_item("en")
        == "<p>Hand-made furniture.</p>"
    )
    assert site.outdated_copies(home) == []


def test_site_texts_have_a_main_text_and_translations():
    site, _home, _content = two_language_site()
    set_site_text(site, "menu_home", "Home")
    set_site_text(site, "menu_home", "Home page", language="en")
    assert translation_states(site, "text_menu_home")["en"]["text"] == "Home page"
    with pytest.raises(DomainError):
        set_site_text(site, "Menu Home", "x")
    with pytest.raises(DomainError, match="No site text"):
        set_site_text(site, "footer", "x", language="en")


def test_main_language_is_fixed_once_translated_and_removing_a_language_drops_it():
    site, home, content = two_language_site()
    set_translation(site, "content_" + content, "en", "<p>EN</p>")
    copy = site.assign_content(home, "body", content)
    with pytest.raises(DomainError, match="main language"):
        set_languages(site, ["en", "it"])
    set_languages(site, ["it", "de"])
    assert translation_states(site, "content_" + content) == {
        "de": {"state": "missing", "text": None}
    }
    assert len(site.page(home).bag.get_item("translations").get_item(copy)) == 0


def test_sources_saved_before_n9_get_the_new_sections():
    site, home, _content = two_language_site()
    for section in ("texts", "translations"):
        site.bag.pop(section)
    site.page(home).bag.pop("translations")
    loaded = site_from_envelope(json.loads(json.dumps(site_envelope(site))))
    assert len(loaded.section("translations")) == 0
    assert len(loaded.page(home).bag.get_item("translations")) == 0
