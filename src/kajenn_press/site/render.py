"""Build the worker request that renders one page of a site.

Data given to the template: `page.title` (the page name) and, for each page asset copy,
`assets.<asset name>.url`, a `data:` URL of its bytes until publication assigns real URLs
(N4). Slot contents travel as their copies' source and format.
"""

import base64

from ..domain import DomainError


def page_request(site, page_id, connections):
    page = site.page(page_id)
    template = page.template
    assets = {}
    for node in page.assets.nodes:
        name = node.attr["name"]
        if "." in name:
            raise DomainError("invalid_input", f"Asset name {name} cannot contain a dot")
        encoded = base64.b64encode(node.value).decode("ascii")
        assets[name] = {"url": f"data:{node.attr['mime_type']};base64,{encoded}"}
    slots = {
        node.attr["slot"]: {"format": node.attr["format"], "source": node.value}
        for node in page.slots.nodes
    }
    data = page.bag.get_item("data")
    return {
        "engine": template.attr["engine"],
        "template": template.value.to_tytx(transport="json"),
        "slots": slots,
        "data": {"page": {"title": page.name}, "assets": assets},
        "page_data": data.to_tytx(transport="json") if len(data) else "",
        "connections": connections,
        "resource_id": page_id,
    }
