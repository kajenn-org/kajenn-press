"""SEO checks (N6 Phase 4)."""

from site_support import template_source

from kajenn_press.site.model import Site
from kajenn_press.site.seo import seo_check, set_image_alt, set_page_seo


def codes(site, page_id=None):
    return sorted((p["page_id"], p["code"]) for p in seo_check(site, page_id))


def described_site(*names, source=None):
    site = Site.create("S")
    template = site.add_template("T", "gramlot", source or template_source("body"))
    pages = [site.add_page(name, template) for name in names]
    set_page_seo(site, pages[0], {"origin": "https://kajenn.org", "description": "Text"})
    return site, pages


def test_a_complete_site_has_no_problem():
    site, (_home, team) = described_site("Home", "Team")
    set_page_seo(site, team, {"description": "Team text"})
    assert codes(site) == []


def test_missing_origin_and_description():
    site, (home, team) = described_site("Home", "Team")
    set_page_seo(site, home, {"origin": "", "description": ""})
    assert codes(site) == sorted(
        [(home, "missing_description"), (home, "missing_origin"), (team, "missing_description")]
    )
    set_page_seo(site, home, {"origin": "https://kajenn.org", "description": "Root"})
    assert codes(site) == []


def test_duplicate_titles_among_indexable_pages_only():
    site, (_home, team, about) = described_site("Home", "Team", "About")
    set_page_seo(site, team, {"title": "Same"})
    set_page_seo(site, about, {"title": "Same"})
    assert codes(site) == sorted([(about, "duplicate_title"), (team, "duplicate_title")])
    set_page_seo(site, about, {"robots": "noindex, follow"})
    assert codes(site) == []


def test_images_without_alt():
    site, (home,) = described_site("Home")
    content = site.add_content("Intro", "html", '<img src="/a.png"><img src="/b.png" alt="">')
    site.assign_content(home, "body", content)
    assert codes(site) == [(home, "missing_alt")]
    image = seo_check(site)[0]
    assert "/a.png" in image["message"] and "slot body" in image["message"]
    set_image_alt(site, home, "slots." + site.page(home).slots.nodes[0].label + "#html0", "A")
    assert codes(site) == []


def test_broken_internal_links():
    site, (home, team) = described_site("Home", "Team")
    site.set_page_url(team, "/team/")
    site.set_page_url(team, "/people/")
    text = (
        '<a href="/people/">ok</a><a href="/team/">redirect</a><a href="/people">slash</a>'
        '<a href="https://example.org/x">external</a><a href="#top">fragment</a>'
        '<a href="/_assets/a.png">asset</a><a href="/sitemap.xml">map</a>'
        '<a href="/missing/?q=1">broken</a>'
    )
    site.assign_content(home, "body", site.add_content("Links", "html", text))
    problems = seo_check(site, home)
    assert [(p["code"], p["message"]) for p in problems] == [
        ("broken_link", "The link /missing/?q=1 in the slot body leads nowhere")
    ]


def test_markdown_and_relative_links():
    site, (_home, team) = described_site("Home", "Team")
    site.set_page_url(team, "/about/team/")
    markdown = "[Team](/about/team/) [Rel](../nowhere/) ![pic](/p.png)"
    site.assign_content(team, "body", site.add_content("M", "markdown", markdown))
    assert codes(site, team) == [(team, "broken_link")]


def test_iframe_slot_without_fallback_on_indexable_pages():
    source = template_source("body")
    source.set_item(
        "html_0.body.app",
        None,
        node_tag="div",
        _attributes={"kpress_slot": "app", "kpress_iframe": "/app/"},
    )
    site, (home,) = described_site("Home", source=source)
    assert codes(site) == [(home, "iframe_without_fallback")]
    site.assign_content(home, "app", site.add_content("Fallback", "html", "<p>App</p>"))
    assert codes(site) == []
