"""Versioned, JSON-only process boundary between the coordinator and the render worker."""

from ..catalog.filesystem import digest as sha256  # noqa: F401 — public shared digest alias
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


class RenderProblem(Exception):
    def __init__(self, code, message, **context):
        super().__init__(message)
        self.diagnostic = {"code": code, "message": message, **context}


class PreparedHTML(str):
    """Derived fragment; only preparation creates these in application Data.

    A type boundary against accidental raw insertion, not a capability boundary
    against the explicitly trusted Python template author.
    """
