"""One canonical language map for build links, SEO and preview navigation."""

import unicodedata
from ipaddress import ip_address
from urllib.parse import quote, unquote, urlsplit

from ..domain import DomainError


def origin(value):
    try:
        parsed = urlsplit(value)
        loopback = parsed.hostname == "localhost" or (parsed.hostname or "").endswith(".localhost")
        try:
            loopback = loopback or ip_address(parsed.hostname).is_loopback
        except ValueError:
            pass
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.port == 0
            or (parsed.scheme == "http" and not loopback)
        ):
            raise ValueError("origin")
        host = parsed.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        port = parsed.port
        suffix = (
            ""
            if port is None or port == {"http": 80, "https": 443}[parsed.scheme]
            else ":" + str(port)
        )
        return f"{parsed.scheme}://{host}{suffix}"
    except (ValueError, TypeError) as exc:
        raise DomainError(
            "invalid_origin", "Use a configured HTTPS origin (HTTP only on loopback)"
        ) from exc


def localized_path(language, path):
    if not isinstance(path, str) or len(path) > 512 or "%" in path or "\\" in path or "//" in path:
        raise DomainError("invalid_path", "Invalid or ambiguous route path")
    parts = unicodedata.normalize("NFC", path).strip("/").split("/") if path.strip("/") else []
    if any(
        not part
        or part.startswith("_")
        or part in {"mcp", "preview", "open", "access"}
        or not all(c.isalnum() or c in "-_" for c in part)
        for part in parts
    ):
        raise DomainError("invalid_path", "Traversal, reserved or invalid route segment")
    return "/" + "/".join([language, *parts]) + "/"


def request_path(raw):
    try:
        encoded = raw.decode("ascii")
        decoded = unquote(encoded, encoding="utf-8", errors="strict")
        if (
            quote(decoded, safe="/-._~") != encoded
            or "\\" in decoded
            or any(p in {".", ".."} for p in decoded.split("/"))
            or "//" in decoded
            or unicodedata.normalize("NFC", decoded) != decoded
        ):
            raise ValueError("ambiguous path")
        return decoded
    except (ValueError, UnicodeError) as exc:
        raise DomainError("invalid_path", "Ambiguous request path") from exc


def route_map(entries, settings):
    result = {}
    for variant_id, entry in entries.items():
        path = entry["route"]["path"]
        if path in result:
            raise DomainError(
                "route_collision",
                "Selected variants share a normalized route",
                resource_id=variant_id,
                details={"path": path},
            )
        result[path] = {
            "variant_id": variant_id,
            "content_id": entry["content_id"],
            "language": entry["language"],
            "title": entry["route"]["title"],
            "description": entry["route"]["description"],
        }
    landing = entries.get(settings["landing_variant"])
    if not landing or landing["language"] != settings["primary_language"]:
        raise DomainError("missing_landing", "Select the primary-language landing variant")
    return result, landing["route"]["path"]
