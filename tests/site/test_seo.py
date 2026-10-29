"""SEO in the site model (N6 Phase 1)."""

import json
import os

import pytest
from site_support import template_source

from kajenn_press.domain import DomainError
from kajenn_press.rendering.process import RenderWorker
from kajenn_press.site.model import Site
from kajenn_press.site.published import page_fingerprint
from kajenn_press.site.render import page_request
from kajenn_press.site.seo import effective_seo, page_images, set_image_alt, set_page_seo
from kajenn_press.site.storage import site_envelope, site_from_envelope


def site_with_pages(*names):
    site = Site.create("Kajenn")
    template = site.add_template("T", "gramlot", template_source("body"))
    return site, [site.add_page(name, template) for name in names]


def test_an_empty_field_takes_the_root_value_never_the_parent():
    site, (home, about, team) = site_with_pages("Home", "About", "Team")
    set_page_seo(site, home, {"description": "Root text", "robots": "index, nofollow"})
    set_page_seo(site, about, {"description": "About text", "robots": "noindex, follow"})
    folder = site.add_folder("About")
    site.move(team, folder)

    before = effective_seo(site, team)
    assert before["description"] == "Root text"
    assert before["robots"] == "index, nofollow"
    assert before["title"] == "Team"
    assert before["social_title"] == "Team"
    site.move(team, None)
    assert effective_seo(site, team) == before


def test_origin_gives_the_canonical_and_organisation_gives_root_json_ld():
    site, (home, team) = site_with_pages("Home", "Team")
    set_page_seo(site, home, {"origin": "https://kajenn.org/", "organisation": "Softwell"})

    assert (
        effective_seo(site, team)["canonical"]
        == "https://kajenn.org" + site.node("pages", team).attr["url"]
    )
    assert json.loads(effective_seo(site, home)["json_ld"]) == {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Softwell",
        "url": "https://kajenn.org/",
    }
    assert effective_seo(site, team)["json_ld"] == ""
    assert effective_seo(site, team)["site_name"] == "Kajenn"


def test_root_fields_only_on_the_root_page_and_404_is_noindex():
    site, (_home, team, missing) = site_with_pages("Home", "Team", "Missing")
    site.set_page_url(missing, "/404/")
    with pytest.raises(DomainError, match="root-only"):
        set_page_seo(site, team, {"origin": "https://kajenn.org"})
    with pytest.raises(DomainError, match="always noindex"):
        set_page_seo(site, missing, {"robots": "index, follow"})
    assert effective_seo(site, missing)["robots"] == "noindex, follow"


@pytest.mark.parametrize(
    "fields",
    [
        {"origin": "https://kajenn.org/blog/"},
        {"robots": "index"},
        {"json_ld": "{not json"},
        {"json_ld": "42"},
        {"canonical": "/relative/"},
        {"social_image": "missing"},
    ],
)
def test_invalid_values_are_refused(fields):
    site, (home,) = site_with_pages("Home")
    with pytest.raises(DomainError):
        set_page_seo(site, home, fields)


def test_an_empty_value_clears_the_field():
    site, (home,) = site_with_pages("Home")
    set_page_seo(site, home, {"title": "Kajenn"})
    set_page_seo(site, home, {"title": ""})
    assert effective_seo(site, home)["title"] == "Home"


def test_the_fingerprint_follows_page_seo_and_inherited_root_values():
    site, (home, team) = site_with_pages("Home", "Team")
    before = page_fingerprint(site, team)
    set_page_seo(site, home, {"description": "Root text"})
    assert page_fingerprint(site, team) != before
    inherited = page_fingerprint(site, team)
    set_page_seo(site, team, {"title": "The team"})
    assert page_fingerprint(site, team) != inherited


def test_alt_texts_are_set_in_the_page_copies():
    site, (home, team) = site_with_pages("Home", "Team")
    text = '<p>Intro</p><img src="/a.png"><img src="/b.png" alt="">'
    content = site.add_content("Intro", "html", text)
    site.assign_content(home, "body", content)
    site.assign_content(team, "body", content)

    images = page_images(site, home)
    assert [(i["where"], i["src"], i["alt"]) for i in images] == [
        ("slot body", "/a.png", None),
        ("slot body", "/b.png", ""),
    ]
    set_image_alt(site, home, images[0]["image"], 'Kajenn "mark"')

    assert page_images(site, home)[0]["alt"] == 'Kajenn "mark"'
    assert page_images(site, team)[0]["alt"] is None
    plan = {item.page_id: item for item in site.update_plan(content)}
    assert plan[home].locally_changed and not plan[team].locally_changed


def test_alt_texts_in_markdown_and_in_the_template():
    site = Site.create("S")
    source = template_source("body")
    source.set_item("html_0.body.logo", None, node_tag="img", _attributes={"src": "/logo.png"})
    page = site.add_page("Home", site.add_template("T", "gramlot", source))
    content = site.add_content("Intro", "markdown", "Text ![](/c.png) more")
    site.assign_content(page, "body", content)

    images = {i["where"]: i for i in page_images(site, page)}
    assert images["template"]["alt"] is None and images["slot body"]["alt"] is None
    set_image_alt(site, page, images["template"]["image"], "Logo")
    set_image_alt(site, page, images["slot body"]["image"], "Chart")
    with pytest.raises(DomainError, match="no \\]"):
        set_image_alt(site, page, images["slot body"]["image"], "a]b")

    assert {i["where"]: i["alt"] for i in page_images(site, page)} == {
        "template": "Logo",
        "slot body": "Chart",
    }
    assert site.page(page).slots.nodes[0].value == "Text ![Chart](/c.png) more"


def test_sources_saved_before_n6_get_an_empty_seo_section():
    site, (home,) = site_with_pages("Home")
    site.page(home).bag.pop("seo")
    loaded = site_from_envelope(json.loads(json.dumps(site_envelope(site))))
    assert len(loaded.page(home).seo) == 0


SEO_LAYOUT = """
def build(source, data):
    doc = source.html(lang="en")
    head = doc.head()
    head.meta(charset="utf-8")
    head.title("^page.title")
    head.meta(name="description", content="Template description")
    head.meta(property="og:title", content="Template")
    doc.body().div(node_label="body", kpress_slot="body")
"""


def test_the_rendered_page_carries_the_seo_in_its_head():
    worker = RenderWorker(os.environ["KAJENN_RENDER_PYTHON"], timeout=30)
    site = Site.create("Kajenn")
    template = site.add_template("T", "gramlot", worker.plain_template("gramlot", SEO_LAYOUT))
    home = site.add_page("Home", template)
    image = site.add_asset("share", "media", b"\x89PNG fake", "image/png")
    set_page_seo(
        site,
        home,
        {
            "origin": "https://kajenn.org",
            "title": 'Kajenn & "friends"',
            "description": "The ASGI framework",
            "social_image": image,
            "json_ld": '{"@type": "WebSite", "name": "</script><b>"}',
        },
    )

    html = worker.render_page(page_request(site, home, {}, published=True))["html"]
    head = html[: html.index("</head>")]

    assert head.count("<title>") == 1
    assert '<title>Kajenn &amp; "friends"</title>' in head
    assert head.count('name="description"') == 1
    assert '<meta name="description" content="The ASGI framework">' in head
    assert '<link rel="canonical" href="https://kajenn.org/">' in head
    assert '<meta name="robots" content="index, follow">' in head
    assert head.count('property="og:title"') == 1
    assert '<meta property="og:url" content="https://kajenn.org/">' in head
    assert 'property="og:image" content="https://kajenn.org/_assets/' in head
    assert "</script><b>" not in head
    assert '"name": "\\u003c/script>\\u003cb>"' in head
    assert '<meta charset="utf-8"/>' in head
