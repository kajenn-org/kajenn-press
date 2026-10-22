"""Versioned, JSON-only process boundary. No catalog handles cross it."""

import json
from dataclasses import dataclass

from ..catalog.filesystem import digest as sha256
from ..catalog.filesystem import encode as canonical  # noqa: F401 — public shared encoding alias

CONTRACT = "kajenn-static-v1"
PREPARATION = "editorial-html-v1"
QUALIFIED = {
    "gramlot": "0.3.8",
    "genro-builders": "0.30.0",
    "genro-bag": "0.28.0",
    "markdown-it-py": "4.2.0",
    "nh3": "0.3.7",
}


@dataclass(frozen=True)
class RenderInput:
    """Canonical immutable bytes, safe to persist later as a candidate input."""

    encoded: bytes

    def unpack(self):
        return json.loads(self.encoded)

    @property
    def digest(self):
        return sha256(self.encoded)


class RenderProblem(Exception):
    def __init__(self, code, message, **context):
        super().__init__(message)
        self.diagnostic = {"code": code, "message": message, **context}


class PreparedHTML(str):
    """Derived fragment; only preparation creates these in application Data.

    A type boundary against accidental raw insertion, not a capability boundary
    against the explicitly trusted Python template author.
    """
