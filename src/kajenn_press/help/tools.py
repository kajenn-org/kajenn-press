"""Help me tools: the site operations Sonnet may use, with their schemas (N8-D1, N8-D2).

Each tool is a site operation of `SiteService`, described by the signature and docstring
of its route in `PressApplication`, so REST, MCP and Help me share one surface. The site
id and the idempotency key are filled in here, never by the model. Publishing stays an
operator command: no Publish, rollback, maintenance, visibility, private link, restore,
site creation or deletion is offered.
"""

import inspect
import json

from ..domain import DomainError

READS = (
    "site_read",
    "page_check",
    "seo_check",
    "publish_plan",
    "copies_update_plan",
    "template_switch_plan",
)
CHANGES = (
    "template_add",
    "content_add",
    "content_save",
    "page_add",
    "page_url_set",
    "page_seo_set",
    "page_alt_set",
    "folder_add",
    "tree_move",
    "page_asset_add",
    "slot_assign",
    "copies_update",
    "template_switch",
    "unplaced_place",
)
SAVES = ("site_save",)
ALLOWED = READS + CHANGES + SAVES
FILLED = {"site_id", "key", "_request"}
JSON_TYPES = {str: "string", dict: "object", list: "array", bool: "boolean", int: "integer"}


def parameter_type(annotation):
    """The JSON type of a route parameter; `X | None` is X, optional."""
    options = [a for a in getattr(annotation, "__args__", (annotation,)) if a is not type(None)]
    if len(options) != 1 or options[0] not in JSON_TYPES:
        raise TypeError(f"No JSON type for {annotation}")
    return JSON_TYPES[options[0]]


def tool_definition(name):
    from ..application import PressApplication

    method = getattr(PressApplication, name)
    properties, required = {}, []
    for parameter in inspect.signature(method).parameters.values():
        if parameter.name == "self" or parameter.name in FILLED:
            continue
        properties[parameter.name] = {"type": parameter_type(parameter.annotation)}
        if parameter.default is inspect.Parameter.empty:
            required.append(parameter.name)
    return {
        "name": name,
        "description": inspect.getdoc(method),
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


def tool_definitions():
    """The tools of a Help me chat, in a fixed order (a stable prefix for prompt caching)."""
    return [tool_definition(name) for name in ALLOWED]


class HelpTools:
    """Runs Help me tool calls on one site, as the operator who opened the chat."""

    def __init__(self, service, identity, site_id):
        self.service, self.identity, self.site_id = service, identity, site_id

    def run(self, name, arguments, call_id):
        """(content, is_error) of one tool call; refusals are returned, never raised."""
        if name not in ALLOWED:
            return f"Help me cannot use {name}", True
        if not isinstance(arguments, dict):
            return "Tool input must be an object", True
        filled = {**arguments, "site_id": self.site_id}
        if name in CHANGES:
            # One key per tool call: a retried call returns the first result (d-idempotency).
            filled["key"] = "help-" + call_id
        try:
            result = self.service.execute(self.identity, name, via="help_me", **filled)
        except DomainError as error:
            return json.dumps(error.as_dict(), ensure_ascii=False), True
        return json.dumps(result, ensure_ascii=False, default=str), False
