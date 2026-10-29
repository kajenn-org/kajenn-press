"""Private links to a published site (N7-D4).

A private link is `<address>/_private/<token>`. The token names the site and its expiry
and is signed with HMAC-SHA256 under a secret shared by websites and the site servers.
The site server answers it with a cookie for that host only; with the cookie, a private
site and a site in maintenance are served as they are. Rotating the secret revokes every
link.
"""

import base64
import hashlib
import hmac
import json
import time

COOKIE = "kpress_private"
PREFIX = "/_private/"
DURATIONS = {8: "8 hours", 168: "7 days"}


def encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(secret, site_id, expires):
    payload = encode(json.dumps({"s": site_id, "e": int(expires)}, separators=(",", ":")).encode())
    mac = hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest()
    return payload + "." + encode(mac)


def private_token(secret, site_id, hours, now=None):
    """(token, expiry in epoch seconds) of a link valid `hours` hours."""
    if hours not in DURATIONS:
        raise ValueError("A private link lasts 8 hours or 7 days")
    expires = int((time.time() if now is None else now) + hours * 3600)
    return sign(secret, site_id, expires), expires


def valid_token(secret, token, site_id, now=None):
    """The expiry of a token signed for this site and not expired, else None."""
    try:
        payload, mac = token.split(".")
        expected = hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(decode(mac), expected):
            return None
        claims = json.loads(decode(payload))
    except (ValueError, UnicodeError):
        return None
    if not isinstance(claims, dict) or claims.get("s") != site_id:
        return None
    expires = claims.get("e")
    if not isinstance(expires, int) or expires <= (time.time() if now is None else now):
        return None
    return expires


def cookie_token(headers):
    """The private-link cookie of a request, or None."""
    for name, value in headers:
        if name.lower() != b"cookie":
            continue
        for part in value.decode("latin-1").split(";"):
            key, _, token = part.strip().partition("=")
            if key == COOKIE:
                return token
    return None
