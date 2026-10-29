"""SVG from Help me, cleaned before it becomes a preview or a site asset (N8-D5).

Published assets are served from the site's own origin, so an SVG must not carry
anything that runs or loads: scripts, event attributes, `foreignObject`, styles with
URLs, and references outside the document. The cleaner keeps a list of drawing elements
and attributes, drops everything else, and refuses a document with nothing left to draw.
"""

import re
from html import escape
from xml.etree import ElementTree

from ..domain import DomainError

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ELEMENTS = {
    "svg", "g", "defs", "title", "desc", "symbol", "use", "path", "rect", "circle",
    "ellipse", "line", "polyline", "polygon", "text", "tspan", "linearGradient",
    "radialGradient", "stop", "clipPath", "mask",
}  # fmt: skip
DRAWING = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "use"}
ATTRIBUTES = {
    "id", "class", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx",
    "cy", "r", "rx", "ry", "d", "points", "fill", "fill-opacity", "fill-rule", "stroke",
    "stroke-width", "stroke-opacity", "stroke-linecap", "stroke-linejoin",
    "stroke-dasharray", "opacity", "transform", "offset", "stop-color", "stop-opacity",
    "gradientUnits", "gradientTransform", "font-family", "font-size", "font-weight",
    "font-style", "text-anchor", "dominant-baseline", "letter-spacing", "clip-path",
    "mask", "preserveAspectRatio", "role", "aria-label", "href",
}  # fmt: skip
LIMIT = 200_000
# Paint and clip values may point only inside the document: url(#id).
OUTSIDE_URL = re.compile(r"url\(\s*['\"]?\s*[^#'\"\s)]", re.IGNORECASE)


def local_name(name):
    return name.rsplit("}", 1)[-1]


def clean_attributes(element):
    kept = {}
    for name, value in element.attrib.items():
        namespace = name[1:].split("}")[0] if name.startswith("{") else ""
        local = local_name(name)
        if namespace not in ("", XLINK) or local not in ATTRIBUTES:
            continue
        if local == "href" and not value.startswith("#"):
            continue
        if OUTSIDE_URL.search(value):
            continue
        kept[local] = value
    return kept


def clean_element(element):
    """(tag, attributes, text, children, tail) of a kept element, or None."""
    namespace = element.tag[1:].split("}")[0] if element.tag.startswith("{") else ""
    tag = local_name(element.tag)
    if namespace != SVG or tag not in ELEMENTS:
        return None
    children = [c for c in (clean_element(child) for child in element) if c is not None]
    return tag, clean_attributes(element), element.text or "", children, element.tail or ""


def drawable(node):
    tag, children = node[0], node[3]
    return tag in DRAWING or any(drawable(child) for child in children)


def serialize(node, root=False):
    tag, attributes, text, children, tail = node
    if root:
        attributes = {"xmlns": SVG, **attributes}
        tail = ""
    parts = "".join(f' {k}="{escape(v, quote=True)}"' for k, v in attributes.items())
    inner = escape(text, quote=False) + "".join(serialize(c) for c in children)
    element = f"<{tag}{parts}>{inner}</{tag}>" if inner.strip() else f"<{tag}{parts}/>"
    return element + escape(tail, quote=False)


def clean_svg(text):
    """The SVG with only drawing elements and attributes; refuses a non-drawing document."""
    if not isinstance(text, str) or len(text) > LIMIT:
        raise DomainError("invalid_input", "An SVG is a text of at most 200,000 characters")
    if re.search(r"<!(DOCTYPE|ENTITY)", text, re.IGNORECASE):
        raise DomainError("invalid_input", "An SVG may not declare a DOCTYPE or entities")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise DomainError("invalid_input", f"The SVG is not well-formed XML: {exc}") from exc
    node = clean_element(root)
    if node is None or node[0] != "svg" or not drawable(node):
        raise DomainError("invalid_input", "The SVG has nothing left to draw")
    return serialize(node, root=True)
