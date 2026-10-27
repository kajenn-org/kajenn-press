"""Site and page Bags saved to and loaded from the local working copy (N2 Phase 2)."""

import json

import pytest
from genro_bag import Bag
from site_support import template_source

from kajenn_press.catalog.errors import IntegrityError
from kajenn_press.catalog.filesystem import encode
from kajenn_press.domain import DomainError
from kajenn_press.site.model import Site, value_digest
from kajenn_press.site.storage import SITE_FILE, WorkingCopy

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
    "0000000b4944415478da63fcff1f0003030200efa3459900000000"
)


def sample_site():
    site = Site.create("Kajenn Press")
    landing = site.add_template("Landing", "gramlot", template_source("hero", "body"))
    article = site.add_template("Article", "htmlbuilder", template_source("body"))
    site.add_content("Welcome", "html", "<p>Caffè &amp; tè</p>\r\n")
    site.add_content("Notes", "markdown", "# Notes\n\n**bold**\n")
    site.add_asset("pixel", "media", PNG, "image/png")
    site.add_asset("site", "css", b"body { color: #222 }\n", "text/css")
    home = site.add_page("Home", landing)
    about = site.add_page("About", article)
    return site, landing, home, about


def test_site_survives_save_and_load_byte_for_byte(tmp_path):
    site, _landing, home, _about = sample_site()
    WorkingCopy(tmp_path / "site").save(site)

    loaded = WorkingCopy(tmp_path / "site").load()

    assert loaded.bag.to_tytx(transport="json") == site.bag.to_tytx(transport="json")
    assert (loaded.site_id, loaded.name) == (site.site_id, "Kajenn Press")
    assert [n.attr["name"] for n in loaded.section("pages").nodes] == ["Home", "About"]
    media = next(n for n in loaded.section("assets").nodes if n.attr["kind"] == "media")
    assert media.value == PNG
    welcome = next(n for n in loaded.section("contents").nodes if n.attr["name"] == "Welcome")
    assert welcome.value == "<p>Caffè &amp; tè</p>\r\n"
    slot = loaded.page(home).template.value.get_node("html_0.body.hero")
    assert (slot.node_tag, slot.attr) == ("div", {"kpress_slot": "hero"})


def test_page_holds_a_copy_of_its_template_with_its_origin():
    site, landing, home, _about = sample_site()
    page = site.page(home)
    original = site.node("templates", landing)

    assert page.template.attr["original_id"] == landing
    assert page.template.attr["original_digest"] == value_digest(original.value)
    assert page.template.attr["engine"] == "gramlot"
    original.value.set_item("html_0.body.extra", None, node_tag="div")
    assert page.template.value.get_node("html_0.body.extra") is None
    assert len(page.slots) == len(page.unplaced) == len(page.assets) == 0


def test_save_replaces_the_previous_copy(tmp_path):
    site, *_ = sample_site()
    copy = WorkingCopy(tmp_path / "site")
    copy.save(site)
    site.add_content("Later", "html", "<p>later</p>")
    copy.save(site)

    names = [n.attr["name"] for n in copy.load().section("contents").nodes]
    assert names == ["Welcome", "Notes", "Later"]
    assert sorted(p.name for p in (tmp_path / "site" / "staging").iterdir()) == []


def test_altered_file_fails_closed(tmp_path):
    site, *_ = sample_site()
    copy = WorkingCopy(tmp_path / "site")
    copy.save(site)
    path = tmp_path / "site" / SITE_FILE
    envelope = json.loads(path.read_bytes())
    envelope["site"] = envelope["site"].replace("Kajenn Press", "Kajenn Prezz")
    path.write_bytes(encode(envelope))

    with pytest.raises(IntegrityError, match="integrity"):
        copy.load()


def test_missing_section_fails_closed(tmp_path):
    site, *_ = sample_site()
    site.bag.del_item("assets")
    copy = WorkingCopy(tmp_path / "site")
    copy.save(site)

    with pytest.raises(IntegrityError, match="assets"):
        copy.load()


def test_missing_file_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        WorkingCopy(tmp_path / "empty").load()


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda s: s.add_template("T", "jinja", Bag()), "engine"),
        (lambda s: s.add_template("T", "gramlot", "<html/>"), "Bag"),
        (lambda s: s.add_content("C", "rst", "text"), "format"),
        (lambda s: s.add_asset("A", "media", "text", "image/png"), "bytes"),
        (lambda s: s.add_asset("A", "font", b"x", "font/woff2"), "kind"),
        (lambda s: s.add_page("P", "missing"), "No template"),
        (lambda s: s.add_content(" ", "html", "x"), "name"),
    ],
)
def test_invalid_input_is_refused(call, message):
    with pytest.raises(DomainError, match=message):
        call(Site.create("S"))
