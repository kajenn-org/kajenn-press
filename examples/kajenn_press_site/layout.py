"""Kajenn Press site layout as a static Source with slots `hero` and `body`.

Nothing is read from Data while building: the title, the asset URLs, the menu labels and
links (site texts, translated per language) and the language links are Data pointers
resolved at render time, and the two blocks are slots. The menu does not mark the
current page.
"""

NAV = ("overview", "features", "start")
LANGUAGES = ("en", "it")
REPOSITORY = "https://github.com/kajenn-org/kajenn-press"


def build(source, data):
    doc = source.html(lang="en")
    head = doc.head()
    head.meta(charset="utf-8")
    head.meta(name="viewport", content="width=device-width, initial-scale=1")
    head.title("^page.title")
    head.link(rel="stylesheet", href="^assets.site.url")
    head.link(rel="icon", type="image/png", href="^assets.logo.url")
    logo = "^assets.logo.url"
    body = doc.body()
    body.a("^texts.skip", href="#main", class_="skip")
    inner = body.header(class_="site-header").div(class_="header-inner")
    brand = inner.a(href="^texts.href_overview", class_="brand", aria_label="Kajenn Press home")
    brand.img(src=logo, width="48", height="48", alt="")
    brand.span("kajenn", class_="brand-name")
    brand.span("press", class_="brand-press")
    nav = inner.nav(id="site-nav", aria_label="Main navigation")
    for key in NAV:
        nav.a(f"^texts.nav_{key}", href=f"^texts.href_{key}")
    for code in LANGUAGES:
        nav.a(code.upper(), href=f"^page.urls.{code}", hreflang=code, class_="nav-language")
    nav.a("GitHub ↗", href=REPOSITORY, class_="nav-cta")
    main = body.main(id="main")
    main.div(node_label="hero", kpress_slot="hero")
    main.div(node_label="body", kpress_slot="body")
    footer = body.footer(class_="site-footer")
    top = footer.div(class_="footer-top")
    about = top.div()
    mark = about.a(href="^texts.href_overview", class_="brand")
    mark.span("kajenn", class_="brand-name")
    mark.span("press", class_="brand-press")
    about.p("^texts.footer_about")
    about.p("^texts.footer_family")
    learn = top.div()
    learn.h2("^texts.footer_learn")
    for key in NAV:
        learn.a(f"^texts.nav_{key}", href=f"^texts.href_{key}")
    family = top.div()
    family.h2("^texts.footer_links")
    family.a("Source on GitHub ↗", href=REPOSITORY)
    family.a("kajenn ↗", href="https://github.com/kajenn-org/kajenn")
    family.a("Gramlot ↗", href="https://www.gramlot.org/")
    family.a("Asqueel ↗", href="https://asqueel.org/")
    bottom = footer.div(class_="footer-bottom")
    bottom.span("© 2026 Softwell S.r.l. · kajenn-press 0.1.0")
    bottom.span("Built with Kajenn Press")
