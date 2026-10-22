"""Authorized exact dependency closure from one pinned local catalog snapshot."""

import base64

from ..domain import DomainError
from .contract import CONTRACT, RenderInput, canonical, sha256


class RenderInputs:
    def __init__(self, catalog, policy):
        self.catalog = catalog
        self.policy = policy

    def freeze(
        self,
        identity,
        variant_id,
        profile,
        *,
        revision_id=None,
        generation=None,
        resource_urls=None,
    ):
        """Trusted coordinator API. URL overrides are supplied by the later release resolver."""
        snapshot = self.catalog.read(generation)
        try:
            variant = snapshot.revisions[revision_id or snapshot.records[variant_id]["revision_id"]]
        except KeyError as exc:
            raise DomainError("not_found", "Variant or revision not found") from exc
        if variant["record_id"] != variant_id or variant["data"]["kind"] != "variant":
            raise DomainError("invalid_input", "Expected an exact language variant")
        scope = variant["scope"]
        self.policy.require(identity, scope, "build")
        self.policy.require(identity, scope, "read")
        if profile.get("contract") != CONTRACT:
            raise DomainError("invalid_profile", "Expected a qualified worker profile")
        site_id = scope.removeprefix("site:")
        attrs = variant["data"]["attributes"]
        references, resources, visiting = {}, {}, set()
        total = 0

        def include(revision, *, dependency=False):
            nonlocal total
            rid = revision["id"]
            if rid in visiting:
                raise DomainError("dependency_cycle", "Cyclic exact dependencies", resource_id=rid)
            if rid in references:
                return
            kind = revision["data"]["kind"]
            allowed_scope = "installation" if kind == "site" else scope
            if revision["scope"] not in {allowed_scope, "library"}:
                raise DomainError("forbidden", "Cross-site rendering input", resource_id=rid)
            actual_scope = "site:" + revision["record_id"] if kind == "site" else revision["scope"]
            self.policy.require(identity, actual_scope, "read")
            if dependency:
                self.policy.require(identity, actual_scope, "use")
                if kind not in {"template", "css", "javascript", "media"}:
                    raise DomainError("invalid_dependency", "Expected an editorial resource")
            if len(references) + len(visiting) >= 256:
                raise DomainError("input_limit", "Too many rendering dependencies")
            visiting.add(rid)
            sources = {}
            for name in revision["payloads"]:
                raw = self.catalog.read_payload(rid, name, snapshot.generation)
                total += len(raw)
                if total > 32 * 1024 * 1024:
                    raise DomainError("input_limit", "Rendering input exceeds 32 MiB")
                sources[name] = base64.b64encode(raw).decode("ascii")
            references[rid] = {
                "record_id": revision["record_id"],
                "revision_id": rid,
                "scope": actual_scope,
                "kind": kind,
                "attributes": revision["data"]["attributes"],
                "payloads": revision["payloads"],
                "sources": sources,
            }
            for dep in revision["data"]["attributes"].get("dependencies", []):
                if dep not in snapshot.revisions:
                    raise DomainError(
                        "missing_dependency", "Exact dependency unavailable", resource_id=dep
                    )
                include(snapshot.revisions[dep], dependency=True)
            if kind in {"css", "javascript", "media"}:
                name = "binary" if kind == "media" else "source"
                raw = base64.b64decode(sources[name])
                suffix = {"css": "css", "javascript": "js", "media": "bin"}[kind]
                resources[rid] = {
                    "kind": kind,
                    "url": (resource_urls or {}).get(rid, f"/_resources/{sha256(raw)}.{suffix}"),
                }
            visiting.remove(rid)

        include(variant)
        site = snapshot.revisions[snapshot.records[site_id]["revision_id"]]
        content = snapshot.revisions[snapshot.records[attrs["content_id"]]["revision_id"]]
        include(site)
        include(content)
        template = references[attrs["template_revision"]]
        if template["kind"] != "template":
            raise DomainError("invalid_template", "Variant needs an exact template")
        blocks = {
            name: {
                "format": declaration["format"],
                "source": self.catalog.read_payload(
                    variant["id"], "block." + name, snapshot.generation
                ).decode("utf-8"),
            }
            for name, declaration in attrs["blocks"].items()
        }
        return RenderInput(
            canonical(
                {
                    "contract": CONTRACT,
                    "profile": profile,
                    "catalog_generation": snapshot.generation,
                    "variant_revision": variant["id"],
                    "template_revision": template["revision_id"],
                    "references": references,
                    "data": {
                        "site": {"id": site_id, "name": site["data"]["attributes"]["name"]},
                        "page": {
                            "id": content["record_id"],
                            "variant_id": variant_id,
                            "title": content["data"]["attributes"]["title"],
                        },
                        "language": attrs["language"],
                        "resources": resources,
                    },
                    "blocks": blocks,
                }
            )
        )

    def authorize(self, identity, frozen, *, permission="build"):
        """Recheck current policy even when an already frozen input is reused."""
        value = frozen.unpack()
        self.policy.require(identity, "site:" + value["data"]["site"]["id"], permission)
        for reference in value["references"].values():
            self.policy.require(identity, reference["scope"], "read")
            if reference["kind"] in {"template", "css", "javascript", "media"}:
                self.policy.require(identity, reference["scope"], "use")
