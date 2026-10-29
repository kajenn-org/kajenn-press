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
from ..rendering.contract import RenderProblem
from .dns import dns_check, dns_plan, public_lookup
from .golive import AgentClient, address_answers, go_live
from .languages import (
    confirm_translation,
    language_url,
    set_languages,
    set_page_url,
    set_site_text,
    set_translation,
    site_languages,
    translation_states,
)
from .lock import EditingLock
from .model import ENGINES, Site, new_id
from .published import DEFAULT_SERVER, page_fingerprint
from .receipts import Receipts
from .render import page_request
from .seo import (
    effective_seo,
    page_images,
    seo_check,
    set_image_alt,
    set_page_seo,
    stored_seo,
)
from .servers import ServerRegistry
from .slots import template_slots
from .storage import WorkingCopy, unpack

READS = {
    "site_export",
    "site_read",
    "site_versions",
    "copies_update_plan",
    "template_switch_plan",
    "page_check",
    "page_render",
    "seo_check",
}
CHANGES = {
    "template_add",
    "content_add",
    "content_save",
    "asset_add",
    "asset_save",
    "page_add",
    "page_url_set",
    "page_seo_set",
    "page_alt_set",
    "site_languages_set",
    "content_translate",
    "site_text_set",
    "translation_confirm",
    "folder_add",
    "tree_move",
    "page_asset_add",
    "slot_assign",
    "copies_update",
    "template_switch",
    "unplaced_place",
}
CONTROLS = {"site_new", "site_open", "site_close", "site_save", "site_restore"}
LIBRARY = {"site_import", "starter_save", "starters_list", "site_list"}
SERVERS = {"server_add", "server_list", "server_remove"}
PUBLISHING = {
    "publish_plan",
    "publish",
    "page_versions",
    "page_rollback",
    "site_rollback",
    "maintenance_set",
    "site_visibility_set",
    "private_link",
    "publication_state",
    "site_server_set",
    "dns_plan",
    "dns_check",
    "site_go_live",
}
PUBLISHING_READS = {
    "publish_plan",
    "page_versions",
    "private_link",
    "publication_state",
    "dns_plan",
    "dns_check",
}
OPERATIONS = READS | CHANGES | CONTROLS | LIBRARY | PUBLISHING | SERVERS
PERMISSIONS = {"page_render": "build", "site_versions": "read"}


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def decode_base64(value):
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise DomainError("invalid_input", "data_base64 is not base64") from exc


class SiteService:
    def __init__(
        self,
        root,
        store,
        policy,
        worker=None,
        connections=None,
        publisher=None,
        agent_tokens=None,
    ):
        self.root = private_directory(root)
        self.store = store
        self.policy = policy
        self.worker = worker
        self.connections = connections or {}
        self.publisher = publisher
        self.lock = EditingLock(self.root / "locks")
        self.servers = ServerRegistry(store)
        # Public resolvers, real agents and real addresses; tests replace them (N7b-D3).
        self.dns_lookup = public_lookup
        self.agents = AgentClient(agent_tokens) if agent_tokens else None
        self.address_answers = address_answers
        self.receipts = Receipts(self.root / "receipts")
        self._mutex = RLock()

    def working_copy(self, site_id):
        return WorkingCopy(self.root / "working" / site_id)

    def execute(self, identity, operation, *, via=None, **arguments):
        """Run one operation; `via="help_me"` marks changes made through Help me (d-audit)."""
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
        params = {k: v for k, v in bound.arguments.items() if k not in ("identity", "via")}
        with self._mutex:
            if operation in ("site_new", "site_import"):
                self.policy.require(identity, "installation", "create_site")
                return handler(identity, **params)
            if operation in ("site_list", "server_list"):
                return handler(identity, **params)
            if operation in SERVERS:
                # Registering servers is an installation grant (N7b-D2).
                self.policy.require(identity, "installation", "servers")
                key = params.pop("key")
                return self.receipts.run(
                    identity, key, operation, params, lambda: handler(identity, key, **params)
                )
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
            if operation == "site_save":
                return handler(identity, via=via, **params)
            if operation in ("site_close", "site_restore"):
                return handler(identity, **params)
            key = params.pop("key")
            return self.receipts.run(
                identity,
                key,
                operation,
                params,
                lambda: self._change(identity, operation, params, via),
            )

    def _change(self, identity, operation, params, via=None):
        copy = self.working_copy(params["site_id"])
        site = copy.load()
        arguments = {k: v for k, v in params.items() if k != "site_id"}
        result = getattr(self, "_" + operation)(identity, site, **arguments)
        site.record(identity, operation, now(), via=via)
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

    def _maintenance_set(self, identity, site_id, key, on):
        def run():
            result = self.publisher.set_maintenance(site_id, on)
            self._record(identity, site_id, "maintenance_set", on=bool(on))
            return result

        return self.receipts.run(
            identity, key, "maintenance_set", {"site_id": site_id, "on": bool(on)}, run
        )

    def _site_visibility_set(self, identity, site_id, key, state):
        def run():
            result = self.publisher.set_visibility(self.site(identity, site_id), state)
            self._record(identity, site_id, "site_visibility_set", state=state)
            return result

        return self.receipts.run(
            identity, key, "site_visibility_set", {"site_id": site_id, "state": state}, run
        )

    def _publication_state(self, identity, site_id):
        return self.publisher.state(self.site(identity, site_id))

    def _site_server_set(self, identity, site_id, key, server, alias=True):
        """Choose the server and whether the other name redirects; a bound site moves."""

        def run():
            if server != DEFAULT_SERVER:
                self.servers.get(server)
            copy = self.working_copy(site_id)
            site = copy.load()
            info = site.bag.get_node("info").attr
            info["server"] = server
            info["alias"] = bool(alias)
            site.record(identity, "site_server_set", now(), server=server)
            copy.save(site)
            self.publisher.set_server(site)
            return {"server": server, "alias": bool(alias)}

        arguments = {"site_id": site_id, "server": server, "alias": bool(alias)}
        return self.receipts.run(identity, key, "site_server_set", arguments, run)

    def site_dns_plan(self, identity, site_id):
        """The records the site's address and alias need on its server (d-dns)."""
        site = self.site(identity, site_id)
        address = self.publisher.site_address(site)
        if address is None:
            raise DomainError("invalid_input", "Give the root page a public origin first")
        server = site.bag.get_node("info").attr.get("server")
        if not server or server == DEFAULT_SERVER:
            raise DomainError("invalid_input", "Choose a registered server for the site first")
        origins = self.publisher.site_origins(site, address)
        return dns_plan(origins, self.servers.get(server))

    def _dns_plan(self, identity, site_id):
        return self.site_dns_plan(identity, site_id)

    def _dns_check(self, identity, site_id):
        return self.dns_check_plan(self.site_dns_plan(identity, site_id))

    def dns_check_plan(self, plan):
        return dns_check(plan, self.dns_lookup)

    def _site_go_live(self, identity, site_id, key):
        """DNS check, Publish, the agent's domain and certificate, the address answering."""
        if self.agents is None:
            raise DomainError("unavailable", "Configure the agent tokens directory first")

        def publish():
            site = self.working_copy(site_id).load()
            selected = [p["entry"] for p in self.publisher.plan(site) if p["selected"]]
            return self._publish(identity, site_id, key + "-publish", selected)

        def run():
            return go_live(self, identity, site_id, publish)

        return self.receipts.run(identity, key, "site_go_live", {"site_id": site_id}, run)

    def _private_link(self, identity, site_id, hours=8):
        return self.publisher.private_link(site_id, hours)

    def _record(self, identity, site_id, operation, **details):
        copy = self.working_copy(site_id)
        site = copy.load()
        site.record(identity, operation, now(), **details)
        copy.save(site)

    def _site_list(self, identity):
        """Sites the caller can read, with the holder of each."""
        return [
            {**item, "holder": self.lock.holder(item["site_id"])}
            for item in self.store.sites()
            if self.policy.allows(identity, "site:" + item["site_id"], "read")
        ]

    def _server_list(self, identity):
        return [{"name": name, **entry} for name, entry in sorted(self.servers.servers().items())]

    def _server_add(self, identity, key, name, ipv4, ipv6, agent_url):
        return self.servers.add(name, ipv4, ipv6, agent_url)

    def _server_remove(self, identity, key, name):
        bound = []
        if self.publisher is not None:
            # One site has its address and possibly an alias: count sites, not origins.
            entries = self.publisher.bindings().values()
            bound = sorted({e["site_id"] for e in entries if e["server"] == name})
        self.servers.remove(name, bound)
        return {"name": name}

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

    def _site_save(self, identity, site_id, via=None):
        copy = self.working_copy(site_id)
        site = copy.load()
        site.record(identity, "site_save", now(), via=via)
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

        online = {}
        if self.publisher is not None:
            online = (self.publisher.index(site_id) or {"pages": {}})["pages"]
        pages = []
        for node in site.section("pages").nodes:
            page = site.page(node.label)
            entry = online.get(node.label)
            pages.append(
                {
                    "id": node.label,
                    "name": page.name,
                    "url": node.attr["url"],
                    "template_id": page.template.attr["original_id"],
                    "slot_names": [slot.name for slot in template_slots(page.template.value)],
                    "slots": {n.attr["slot"]: n.attr["original_id"] for n in page.slots.nodes},
                    "unplaced": [n.label for n in page.unplaced.nodes],
                    "changed": entry is None
                    or entry["fingerprint"] != page_fingerprint(site, node.label),
                    "outdated": bool(site.outdated_copies(node.label)),
                    "seo": stored_seo(site, node.label),
                    "seo_effective": effective_seo(site, node.label),
                    "seo_inherited": effective_seo(site, node.label, {}),
                    "urls": {
                        language: language_url(site, node.label, language)
                        for language in site_languages(site)
                    },
                    "seo_languages": {
                        language: {
                            "seo": stored_seo(site, node.label, language),
                            "seo_effective": effective_seo(site, node.label, None, language),
                            "seo_inherited": effective_seo(site, node.label, {}, language),
                        }
                        for language in site_languages(site)[1:]
                    },
                    "images": page_images(site, node.label),
                }
            )
        return {
            "site_id": site.site_id,
            "name": site.name,
            "languages": site_languages(site),
            "server": site.bag.get_node("info").attr.get("server", ""),
            "texts": {
                n.label: {
                    "text": n.value,
                    "translations": translation_states(site, "text_" + n.label),
                }
                for n in site.section("texts").nodes
            },
            "holder": self.lock.holder(site_id),
            "templates": items("templates"),
            "contents": [
                {
                    **item,
                    "text": site.node("contents", item["id"]).value,
                    "translations": translation_states(site, "content_" + item["id"]),
                }
                for item in items("contents")
            ],
            "assets": [
                # A style sheet's text, for the CSS tab of the block window (d-css-rules).
                {**item, "text": site.node("assets", item["id"]).value.decode("utf-8", "replace")}
                if item["kind"] == "css"
                else item
                for item in items("assets")
            ],
            "pages": pages,
            "tree": site.tree(),
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

    def _seo_check(self, identity, site_id, page_id=None):
        return seo_check(self.site(identity, site_id), page_id)

    def _page_render(self, identity, site_id, page_id, language=None):
        if self.worker is None:
            raise DomainError("unavailable", "Configure the render worker first")
        site = self.site(identity, site_id)
        if language is not None and language not in site_languages(site):
            raise DomainError("invalid_input", f"{language} is not a language of the site")
        request = page_request(site, page_id, self.connections, language=language)
        return self.worker.render_page(request)

    # Changes on the working copy

    def _template_add(self, identity, site, name, engine, source=None, python_source=None):
        if (source is None) == (python_source is None):
            raise DomainError("invalid_input", "Give either source or python_source")
        if engine not in ENGINES:
            raise DomainError("invalid_input", "Template engine is gramlot or htmlbuilder")
        if python_source is not None:
            if self.worker is None:
                raise DomainError("unavailable", "Configure the render worker first")
            try:
                plain = self.worker.plain_template(engine, python_source)
            except RenderProblem as problem:
                raise DomainError(
                    "invalid_template", str(problem), details=problem.diagnostic
                ) from problem
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

    def _asset_save(self, identity, site, asset_id, data_base64):
        # The site's original changes; page copies change only through copies_update (GS-D2).
        site.node("assets", asset_id).value = decode_base64(data_base64)
        return {"asset_id": asset_id}

    def _page_add(self, identity, site, name, template_id):
        return {"page_id": site.add_page(name, template_id)}

    def _folder_add(self, identity, site, name, parent=None):
        return {"folder_id": site.add_folder(name, parent)}

    def _tree_move(self, identity, site, item_id, parent=None, position=None):
        site.move(item_id, parent, position)
        return {"item_id": item_id, "parent": parent}

    def _page_url_set(self, identity, site, page_id, url, language=None):
        return {"page_id": page_id, "url": set_page_url(site, page_id, url, language)}

    def _page_seo_set(self, identity, site, page_id, fields, language=None):
        set_page_seo(site, page_id, fields, language)
        return {"page_id": page_id, "seo": stored_seo(site, page_id, language)}

    def _page_alt_set(self, identity, site, page_id, image, alt):
        set_image_alt(site, page_id, image, alt)
        return {"page_id": page_id, "image": image}

    def _site_languages_set(self, identity, site, languages):
        set_languages(site, languages)
        return {"languages": site_languages(site)}

    def _content_translate(self, identity, site, content_id, language, text, proposed=False):
        set_translation(site, "content_" + content_id, language, text, proposed)
        return {"content_id": content_id, "language": language}

    def _site_text_set(self, identity, site, name, text, language=None, proposed=False):
        set_site_text(site, name, text, language, proposed)
        return {"name": name, "language": language}

    def _translation_confirm(self, identity, site, translation, language):
        confirm_translation(site, translation, language)
        return {"translation": translation, "language": language}

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
