"""Site operations shared by REST, MCP and the administration (N3).

Same entry pattern as `EditorialService.execute`: a trusted identity, bound arguments and
grants checked by `AccessPolicy` on `site:<id>`. Every change works on the holder's local
working copy; `site_save` makes it an S3 version. Changes carry an idempotency key, need
the editing lock and are recorded in the audit log.
"""

import base64
import binascii
import inspect
from dataclasses import asdict
from datetime import UTC, datetime
from threading import RLock

from genro_bag import Bag, BagException

from ..catalog.filesystem import digest, private_directory
from ..domain import DomainError
from .lock import EditingLock
from .model import Site, new_id
from .receipts import Receipts
from .render import page_request
from .storage import WorkingCopy, unpack

READS = {
    "site_export",
    "site_read",
    "site_versions",
    "copies_update_plan",
    "template_switch_plan",
    "page_check",
    "page_render",
}
CHANGES = {
    "template_add",
    "content_add",
    "content_save",
    "asset_add",
    "page_add",
    "page_url_set",
    "page_asset_add",
    "slot_assign",
    "copies_update",
    "template_switch",
    "unplaced_place",
}
CONTROLS = {"site_new", "site_open", "site_close", "site_save", "site_restore"}
LIBRARY = {"site_import", "starter_save", "starters_list"}
PUBLISHING = {"publish_plan", "publish", "page_versions", "page_rollback", "site_rollback"}
PUBLISHING_READS = {"publish_plan", "page_versions"}
OPERATIONS = READS | CHANGES | CONTROLS | LIBRARY | PUBLISHING
PERMISSIONS = {"page_render": "build", "site_versions": "read"}


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def decode_base64(value):
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise DomainError("invalid_input", "data_base64 is not base64") from exc


class SiteService:
    def __init__(self, root, store, policy, worker=None, connections=None, publisher=None):
        self.root = private_directory(root)
        self.store = store
        self.policy = policy
        self.worker = worker
        self.connections = connections or {}
        self.publisher = publisher
        self.lock = EditingLock(self.root / "locks")
        self.receipts = Receipts(self.root / "receipts")
        self._mutex = RLock()

    def working_copy(self, site_id):
        return WorkingCopy(self.root / "working" / site_id)

    def execute(self, identity, operation, **arguments):
        if not identity:
            raise DomainError("unauthenticated", "An authenticated principal is required")
        if operation not in OPERATIONS:
            raise DomainError("invalid_operation", "Unknown site operation")
        handler = getattr(self, "_" + operation)
        signature = inspect.signature(handler)
        if operation in CHANGES:
            # Public form: (identity, site_id, key, ...); the handler receives the loaded site.
            parameters = list(signature.parameters.values())
            public = [
                parameters[0],
                inspect.Parameter("site_id", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("key", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                *parameters[2:],
            ]
            signature = signature.replace(parameters=public)
        try:
            bound = signature.bind(identity, **arguments)
        except TypeError as exc:
            raise DomainError("invalid_input", str(exc)) from exc
        bound.apply_defaults()
        params = {k: v for k, v in bound.arguments.items() if k != "identity"}
        with self._mutex:
            if operation in ("site_new", "site_import"):
                self.policy.require(identity, "installation", "create_site")
                return handler(identity, **params)
            if operation == "starters_list":
                self.policy.require(identity, "library", "read")
                return handler(identity, **params)
            if operation == "starter_save":
                self.policy.require(identity, "library", "write")
                self.policy.require(identity, "site:" + params["site_id"], "read")
                return handler(identity, **params)
            site_id = params["site_id"]
            scope = "site:" + site_id
            if operation in PUBLISHING:
                if self.publisher is None:
                    raise DomainError("unavailable", "Configure the release bucket first")
                self.policy.require(identity, scope, "publish")
                if operation in PUBLISHING_READS:
                    return handler(identity, **params)
                self.policy.require(identity, scope, "write")
                self.lock.require(site_id, identity)
                return handler(identity, **params)
            if operation in READS:
                self.policy.require(identity, scope, PERMISSIONS.get(operation, "read"))
                return handler(identity, **params)
            self.policy.require(identity, scope, "write")
            if operation == "site_open":
                return handler(identity, **params)
            self.lock.require(site_id, identity)
            if operation in ("site_close", "site_save", "site_restore"):
                return handler(identity, **params)
            key = params.pop("key")
            return self.receipts.run(
                identity, key, operation, params, lambda: self._change(identity, operation, params)
            )

    def _change(self, identity, operation, params):
        copy = self.working_copy(params["site_id"])
        site = copy.load()
        arguments = {k: v for k, v in params.items() if k != "site_id"}
        result = getattr(self, "_" + operation)(identity, site, **arguments)
        site.record(identity, operation, now())
        copy.save(site)
        return result

    def site(self, identity, site_id):
        """The holder's working copy, or the latest saved version for anyone else."""
        if self.lock.holder(site_id) == identity:
            return self.working_copy(site_id).load()
        return self.store.open(site_id)

    # Controls

    def _site_new(self, identity, key, name, starter_id=None):
        def create():
            if starter_id is None:
                site = Site.create(name)
            else:
                site = self.store.starter_open(starter_id).reidentify(name)
            site.record(identity, "site_new", now(), starter_id=starter_id)
            return self._first_save(identity, site)

        arguments = {"name": name, "starter_id": starter_id}
        return self.receipts.run(identity, key, "site_new", arguments, create)

    def _site_import(self, identity, key, data_base64, name=None):
        def create():
            site = unpack(decode_base64(data_base64)).reidentify(name)
            site.record(identity, "site_import", now())
            return self._first_save(identity, site)

        arguments = {"sha256": digest(data_base64.encode()), "name": name}
        return self.receipts.run(identity, key, "site_import", arguments, create)

    def _first_save(self, identity, site):
        version = self.store.save(site)
        self.working_copy(site.site_id).save(site)
        self.lock.take(site.site_id, identity)
        return {"site_id": site.site_id, "version_id": version}

    def _starter_save(self, identity, key, site_id, name):
        def keep():
            starter_id = new_id()
            self.store.starter_save(starter_id, self.store.open(site_id).reidentify(name))
            return {"starter_id": starter_id}

        return self.receipts.run(
            identity, key, "starter_save", {"site_id": site_id, "name": name}, keep
        )

    def _publish_plan(self, identity, site_id):
        return self.publisher.plan(self.site(identity, site_id))

    def _publish(self, identity, site_id, key, selected):
        """Save the source, then publish the selected pages from that version."""

        def run():
            copy = self.working_copy(site_id)
            site = copy.load()
            site.record(identity, "publish", now(), pages=len(selected))
            copy.save(site)
            version = self.store.save_from(copy)
            return {"source_version": version, **self.publisher.publish(site, version, selected)}

        arguments = {"site_id": site_id, "selected": selected}
        return self.receipts.run(identity, key, "publish", arguments, run)

    def _page_versions(self, identity, site_id, page_id):
        return self.publisher.page_versions(site_id, page_id)

    def _page_rollback(self, identity, site_id, key, page_id, version_id):
        def run():
            result = self.publisher.page_rollback(site_id, page_id, version_id)
            self._record(identity, site_id, "page_rollback", page_id=page_id, to=version_id)
            return result

        arguments = {"site_id": site_id, "page_id": page_id, "version_id": version_id}
        return self.receipts.run(identity, key, "page_rollback", arguments, run)

    def _site_rollback(self, identity, site_id, key, version_id):
        """Restore a source version and publish every page from it."""

        def run():
            version = self.store.restore(site_id, version_id)
            site = self.store.load_into(site_id, self.working_copy(site_id))
            selected = [
                p["page_id"] for p in self.publisher.plan(site) if p["state"] != "unchanged"
            ]
            result = self.publisher.publish(site, version, selected)
            self._record(identity, site_id, "site_rollback", to=version_id)
            return {"source_version": version, **result}

        arguments = {"site_id": site_id, "version_id": version_id}
        return self.receipts.run(identity, key, "site_rollback", arguments, run)

    def _record(self, identity, site_id, operation, **details):
        copy = self.working_copy(site_id)
        site = copy.load()
        site.record(identity, operation, now(), **details)
        copy.save(site)

    def _starters_list(self, identity):
        return self.store.starters()

    def _site_open(self, identity, site_id, force=False):
        """Take the site; unless already held by the caller, edit its latest version."""
        held = self.lock.holder(site_id) == identity
        taken = self.lock.take(site_id, identity, force=force)
        if not held:
            self.store.load_into(site_id, self.working_copy(site_id))
        return taken

    def _site_close(self, identity, site_id):
        self.lock.release(site_id, identity)
        return {"holder": None}

    def _site_save(self, identity, site_id):
        copy = self.working_copy(site_id)
        site = copy.load()
        site.record(identity, "site_save", now())
        copy.save(site)
        return {"version_id": self.store.save_from(copy)}

    def _site_restore(self, identity, site_id, version_id):
        version = self.store.restore(site_id, version_id)
        site = self.store.load_into(site_id, self.working_copy(site_id))
        site.record(identity, "site_restore", now(), restored=version_id)
        self.working_copy(site_id).save(site)
        return {"version_id": version}

    # Reads

    def _site_read(self, identity, site_id):
        site = self.site(identity, site_id)

        def items(section):
            return [
                {"id": n.label, **n.attr, "uses": site.use_count(n.label)}
                for n in site.section(section).nodes
            ]

        pages = []
        for node in site.section("pages").nodes:
            page = site.page(node.label)
            pages.append(
                {
                    "id": node.label,
                    "name": page.name,
                    "url": node.attr["url"],
                    "template_id": page.template.attr["original_id"],
                    "slots": {n.attr["slot"]: n.attr["original_id"] for n in page.slots.nodes},
                    "unplaced": [n.label for n in page.unplaced.nodes],
                }
            )
        return {
            "site_id": site.site_id,
            "name": site.name,
            "holder": self.lock.holder(site_id),
            "templates": items("templates"),
            "contents": items("contents"),
            "assets": items("assets"),
            "pages": pages,
            "redirects": site.redirects(),
        }

    def _site_export(self, identity, site_id, version_id=None):
        data = self.store.export(site_id, version_id)
        return {"site_id": site_id, "data_base64": base64.b64encode(data).decode("ascii")}

    def _site_versions(self, identity, site_id):
        return [
            {**v, "last_modified": str(v["last_modified"])} for v in self.store.versions(site_id)
        ]

    def _copies_update_plan(self, identity, site_id, original_id):
        return [asdict(item) for item in self.site(identity, site_id).update_plan(original_id)]

    def _template_switch_plan(self, identity, site_id, page_id, template_id):
        return self.site(identity, site_id).switch_plan(page_id, template_id)

    def _page_check(self, identity, site_id, page_id):
        return self.site(identity, site_id).page_check(page_id)

    def _page_render(self, identity, site_id, page_id):
        if self.worker is None:
            raise DomainError("unavailable", "Configure the render worker first")
        site = self.site(identity, site_id)
        return self.worker.render_page(page_request(site, page_id, self.connections))

    # Changes on the working copy

    def _template_add(self, identity, site, name, engine, source=None, python_source=None):
        if (source is None) == (python_source is None):
            raise DomainError("invalid_input", "Give either source or python_source")
        if python_source is not None:
            if self.worker is None:
                raise DomainError("unavailable", "Configure the render worker first")
            plain = self.worker.plain_template(engine, python_source)
        else:
            try:
                plain = Bag.from_tytx(source)
            except (BagException, TypeError, ValueError) as exc:
                raise DomainError("invalid_input", "source is not a TYTX Bag") from exc
        return {"template_id": site.add_template(name, engine, plain)}

    def _content_add(self, identity, site, name, format, text):
        return {"content_id": site.add_content(name, format, text)}

    def _content_save(self, identity, site, content_id, text):
        if not isinstance(text, str):
            raise DomainError("invalid_input", "Content text is a string")
        site.node("contents", content_id).value = text
        return {"content_id": content_id}

    def _asset_add(self, identity, site, name, kind, data_base64, mime_type):
        return {"asset_id": site.add_asset(name, kind, decode_base64(data_base64), mime_type)}

    def _page_add(self, identity, site, name, template_id):
        return {"page_id": site.add_page(name, template_id)}

    def _page_url_set(self, identity, site, page_id, url):
        site.set_page_url(page_id, url)
        return {"page_id": page_id, "url": url}

    def _page_asset_add(self, identity, site, page_id, asset_id):
        return {"copy": site.add_page_asset(page_id, asset_id)}

    def _slot_assign(self, identity, site, page_id, slot, content_id):
        return {"copy": site.assign_content(page_id, slot, content_id)}

    def _copies_update(self, identity, site, original_id, selected):
        site.apply_update(original_id, [tuple(item) for item in selected])
        return {"updated": len(selected)}

    def _template_switch(self, identity, site, page_id, template_id, mapping):
        site.switch_template(page_id, template_id, mapping)
        return {"page_id": page_id, "template_id": template_id}

    def _unplaced_place(self, identity, site, page_id, copy_id, slot):
        site.place_unplaced(page_id, copy_id, slot)
        return {"page_id": page_id, "slot": slot}
