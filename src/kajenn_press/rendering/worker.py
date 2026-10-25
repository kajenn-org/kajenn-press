"""Installed, one-request worker. Trusted code, not an OS security sandbox."""

import base64
import json
import sys
from contextlib import redirect_stdout

from .contract import CONTRACT, RenderProblem, canonical, sha256
from .engines import installed_profile, render_template
from .preparation import prepare_blocks


def run_request(request):
    profile = installed_profile()
    if request["action"] == "profile":
        return {"ok": True, "profile": profile}
    if request["action"] != "render":
        raise RenderProblem("invalid_request", "Unknown worker action")
    value = request["input"]
    if value["contract"] != CONTRACT or value["profile"] != profile:
        raise RenderProblem("profile_mismatch", "Frozen profile differs from installed worker")
    if sha256(canonical(value)) != request["input_digest"]:
        raise RenderProblem("invalid_input", "Frozen input digest differs")
    template = value["references"][value["template_revision"]]
    attributes = template["attributes"]
    data = value["data"]
    data["blocks"], diagnostics = prepare_blocks(
        value["blocks"], attributes["blocks"], data["page"]["variant_id"]
    )
    source = base64.b64decode(template["sources"]["source"], validate=True).decode("utf-8")
    try:
        html = render_template(attributes["engine"], source, data)
    except RenderProblem as exc:
        exc.diagnostic.setdefault("resource_id", template["record_id"])
        raise
    return {
        "ok": True,
        "profile": profile,
        "input_digest": request["input_digest"],
        "html": html,
        "digest": sha256(html.encode()),
        "diagnostics": diagnostics,
    }


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
