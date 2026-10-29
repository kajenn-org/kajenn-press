"""Published page objects and the site index (N4 Phase 2)."""

import hashlib
import io
import zipfile

import pytest
from site_support import template_source

from kajenn_press.catalog.errors import IntegrityError
from kajenn_press.site.model import Site
from kajenn_press.site.published import (
    PublishedPage,
    make_bindings,
    make_index,
    pack_page,
    page_fingerprint,
    read_bindings,
    read_index,
    unpack_page,
)

PNG = b"\x89PNG\r\n\x1a\n\x00"
PNG_NAME = hashlib.sha256(PNG).hexdigest() + ".png"


def published():
    return PublishedPage(
        "p1", "/", "f" * 64, "{}::X", "<!doctype html><p>Hi</p>", {PNG_NAME: PNG}, True, "en"
    )


def test_published_page_round_trip_is_deterministic():
    raw = pack_page(published())
    assert raw == pack_page(published())
    assert unpack_page(raw) == published()


def rezip(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return stream.getvalue()


def entries():
    with zipfile.ZipFile(io.BytesIO(pack_page(published()))) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda e: e.update({"index.html": b"<p>other</p>"}), "integrity"),
        (lambda e: e.update({"assets/" + PNG_NAME: b"tampered"}), "does not match"),
        (lambda e: e.update({"notes.txt": b"x"}), "Unexpected entry"),
        (lambda e: e.pop("page.json"), "starts with"),
    ],
)
def test_altered_published_pages_fail_closed(change, message):
    altered = entries()
    change(altered)
    with pytest.raises(IntegrityError, match=message):
        unpack_page(rezip(altered))


def test_a_dynamic_page_keeps_its_render_request():
    dynamic = PublishedPage(
        "p1", "/", "f" * 64, "{}::X", "<p>x</p>", {}, True, "en", '{"engine": "gramlot"}'
    )
    assert unpack_page(pack_page(dynamic)).request == '{"engine": "gramlot"}'


def test_not_a_zip_fails_closed():
    with pytest.raises(IntegrityError, match="not readable"):
        unpack_page(b"nope")


def page_entry(url):
    return {
        "url": url,
        "key": "k",
        "version_id": "v",
        "fingerprint": "f",
        "assets": [],
        "refresh": 0,
        "indexable": True,
        "language": "en",
    }


def test_index_round_trip_and_checks():
    raw = make_index("s", "sv", {"a": page_entry("/"), "b": page_entry("/x/")}, {"/old/": "/x/"})
    index = read_index(raw)
    assert index["pages"]["b"]["url"] == "/x/"
    assert index["redirects"] == {"/old/": "/x/"}
    assert index["maintenance"] is False
    with pytest.raises(IntegrityError, match="share a URL"):
        make_index("s", "sv", {"a": page_entry("/"), "b": page_entry("/")}, {})
    with pytest.raises(IntegrityError):
        read_index(raw.replace(b'"schema":3', b'"schema":2'))
    with pytest.raises(IntegrityError):
        read_index(b"{")


def test_fingerprint_follows_name_url_and_content():
    site = Site.create("S")
    page = site.add_page("Home", site.add_template("T", "gramlot", template_source("body")))
    first = page_fingerprint(site, page)
    site.node("pages", page).attr["name"] = "Start"
    renamed = page_fingerprint(site, page)
    site.set_page_url(page, "/start/")
    moved = page_fingerprint(site, page)
    site.assign_content(page, "body", site.add_content("C", "html", "<p>c</p>"))
    assert len({first, renamed, moved, page_fingerprint(site, page)}) == 4


def test_bindings_of_schema_1_are_read_with_the_default_server():
    old = b'{"bindings":{"https://a.example":{"site_id":"s1","state":"public"}},"schema":1}'
    assert read_bindings(old) == {
        "https://a.example": {
            "site_id": "s1",
            "state": "public",
            "server": "default",
            "redirect": None,
        }
    }
    with pytest.raises(IntegrityError, match="not its site's address"):
        make_bindings(
            {
                "https://a.example": {
                    "site_id": "s1",
                    "state": "public",
                    "server": "w",
                    "redirect": None,
                },
                "https://www.a.example": {
                    "site_id": "s2",
                    "state": "public",
                    "server": "w",
                    "redirect": "https://a.example",
                },
            }
        )
