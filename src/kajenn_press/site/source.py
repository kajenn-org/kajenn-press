"""Template sources as plain Bags, independent of the engine that authored them.

A builder Source saved with its engine class loads only where that engine is installed,
and its loaded nodes carry no builder. A plain Bag keeps tag, label and attributes of
every node; `replay` rebuilds it through a target builder's grammar for rendering.
"""

from genro_bag import Bag


def plain_source(source):
    """Copy a builder Source into a plain Bag, node by node, with tags and attributes."""
    plain = Bag()
    for node in source:
        value = node.value
        plain.set_item(
            node.label,
            plain_source(value) if isinstance(value, Bag) else value,
            node_tag=node.node_tag,
            _attributes=dict(node.attr),
        )
    return plain


def replay(target, plain):
    """Rebuild a plain Source under `target` (a builder Source or one of its nodes)."""
    for node in plain:
        value = node.value
        attributes = dict(node.attr)
        if node.label != node.node_tag:
            attributes["node_label"] = node.label
        args = () if value is None or isinstance(value, Bag) else (value,)
        child = getattr(target, node.node_tag)(*args, **attributes)
        if isinstance(value, Bag):
            replay(child, value)
