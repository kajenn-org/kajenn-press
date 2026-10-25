"""Adapters over qualified public Source/Data and renderer extension APIs."""

import platform
import sys
from html import escape
from importlib import metadata
from pathlib import Path

from .contract import CONTRACT, PREPARATION, QUALIFIED, PreparedHTML, RenderProblem, sha256

# This first static profile deliberately rejects component/sub-builder and
# controller nodes rather than silently dropping essential browser-only output.
STATIC_TAGS = {
    "html",
    "head",
    "title",
    "meta",
    "link",
    "style",
    "script",
    "body",
    "main",
    "header",
    "footer",
    "nav",
    "section",
    "article",
    "aside",
    "div",
    "span",
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "picture",
    "source",
    "figure",
    "figcaption",
    "table",
    "caption",
    "colgroup",
    "col",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "pre",
    "code",
    "blockquote",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "small",
    "sub",
    "sup",
    "mark",
    "abbr",
    "cite",
    "q",
    "time",
    "address",
    "br",
    "hr",
    "wbr",
    "details",
    "summary",
    "audio",
    "video",
    "track",
    "noscript",
    "form",
    "label",
    "input",
    "button",
    "select",
    "option",
    "optgroup",
    "textarea",
    "fieldset",
    "legend",
    "datalist",
    "output",
    "progress",
    "meter",
    "ins",
    "del_",
    "ruby",
    "rt",
    "rp",
    "bdi",
    "bdo",
    "kbd",
    "samp",
    "var",
}


def installed_profile():
    """Exact installed runtime, including engine transitive distributions."""
    versions = {
        name: metadata.version(name)
        for name in (
            *QUALIFIED,
            "genro-tytx",
            "genro-toolbox",
            "httpx",
            "httpcore",
            "anyio",
            "idna",
            "certifi",
            "h11",
            "mdurl",
        )
    }
    if sys.version_info < (3, 15):
        versions["typing-extensions"] = metadata.version("typing-extensions")
    if any(versions[name] != version for name, version in QUALIFIED.items()):
        raise RenderProblem("unqualified_profile", "Installed rendering versions differ")
    return {
        "contract": CONTRACT,
        "preparation": PREPARATION,
        "python": platform.python_version(),
        "versions": versions,
        "adapter_digest": sha256(
            b"".join(
                Path(__file__).with_name(name + ".py").read_bytes()
                for name in ("contract", "engines", "preparation", "worker")
            )
        ),
    }


def make_builder(engine):
    # Optional imports are reached only in the worker/qualification process.
    from genro_builders.contrib.html import HtmlBuilder
    from genro_builders.contrib.html.html_renderer import HtmlRenderer
    from gramlot import GramlotBuilder, GramlotHtmlRenderer

    class FragmentRenderer(HtmlRenderer):
        def rendered_item(self, node, item, runtime_attrs, *, tag, **options):
            if isinstance(item, PreparedHTML):
                if tag in {"script", "style", "title", "textarea"}:
                    raise RenderProblem("invalid_fragment_context", "HTML needs an HTML container")
                item = str(item) + "::HTML"
            elif isinstance(item, str) and item.endswith("::HTML"):
                # Encode the entire ordinary string, including the literal marker.
                # This translation is at the final resolved leaf boundary.
                item = escape(item, quote=False) + "::HTML"
            return super().rendered_item(node, item, runtime_attrs, tag=tag, **options)

    class StaticGramlotRenderer(GramlotHtmlRenderer, FragmentRenderer):
        pass

    class StaticHtmlBuilder(HtmlBuilder):
        @property
        def renderer_html(self):
            return FragmentRenderer(self)

    class StaticGramlotBuilder(GramlotBuilder):
        @property
        def renderer_html(self):
            return StaticGramlotRenderer(self)

    if engine not in {"gramlot", "htmlbuilder"}:
        raise RenderProblem("unsupported_engine", "Unknown template engine")
    return (StaticGramlotBuilder if engine == "gramlot" else StaticHtmlBuilder)()


def populate_data(bag, data, prefix=""):
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            populate_data(bag, value, path)
        else:
            bag.set_item(path, value)


def validate_static_source(builder):
    roots = list(builder.source.query("#p,#n", iter=True, static=True))
    if len(roots) != 1 or roots[0][1].node_tag != "html":
        raise RenderProblem("invalid_document", "Template must author exactly one html root")
    tags = []
    for path, node in builder.source.query("#p,#n", deep=True, iter=True, static=True):
        tag = node.node_tag
        tags.append(tag)
        if tag not in STATIC_TAGS:
            raise RenderProblem(
                "unsupported_static_node", "Node needs an unsupported runtime", path=path, tag=tag
            )
        values = {"value": node.get_value(static=True), **node.attr}
        for name, value in values.items():
            if not isinstance(value, str):
                continue
            if value.startswith("=="):
                raise RenderProblem(
                    "browser_binding", "Browser expression is not static", path=path, attribute=name
                )
            if value.startswith(("^", "=")):
                # v1 supports absolute Data pointers. No implicit unresolved paths.
                pointer = value[1:]
                if not pointer or builder.data.get_node(pointer) is None:
                    raise RenderProblem(
                        "unresolved_data",
                        "Data pointer does not resolve",
                        path=path,
                        attribute=name,
                        pointer=pointer,
                    )
        if (
            tag in {"script", "style"}
            and isinstance(values["value"], str)
            and values["value"].startswith(("^", "="))
        ):
            raise RenderProblem("invalid_fragment_context", "Editorial Data is not code", path=path)
    if "head" not in tags or "body" not in tags:
        raise RenderProblem("invalid_document", "Template needs head and body")
    errors = builder.validate_source()
    if errors:
        raise RenderProblem("invalid_source", "Source violates engine grammar", errors=str(errors))


def render_template(engine, source, data):
    builder = make_builder(engine)
    populate_data(builder.data, data)
    namespace = {"__name__": "kajenn_static_template"}
    exec(compile(source, "<trusted-template>", "exec"), namespace)  # noqa: S102 — trusted worker code
    entry = namespace.get("build")
    if not callable(entry):
        raise RenderProblem("invalid_template", "Template must define build(source, data)")
    if entry(builder.source, builder.data) is not None:
        raise RenderProblem("invalid_template", "build must return None and author Source")
    validate_static_source(builder)
    result = builder.render(mode="html", target=False, doctype=True)
    if not isinstance(result, str):
        raise RenderProblem("invalid_output", "Engine did not return HTML text")
    if not result.lower().startswith("<!doctype html>"):
        result = "<!doctype html>" + result
    return result
