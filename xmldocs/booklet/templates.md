<!-- generated from templates.xml by xmldocs: do not edit, edit the XML -->

## Writing a template
*Instruction booklet · booklet/templates · 2026-10-29*

### Purpose

How to write the layout of a Kajenn Press site: Python build code that produces one HTML document with slots for contents, reading site texts, assets and page data.

### Requirements

- A websites installation with its render worker (the `render` extra).
- A site open for editing; templates are added through `template_add` (REST, MCP, or Help me).

#### 1. Write build code

A template is Python that defines `build(source, data)`. It runs once in the render worker when the template is added; the result is stored as a plain Source Bag and replayed at every rendering. The engine is `gramlot` or `htmlbuilder`.

HTML attributes are keyword arguments; `class` is written `class_`, `for` is `for_`. The document has exactly one `html` root.

**Example — A minimal template with two slots**

```python
def build(source, data):
    doc = source.html(lang="en")
    head = doc.head()
    head.title("^page.title")
    head.link(rel="stylesheet", href="^assets.site.url")
    body = doc.body()
    body.div(node_label="hero", kpress_slot="hero")
    body.div(node_label="body", kpress_slot="body")
```

`build` reads nothing while building: values that change per page or per language are Data pointers, strings starting with `^`, resolved at rendering.

#### 2. Declare slots

An element with `kpress_slot="name"` is a slot: the place where a page shows the content assigned to it. `kpress_slot=True` names the slot by its label path. Slot names are unique in a template, and a slot is an element able to hold content (`div`, `main`, `section`, `article`, `aside`, `header`, `footer`, `nav`, `td`, `li` and similar).

A slot that also has `kpress_iframe="URL"` is filled by that iframe in the browser; the content assigned to it is the static fallback written in the page, which search engines and readers without JavaScript see.

Contents are filtered before they enter a slot: HTML through an allow-list of tags, attributes and URL schemes; Markdown is converted first. Scripts, styles and iframes inside a content are removed.

#### 3. Read page data

*Data pointers available to every template*

| Pointer | Value |
|---|---|
| `^page.title` | The page name. |
| `^page.language` | The language being rendered. |
| `^page.urls.<language>` | This page's path in a language, for a language selector. |
| `^texts.<name>` | A site text in the language being rendered; the main text where its translation is missing. |
| `^assets.<name>.url` | The address of an asset the page holds: a content-addressed path when published, a `data:` URL in previews. |

Site texts are the template's own words: menu labels, menu links, footer sentences. They are set with `site_text_set`, translated like contents, and shared by every page.

**Example — Menu and language links from the example site**

`examples/kajenn_press_site/layout.py`
```python
NAV = ("overview", "features", "start")
LANGUAGES = ("en", "it")

nav = inner.nav(id="site-nav", aria_label="Main navigation")
for key in NAV:
    nav.a(f"^texts.nav_{key}", href=f"^texts.href_{key}")
for code in LANGUAGES:
    nav.a(code.upper(), href=f"^page.urls.{code}", hreflang=code, class_="nav-language")
```

#### 4. Leave the SEO to the page

The page's SEO is written into the `head` after the template: title, description, canonical, robots, Open Graph and Twitter tags, JSON-LD and `hreflang` links. Those tags written by the template are removed first, so a template may keep a `title` for previews without producing a duplicate. The `lang` of the `html` root is set to the language being rendered.

#### 5. Data from connections

A page's Data may hold resolvers that read a named connection at rendering, such as a configuration value. The connection's address and credentials come from the server that renders, never from the page. A value enters the page as text, or as filtered HTML when the resolver says so.

A published page with resolvers is rendered again by the site server when its cache time expires (600 seconds by default), and kept in a local cache; a page without resolvers is served as published.

### Rules

- **must** — Author exactly one `html` root. *(Validation refuses any other document.)*
- **must-not** — Read Data while building; use `^` pointers. *(Values that differ per page or language would be frozen at template time.)*
- **should** — Put the template's words and links in site texts. *(Every language then gets its own menu and links.)*

### Current limits

- Template code is trusted code: the render worker is a separate process, not an OS security sandbox. · `src/kajenn_press/rendering/worker.py:1`
- A template is shared by every language of a site; there is no template per language.

### Verified facts

- `READ` `src/kajenn_press/rendering/page.py:18` · 2026-10-29 — `plain_template` runs `build(source, data)` once and stores the plain Source.
- `TEST` `src/kajenn_press/site/service.py:465` · 2026-10-29 — An unknown engine or a template that does not build is refused as `invalid_input` or `invalid_template` with diagnostics.
- `READ` `src/kajenn_press/site/slots.py:43` · 2026-10-29 — Slots come from `kpress_slot`; duplicate names and elements that cannot host content are refused.
- `READ` `src/kajenn_press/rendering/preparation.py:97` · 2026-10-29 — Contents are filtered with an allow-list (nh3); Markdown is converted with markdown-it first.
- `READ` `src/kajenn_press/site/render.py:1` · 2026-10-29 — Templates receive `page.title`, `page.language`, `page.urls`, `texts` and `assets`.
- `TEST` `src/kajenn_press/rendering/page.py:30` · 2026-10-29 — Template title, description, robots, canonical, Open Graph, Twitter and JSON-LD tags are replaced by the page's SEO.
- `READ` `src/kajenn_press/rendering/resolvers.py:17` · 2026-10-29 — Connection resolvers default to a 600-second cache time.
- `TEST` `tests/site/test_page_rendering.py:1` · 2026-10-29 — The example layout renders every example page in English and the home page in Italian.

### Related documents

- `booklet/site-tab`
