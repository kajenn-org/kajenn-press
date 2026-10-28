"""SEO of the pages of a site (N6).

Each page Bag has a section `seo` with its stored fields. The root page (URL `/`) also
holds the site defaults: site name, public origin and organisation. An empty field of a
page takes the root value, never the value of the page above it in the tree
(d-seo-inherit); title, canonical and social fields are derived from the page when the
root has nothing either. The page at `/404/` is always `noindex`.

Images of a page are the `img` elements of its template copy and of the contents placed in
its slots; their alt texts are edited in the page's copies, which makes them local changes
(N6-D3).
"""

import json
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ..domain import DomainError

ROOT_URL = "/"
NOT_FOUND_URL = "/404/"
PAGE_FIELDS = (
    "title",
    "description",
    "canonical",
    "robots",
    "social_title",
    "social_description",
    "social_image",
    "json_ld",
)
ROOT_FIELDS = ("site_name", "origin", "organisation")
ROBOTS = ("index, follow", "noindex, follow", "index, nofollow", "noindex, nofollow")
DEFAULT_ROBOTS = "index, follow"
NOT_FOUND_ROBOTS = "noindex, follow"
HTML_IMAGE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
MARKDOWN_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(([^)\s]+)[^)]*\)")


def root_page_id(site):
    return site.page_urls().get(ROOT_URL)


def stored_seo(site, page_id):
    """The fields stored on a page, as strings."""
    return {node.label: node.value for node in site.page(page_id).seo.nodes}


def http_origin(value):
    parts = urlsplit(value)
    if (
        parts.scheme not in ("http", "https")
        or not parts.netloc
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise DomainError(
            "invalid_input", "The public origin is scheme and host, such as https://example.org"
        )
    return f"{parts.scheme}://{parts.netloc}"


def http_url(value):
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise DomainError("invalid_input", "A canonical URL is absolute, http or https")
    return value


def checked_value(site, field, value):
    """The value to store for a field; refuses invalid ones."""
    if field == "origin":
        return http_origin(value)
    if field == "canonical":
        return http_url(value)
    if field == "robots":
        if value not in ROBOTS:
            raise DomainError("invalid_input", "Robots is one of: " + "; ".join(ROBOTS))
        return value
    if field == "social_image":
        node = site.node("assets", value)
        if not node.attr["mime_type"].startswith("image/"):
            raise DomainError("invalid_input", "The social image is an image asset")
        return value
    if field == "json_ld":
        try:
            parsed = json.loads(value)
        except ValueError as exc:
            raise DomainError("invalid_input", "JSON-LD is not valid JSON") from exc
        if not isinstance(parsed, (dict, list)):
            raise DomainError("invalid_input", "JSON-LD is an object or a list")
        return value
    return value


def set_page_seo(site, page_id, fields):
    """Store the given fields of a page; an empty value clears the field."""
    if not isinstance(fields, dict):
        raise DomainError("invalid_input", "SEO fields are an object")
    page = site.page(page_id)
    url = site.node("pages", page_id).attr["url"]
    allowed = PAGE_FIELDS + (ROOT_FIELDS if url == ROOT_URL else ())
    unknown = set(fields) - set(allowed)
    if unknown:
        raise DomainError(
            "invalid_input", "Unknown or root-only SEO fields: " + ", ".join(sorted(unknown))
        )
    if url == NOT_FOUND_URL and fields.get("robots"):
        raise DomainError("invalid_input", "The 404 page is always noindex")
    seo = page.seo
    for field, value in fields.items():
        if value is not None and not isinstance(value, str):
            raise DomainError("invalid_input", f"SEO field {field} is a string")
        value = (value or "").strip()
        if value:
            seo.set_item(field, checked_value(site, field, value))
        elif seo.get_node(field) is not None:
            seo.pop(field)


def effective_seo(site, page_id):
    """The SEO a page is published with: stored, else root, else derived."""
    stored = stored_seo(site, page_id)
    root_id = root_page_id(site)
    root = stored_seo(site, root_id) if root_id is not None else {}
    node = site.node("pages", page_id)
    url = node.attr["url"]
    origin = root.get("origin", "")
    title = stored.get("title") or node.attr["name"]
    description = stored.get("description") or root.get("description", "")
    json_ld = stored.get("json_ld", "")
    if not json_ld and page_id == root_id and root.get("organisation"):
        organisation = {"@context": "https://schema.org", "@type": "Organization"}
        organisation["name"] = root["organisation"]
        if origin:
            organisation["url"] = origin + ROOT_URL
        json_ld = json.dumps(organisation, ensure_ascii=False)
    return {
        "site_name": root.get("site_name") or site.name,
        "origin": origin,
        "organisation": root.get("organisation", ""),
        "url": url,
        "title": title,
        "description": description,
        "canonical": stored.get("canonical") or (origin + url if origin else ""),
        "robots": NOT_FOUND_ROBOTS
        if url == NOT_FOUND_URL
        else stored.get("robots") or root.get("robots") or DEFAULT_ROBOTS,
        "social_title": stored.get("social_title") or title,
        "social_description": stored.get("social_description") or description,
        "social_image": stored.get("social_image") or root.get("social_image", ""),
        "json_ld": json_ld,
    }


def indexable(seo):
    return not seo["robots"].startswith("noindex")


def head_html(seo, image_path=None):
    """The SEO tags written into the `head` of the rendered page (N6-D1).

    `image_path` is the site path of the social image; Open Graph wants it absolute, so it
    is written only when the site has a public origin.
    """

    def meta(attribute, name, content):
        return f'<meta {attribute}="{name}" content="{escape(content, quote=True)}">'

    tags = [f"<title>{escape(seo['title'], quote=False)}</title>"]
    if seo["description"]:
        tags.append(meta("name", "description", seo["description"]))
    if seo["canonical"]:
        tags.append(f'<link rel="canonical" href="{escape(seo["canonical"], quote=True)}">')
    tags.append(meta("name", "robots", seo["robots"]))
    tags.append(meta("property", "og:type", "website"))
    tags.append(meta("property", "og:site_name", seo["site_name"]))
    tags.append(meta("property", "og:title", seo["social_title"]))
    if seo["social_description"]:
        tags.append(meta("property", "og:description", seo["social_description"]))
    if seo["canonical"]:
        tags.append(meta("property", "og:url", seo["canonical"]))
    image = seo["origin"] + image_path if image_path and seo["origin"] else ""
    if image:
        tags.append(meta("property", "og:image", image))
    tags.append(meta("name", "twitter:card", "summary_large_image" if image else "summary"))
    if seo["json_ld"]:
        data = json.dumps(json.loads(seo["json_ld"]), ensure_ascii=False).replace("<", "\\u003c")
        tags.append(f'<script type="application/ld+json">{data}</script>')
    return "".join(tags)


class StartTag(HTMLParser):
    """Attributes of one HTML start tag, in order."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.attrs = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.attrs = attrs

    handle_startendtag = handle_starttag


def html_images(text):
    """(match, attributes) of each `img` tag of an HTML text, in order."""
    return [(match, dict(StartTag(match.group(0)).attrs)) for match in HTML_IMAGE.finditer(text)]


def html_with_alt(text, index, alt):
    match, _attrs = html_images(text)[index]
    attrs = [(k, v) for k, v in StartTag(match.group(0)).attrs if k != "alt"] + [("alt", alt)]
    parts = [k if v is None else f'{k}="{escape(v, quote=True)}"' for k, v in attrs]
    closing = " />" if match.group(0).rstrip().endswith("/>") else ">"
    tag = "<img " + " ".join(parts) + closing
    return text[: match.start()] + tag + text[match.end() :]


def markdown_with_alt(text, index, alt):
    if "]" in alt or "\n" in alt:
        raise DomainError("invalid_input", "A Markdown alt text has no ] and no line break")
    match = list(MARKDOWN_IMAGE.finditer(text))[index]
    return text[: match.start(1)] + alt + text[match.end(1) :]


def content_images(path, slot, copy):
    """Images of a placed content copy: id, where, src and alt."""
    found = [
        {
            "image": f"{path}#html{n}",
            "where": "slot " + slot,
            "src": attrs.get("src", ""),
            "alt": attrs.get("alt"),
        }
        for n, (_match, attrs) in enumerate(html_images(copy.value))
    ]
    if copy.attr["format"] == "markdown":
        found += [
            {
                "image": f"{path}#markdown{n}",
                "where": "slot " + slot,
                "src": match.group(2),
                "alt": match.group(1) or None,
            }
            for n, match in enumerate(MARKDOWN_IMAGE.finditer(copy.value))
        ]
    return found


def page_images(site, page_id):
    """The images of a page with their alt: None when missing, "" when decorative."""
    page = site.page(page_id)
    found = [
        {
            "image": "template#" + path,
            "where": "template",
            "src": node.attr.get("src", ""),
            "alt": node.attr.get("alt"),
        }
        for path, node in page.template.value.query("#p,#n", deep=True)
        if node.node_tag == "img"
    ]
    for node in page.slots.nodes:
        found += content_images("slots." + node.label, node.attr["slot"], node)
    return found


def set_image_alt(site, page_id, image, alt):
    """Set the alt of one image in the page's copy; a local change of that copy."""
    if not isinstance(alt, str) or not alt.strip():
        raise DomainError("invalid_input", "An alt text is required")
    alt = alt.strip()
    if image not in {item["image"] for item in page_images(site, page_id)}:
        raise DomainError("not_found", f"No image {image} in this page", resource_id=image)
    page = site.page(page_id)
    path, _, position = image.partition("#")
    if path == "template":
        page.template.value.get_node(position).attr["alt"] = alt
        return
    copy = page.bag.get_node(path)
    if position.startswith("html"):
        copy.value = html_with_alt(copy.value, int(position[4:]), alt)
    else:
        copy.value = markdown_with_alt(copy.value, int(position[8:]), alt)
