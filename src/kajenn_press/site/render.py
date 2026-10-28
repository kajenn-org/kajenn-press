"""Build the worker request that renders one page of a site.

Data given to the template: `page.title` (the page name) and, for each page asset copy,
`assets.<asset name>.url`: a `data:` URL of its bytes for previews, or the
content-addressed path `/_assets/<sha256>.<ext>` for publication (N4-D1). Slot contents
travel as their copies' source and format. `head` holds the SEO tags the worker writes into
the page `head` (N6-D1).
"""

import base64
import hashlib
import mimetypes

from ..domain import DomainError
from .seo import effective_seo, head_html

EXTENSIONS = {
    "text/css": "css",
    "application/javascript": "js",
    "text/javascript": "js",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def published_asset_name(data, mime_type):
    extension = EXTENSIONS.get(mime_type) or (mimetypes.guess_extension(mime_type) or ".bin")[1:]
    return f"{hashlib.sha256(data).hexdigest()}.{extension}"


def page_assets(site, page_id, published=False):
    """Asset name -> (URL, published file name, bytes) for a page."""
    assets = {}
    for node in site.page(page_id).assets.nodes:
        name = node.attr["name"]
        if "." in name:
            raise DomainError("invalid_input", f"Asset name {name} cannot contain a dot")
        file_name = published_asset_name(node.value, node.attr["mime_type"])
        if published:
            url = "/_assets/" + file_name
        else:
            encoded = base64.b64encode(node.value).decode("ascii")
            url = f"data:{node.attr['mime_type']};base64,{encoded}"
        assets[name] = (url, file_name, node.value)
    return assets


def social_image_file(site, page_id):
    """(published file name, bytes) of the page's effective social image, or None."""
    asset_id = effective_seo(site, page_id)["social_image"]
    if not asset_id:
        return None
    node = site.node("assets", asset_id)
    return published_asset_name(node.value, node.attr["mime_type"]), node.value


def page_request(site, page_id, connections, published=False):
    page = site.page(page_id)
    template = page.template
    assets = {
        name: {"url": url}
        for name, (url, _file, _data) in page_assets(site, page_id, published).items()
    }
    slots = {
        node.attr["slot"]: {"format": node.attr["format"], "source": node.value}
        for node in page.slots.nodes
    }
    data = page.bag.get_item("data")
    image = social_image_file(site, page_id)
    return {
        "engine": template.attr["engine"],
        "template": template.value.to_tytx(transport="json"),
        "slots": slots,
        "data": {"page": {"title": page.name}, "assets": assets},
        "page_data": data.to_tytx(transport="json") if len(data) else "",
        "connections": connections,
        "resource_id": page_id,
        "head": head_html(effective_seo(site, page_id), image and "/_assets/" + image[0]),
    }
