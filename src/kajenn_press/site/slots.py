"""Slots declared by a template source with `kpress_slot`.

`kpress_slot='name'` names a slot; `kpress_slot=True` names it by its label path, such as
`center.info.top.tab1`. Names are unique per template. A slot is a plain HTML element
able to host content, so static HTML needs no JavaScript. A slot that also carries
`kpress_iframe` is filled by that iframe in the browser; its assigned content is the
static fallback rendered in the page (d-dynamic-seo).
"""

from dataclasses import dataclass

from ..domain import DomainError

HOSTING_TAGS = {
    "main",
    "header",
    "footer",
    "nav",
    "section",
    "article",
    "aside",
    "div",
    "td",
    "th",
    "li",
    "dd",
    "blockquote",
    "figure",
    "figcaption",
    "details",
}


@dataclass(frozen=True)
class Slot:
    name: str
    path: str
    tag: str
    kind: str
    iframe: str | None = None


def template_slots(source):
    """The slots of a plain template source, in document order; refuses invalid ones."""
    slots, problems = [], []
    for path, node in source.query("#p,#n", deep=True):
        declared = node.attr.get("kpress_slot")
        if declared is None or declared is False:
            continue
        if declared is True:
            name = path
        elif isinstance(declared, str) and declared.strip():
            name = declared
        else:
            problems.append({"path": path, "problem": "kpress_slot is True or a name"})
            continue
        if node.node_tag not in HOSTING_TAGS:
            problems.append({"path": path, "tag": node.node_tag, "problem": "tag cannot host"})
            continue
        iframe = node.attr.get("kpress_iframe")
        slots.append(
            Slot(name, path, node.node_tag, "iframe" if iframe else "content", iframe or None)
        )
    paths = {}
    for slot in slots:
        paths.setdefault(slot.name, []).append(slot.path)
    for name, found in paths.items():
        if len(found) > 1:
            problems.append({"name": name, "paths": found, "problem": "duplicate slot name"})
    if problems:
        raise DomainError("invalid_template", "Template declares invalid slots", details=problems)
    return slots
