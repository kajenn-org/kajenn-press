"""A site as one Bag: templates, contents, assets and pages.

A page holds copies, never references: a copy of its template, copies of the contents
assigned to its slots and copies of its assets. Every copy records the id of its original
and the digest of the original at copy time, so later changes on either side can be told
apart. Template sources are plain Bags (tag, label and attributes on each node) with the
name of their engine; the render worker rebuilds them through that engine's grammar.
"""

import difflib
import hashlib
from dataclasses import dataclass
from uuid import uuid4

from genro_bag import Bag

from ..domain import DomainError
from .linking import LIBRARY, SITE, rebase
from .slots import template_slots

ENGINES = {"gramlot", "htmlbuilder"}
CONTENT_FORMATS = {"html", "markdown"}
ASSET_KINDS = {"css", "javascript", "media"}
SECTIONS = ("templates", "template_bases", "contents", "assets", "pages")
PAGE_SECTIONS = ("template", "slots", "unplaced", "assets", "data")


def new_id():
    return uuid4().hex


def value_digest(value):
    """SHA-256 of a copyable value: text, bytes or a Bag in TYTX JSON."""
    if isinstance(value, Bag):
        raw = value.to_tytx(transport="json").encode("utf-8")
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raise DomainError("invalid_input", "Only text, bytes and Bags can be copied")
    return hashlib.sha256(raw).hexdigest()


def copy_value(value):
    return value.deepcopy() if isinstance(value, Bag) else value


def text_difference(copy, original):
    """Unified diff from a text copy to its original; None for bytes and Bags."""
    if not (isinstance(copy, str) and isinstance(original, str)):
        return None
    return "".join(
        difflib.unified_diff(
            copy.splitlines(keepends=True), original.splitlines(keepends=True), "copy", "original"
        )
    )


@dataclass(frozen=True)
class UpdateItem:
    page_id: str
    path: str
    locally_changed: bool
    up_to_date: bool
    selected: bool
    difference: str | None


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise DomainError("invalid_input", f"A nonempty {label} is required")
    return value


class Page:
    """View on one page Bag inside a site."""

    def __init__(self, site, page_id):
        self.site = site
        self.page_id = page_id

    @property
    def node(self):
        return self.site.node("pages", self.page_id)

    @property
    def bag(self):
        return self.node.value

    @property
    def name(self):
        return self.node.attr["name"]

    @property
    def template(self):
        """The page's copy of its template: attributes and source Bag."""
        return self.bag.get_node("template")

    @property
    def slots(self):
        return self.bag.get_item("slots")

    @property
    def unplaced(self):
        return self.bag.get_item("unplaced")

    @property
    def assets(self):
        return self.bag.get_item("assets")


class Site:
    """One site Bag. Ids are stable across saves; names are labels for people."""

    def __init__(self, bag):
        self.bag = bag

    @classmethod
    def create(cls, name):
        bag = Bag()
        bag.set_item(
            "info", None, _attributes={"site_id": new_id(), "name": required_text(name, "name")}
        )
        for section in SECTIONS:
            bag.set_item(section, Bag())
        return cls(bag)

    @property
    def site_id(self):
        return self.bag.get_node("info").attr["site_id"]

    @property
    def name(self):
        return self.bag.get_node("info").attr["name"]

    def section(self, name):
        return self.bag.get_item(name)

    def node(self, section, item_id):
        node = self.section(section).get_node(item_id)
        if node is None:
            raise DomainError("not_found", f"No {section[:-1]} {item_id}", resource_id=item_id)
        return node

    def add_template(self, name, engine, source):
        if engine not in ENGINES:
            raise DomainError("invalid_input", "Unknown template engine")
        if not isinstance(source, Bag):
            raise DomainError("invalid_input", "A template source is a Bag")
        return self._add(
            "templates", source.deepcopy(), name=required_text(name, "name"), engine=engine
        )

    def add_content(self, name, content_format, text):
        if content_format not in CONTENT_FORMATS:
            raise DomainError("invalid_input", "Content format is html or markdown")
        if not isinstance(text, str):
            raise DomainError("invalid_input", "Content text is a string")
        return self._add("contents", text, name=required_text(name, "name"), format=content_format)

    def add_asset(self, name, kind, data, mime_type):
        if kind not in ASSET_KINDS:
            raise DomainError("invalid_input", "Asset kind is css, javascript or media")
        if not isinstance(data, bytes):
            raise DomainError("invalid_input", "Asset data are bytes")
        return self._add(
            "assets",
            data,
            name=required_text(name, "name"),
            kind=kind,
            mime_type=required_text(mime_type, "MIME type"),
        )

    def add_page(self, name, template_id):
        """A new page with a copy of a site template and no slot assigned yet."""
        original = self.node("templates", template_id)
        page = Bag()
        page.set_item(
            "template",
            copy_value(original.value),
            _attributes={**original.attr, **self.copy_attributes(template_id, original)},
        )
        for section in PAGE_SECTIONS[1:]:
            page.set_item(section, Bag())
        return self._add("pages", page, name=required_text(name, "name"))

    def import_template(self, library, library_template_id, linked):
        """Bring a Library template into the site, linked to its future versions or not."""
        original = library.node("templates", library_template_id)
        attributes = {
            "name": original.attr["name"],
            "engine": original.attr["engine"],
            "library_id": library_template_id,
            "library_digest": value_digest(original.value),
            "linked": bool(linked),
        }
        template_id = self._add("templates", copy_value(original.value), **attributes)
        if linked:
            self.section("template_bases").set_item(template_id, copy_value(original.value))
        return template_id

    def rebase_template(self, template_id, library, resolutions=None):
        """Rebase a linked template on the current Library version (d-template-conflict).

        Returns the conflicts left; when there are none the template takes the merged
        source and records the new Library version as its base.
        """
        template = self.node("templates", template_id)
        if not template.attr.get("linked"):
            raise DomainError("invalid_input", "Only a linked template follows the Library")
        if any(choice not in (SITE, LIBRARY) for choice in (resolutions or {}).values()):
            raise DomainError("invalid_input", "A resolution keeps site or takes library")
        current = library.node("templates", template.attr["library_id"])
        base = self.section("template_bases").get_node(template_id)
        merged, conflicts = rebase(base.value, template.value, current.value, resolutions)
        if merged is not None:
            template.value = merged
            base.value = copy_value(current.value)
            template.attr["library_digest"] = value_digest(current.value)
        return conflicts

    def page(self, page_id):
        self.node("pages", page_id)
        return Page(self, page_id)

    def copy_attributes(self, original_id, original):
        return {"original_id": original_id, "original_digest": value_digest(original.value)}

    def original(self, original_id):
        """The site template, content or asset with this id, and its section."""
        for section in ("templates", "contents", "assets"):
            node = self.section(section).get_node(original_id)
            if node is not None:
                return section, node
        raise DomainError("not_found", f"No original {original_id}", resource_id=original_id)

    def assign_content(self, page_id, slot_name, content_id):
        """Copy a content into a slot of the page; a copy already there becomes unplaced."""
        page = self.page(page_id)
        if slot_name not in {slot.name for slot in template_slots(page.template.value)}:
            raise DomainError("invalid_input", f"The page template has no slot {slot_name}")
        for node in list(page.slots.nodes):
            if node.attr["slot"] == slot_name:
                self._unplace(page, node)
        original = self.node("contents", content_id)
        return self._place_copy(page.slots, content_id, original, slot=slot_name)

    def add_page_asset(self, page_id, asset_id):
        return self._place_copy(self.page(page_id).assets, asset_id, self.node("assets", asset_id))

    def uses(self, original_id):
        """Every copy of an original: (page id, path of the copy inside the page Bag)."""
        found = []
        for page_node in self.section("pages").nodes:
            page = page_node.value
            if page.get_node("template").attr.get("original_id") == original_id:
                found.append((page_node.label, "template"))
            for section in PAGE_SECTIONS[1:]:
                for node in page.get_item(section).nodes:
                    if node.attr.get("original_id") == original_id:
                        found.append((page_node.label, f"{section}.{node.label}"))
        return found

    def use_count(self, original_id):
        return len(self.uses(original_id))

    def update_plan(self, original_id):
        """What Update would do for each copy of an original (d-update-local)."""
        _section, original = self.original(original_id)
        current = value_digest(original.value)
        plan = []
        for page_id, path in self.uses(original_id):
            copy = self.page(page_id).bag.get_node(path)
            copy_digest = value_digest(copy.value)
            changed = copy_digest != copy.attr["original_digest"]
            plan.append(
                UpdateItem(
                    page_id=page_id,
                    path=path,
                    locally_changed=changed,
                    up_to_date=copy_digest == current,
                    selected=not changed and copy_digest != current,
                    difference=text_difference(copy.value, original.value),
                )
            )
        return plan

    def apply_update(self, original_id, selected):
        """Replace the selected copies, given as (page id, path), with the current original.

        A page whose new template copy no longer declares a slot keeps that slot's content
        copy among its unplaced contents (d-slot-removed).
        """
        section, original = self.original(original_id)
        known = set(self.uses(original_id))
        for page_id, path in selected:
            if (page_id, path) not in known:
                raise DomainError("invalid_input", f"No copy of {original_id} at {page_id} {path}")
            copy = self.page(page_id).bag.get_node(path)
            copy.value = copy_value(original.value)
            copy.attr.update(self.copy_attributes(original_id, original))
            if section == "templates":
                self._unplace_missing_slots(self.page(page_id))

    def switch_plan(self, page_id, template_id):
        """Proposed mapping from the page's slots to the new template's slots, by name."""
        page = self.page(page_id)
        new_names = {
            slot.name for slot in template_slots(self.node("templates", template_id).value)
        }
        return {
            slot.name: (slot.name if slot.name in new_names else None)
            for slot in template_slots(page.template.value)
        }

    def switch_template(self, page_id, template_id, mapping):
        """Give the page a copy of another template; contents follow the confirmed mapping.

        `mapping` sends each old slot name to a new slot name or None; contents of slots
        mapped to None, or not mapped, become unplaced (d-template-switch).
        """
        page = self.page(page_id)
        original = self.node("templates", template_id)
        new_names = {slot.name for slot in template_slots(original.value)}
        targets = [name for name in mapping.values() if name is not None]
        if not set(targets) <= new_names:
            raise DomainError("invalid_input", "Mapping targets a slot the template lacks")
        if len(targets) != len(set(targets)):
            raise DomainError("invalid_input", "Two slots are mapped to the same slot")
        page.bag.set_item(
            "template",
            copy_value(original.value),
            _attributes={**original.attr, **self.copy_attributes(template_id, original)},
        )
        for node in list(page.slots.nodes):
            target = mapping.get(node.attr["slot"])
            if target is None:
                self._unplace(page, node)
            else:
                node.attr["slot"] = target

    def place_unplaced(self, page_id, key, slot_name):
        """Move an unplaced content copy into a free slot of the page."""
        page = self.page(page_id)
        node = page.unplaced.get_node(key)
        if node is None:
            raise DomainError("not_found", f"No unplaced content {key}")
        if slot_name not in {slot.name for slot in template_slots(page.template.value)}:
            raise DomainError("invalid_input", f"The page template has no slot {slot_name}")
        if any(n.attr["slot"] == slot_name for n in page.slots.nodes):
            raise DomainError("conflict", f"Slot {slot_name} already holds a content")
        page.unplaced.pop(key)
        page.slots.set_item(key, node.value, _attributes={**node.attr, "slot": slot_name})

    def page_check(self, page_id):
        """Empty slots and unplaced contents of a page, for the check before Publish."""
        page = self.page(page_id)
        filled = {node.attr["slot"] for node in page.slots.nodes}
        return {
            "empty_slots": [
                slot.name for slot in template_slots(page.template.value) if slot.name not in filled
            ],
            "unplaced": [node.label for node in page.unplaced.nodes],
        }

    def _unplace(self, page, node):
        page.slots.pop(node.label)
        attributes = {k: v for k, v in node.attr.items() if k != "slot"}
        page.unplaced.set_item(node.label, node.value, _attributes=attributes)

    def _unplace_missing_slots(self, page):
        names = {slot.name for slot in template_slots(page.template.value)}
        for node in list(page.slots.nodes):
            if node.attr["slot"] not in names:
                self._unplace(page, node)

    def _place_copy(self, target, original_id, original, **extra):
        key = new_id()
        target.set_item(
            key,
            copy_value(original.value),
            _attributes={**original.attr, **self.copy_attributes(original_id, original), **extra},
        )
        return key

    def _add(self, section, value, **attributes):
        item_id = new_id()
        self.section(section).set_item(item_id, value, _attributes=attributes)
        return item_id


class Library(Site):
    """Templates, contents and assets shared by several sites; it has no pages."""

    def add_page(self, name, template_id):
        raise DomainError("invalid_input", "The Library has no pages")
