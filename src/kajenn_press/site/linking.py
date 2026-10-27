"""Three-way rebase of a linked site template on a new Library version (d-template-conflict).

A linked site template keeps the Library source it was based on. Its node changes are the
difference between that base and the site source, addressed by label path. Rebasing on a
new Library source keeps each side's change where only one side changed a node; a node
changed differently on both sides, or changed by the site and removed or renamed by the
Library, is a conflict. Conflicts are resolved per node by keeping the site version or
taking the Library one; until all are resolved nothing changes.
"""

from dataclasses import dataclass

from genro_bag import Bag

CONTAINER = object()
SITE, LIBRARY = "site", "library"


@dataclass(frozen=True)
class Conflict:
    path: str
    base: tuple | None
    site: tuple | None
    library: tuple | None


def node_entries(source):
    """Label path -> (tag, value, attributes); value is CONTAINER for nested Bags."""
    entries = {}
    for path, node in source.query("#p,#n", deep=True):
        value = CONTAINER if isinstance(node.value, Bag) else node.value
        entries[path] = (node.node_tag, value, dict(node.attr))
    return entries


def child_labels(source, path):
    container = source.get_item(path) if path else source
    return list(container.keys()) if isinstance(container, Bag) else []


def rebase(base, site, library, resolutions=None):
    """Merged source and the conflicts left unresolved; the source is None if any remain."""
    resolutions = resolutions or {}
    entries = {SITE: node_entries(site), LIBRARY: node_entries(library)}
    base_entries = node_entries(base)
    conflicts = []

    def resolution(path):
        """The operator's choice on this node or on its closest resolved ancestor."""
        while path:
            if path in resolutions:
                return resolutions[path]
            path = path.rpartition(".")[0]
        return None

    def site_changed_below(path):
        prefix = path + "."
        paths = {p for p in entries[SITE].keys() | base_entries.keys() if p.startswith(prefix)}
        return any(entries[SITE].get(p) != base_entries.get(p) for p in paths)

    def under_conflict(path):
        return any(path.startswith(c.path + ".") for c in conflicts)

    def chosen(path):
        old, mine = base_entries.get(path), entries[SITE].get(path)
        theirs = entries[LIBRARY].get(path)
        if under_conflict(path):
            return mine
        choice = resolution(path)
        if choice is not None:
            return mine if choice == SITE else theirs
        if mine == old and not (theirs is None and site_changed_below(path)):
            return theirs
        if theirs == old or mine == theirs:
            return mine
        conflicts.append(Conflict(path, displayable(old), displayable(mine), displayable(theirs)))
        return mine

    def merge(target, path):
        order = child_labels(library, path)
        site_order = child_labels(site, path)
        for index, label in enumerate(site_order):
            if label not in order:
                previous = site_order[index - 1] if index else None
                order.insert(order.index(previous) + 1 if previous in order else len(order), label)
        for label in order:
            full = f"{path}.{label}" if path else label
            entry = chosen(full)
            if entry is None:
                continue
            tag, value, attributes = entry
            if value is CONTAINER:
                child = Bag()
                target.set_item(label, child, node_tag=tag, _attributes=attributes)
                merge(child, full)
            else:
                target.set_item(label, value, node_tag=tag, _attributes=attributes)

    merged = Bag()
    merge(merged, "")
    return (None if conflicts else merged), conflicts


def displayable(entry):
    if entry is None:
        return None
    tag, value, attributes = entry
    return (tag, None if value is CONTAINER else value, attributes)
