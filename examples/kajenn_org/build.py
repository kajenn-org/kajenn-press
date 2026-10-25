"""Build, publish and register kajenn.org through MCP only; re-runnable, changes make revisions.

Sources next to this file: template.py, site.css, kajenn-mark.png and pages/<key>.<block>.html.
The state file keeps record IDs and generations between runs.
"""

import argparse
import base64
import hashlib
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
BLOCKS = {"hero": {"format": "html", "required": True}, "body": {"format": "html", "required": True}}
PAGES = (
    {
        "key": "home",
        "title": "kajenn",
        "route_title": "kajenn · A spicy ASGI application server",
        "path": "",
        "description": "kajenn is an ASGI application server with sessions, authentication, websocket channels, tasks, MCP and storage included.",
    },
    {
        "key": "concepts",
        "title": "Core concepts",
        "route_title": "Core concepts · kajenn",
        "path": "concepts",
        "description": "How a kajenn server relates to its applications, how a request finds its handler, and the design principles behind it.",
    },
    {
        "key": "start",
        "title": "Get started",
        "route_title": "Get started · kajenn",
        "path": "get-started",
        "description": "Install kajenn, write a two-route hello world and serve it from Python or the kajenn command.",
    },
)


class Mcp:
    """JSON-RPC tools/call against an installation, with the Host its management origin expects."""

    def __init__(self, endpoint, host, token):
        self.endpoint, self.host, self.token = endpoint, host, token

    def __call__(self, operation, **arguments):
        envelope = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": operation, "arguments": arguments},
        }
        request = urllib.request.Request(
            self.endpoint + "/mcp",
            data=json.dumps(envelope).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "Host": self.host,
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)["result"]["structuredContent"]
        if not result.get("ok"):
            raise RuntimeError(f"{operation}: {json.dumps(result.get('error'), indent=2)}")
        return result["result"]

    def wait(self, seconds=180):
        deadline = time.monotonic() + seconds
        while True:
            try:
                return self("child_channels")
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(2)


def digest(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:12]


def save_resource(mcp, state, slot, **arguments):
    """Create the resource once; afterwards save a new revision only when the input changed."""
    fingerprint = digest(arguments)
    known = state.get(slot)
    if known and known["fingerprint"] == fingerprint:
        return known
    operation = "media_save" if "data_base64" in arguments else "resource_save"
    extra = {"record_id": known["record_id"], "expected_generation": known["generation"]} if known else {}
    record = mcp(operation, key=f"{slot}-{fingerprint}", **arguments, **extra)["records"][0]
    state[slot] = {**record, "fingerprint": fingerprint}
    return state[slot]


def page_blocks(key):
    return {
        name: {"format": "html", "source": (HERE / "pages" / f"{key}.{name}.html").read_text()}
        for name in ("hero", "body")
    }


def build(mcp, state, public_origin, serving_address):
    if "site" not in state:
        state["site"] = mcp("site_create", key="kajenn-org", name="kajenn.org", languages=["en"])[
            "records"
        ][0]
    site_id = state["site"]["record_id"]
    scope = "site:" + site_id
    css = save_resource(
        mcp, state, "css", scope=scope, kind="css", name="kajenn site styles",
        source=(HERE / "site.css").read_text(),
    )
    logo = save_resource(
        mcp, state, "logo", scope=scope, name="kajenn mark", mime_type="image/png",
        data_base64=base64.b64encode((HERE / "kajenn-mark.png").read_bytes()).decode(),
    )
    template = save_resource(
        mcp, state, "template", scope=scope, kind="template", name="kajenn sibling page",
        engine="gramlot", source=(HERE / "template.py").read_text(),
        dependencies=[css["revision_id"], logo["revision_id"]], blocks=BLOCKS,
    )
    revisions = []
    for page in PAGES:
        blocks = page_blocks(page["key"])
        entry = state.setdefault("pages", {}).get(page["key"])
        fingerprint = digest(template["revision_id"], blocks)
        if entry is None:
            content = mcp(
                "content_create", key="content-" + page["key"], site_id=site_id, title=page["title"]
            )["records"][0]
            variant = mcp(
                "variant_create", key=f"variant-{page['key']}-{fingerprint}",
                content_id=content["record_id"], language="en",
                template_revision=template["revision_id"], blocks=blocks,
            )["records"][0]
            mcp(
                "publication_route_save", key="route-" + page["key"],
                variant_id=variant["record_id"], path=page["path"],
                title=page["route_title"], description=page["description"],
            )
            entry = {"content_id": content["record_id"], **variant, "fingerprint": fingerprint}
        elif entry["fingerprint"] != fingerprint:
            variant = mcp(
                "draft_save", key=f"draft-{page['key']}-{fingerprint}",
                variant_id=entry["record_id"], expected_generation=entry["generation"],
                template_revision=template["revision_id"], blocks=blocks,
            )["records"][0]
            entry = {**entry, **variant, "fingerprint": fingerprint}
        state["pages"][page["key"]] = entry
        revisions.append(entry["revision_id"])
    if "settings" not in state:
        state["settings"] = mcp(
            "publication_settings_save", key="settings", site_id=site_id, channel="main",
            public_origin=public_origin, primary_language="en",
            landing_variant=state["pages"]["home"]["record_id"],
        )
    settings_id = state["settings"]["record_id"]
    release_key = digest(revisions)
    candidate = mcp(
        "candidate_create", key="candidate-" + release_key, settings_id=settings_id,
        variant_revisions=revisions,
    )
    job = mcp("build_start", key="build-" + release_key, candidate_id=candidate["record_id"])
    deadline, status = time.monotonic() + 300, None
    while time.monotonic() < deadline:
        status = mcp("build_status", build_id=job["record_id"])
        if status["attributes"]["state"] not in {"queued", "running"}:
            break
        time.sleep(0.5)
    if status["attributes"]["state"] != "succeeded":
        raise RuntimeError(json.dumps(status["attributes"].get("diagnostics"), indent=2))
    channel = mcp("channel_read", settings_id=settings_id)
    # A channel never activated answers without attributes.
    if channel.get("attributes", {}).get("active_build") != job["record_id"]:
        activated = mcp(
            "release_activate", key="activate-" + release_key, settings_id=settings_id,
            build_id=job["record_id"], expected_generation=channel["generation"],
        )
        if activated["export"]["state"] != "exported":
            raise RuntimeError("Release activated but not exported: " + json.dumps(activated["export"]))
    if "child" not in state:
        state["child"] = mcp(
            "child_save", key="child-kajenn-org", settings_id=settings_id, name="kajenn-org",
            public_origin=public_origin, serving_address=serving_address,
        )
    return settings_id, job["record_id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, help="Management URL reachable from here")
    parser.add_argument("--host", required=True, help="Host header of the management origin")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--public-origin", required=True)
    parser.add_argument("--serving-address", required=True)
    parser.add_argument("--state", type=Path, required=True, help="JSON state file")
    parser.add_argument("--child-config", type=Path, help="Write the child's bindings here")
    args = parser.parse_args()
    mcp = Mcp(args.endpoint, args.host, args.token_file.read_text().strip())
    mcp.wait()
    state = json.loads(args.state.read_text()) if args.state.exists() else {}
    try:
        settings_id, build_id = build(mcp, state, args.public_origin, args.serving_address)
    finally:
        args.state.write_text(json.dumps(state, indent=2))
    if args.child_config:
        args.child_config.write_text(json.dumps({"bindings": {args.public_origin: settings_id}}))
    print("published build", build_id, "for", args.public_origin, flush=True)


if __name__ == "__main__":
    main()
