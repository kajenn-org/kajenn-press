"""Slots read from a plain template source (N2 Phase 3)."""

import pytest
from genro_bag import Bag

from kajenn_press.domain import DomainError
from kajenn_press.rendering.engines import STATIC_TAGS
from kajenn_press.site.slots import HOSTING_TAGS, Slot, template_slots


def source(*nodes):
    """Plain Source: html > body > the given (label, tag, attributes) nodes."""
    bag = Bag()
    bag.set_item("html_0", Bag(), node_tag="html")
    bag.set_item("html_0.body", Bag(), node_tag="body")
    for label, tag, attributes in nodes:
        bag.set_item(f"html_0.body.{label}", None, node_tag=tag, _attributes=attributes)
    return bag


def test_named_and_path_slots_in_document_order():
    slots = template_slots(
        source(
            ("hero", "header", {"kpress_slot": "hero"}),
            ("text", "p", {}),
            ("info", "section", {"kpress_slot": True}),
        )
    )
    assert slots == [
        Slot("hero", "html_0.body.hero", "header", "content"),
        Slot("html_0.body.info", "html_0.body.info", "section", "content"),
    ]


def test_iframe_slot_keeps_its_url_and_is_a_fallback_host():
    (slot,) = template_slots(
        source(("map", "div", {"kpress_slot": "map", "kpress_iframe": "/app/map"}))
    )
    assert (slot.kind, slot.iframe) == ("iframe", "/app/map")


def test_duplicate_names_are_refused_with_their_paths():
    with pytest.raises(DomainError) as refused:
        template_slots(
            source(("a", "div", {"kpress_slot": "body"}), ("b", "section", {"kpress_slot": "body"}))
        )
    assert refused.value.details == [
        {
            "name": "body",
            "paths": ["html_0.body.a", "html_0.body.b"],
            "problem": "duplicate slot name",
        }
    ]


@pytest.mark.parametrize(
    ("tag", "value", "problem"),
    [
        ("span", "x", "tag cannot host"),
        ("img", True, "tag cannot host"),
        ("div", "  ", "kpress_slot"),
    ],
)
def test_invalid_slots_are_refused(tag, value, problem):
    with pytest.raises(DomainError) as refused:
        template_slots(source(("x", tag, {"kpress_slot": value})))
    assert problem in refused.value.details[0]["problem"]


def test_false_and_absent_are_not_slots():
    assert template_slots(source(("a", "div", {"kpress_slot": False}), ("b", "div", {}))) == []


def test_hosting_tags_belong_to_the_static_profile():
    assert HOSTING_TAGS <= STATIC_TAGS
