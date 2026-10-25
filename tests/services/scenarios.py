"""Small complete editorial fixtures with actual local persistence."""

from kajenn_press.catalog.local import LocalCatalog
from kajenn_press.domain import AccessPolicy
from kajenn_press.services.editorial import EditorialService

ADMIN = {"admin": {"*": ["read", "write", "use", "create_site"]}}
DECLARATIONS = {
    "intro": {"format": "html", "required": True},
    "body": {"format": "markdown", "required": False},
}
BLOCKS = {
    "intro": {"format": "html", "source": "<p>Caffè &amp; tè</p>\r\n"},
    "body": {"format": "markdown", "source": "# Esatto\n\n**testo**  \n"},
}


def create_service(root, grants=None):
    catalog = LocalCatalog(root)
    return EditorialService(catalog, AccessPolicy(grants or ADMIN))


def record(service, operation, **arguments):
    return service.execute("admin", operation, **arguments)["records"][0]


def seed(service):
    site = record(service, "site_create", key="site", name="First site", languages=["it", "en"])
    other = record(service, "site_create", key="other", name="Second site", languages=["it"])
    template = record(
        service,
        "resource_save",
        key="template",
        scope="library",
        kind="template",
        name="page",
        source='raise RuntimeError("must never execute")\r\n',
        engine="gramlot",
        blocks=DECLARATIONS,
    )
    content = record(
        service, "content_create", key="content", site_id=site["record_id"], title="Article"
    )
    variant = record(
        service,
        "variant_create",
        key="variant",
        content_id=content["record_id"],
        language="it",
        template_revision=template["revision_id"],
        blocks=BLOCKS,
    )
    return site, other, template, content, variant
