"""Page URLs and redirects (N4 Phase 1)."""

import pytest
from site_support import template_source

from kajenn_press.domain import DomainError
from kajenn_press.site.model import Site
from kajenn_press.site.store import pack, unpack


def site_with(*names):
    site = Site.create("S")
    template = site.add_template("T", "gramlot", template_source("body"))
    return site, [site.add_page(name, template) for name in names]


def url(site, page_id):
    return site.node("pages", page_id).attr["url"]


def test_first_page_is_the_root_and_others_get_unique_paths():
    site, pages = site_with("Home", "About us", "About us", "Ç'è!")
    assert [url(site, p) for p in pages] == ["/", "/about-us/", "/about-us-2/", "/c-e/"]


def test_moving_a_page_records_a_redirect_and_collapses_chains():
    site, (_home, about) = site_with("Home", "About")
    site.set_page_url(about, "/team/")
    site.set_page_url(about, "/people/")

    assert url(site, about) == "/people/"
    assert site.redirects() == {"/about/": "/people/", "/team/": "/people/"}


def test_moving_back_reclaims_the_old_path():
    site, (_home, about) = site_with("Home", "About")
    site.set_page_url(about, "/team/")
    site.set_page_url(about, "/about/")
    assert site.redirects() == {"/team/": "/about/"}


def test_a_new_page_does_not_take_a_redirected_path():
    site, (_home, about) = site_with("Home", "About")
    site.set_page_url(about, "/team/")
    template = next(iter(site.section("templates").keys()))
    assert url(site, site.add_page("About", template)) == "/about-2/"


def test_a_path_of_another_page_is_refused():
    site, (_home, about) = site_with("Home", "About")
    with pytest.raises(DomainError, match="belongs to another page"):
        site.set_page_url(about, "/")


@pytest.mark.parametrize("bad", ["about", "/a//b", "/a?x=1", "/a#top", "/a b", "/../x", 3])
def test_invalid_paths_are_refused(bad):
    site, (_home, about) = site_with("Home", "About")
    with pytest.raises(DomainError, match="URL path"):
        site.set_page_url(about, bad)


def test_urls_and_redirects_survive_the_zip():
    site, (_home, about) = site_with("Home", "About")
    site.set_page_url(about, "/team/")
    loaded = unpack(pack(site))
    assert loaded.page_urls() == site.page_urls()
    assert loaded.redirects() == {"/about/": "/team/"}
