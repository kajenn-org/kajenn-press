"""Verified, complete artifact bundles; no partial output is a sealed release."""

import base64
import re
import struct
import zlib
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring

from ..catalog.filesystem import digest, encode
from ..domain import DomainError
from ..rendering.contract import RenderInput


def verify_png(raw):
    try:
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("signature")
        offset, types, compressed = 8, [], bytearray()
        width = height = channels = 0
        while offset < len(raw):
            length = struct.unpack(">I", raw[offset : offset + 4])[0]
            kind, data = raw[offset + 4 : offset + 8], raw[offset + 8 : offset + 8 + length]
            checksum = struct.unpack(">I", raw[offset + 8 + length : offset + 12 + length])[0]
            if zlib.crc32(kind + data) != checksum:
                raise ValueError("CRC")
            types.append(kind)
            if kind == b"IHDR":
                width, height, depth, color, comp, filtering, interlace = struct.unpack(
                    ">IIBBBBB", data
                )
                channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color, 0)
                if (
                    not channels
                    or depth != 8
                    or comp
                    or filtering
                    or interlace
                    or not 0 < width <= 4096
                    or not 0 < height <= 4096
                ):
                    raise ValueError("unqualified PNG profile")
            elif kind == b"IDAT":
                compressed.extend(data)
            elif kind == b"IEND":
                if data or offset + 12 != len(raw):
                    raise ValueError("trailing bytes")
            elif kind[0] & 32 == 0:
                raise ValueError("unknown critical chunk")
            offset += length + 12
        if types[0] != b"IHDR" or types[-1] != b"IEND" or types.count(b"IHDR") != 1:
            raise ValueError("chunk sequence")
        expected = height * (1 + width * channels)
        if expected > 32 * 1024 * 1024:
            raise ValueError("decoded size")
        decompressor = zlib.decompressobj()
        pixels = decompressor.decompress(bytes(compressed), expected + 1)
        if (
            len(pixels) != expected
            or not decompressor.eof
            or decompressor.unused_data
            or any(pixels[n] > 4 for n in range(0, expected, 1 + width * channels))
        ):
            raise ValueError("image data")
    except (ValueError, IndexError, struct.error, zlib.error) as exc:
        raise DomainError(
            "unsupported_media", "Inline images require a valid noninterlaced 8-bit PNG"
        ) from exc


class LinkResolver:
    def __init__(self, candidate, resources, language, page_path, prefix):
        self.candidate, self.resources = candidate, resources
        self.language, self.page_path, self.prefix = language, page_path, prefix

    def resolve(self, value, *, asset=False):
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            public = self.candidate["settings"]["public_origin"]
            if value.startswith(public + "/"):
                value = value[len(public) :]
                parsed = urlsplit(value)
            elif not asset and parsed.scheme in {"https", "http", "mailto", "tel"}:
                return value
            else:
                raise DomainError(
                    "unresolved_reference",
                    "Resource is not an exact declared dependency",
                    details={"target": value},
                )
        if not value or value.startswith("#"):
            if asset:
                raise DomainError("unresolved_reference", "Empty resource reference")
            return value
        path = parsed.path
        if path.startswith("/_content/"):
            content_id = path.removeprefix("/_content/").strip("/")
            choices = [
                p
                for p, e in self.candidate["routes"].items()
                if e["content_id"] == content_id and e["language"] == self.language
            ]
            if len(choices) != 1:
                raise DomainError(
                    "unresolved_reference",
                    "Internal content has no selected language",
                    resource_id=content_id,
                )
            path = choices[0]
        elif path.startswith("/_media/"):
            rid = path.removeprefix("/_media/").strip("/")
            if rid not in self.resources:
                raise DomainError(
                    "unresolved_reference", "Media revision not declared", resource_id=rid
                )
            path = self.resources[rid]["url"]
        else:
            if "%" in path or "\\" in path or any(p in {".", ".."} for p in path.split("/")):
                raise DomainError("invalid_path", "Ambiguous output reference")
            path = urljoin(self.page_path, path)
        resource_paths = {item["url"] for item in self.resources.values()}
        if path not in resource_paths and (
            asset or path not in self.candidate["routes"] and path != "/"
        ):
            raise DomainError(
                "unresolved_reference",
                "Target absent from frozen release",
                details={"target": value},
            )
        return (
            self.prefix
            + quote(path, safe="/-._~")
            + ("?" + parsed.query if parsed.query else "")
            + ("#" + parsed.fragment if parsed.fragment else "")
        )

    def css(self, source):
        def replace(match):
            return 'url("' + self.resolve(match.group(1).strip().strip("\"'"), asset=True) + '")'

        if re.search(r"@import|\\", source, re.IGNORECASE):
            raise DomainError(
                "unsupported_css", "CSS imports/escapes need an explicitly qualified profile"
            )
        return re.sub(r"url\s*\(([^)]*)\)", replace, source, flags=re.IGNORECASE)


class PageHTML(HTMLParser):
    def __init__(self, resolver, metadata):
        super().__init__(convert_charrefs=False)
        self.resolver, self.metadata, self.parts = resolver, metadata, []
        self.skipping_title = False
        self.heads = 0
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "style":
            self.in_style = True
        if tag == "title":
            self.skipping_title = True
            return
        relations = set(re.split(r"[ \t\n\r\f]+", (values.get("rel") or "").lower()))
        if (
            tag == "link"
            and (
                "canonical" in relations
                or "alternate" in relations
                and "stylesheet" not in relations
            )
        ) or (tag == "meta" and (values.get("name") or "").lower() == "description"):
            return
        rewritten = []
        for name, value in attrs:
            if name == "srcset":
                raise DomainError(
                    "unsupported_reference", "srcset is not qualified by this static profile"
                )
            if value is not None:
                if name in {"href", "src", "poster", "action"}:
                    value = self.resolver.resolve(value, asset=not (tag == "a" and name == "href"))
                elif name == "style":
                    value = self.resolver.css(value)
            rewritten.append(
                " " + name + ("" if value is None else '="' + escape(value, quote=True) + '"')
            )
        self.parts.append("<" + tag + "".join(rewritten) + ">")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False
        if tag == "title":
            self.skipping_title = False
            return
        if tag == "head":
            self.heads += 1
            self.parts.append(self.metadata)
        self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.skipping_title:
            self.parts.append(self.resolver.css(data) if self.in_style else data)

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")

    def handle_decl(self, decl):
        self.parts.append("<!" + decl + ">")

    def handle_comment(self, data):
        self.parts.append("<!--" + data + "-->")


def validate_references(candidate):
    """Recheck the frozen graph before accepting any worker or artifact output."""
    for entry in candidate["entries"].values():
        refs = entry["input"]["references"]
        visited, visiting = set(), set()

        def visit(rid, refs=refs, visited=visited, visiting=visiting):
            if rid in visiting:
                raise DomainError("dependency_cycle", "Cyclic frozen dependency", resource_id=rid)
            if rid in visited:
                return
            reference = refs.get(rid)
            if reference is None:
                raise DomainError(
                    "missing_dependency", "Missing frozen dependency", resource_id=rid
                )
            if reference["scope"] not in {"library", "site:" + candidate["settings"]["site_id"]}:
                raise DomainError("forbidden", "Cross-site frozen dependency", resource_id=rid)
            visiting.add(rid)
            for dependency in reference["attributes"].get("dependencies", []):
                visit(dependency)
            for name, encoded in reference["sources"].items():
                raw = base64.b64decode(encoded, validate=True)
                expected = reference["payloads"][name]
                if digest(raw) != expected["sha256"] or len(raw) != expected["size"]:
                    raise DomainError(
                        "invalid_input", "Frozen source integrity failure", resource_id=rid
                    )
            visiting.remove(rid)
            visited.add(rid)

        for rid in refs:
            visit(rid)


def build_artifacts(candidate, build_id, worker, cancelled):
    validate_references(candidate)
    payloads, artifacts, diagnostics = {}, {"public": {}, "preview": {}}, []
    resources, sources = {}, {}
    for entry in candidate["entries"].values():
        value = entry["input"]
        resources.update(value["data"]["resources"])
        sources.update(value["references"])
    total = 0

    def add(context, path, raw, media_type):
        nonlocal total
        if not path.startswith("/") or ".." in path.split("/") or "%" in path or "\\" in path:
            raise DomainError("invalid_path", "Invalid artifact path")
        total += len(raw)
        if total > 64 * 1024 * 1024:
            raise DomainError("output_limit", "Complete release exceeds 64 MiB")
        name = "artifact_" + str(len(payloads))
        payloads[name] = raw
        artifacts[context][path] = {
            "payload": name,
            "sha256": digest(raw),
            "size": len(raw),
            "media_type": media_type,
        }

    for context, prefix in (("public", ""), ("preview", "/preview/" + build_id)):
        resolver = LinkResolver(
            candidate, resources, candidate["settings"]["primary_language"], "/", prefix
        )
        for rid, resource in resources.items():
            reference = sources[rid]
            source = base64.b64decode(next(iter(reference["sources"].values())), validate=True)
            kind = reference["kind"]
            if kind == "media":
                verify_png(source)
                if reference["attributes"]["mime_type"].lower() != "image/png":
                    raise DomainError(
                        "unsupported_media", "Declared media type differs from verified PNG"
                    )
                media_type = "image/png"
            elif kind == "css":
                source = resolver.css(source.decode()).encode()
                media_type = "text/css; charset=utf-8"
            elif kind == "javascript":
                source.decode("utf-8")
                media_type = "text/javascript; charset=utf-8"
            else:
                raise DomainError("unsupported_media", "Unknown serving resource type")
            add(context, resource["url"], source, media_type)
    for variant_id, entry in candidate["entries"].items():
        if cancelled():
            raise DomainError("interrupted", "Coordinator is shutting down")
        result = worker.render(RenderInput(encode(entry["input"])))
        diagnostics.extend(result["diagnostics"])
        if result["status"] != "succeeded":
            raise DomainError(
                "render_failed",
                "Page failed rendering",
                resource_id=variant_id,
                details=result["diagnostics"],
            )
        path, origin = entry["route"]["path"], candidate["settings"]["public_origin"]
        metadata = (
            "<title>"
            + escape(entry["route"]["title"])
            + '</title><meta name="description" content="'
            + escape(entry["route"]["description"], quote=True)
            + '">'
        )
        metadata += (
            '<link rel="canonical" href="'
            + escape(origin + quote(path, safe="/"), quote=True)
            + '">'
        )
        for alternate, info in candidate["routes"].items():
            if info["content_id"] == entry["content_id"]:
                metadata += (
                    '<link rel="alternate" hreflang="'
                    + escape(info["language"], quote=True)
                    + '" href="'
                    + escape(origin + quote(alternate, safe="/"), quote=True)
                    + '">'
                )
        for context, prefix in (("public", ""), ("preview", "/preview/" + build_id)):
            parser = PageHTML(
                LinkResolver(candidate, resources, entry["language"], path, prefix), metadata
            )
            parser.feed(result["html"])
            parser.close()
            if parser.heads != 1:
                raise DomainError("invalid_output", "Exactly one document head is required")
            add(context, path, "".join(parser.parts).encode(), "text/html; charset=utf-8")
    sitemap = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path in sorted(candidate["routes"]):
        SubElement(SubElement(sitemap, "url"), "loc").text = candidate["settings"][
            "public_origin"
        ] + quote(path, safe="/")
    for context in artifacts:
        add(
            context,
            "/sitemap.xml",
            tostring(sitemap, encoding="utf-8", xml_declaration=True),
            "application/xml; charset=utf-8",
        )
    manifest = {
        "schema": 1,
        "release_key": candidate["release_key"],
        "build_id": build_id,
        "profile": candidate["profile"],
        "settings_id": candidate["settings_id"],
        "settings_revision": candidate["settings_revision"],
        "routes": candidate["routes"],
        "redirects": {"/": candidate["landing"]},
        "artifacts": artifacts,
    }
    verify_bundle(manifest, payloads)
    payloads["manifest"] = encode(manifest)
    return payloads, diagnostics


def verify_bundle(manifest, payloads):
    expected = set(manifest["routes"]) | {"/sitemap.xml"}
    for context in ("public", "preview"):
        entries = manifest["artifacts"][context]
        if not expected <= set(entries) or manifest["redirects"]["/"] not in entries:
            raise DomainError("incomplete_artifacts", "Required output is missing")
        for path, item in entries.items():
            if (
                not path.startswith("/")
                or "%" in path
                or "\\" in path
                or "//" in path
                or any(p in {".", ".."} for p in path.split("/"))
            ):
                raise DomainError("invalid_path", "Invalid manifest path")
            raw = payloads.get(item["payload"])
            if raw is None or len(raw) != item["size"] or digest(raw) != item["sha256"]:
                raise DomainError(
                    "incomplete_artifacts",
                    "Artifact bytes failed verification",
                    details={"path": path},
                )
            if item["media_type"] not in {
                "text/html; charset=utf-8",
                "text/css; charset=utf-8",
                "text/javascript; charset=utf-8",
                "application/xml; charset=utf-8",
                "image/png",
            }:
                raise DomainError("unsupported_media", "Unqualified serving type")
