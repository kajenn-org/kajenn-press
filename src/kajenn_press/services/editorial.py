"""Filesystem-backed editorial rules; no rendering or source execution."""

import base64
import binascii
import difflib
import inspect
import re
from copy import deepcopy
from threading import RLock

from ..catalog.errors import Conflict
from ..catalog.filesystem import digest, encode
from ..catalog.local import Change
from ..domain import EDITORIAL_KINDS, MUTATIONS, OPERATIONS, DomainError
from ..objects import ObjectRef

NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")
SOURCE_LIMIT = 8 * 1024 * 1024


class EditorialService:
    def __init__(self, catalog, policy):
        self.catalog = catalog
        self.policy = policy
        self._lock = RLock()

    def execute(self, identity, operation, **arguments):
        """Trusted caller identity is separate from untrusted command arguments."""
        if not identity:
            raise DomainError("unauthenticated", "An authenticated principal is required")
        if operation not in OPERATIONS:
            raise DomainError("invalid_operation", "Unknown editorial operation")
        with self._lock:
            snapshot = self.catalog.read()
            handler = getattr(self, "_" + operation)
            try:
                bound = inspect.signature(handler).bind(snapshot, identity, **deepcopy(arguments))
                bound.apply_defaults()
                params = {
                    k: v for k, v in bound.arguments.items() if k not in ("snapshot", "identity")
                }
                fingerprint = digest(encode([operation, params]))
            except (TypeError, ValueError) as exc:
                raise DomainError("invalid_input", str(exc)) from exc
            self._authorize(snapshot, identity, operation, params)
            if operation not in MUTATIONS:
                return handler(snapshot, identity, **params)
            key = params["key"]
            if not isinstance(key, str) or not key or len(key) > 256:
                raise DomainError(
                    "invalid_input", "A nonempty key of at most 256 characters is required"
                )
            prior = snapshot.receipts.get(digest(encode([identity, "editorial", key])))
            if prior:
                saved = snapshot.revisions[prior["results"][0]["revision_id"]]
                if saved["data"]["command_hash"] != fingerprint:
                    raise DomainError("conflict", "Idempotency key reused with different input")
                return self._result(identity, snapshot, prior)
            change = handler(snapshot, identity, **params)
            change.data["command_hash"] = fingerprint

            def authorize(principal, current, changes):
                self._authorize(current, principal, operation, params)
                # Recheck uniqueness, language configuration and exact dependencies
                # under the coordinator, including callers using another service instance.
                if not any(
                    r["principal"] == principal and r["scope"] == "editorial" and r["key"] == key
                    for r in current.receipts.values()
                ):
                    handler(current, principal, **params)

            try:
                receipt = self.catalog.commit(
                    principal=identity,
                    scope="editorial",
                    key=key,
                    changes=[change],
                    authorize=authorize,
                )
            except Conflict as exc:
                raise DomainError(
                    "conflict",
                    str(exc),
                    resource_id=params.get("record_id")
                    or params.get("variant_id")
                    or params.get("site_id"),
                ) from exc
            return self._result(identity, self.catalog.read(), receipt)

    def _result(self, identity, snapshot, receipt):
        return {
            "receipt": receipt,
            "records": [
                self._view(snapshot, identity, r["record_id"], r["revision_id"])
                for r in receipt["results"]
            ],
        }

    def _revision(self, snapshot, record_id, revision_id=None):
        try:
            head = snapshot.records[record_id]
            revision = snapshot.revisions[revision_id or head["revision_id"]]
            if (
                revision["record_id"] != record_id
                or revision["data"]["schema"] != 1
                or revision["data"].get("kind") not in EDITORIAL_KINDS
            ):
                raise KeyError(record_id)
            return revision
        except (KeyError, TypeError) as exc:
            raise DomainError(
                "not_found", "Record or exact revision not found", resource_id=record_id
            ) from exc

    def _scope(self, revision):
        return (
            "site:" + revision["record_id"]
            if revision["data"]["kind"] == "site"
            else revision["scope"]
        )

    def _authorize(self, snapshot, identity, operation, params):
        if operation in ("capabilities", "sites_list"):
            return
        if operation == "site_create":
            self.policy.require(identity, "installation", "create_site")
            # Creators must be able to inspect and manage the newly assigned site ID.
            for permission in ("read", "write", "use"):
                self.policy.require(identity, "*", permission)
            return
        if operation == "scope_capabilities" and params.get("scope") == "installation":
            return
        permission = "write" if operation in MUTATIONS else "read"
        if operation in ("resource_save", "media_save", "records_list", "records_index", "scope_capabilities"):
            scope = params["scope"]
            if scope != "library":
                if not isinstance(scope, str) or not scope.startswith("site:"):
                    raise DomainError("invalid_input", "Scope must be library or site:<ID>")
                site = self._revision(snapshot, scope[5:])
                if site["data"]["kind"] != "site":
                    raise DomainError("invalid_input", "Scope does not identify a site")
        else:
            record_id = next(
                (
                    params[k]
                    for k in ("site_id", "content_id", "variant_id", "record_id")
                    if k in params
                ),
                None,
            )
            scope = self._scope(self._revision(snapshot, record_id))
        self.policy.require(identity, scope, permission)
        if operation in MUTATIONS:
            self.policy.require(identity, scope, "read")
        if operation == "resource_copy":
            ref = snapshot.revisions.get(params["source_revision"])
            if ref is None or ref["scope"] != "library":
                raise DomainError(
                    "invalid_input", "Copy requires an exact generic-library revision"
                )
            self.policy.require(identity, "library", "read")
            self.policy.require(identity, "library", "use")

    def _view(self, snapshot, identity, record_id, revision_id=None):
        revision = self._revision(snapshot, record_id, revision_id)
        self.policy.require(identity, self._scope(revision), "read")
        data = revision["data"]
        sources = {}
        for name in revision["payloads"]:
            raw = self.catalog.read_payload(revision["id"], name, snapshot.generation)
            sources[name] = (
                {"base64": base64.b64encode(raw).decode()}
                if data["kind"] == "media"
                else {"text": raw.decode("utf-8")}
            )
        return {
            "record_id": record_id,
            "revision_id": revision["id"],
            "generation": revision["generation"],
            "scope": self._scope(revision),
            "kind": data["kind"],
            "attributes": deepcopy(data["attributes"]),
            "payloads": deepcopy(revision["payloads"]),
            "sources": sources,
            "previous_revision": revision["previous"],
        }

    def _change(
        self, scope, kind, attributes, payloads=None, record_id=None, expected_generation=0
    ):
        if type(expected_generation) is not int or expected_generation < 0:
            raise DomainError(
                "invalid_input",
                "expected_generation must be a nonnegative integer",
                resource_id=record_id,
            )
        if (record_id is None and expected_generation != 0) or (
            record_id is not None
            and (
                not isinstance(record_id, str)
                or re.fullmatch(r"[0-9a-f]{32}", record_id) is None
                or expected_generation < 1
            )
        ):
            raise DomainError(
                "invalid_input",
                "Creation requires generation 0; updates require an ID and positive generation",
                resource_id=record_id,
            )
        return Change(
            scope,
            record_id,
            expected_generation,
            {"schema": 1, "kind": kind, "attributes": attributes},
            payloads or {},
        )

    def _text(self, value, label, allow_empty=False):
        if (
            not isinstance(value, str)
            or (not allow_empty and not value.strip())
            or len(value.encode()) > SOURCE_LIMIT
        ):
            raise DomainError("invalid_input", f"{label} must be UTF-8 text, at most 8 MiB")
        return value

    def _dependencies_checked(self, snapshot, identity, scope, dependencies):
        if (
            not isinstance(dependencies, list)
            or any(not isinstance(ref, str) for ref in dependencies)
            or len(set(dependencies)) != len(dependencies)
        ):
            raise DomainError("invalid_input", "Dependencies must be unique exact revision IDs")
        for ref in dependencies:
            revision = snapshot.revisions.get(ref)
            if revision is None or revision["data"]["kind"] not in (
                "template",
                "css",
                "javascript",
                "media",
            ):
                raise DomainError(
                    "invalid_dependency",
                    "An exact source/resource revision is required",
                    details={"revision_id": ref},
                )
            if revision["scope"] not in ("library", scope):
                raise DomainError(
                    "invalid_dependency", "Cross-site dependencies require an independent copy"
                )
            self.policy.require(identity, revision["scope"], "use")
        return dependencies

    def _unique(self, snapshot, scope, kind, attributes, record_id=None):
        for rid in snapshot.records:
            if (
                snapshot.revisions[snapshot.records[rid]["revision_id"]]["data"].get("kind")
                not in EDITORIAL_KINDS
            ):
                continue
            rev = self._revision(snapshot, rid)
            if rid == record_id or rev["scope"] != scope or rev["data"]["kind"] != kind:
                continue
            old = rev["data"]["attributes"]
            same = (
                (old["content_id"], old["language"])
                == (attributes["content_id"], attributes["language"])
                if kind == "variant"
                else old.get("name") == attributes.get("name")
            )
            if same:
                raise DomainError(
                    "conflict",
                    "A record with this name or language variant already exists",
                    resource_id=rid,
                )

    def _capabilities(self, snapshot, identity):
        return {
            "schema_version": 1,
            "operations": sorted(OPERATIONS),
            "source_formats": ["html", "markdown", "python", "css", "javascript", "binary"],
            "template_engines": ["gramlot", "htmlbuilder"],
            "scopes": ["library", "site:<ID>"],
            "block_declaration": {"<name>": {"format": "html|markdown", "required": "boolean"}},
            "block_value": {"<name>": {"format": "html|markdown", "source": "exact text"}},
            "permissions": ["read", "write", "use", "create_site"],
            "source_limit_bytes": SOURCE_LIMIT,
            "publication": False,
            "rendering": False,
            "database_required": False,
        }

    def _site_create(self, snapshot, identity, key, name, languages, review_required=False):
        attributes = self._site_attributes(name, languages, review_required)
        return self._change("installation", "site", attributes)

    def _site_attributes(self, name, languages, review_required):
        if (
            not isinstance(languages, list)
            or not languages
            or any(not isinstance(x, str) or not LANGUAGE.fullmatch(x) for x in languages)
            or len(languages) != len(set(languages))
            or type(review_required) is not bool
        ):
            raise DomainError(
                "invalid_input", "Unique language tags and a boolean review_required are required"
            )
        return {
            "name": self._text(name, "name"),
            "languages": languages,
            "review_required": review_required,
        }

    def _sites_list(self, snapshot, identity):
        return [
            self._view(snapshot, identity, rid)
            for rid in snapshot.records
            if snapshot.revisions[snapshot.records[rid]["revision_id"]]["data"].get("kind")
            == "site"
            and self.policy.allows(identity, "site:" + rid, "read")
        ]

    def _site_configure(
        self,
        snapshot,
        identity,
        site_id,
        expected_generation,
        key,
        name,
        languages,
        review_required=False,
    ):
        revision = self._revision(snapshot, site_id)
        if revision["data"]["kind"] != "site":
            raise DomainError("invalid_input", "Expected a site", resource_id=site_id)
        attributes = self._site_attributes(name, languages, review_required)
        for rid in snapshot.records:
            if (
                snapshot.revisions[snapshot.records[rid]["revision_id"]]["data"].get("kind")
                not in EDITORIAL_KINDS
            ):
                continue
            rev = self._revision(snapshot, rid)
            if (
                rev["scope"] == "site:" + site_id
                and rev["data"]["kind"] == "variant"
                and rev["data"]["attributes"]["language"] not in languages
            ):
                raise DomainError(
                    "conflict",
                    "Cannot remove a language with existing variants",
                    resource_id=site_id,
                )
        return self._change(
            "installation",
            "site",
            attributes,
            record_id=site_id,
            expected_generation=expected_generation,
        )

    def _records_list(self, snapshot, identity, scope, kind=None):
        return [
            self._view(snapshot, identity, rid)
            for rid in snapshot.records
            if snapshot.revisions[snapshot.records[rid]["revision_id"]]["data"].get("kind")
            in EDITORIAL_KINDS
            and self._scope(self._revision(snapshot, rid)) == scope
            and (kind is None or self._revision(snapshot, rid)["data"]["kind"] == kind)
        ]

    def _metadata(self, snapshot, identity, record_id, revision_id=None):
        revision = self._revision(snapshot, record_id, revision_id)
        self.policy.require(identity, self._scope(revision), "read")
        return {
            "record_id": record_id,
            "revision_id": revision["id"],
            "generation": revision["generation"],
            "scope": self._scope(revision),
            "kind": revision["data"]["kind"],
            "attributes": deepcopy(revision["data"]["attributes"]),
            "previous_revision": revision["previous"],
        }

    def _records_index(self, snapshot, identity, scope, kind=None):
        if kind is not None and kind not in EDITORIAL_KINDS:
            raise DomainError("invalid_input", "Unknown editorial kind")
        return [
            self._metadata(snapshot, identity, rid)
            for rid, head in snapshot.records.items()
            if snapshot.revisions[head["revision_id"]]["data"].get("kind") in EDITORIAL_KINDS
            and self._scope(self._revision(snapshot, rid)) == scope
            and (kind is None or self._revision(snapshot, rid)["data"]["kind"] == kind)
        ]

    def _revision_index(self, snapshot, identity, record_id):
        return [
            self._metadata(snapshot, identity, record_id, revision["id"])
            for revision in sorted(snapshot.revisions.values(), key=lambda r: r["generation"],
                                   reverse=True)
            if revision["record_id"] == record_id
        ]

    def _scope_capabilities(self, snapshot, identity, scope):
        if scope == "installation":
            allowed = self.policy.allows(identity, scope, "create_site") and all(
                self.policy.allows(identity, "*", permission) for permission in ("read", "write", "use"))
            return {"scope": scope, "permissions": ["create_site"] if allowed else []}
        permissions = ("read", "write", "use", "build", "preview_grant", "publish")
        return {"scope": scope, "permissions": [
            name for name in permissions if self.policy.allows(identity, scope, name)
        ]}

    def _content_create(self, snapshot, identity, site_id, key, title):
        if self._revision(snapshot, site_id)["data"]["kind"] != "site":
            raise DomainError("invalid_input", "Expected a site", resource_id=site_id)
        return self._change("site:" + site_id, "content", {"title": self._text(title, "title")})

    def _variant_change(
        self,
        snapshot,
        identity,
        content_id,
        language,
        template_revision,
        blocks,
        translated_from=None,
        record_id=None,
        expected_generation=0,
    ):
        content = self._revision(snapshot, content_id)
        if content["data"]["kind"] != "content":
            raise DomainError("invalid_input", "Expected a content record", resource_id=content_id)
        scope = content["scope"]
        site = self._revision(snapshot, scope[5:])
        if language not in site["data"]["attributes"]["languages"]:
            raise DomainError("invalid_input", "Language is not configured for this site")
        self._dependencies_checked(snapshot, identity, scope, [template_revision])
        template = snapshot.revisions[template_revision]
        if template["data"]["kind"] != "template":
            raise DomainError("invalid_dependency", "Expected an exact template revision")
        declarations = template["data"]["attributes"]["blocks"]
        if not isinstance(blocks, dict):
            raise DomainError("invalid_input", "blocks must be an object")
        attributes = {
            "content_id": content_id,
            "language": language,
            "template_revision": template_revision,
            "dependencies": [template_revision],
            "blocks": {},
        }
        payloads = {}
        for name, value in blocks.items():
            if (
                name not in declarations
                or not isinstance(value, dict)
                or set(value) != {"format", "source"}
                or value["format"] != declarations[name]["format"]
            ):
                raise DomainError(
                    "invalid_block",
                    "Block name or format does not match the selected template",
                    resource_id=record_id or content_id,
                    block=name,
                )
            payloads["block." + name] = self._text(value["source"], "block source", True).encode()
            attributes["blocks"][name] = {"format": value["format"]}
        if translated_from is not None:
            original = snapshot.revisions.get(translated_from)
            if (
                original is None
                or original["record_id"] == record_id
                or original["data"]["kind"] != "variant"
                or original["data"]["attributes"]["content_id"] != content_id
            ):
                raise DomainError(
                    "invalid_dependency",
                    "Translation source must be another variant of the same content",
                )
            self.policy.require(identity, self._scope(original), "read")
            attributes["translated_from"] = translated_from
        self._unique(snapshot, scope, "variant", attributes, record_id)
        return self._change(scope, "variant", attributes, payloads, record_id, expected_generation)

    def _variant_create(
        self,
        snapshot,
        identity,
        content_id,
        language,
        template_revision,
        key,
        blocks=None,
        translated_from=None,
    ):
        return self._variant_change(
            snapshot,
            identity,
            content_id,
            language,
            template_revision,
            {} if blocks is None else blocks,
            translated_from,
        )

    def _draft_save(
        self, snapshot, identity, variant_id, expected_generation, template_revision, blocks, key
    ):
        revision = self._revision(snapshot, variant_id)
        if revision["data"]["kind"] != "variant":
            raise DomainError(
                "invalid_input", "Expected a language variant", resource_id=variant_id
            )
        attrs = revision["data"]["attributes"]
        return self._variant_change(
            snapshot,
            identity,
            attrs["content_id"],
            attrs["language"],
            template_revision,
            blocks,
            attrs.get("translated_from"),
            variant_id,
            expected_generation,
        )

    def _resource_save(
        self,
        snapshot,
        identity,
        scope,
        kind,
        name,
        source,
        key,
        record_id=None,
        expected_generation=0,
        engine=None,
        blocks=None,
        dependencies=None,
    ):
        if kind not in ("template", "css", "javascript"):
            raise DomainError("invalid_input", "Source kind must be template, css or javascript")
        if record_id:
            old = self._revision(snapshot, record_id)
            if old["scope"] != scope or old["data"]["kind"] != kind:
                raise DomainError(
                    "invalid_input", "Resource kind and scope are immutable", resource_id=record_id
                )
        attrs = {
            "name": self._text(name, "name"),
            "dependencies": self._dependencies_checked(
                snapshot, identity, scope, [] if dependencies is None else dependencies
            ),
            "format": "python" if kind == "template" else kind,
        }
        if kind == "template":
            if engine not in ("gramlot", "htmlbuilder") or not isinstance(blocks, dict):
                raise DomainError(
                    "invalid_input", "Templates require an engine and block declarations"
                )
            for block, declaration in blocks.items():
                if (
                    not isinstance(block, str)
                    or not NAME.fullmatch(block)
                    or not isinstance(declaration, dict)
                    or set(declaration) != {"format", "required"}
                    or declaration["format"] not in ("html", "markdown")
                    or type(declaration["required"]) is not bool
                ):
                    raise DomainError(
                        "invalid_block",
                        "Invalid template block declaration",
                        resource_id=record_id,
                        block=block,
                    )
            attrs.update(engine=engine, blocks=blocks)
        elif engine is not None or blocks is not None:
            raise DomainError("invalid_input", "Only templates declare an engine or blocks")
        if record_id and "copied_from" in old["data"]["attributes"]:
            attrs["copied_from"] = old["data"]["attributes"]["copied_from"]
        self._unique(snapshot, scope, kind, attrs, record_id)
        return self._change(
            scope,
            kind,
            attrs,
            {"source": self._text(source, "source", True).encode()},
            record_id,
            expected_generation,
        )

    def _media_save(
        self,
        snapshot,
        identity,
        scope,
        name,
        data_base64,
        mime_type,
        key,
        record_id=None,
        expected_generation=0,
    ):
        if record_id:
            old = self._revision(snapshot, record_id)
            if old["scope"] != scope or old["data"]["kind"] != "media":
                raise DomainError(
                    "invalid_input", "Media kind and scope are immutable", resource_id=record_id
                )
        try:
            if not isinstance(data_base64, str) or len(data_base64) > SOURCE_LIMIT * 4 // 3 + 4:
                raise ValueError("oversized base64")
            raw = base64.b64decode(data_base64, validate=True)
            if len(raw) > SOURCE_LIMIT:
                raise ValueError("oversized media")
        except (ValueError, binascii.Error) as exc:
            raise DomainError("invalid_input", "Media must be valid base64, at most 8 MiB") from exc
        attrs = {
            "name": self._text(name, "name"),
            "mime_type": self._text(mime_type, "MIME type"),
            "mime_verified": False,
            "format": "binary",
            "dependencies": [],
        }
        if record_id and "copied_from" in old["data"]["attributes"]:
            attrs["copied_from"] = old["data"]["attributes"]["copied_from"]
        self._unique(snapshot, scope, "media", attrs, record_id)
        return self._change(scope, "media", attrs, {"binary": raw}, record_id, expected_generation)

    def _resource_copy(self, snapshot, identity, source_revision, site_id, name, key):
        if self._revision(snapshot, site_id)["data"]["kind"] != "site":
            raise DomainError(
                "invalid_input", "Copy destination must be a site", resource_id=site_id
            )
        source = snapshot.revisions[source_revision]
        if source["data"]["kind"] not in ("template", "css", "javascript", "media"):
            raise DomainError("invalid_input", "Only resources can be independently copied")
        scope = "site:" + site_id
        attrs = deepcopy(source["data"]["attributes"])
        attrs.update(name=self._text(name, "name"), copied_from=source_revision)
        self._dependencies_checked(snapshot, identity, scope, attrs["dependencies"])
        self._unique(snapshot, scope, source["data"]["kind"], attrs)
        return self._change(
            scope,
            source["data"]["kind"],
            attrs,
            {name: ObjectRef(**ref) for name, ref in source["payloads"].items()},
        )

    def _record_read(self, snapshot, identity, record_id, revision_id=None):
        return self._view(snapshot, identity, record_id, revision_id)

    def _revision_history(self, snapshot, identity, record_id):
        revisions = sorted(
            (r for r in snapshot.revisions.values() if r["record_id"] == record_id),
            key=lambda r: r["generation"],
        )
        return [self._view(snapshot, identity, record_id, revision["id"]) for revision in revisions]

    def _revision_compare(self, snapshot, identity, record_id, left_revision, right_revision):
        left, right = [
            self._view(snapshot, identity, record_id, r) for r in (left_revision, right_revision)
        ]
        diffs = {}
        for name in sorted(set(left["sources"]) | set(right["sources"])):
            a, b = left["sources"].get(name, {}), right["sources"].get(name, {})
            diffs[name] = {
                "changed": a != b,
                "diff": "".join(
                    difflib.unified_diff(
                        a.get("text", "").splitlines(True),
                        b.get("text", "").splitlines(True),
                        fromfile=left_revision,
                        tofile=right_revision,
                    )
                ),
            }
        return {
            "record_id": record_id,
            "left_revision": left_revision,
            "right_revision": right_revision,
            "attributes_changed": left["attributes"] != right["attributes"],
            "sources": diffs,
        }

    def _revision_checkpoint(
        self, snapshot, identity, record_id, expected_generation, key, message
    ):
        source = self._revision(snapshot, record_id)
        attrs = deepcopy(source["data"]["attributes"])
        attrs["checkpoint"] = {
            "message": self._text(message, "checkpoint message"),
            "source_revision": source["id"],
        }
        self._dependencies_checked(
            snapshot, identity, self._scope(source), attrs.get("dependencies", [])
        )
        return self._change(
            source["scope"],
            source["data"]["kind"],
            attrs,
            {n: ObjectRef(**r) for n, r in source["payloads"].items()},
            record_id,
            expected_generation,
        )

    def _revision_restore(
        self, snapshot, identity, record_id, source_revision, expected_generation, key
    ):
        source = self._revision(snapshot, record_id, source_revision)
        attrs = deepcopy(source["data"]["attributes"])
        attrs["restored_from"] = source_revision
        self._dependencies_checked(
            snapshot, identity, self._scope(source), attrs.get("dependencies", [])
        )
        if source["data"]["kind"] == "site":
            self._site_configure(
                snapshot,
                identity,
                record_id,
                expected_generation,
                key,
                attrs["name"],
                attrs["languages"],
                attrs["review_required"],
            )
        if source["data"]["kind"] in ("template", "css", "javascript", "media"):
            self._unique(snapshot, source["scope"], source["data"]["kind"], attrs, record_id)
        return self._change(
            source["scope"],
            source["data"]["kind"],
            attrs,
            {n: ObjectRef(**r) for n, r in source["payloads"].items()},
            record_id,
            expected_generation,
        )

    def _dependencies(self, snapshot, identity, record_id, revision_id=None):
        source = self._revision(snapshot, record_id, revision_id)
        refs = source["data"]["attributes"].get("dependencies", [])
        return {
            "revision_id": source["id"],
            "dependencies": [
                self._view(snapshot, identity, snapshot.revisions[r]["record_id"], r) for r in refs
            ],
        }

    def _readiness(self, snapshot, identity, record_id, revision_id=None):
        revision = self._revision(snapshot, record_id, revision_id)
        if revision["data"]["kind"] != "variant":
            raise DomainError(
                "invalid_input", "Readiness requires a language variant", resource_id=record_id
            )
        attrs = revision["data"]["attributes"]
        self._dependencies_checked(snapshot, identity, revision["scope"], attrs["dependencies"])
        template = snapshot.revisions[attrs["template_revision"]]["data"]["attributes"]
        diagnostics = []
        for name, declaration in template["blocks"].items():
            payload = revision["payloads"].get("block." + name)
            if declaration["required"] and (
                payload is None
                or not self.catalog.read_payload(
                    revision["id"], "block." + name, snapshot.generation
                )
                .decode()
                .strip()
            ):
                diagnostics.append(
                    {
                        "code": "required_block_missing",
                        "resource_id": record_id,
                        "block": name,
                        "message": "Required block is missing or empty",
                    }
                )
        return {
            "revision_id": revision["id"],
            "ready": not diagnostics,
            "diagnostics": diagnostics,
            "checks": ["template_blocks"],
            "publication_implemented": False,
        }
