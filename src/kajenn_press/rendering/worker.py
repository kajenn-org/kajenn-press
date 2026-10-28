"""Installed, one-request worker. Trusted code, not an OS security sandbox."""

import json
import sys
from contextlib import redirect_stdout

from genro_bag import Bag

from .contract import RenderProblem, canonical, sha256
from .engines import installed_profile
from .page import page_data_bag, plain_template, render_page


def run_request(request):
    profile = installed_profile()
    if request["action"] == "profile":
        return {"ok": True, "profile": profile}
    if request["action"] == "plain_template":
        template = plain_template(request["engine"], request["source"])
        return {"ok": True, "template": template.to_tytx(transport="json")}
    if request["action"] == "render_page":
        html, diagnostics = render_page(
            request["engine"],
            Bag.from_tytx(request["template"]),
            request["slots"],
            request["data"],
            page_data_bag(request["page_data"]),
            request["connections"],
            request["resource_id"],
        )
        return {
            "ok": True,
            "html": html,
            "digest": sha256(html.encode()),
            "diagnostics": diagnostics,
        }
    raise RenderProblem("invalid_request", "Unknown worker action")


def main():
    try:
        # Parent enforces its input cap; the protocol also rejects extra input.
        raw = sys.stdin.buffer.read(48 * 1024 * 1024 + 1)
        if len(raw) > 48 * 1024 * 1024:
            raise RenderProblem("input_limit", "Worker input exceeds limit")
        with redirect_stdout(sys.stderr):
            response = run_request(json.loads(raw))
    except RenderProblem as exc:
        response = {"ok": False, "diagnostics": [exc.diagnostic]}
    except Exception as exc:  # noqa: BLE001 — turn arbitrary trusted-template failures into diagnostics
        response = {
            "ok": False,
            "diagnostics": [
                {"code": "template_error", "message": f"{type(exc).__name__}: {str(exc)[:2048]}"}
            ],
        }
    sys.stdout.buffer.write(canonical(response))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
