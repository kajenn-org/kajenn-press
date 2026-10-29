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
from urllib.parse import urljoin, urlsplit

from ..domain import DomainError
from .slots import template_slots

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


def stored_seo(site, page_id, language=None):
    """The fields stored on a page, as strings; another language has its own (N9)."""
    from .languages import main_language, page_language

    if language is None or language == main_language(site):
        return {node.label: node.value for node in site.page(page_id).seo.nodes}
    own = page_language(site, page_id, language)
    return {n.label: n.value for n in own.nodes if n.label != "url"} if own is not None else {}


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


def set_page_seo(site, page_id, fields, language=None):
    """Store the given fields of a page; an empty value clears the field.

    Another language stores its own fields; the public origin is one per site.
    """
    from .languages import main_language, page_language

    if not isinstance(fields, dict):
        raise DomainError("invalid_input", "SEO fields are an object")
    page = site.page(page_id)
    url = site.node("pages", page_id).attr["url"]
    main = language is None or language == main_language(site)
    root_fields = ROOT_FIELDS if main else tuple(f for f in ROOT_FIELDS if f != "origin")
    allowed = PAGE_FIELDS + (root_fields if url == ROOT_URL else ())
    unknown = set(fields) - set(allowed)
    if unknown:
        raise DomainError(
            "invalid_input", "Unknown or root-only SEO fields: " + ", ".join(sorted(unknown))
        )
    if url == NOT_FOUND_URL and fields.get("robots"):
        raise DomainError("invalid_input", "The 404 page is always noindex")
    seo = page.seo if main else page_language(site, page_id, language, create=True)
    for field, value in fields.items():
        if value is not None and not isinstance(value, str):
            raise DomainError("invalid_input", f"SEO field {field} is a string")
        value = (value or "").strip()
        if value:
            seo.set_item(field, checked_value(site, field, value))
        elif seo.get_node(field) is not None:
            seo.pop(field)


def effective_seo(site, page_id, stored=None, language=None):
    """The SEO a page is published with: stored, else root, else derived.

    `stored` replaces the page's own fields: `{}` gives what every empty field would show.
    In another language a field missing there takes the value of the main language
    (d-lang-missing), and the URL carries the language prefix.
    """
    from .languages import language_url, main_language

    main = main_language(site)
    if language is not None and language != main:
        return language_seo(site, page_id, language, stored)
    stored = stored_seo(site, page_id) if stored is None else stored
    root_id = root_page_id(site)
    if page_id == root_id:
        root = stored
    else:
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
        "language": main,
        "path": language_url(site, page_id, main),
    }


def language_seo(site, page_id, language, stored=None):
    """Effective SEO in another language over the main language's (d-lang-seo)."""
    from .languages import language_url

    base = effective_seo(site, page_id)
    stored = stored_seo(site, page_id, language) if stored is None else stored
    root_id = root_page_id(site)
    if page_id == root_id:
        root = stored
    else:
        root = stored_seo(site, root_id, language) if root_id is not None else {}
    path = language_url(site, page_id, language)
    title = stored.get("title") or base["title"]
    description = stored.get("description") or root.get("description") or base["description"]
    origin = base["origin"]
    robots = base["robots"]
    if site.node("pages", page_id).attr["url"] != NOT_FOUND_URL:
        robots = stored.get("robots") or root.get("robots") or base["robots"]
    return {
        **base,
        "site_name": root.get("site_name") or base["site_name"],
        "organisation": root.get("organisation") or base["organisation"],
        "url": path,
        "title": title,
        "description": description,
        "canonical": stored.get("canonical") or (origin + path if origin else ""),
        "robots": robots,
        "social_title": stored.get("social_title") or title,
        "social_description": stored.get("social_description") or description,
        "social_image": stored.get("social_image")
        or root.get("social_image")
        or base["social_image"],
        "json_ld": stored.get("json_ld") or base["json_ld"],
        "language": language,
        "path": path,
    }


def indexable(seo):
    return not seo["robots"].startswith("noindex")


def head_html(seo, image_path=None, alternates=()):
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
    for language, href in alternates:
        tags.append(
            f'<link rel="alternate" hreflang="{escape(language, quote=True)}"'
            f' href="{escape(href, quote=True)}">'
        )
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


HTML_LINK = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)[^)]*\)")
SERVED_PATHS = ("/sitemap.xml", "/robots.txt")


def page_links(site, page_id):
    """(where, href) of the links of a page: template `a` nodes and placed contents."""
    page = site.page(page_id)
    links = [
        ("template", node.attr["href"])
        for _path, node in page.template.value.query("#p,#n", deep=True)
        if node.node_tag == "a"
        and isinstance(node.attr.get("href"), str)
        and not node.attr["href"].startswith("^")
    ]
    for node in page.slots.nodes:
        where = "slot " + node.attr["slot"]
        for match in HTML_LINK.finditer(node.value):
            href = dict(StartTag(match.group(0)).attrs).get("href")
            if href:
                links.append((where, href))
        if node.attr["format"] == "markdown":
            links += [(where, match.group(1)) for match in MARKDOWN_LINK.finditer(node.value)]
    return links


def internal_path(page_url, href):
    """The site path a link leads to, or None for external, fragment and scheme links."""
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    return urljoin(page_url, parts.path)


def seo_check(site, page_id=None):
    """SEO problems of one page or of the whole site, as {page_id, code, message}."""
    pages = [node.label for node in site.section("pages").nodes]
    effective = {pid: effective_seo(site, pid) for pid in pages}
    urls = set(site.page_urls())
    redirects = set(site.redirects())
    titles = {}
    for pid in pages:
        if indexable(effective[pid]):
            titles.setdefault(effective[pid]["title"], []).append(pid)
    problems = []

    def report(pid, code, message):
        problem = {"page_id": pid, "code": code, "message": message}
        if problem not in problems:
            problems.append(problem)

    root_id = root_page_id(site)
    for pid in pages if page_id is None else [site.page(page_id).page_id]:
        seo = effective[pid]
        if pid == root_id and not seo["origin"]:
            report(
                pid, "missing_origin", "No public origin: canonical URLs and og:image are left out"
            )
        if indexable(seo):
            if len(titles[seo["title"]]) > 1:
                report(pid, "duplicate_title", f"Title also used by another page: {seo['title']}")
            if not seo["description"]:
                report(pid, "missing_description", "Missing description")
            filled = {node.attr["slot"] for node in site.page(pid).slots.nodes}
            for slot in template_slots(site.page(pid).template.value):
                if slot.kind == "iframe" and slot.name not in filled:
                    report(
                        pid,
                        "iframe_without_fallback",
                        f"Iframe slot {slot.name} has no fallback content",
                    )
        for image in page_images(site, pid):
            if image["alt"] is None:
                report(
                    pid,
                    "missing_alt",
                    f"Image {image['src']} in the {image['where']} has no alt text",
                )
        for where, href in page_links(site, pid):
            path = internal_path(seo["url"], href)
            if path is None or path.startswith("/_assets/") or path in SERVED_PATHS:
                continue
            if path not in urls and path not in redirects and path + "/" not in urls:
                report(pid, "broken_link", f"The link {href} in the {where} leads nowhere")
    return problems
