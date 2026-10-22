"""The same complete Source/Data template runs on either qualified engine."""


def build(source, data):
    document = source.html(lang="^language")
    head = document.head()
    head.meta(charset="utf-8")
    head.title("^page.title")
    body = document.body()
    body.h1("^page.title", title="^page.title")
    body.div("^blocks.intro")
    body.div("^blocks.body")
    body.a("Versione Gramlot", href="gramlot.html")
    body.a("Versione HtmlBuilder", href="htmlbuilder.html")
    for asset in data.get_item("resources").values():
        kind, url = asset.get_item("kind"), asset.get_item("url")
        if kind == "css":
            head.link(rel="stylesheet", href=url)
        elif kind == "media":
            body.img(src=url, alt="Pixel dimostrativo", width=24, height=24)
        elif kind == "javascript":
            body.script(src=url)
