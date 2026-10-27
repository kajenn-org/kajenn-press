# In a release build page.title is the route title (service.py), so the menu matches those.
NAV = (
    ("/en/", "Overview", "Kajenn Press · Editorial publishing with releases"),
    ("/en/features/", "Features", "Features · Kajenn Press"),
    ("/en/get-started/", "Get started", "Get started · Kajenn Press"),
)
REPOSITORY = "https://github.com/kajenn-org/kajenn-press"


def build(source, data):
    title = data.get_item("page.title")
    doc = source.html(lang="^language")
    head = doc.head()
    head.meta(charset="utf-8")
    head.meta(name="viewport", content="width=device-width, initial-scale=1")
    logo = ""
    for asset in data.get_item("resources").values():
        if asset.get_item("kind") == "css":
            head.link(rel="stylesheet", href=asset.get_item("url"))
        elif asset.get_item("kind") == "media":
            logo = asset.get_item("url")
            head.link(rel="icon", type="image/png", href=logo)
    body = doc.body()
    body.a("Skip to content", href="#main", class_="skip")
    inner = body.header(class_="site-header").div(class_="header-inner")
    brand = inner.a(href="/en/", class_="brand", aria_label="Kajenn Press home")
    brand.img(src=logo, width="48", height="48", alt="")
    brand.span("kajenn", class_="brand-name")
    brand.span("press", class_="brand-press")
    nav = inner.nav(id="site-nav", aria_label="Main navigation")
    for href, label, page_title in NAV:
        if page_title == title:
            nav.a(label, href=href, aria_current="page")
        else:
            nav.a(label, href=href)
    nav.a("GitHub ↗", href=REPOSITORY, class_="nav-cta")
    main = body.main(id="main")
    main.div("^blocks.hero")
    main.div("^blocks.body")
    footer = body.footer(class_="site-footer")
    top = footer.div(class_="footer-top")
    about = top.div()
    mark = about.a(href="/en/", class_="brand")
    mark.span("kajenn", class_="brand-name")
    mark.span("press", class_="brand-press")
    about.p("Write, review and publish sites as complete releases, with exact history and rollback.")
    about.p("Part of the Genro family.")
    learn = top.div()
    learn.h2("Learn")
    for href, label, _page_title in NAV:
        learn.a(label, href=href)
    family = top.div()
    family.h2("Family")
    family.a("Source on GitHub ↗", href=REPOSITORY)
    family.a("kajenn ↗", href="https://github.com/kajenn-org/kajenn")
    family.a("Gramlot ↗", href="https://www.gramlot.org/")
    family.a("Asqueel ↗", href="https://asqueel.org/")
    bottom = footer.div(class_="footer-bottom")
    bottom.span("© 2026 Softwell S.r.l. · kajenn-press 0.1.0")
    bottom.span("Built with Kajenn Press")
