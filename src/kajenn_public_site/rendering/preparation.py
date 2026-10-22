"""Derived editorial HTML; original source bytes never enter a write path."""

import re
from html.parser import HTMLParser

from .contract import PreparedHTML, RenderProblem

ALLOWED_TAGS = {
    "p",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "br",
    "hr",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "del",
    "small",
    "sub",
    "sup",
    "mark",
    "blockquote",
    "pre",
    "code",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "a",
    "img",
    "figure",
    "figcaption",
    "table",
    "caption",
    "colgroup",
    "col",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "abbr",
    "cite",
    "q",
    "time",
    "kbd",
    "samp",
}
STYLE_PROPERTIES = {
    "color",
    "background-color",
    "text-align",
    "font-weight",
    "font-style",
    "text-decoration",
    "text-decoration-line",
    "font-size",
    "line-height",
}


class MeaningfulHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meaningful = False

    def handle_data(self, data):
        if data.replace("\u200b", "").replace("\ufeff", "").strip():
            self.meaningful = True

    def handle_starttag(self, tag, attrs):
        if tag == "img" and dict(attrs).get("src", "").strip():
            self.meaningful = True


def filter_attribute(tag, attribute, value):
    if attribute == "style" and (
        re.search(r"url\s*\(|expression\s*\(|var\s*\(|[@\\]", value, re.IGNORECASE)
        or not re.fullmatch(r"[\w\s#.,()%+;:\-]*", value, re.ASCII)
    ):
        return None
    return value


def prepare_blocks(blocks, declarations, resource_id):
    import nh3
    from markdown_it import MarkdownIt

    markdown = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    cleaner = nh3.Cleaner(
        tags=ALLOWED_TAGS,
        clean_content_tags={"script", "style", "iframe", "object", "embed", "svg", "math"},
        attributes={
            "*": {"class", "title", "lang", "dir", "style"},
            "a": {"href"},
            "img": {"src", "alt", "width", "height"},
            "td": {"colspan", "rowspan"},
            "th": {"colspan", "rowspan", "scope"},
            "ol": {"start", "reversed"},
            "li": {"value"},
            "time": {"datetime"},
        },
        attribute_filter=filter_attribute,
        filter_style_properties=STYLE_PROPERTIES,
        url_schemes={"https", "http", "mailto", "tel"},
        strip_comments=True,
        link_rel="noopener noreferrer",
    )
    prepared, diagnostics, missing = {}, [], []
    for name, declaration in declarations.items():
        block = blocks.get(name)
        if block is not None and block["format"] != declaration["format"]:
            raise RenderProblem(
                "invalid_block",
                "Block format differs from template",
                resource_id=resource_id,
                block=name,
            )
        source = block["source"] if block else ""
        html = markdown.render(source) if declaration["format"] == "markdown" else source
        cleaned = cleaner.clean(html)
        if cleaned != html:
            diagnostics.append(
                {
                    "code": "html_filtered",
                    "resource_id": resource_id,
                    "block": name,
                    "message": "Editorial markup normalized or filtered",
                }
            )
        content = MeaningfulHTML()
        content.feed(cleaned)
        if declaration["required"] and not content.meaningful:
            missing.append(
                {
                    "code": "required_block_empty",
                    "resource_id": resource_id,
                    "block": name,
                    "message": "Required block empty after preparation",
                }
            )
        prepared[name] = PreparedHTML(cleaned)
    if missing:
        raise RenderProblem(
            "not_ready",
            "Required blocks are missing or empty",
            resource_id=resource_id,
            diagnostics=diagnostics + missing,
        )
    return prepared, diagnostics
