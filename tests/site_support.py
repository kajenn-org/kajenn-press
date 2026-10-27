"""Plain template sources shared by the site tests."""

from genro_bag import Bag


def template_source(*slots):
    source = Bag()
    source.set_item("html_0", Bag(), node_tag="html", _attributes={"lang": "en"})
    source.set_item("html_0.head", Bag(), node_tag="head")
    source.set_item("html_0.head.title", "Title", node_tag="title")
    source.set_item("html_0.body", Bag(), node_tag="body")
    for name in slots:
        source.set_item(
            f"html_0.body.{name}", None, node_tag="div", _attributes={"kpress_slot": name}
        )
    return source
