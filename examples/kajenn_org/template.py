# In a release build page.title is the route title (service.py), so the menu matches those.
NAV = (
    ("/en/", "Overview", "kajenn · A spicy ASGI application server"),
    ("/en/concepts/", "Concepts", "Core concepts · kajenn"),
    ("/en/get-started/", "Get started", "Get started · kajenn"),
)


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
    body = doc.body()
    body.a("Skip to content", href="#main", class_="skip")
    inner = body.header(class_="site-header").div(class_="header-inner")
    brand = inner.a(href="/en/", class_="brand", aria_label="kajenn home")
    brand.img(src=logo, width="40", height="40", alt="")
    brand.span("kajenn", class_="brand-name")
    brand.span(".", class_="brand-dot")
    nav = inner.nav(id="site-nav", aria_label="Main navigation")
    for href, label, page_title in NAV:
        if page_title == title:
            nav.a(label, href=href, aria_current="page")
        else:
            nav.a(label, href=href)
    nav.a("GitHub ↗", href="https://github.com/kajenn-org/kajenn", class_="nav-cta")
    main = body.main(id="main")
    main.div("^blocks.hero")
    main.div("^blocks.body")
    footer = body.footer(class_="site-footer")
    top = footer.div(class_="footer-top")
    about = top.div()
    mark = about.a(href="/en/", class_="brand")
    mark.span("kajenn", class_="brand-name")
    mark.span(".", class_="brand-dot")
    about.p("A spicy ASGI application server. Pronounced KAY-jen: cayenne and Cajun, spicy, with rhythm.")
    about.p("Proud member of the Genro family.")
    learn = top.div()
    learn.h2("Learn")
    for href, label, _page_title in NAV:
        learn.a(label, href=href)
    project = top.div()
    project.h2("Project")
    project.a("Source on GitHub ↗", href="https://github.com/kajenn-org/kajenn")
    project.a("Documentation ↗", href="https://kajenn.readthedocs.io/en/latest/")
    project.a("Gramlot ↗", href="https://www.gramlot.org/")
    project.a("Asqueel ↗", href="https://asqueel.org/")
    bottom = footer.div(class_="footer-bottom")
    bottom.span("© 2026 Softwell S.r.l. · Open source · Apache 2.0")
    bottom.span("Built with kajenn public site")
