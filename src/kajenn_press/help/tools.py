"""Help me tools: the site operations Sonnet may use, with their schemas (N8-D1, N8-D2).

Each tool is a site operation of `SiteService`, described by the signature and docstring
of its route in `PressApplication`, so REST, MCP and Help me share one surface. The site
id and the idempotency key are filled in here, never by the model. Publishing stays an
operator command: no Publish, rollback, maintenance, visibility, private link, restore,
site creation or deletion is offered.
"""

import base64
import inspect
import json
import re

from ..domain import DomainError
from .svg import clean_svg

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
# Font stacks the site's own pages can use: no font file leaves or enters the site (N8-D4).
FONT_STACKS = {
    "serif": "Georgia, 'Times New Roman', serif",
    "sans": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    "humanist": "'Gill Sans', 'Gill Sans MT', Calibri, sans-serif",
    "rounded": "ui-rounded, 'SF Pro Rounded', system-ui, sans-serif",
    "slab": "Rockwell, 'Roboto Slab', 'DejaVu Serif', serif",
    "mono": "ui-monospace, 'SF Mono', Menlo, Consolas, monospace",
}
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
EXTRA = {
    "offer_choices": {
        "description": (
            "Show the user clickable choices and wait: their pick arrives as the next "
            "message. kind palette: each option has label and colors (2 to 6 #rrggbb). "
            "kind fonts: each option has label, heading and body, names of font stacks: "
            + ", ".join(FONT_STACKS)
            + ". kind svg: each option has label and svg (cleaned before it is shown)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "kind": {"type": "string", "enum": ["palette", "fonts", "svg"]},
                "options": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["question", "kind", "options"],
        },
    },
    "css_asset_add": {
        "description": "Add a CSS stylesheet to the site as an asset; give pages a copy of it.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "css": {"type": "string"}},
            "required": ["name", "css"],
        },
    },
    "svg_asset_add": {
        "description": (
            "Add an SVG drawing (logo, icon) to the site as an image asset; it is cleaned "
            "first: no scripts, event attributes, foreignObject or external references."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "svg": {"type": "string"}},
            "required": ["name", "svg"],
        },
    },
}
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
    extra = [{"name": name, **definition} for name, definition in EXTRA.items()]
    return [tool_definition(name) for name in ALLOWED] + extra


def checked_choices(kind, options):
    """The options as the tab shows them: colours checked, stacks resolved, SVG cleaned."""
    if not isinstance(options, list) or not 2 <= len(options) <= 6:
        raise DomainError("invalid_input", "Offer 2 to 6 options")
    shown = []
    for option in options:
        if not isinstance(option, dict) or not str(option.get("label", "")).strip():
            raise DomainError("invalid_input", "Every option has a label")
        label = str(option["label"]).strip()
        if kind == "palette":
            colors = option.get("colors")
            if not isinstance(colors, list) or not 2 <= len(colors) <= 6:
                raise DomainError("invalid_input", "A palette has 2 to 6 colours")
            if not all(isinstance(c, str) and COLOR.fullmatch(c) for c in colors):
                raise DomainError("invalid_input", "Colours are written #rrggbb")
            shown.append({"label": label, "colors": colors})
        elif kind == "fonts":
            stacks = [option.get("heading"), option.get("body")]
            if not all(stack in FONT_STACKS for stack in stacks):
                raise DomainError("invalid_input", "Fonts are names of: " + ", ".join(FONT_STACKS))
            shown.append(
                {
                    "label": label,
                    "heading": FONT_STACKS[stacks[0]],
                    "body": FONT_STACKS[stacks[1]],
                }
            )
        elif kind == "svg":
            shown.append({"label": label, "svg": clean_svg(option.get("svg"))})
        else:
            raise DomainError("invalid_input", "kind is palette, fonts or svg")
    return shown


class HelpTools:
    """Runs Help me tool calls on one site, as the operator who opened the chat."""

    def __init__(self, service, identity, site_id):
        self.service, self.identity, self.site_id = service, identity, site_id

    def run(self, name, arguments, call_id):
        """(content, is_error) of one tool call; refusals are returned, never raised."""
        if name not in ALLOWED and name not in EXTRA:
            return f"Help me cannot use {name}", True
        if not isinstance(arguments, dict):
            return "Tool input must be an object", True
        try:
            result = self.call(name, arguments, call_id)
        except DomainError as error:
            return json.dumps(error.as_dict(), ensure_ascii=False), True
        return json.dumps(result, ensure_ascii=False, default=str), False

    def call(self, name, arguments, call_id):
        if name == "offer_choices":
            choices = checked_choices(arguments.get("kind"), arguments.get("options"))
            return {
                "question": str(arguments.get("question", "")),
                "kind": arguments["kind"],
                "choices": choices,
                "shown": "The user sees the choices; their pick arrives as the next message.",
            }
        if name == "css_asset_add":
            data, kind, mime = arguments.get("css"), "css", "text/css"
        elif name == "svg_asset_add":
            data, kind, mime = clean_svg(arguments.get("svg")), "media", "image/svg+xml"
        else:
            filled = {**arguments, "site_id": self.site_id}
            if name in CHANGES:
                # One key per tool call: a retried call returns the first result (d-idempotency).
                filled["key"] = "help-" + call_id
            return self.service.execute(self.identity, name, via="help_me", **filled)
        if not isinstance(data, str):
            raise DomainError("invalid_input", "The asset text is a string")
        return self.service.execute(
            self.identity,
            "asset_add",
            via="help_me",
            site_id=self.site_id,
            key="help-" + call_id,
            name=arguments.get("name"),
            kind=kind,
            data_base64=base64.b64encode(data.encode("utf-8")).decode("ascii"),
            mime_type=mime,
        )
