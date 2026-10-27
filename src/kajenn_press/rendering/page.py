"""Page Bag rendering in the worker: template source, slot contents, Data and resolvers.

Runs only in the render interpreter. The template is a plain Source rebuilt through the
engine grammar; each slot node receives its prepared content; the page Data may hold
`ConnectionResolver` nodes, bound to the deployment's named connections.
"""

from genro_bag import Bag

from ..site.slots import template_slots
from ..site.source import plain_source, replay
from .contract import RenderProblem
from .engines import make_builder, populate_data, validate_static_source
from .preparation import prepare_blocks
from .resolvers import ConnectionResolver


def plain_template(engine, python_source):
    """Run a Python `build(source, data)` once and return its Source as a plain Bag."""
    builder = make_builder(engine)
    namespace = {"__name__": "kajenn_page_template"}
    exec(compile(python_source, "<trusted-template>", "exec"), namespace)  # noqa: S102
    entry = namespace.get("build")
    if not callable(entry):
        raise RenderProblem("invalid_template", "Template must define build(source, data)")
    entry(builder.source, builder.data)
    return plain_source(builder.source)


def render_page(engine, template, slots, data, page_data, connections, resource_id):
    """HTML of a page and the preparation diagnostics.

    `slots` maps slot names to {"format", "source"}; `data` is plain JSON Data such as
    `page.title` and asset URLs; `page_data` is the page's Data Bag, possibly with
    connection resolvers.
    """
    declared = template_slots(template)
    prepared, diagnostics = prepare_blocks(
        slots,
        {
            slot.name: {"format": slots[slot.name]["format"], "required": False}
            for slot in declared
            if slot.name in slots
        },
        resource_id,
    )
    builder = make_builder(engine)
    populate_data(builder.data, data)
    for node in page_data:
        # Bind before insertion: placing a resolver in Data may already read it.
        resolver = node.resolver
        if resolver is not None:
            if not isinstance(resolver, ConnectionResolver):
                raise RenderProblem("invalid_resolver", "Only connection resolvers render")
            resolver.bind(connections)
            builder.data.set_item(node.label, None, _attributes=dict(node.attr), resolver=resolver)
        else:
            builder.data.set_item(node.label, node.static_value, _attributes=dict(node.attr))
    replay(builder.source, template)
    for slot in declared:
        if slot.name in prepared:
            builder.source.get_node(slot.path).value = prepared[slot.name]
    validate_static_source(builder)
    result = builder.render(mode="html", target=False, doctype=True)
    if not result.lower().startswith("<!doctype html>"):
        result = "<!doctype html>" + result
    return result, diagnostics


def page_data_bag(raw):
    return Bag.from_tytx(raw) if raw else Bag()
