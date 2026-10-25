"""Installed local full cycle through REST/MCP. Never print the private credentials."""

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

import uvicorn
from private_preview import PERMISSIONS, prepare

from kajenn_press.application import create_server


def save_config(root, config):
    path = Path(root) / "demo-credentials.json"
    with path.open("w") as stream:
        json.dump(config, stream, indent=2)
    path.chmod(0o600)


def prepare_cycle(root, python, port):
    config = prepare(
        root,
        python,
        port,
        public_origins={
            "gramlot": f"http://gramlot.localhost:{port}",
            "htmlbuilder": f"http://htmlbuilder.localhost:{port}",
        },
    )
    if "cycle" not in config:
        config["cycle"] = {}
        save_config(root, config)
    return config


def command(config, channel, operation, **arguments):
    envelope = (
        arguments
        if channel == "rest"
        else {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": operation, "arguments": arguments},
        }
    )
    url = config["management_origin"] + ("/" + operation if channel == "rest" else "/mcp")
    request = urllib.request.Request(
        url,
        data=json.dumps(envelope).encode(),
        headers={
            "Authorization": "Bearer " + config["admin_token"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        result = json.load(response)
    if channel == "mcp":
        result = result["result"]["structuredContent"]
    if not result.get("ok"):
        raise RuntimeError(result.get("error", {}).get("code", "invalid_response"))
    return result["result"]


def step(root, config, action):
    for index, grant in enumerate(config["grants"]):
        initial = command(config, "rest", "release_read", build_id=grant["attributes"]["build_id"])
        settings_id = initial["manifest"]["settings_id"]
        state = config["cycle"].setdefault(settings_id, {"initial_build": initial["record_id"]})
        current = command(config, "mcp", "channel_read", settings_id=settings_id)
        if action == "activate":
            result = command(
                config,
                "rest",
                "release_activate",
                settings_id=settings_id,
                build_id=initial["record_id"],
                expected_generation=0,
                key=f"cycle-activate-{index}",
            )
            state["first_activation"] = result
        elif action == "update":
            selection = command(
                config, "mcp", "candidate_read", candidate_id=initial["attributes"]["candidate_id"]
            )["selection"]
            changed = None
            for variant_id, item in selection.items():
                draft = command(config, "rest", "record_read", record_id=variant_id)
                language = item["language"]
                saved = command(
                    config,
                    "mcp",
                    "draft_save",
                    variant_id=variant_id,
                    expected_generation=draft["generation"],
                    template_revision=draft["attributes"]["template_revision"],
                    blocks={
                        "body": {
                            "format": "markdown",
                            "source": "## AGGIORNAMENTO PUBBLICO"
                            if language == "it"
                            else "UNFINISHED ENGLISH",
                        }
                    },
                    key=f"cycle-{index}-{language}",
                )
                if language == "it":
                    changed = saved["records"][0]["revision_id"]
            selected = command(
                config,
                "rest",
                "candidate_create",
                settings_id=settings_id,
                variant_revisions=[changed],
                base_build_id=initial["record_id"],
                key=f"cycle-candidate-{index}",
            )
            job = command(
                config,
                "mcp",
                "build_start",
                candidate_id=selected["record_id"],
                key=f"cycle-build-{index}",
            )
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                status = command(config, "rest", "build_status", build_id=job["record_id"])
                if status["attributes"]["state"] not in {"queued", "running"}:
                    break
                time.sleep(0.1)
            if status["attributes"]["state"] != "succeeded":
                raise RuntimeError("Updated build did not succeed")
            result = command(
                config,
                "mcp",
                "release_activate",
                settings_id=settings_id,
                build_id=job["record_id"],
                expected_generation=current["generation"],
                key=f"cycle-update-{index}",
            )
            state["updated_build"] = job["record_id"]
            state["updated_activation"] = result
        else:
            result = command(
                config,
                "rest",
                "release_rollback",
                settings_id=settings_id,
                build_id=initial["record_id"],
                expected_generation=current["generation"],
                key=f"cycle-rollback-{index}",
            )
            state["rollback"] = result
        save_config(root, config)
    print(action + ": completato per entrambi i siti", flush=True)


def serve_cycle(root, config):
    publication = {
        k: config[k]
        for k in ("management_origin", "preview_origin", "render_python", "public_origins")
    }
    publication["preview_secret"] = bytes.fromhex(config["preview_secret"])
    app = create_server(
        Path(root) / "catalog",
        auth={"bearer": {"demo": {"token": config["admin_token"], "tags": "editor"}}},
        grants={"demo": {"*": PERMISSIONS + ["publish"]}},
        publication=publication,
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=config["port"],
        access_log=False,
        proxy_headers=False,
        log_level="warning",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", default=os.sys.executable)
    parser.add_argument("--port", type=int, default=19765)
    parser.add_argument("--step", choices=["activate", "update", "rollback"])
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    configuration = prepare_cycle(args.root, args.python, args.port)
    if args.step:
        step(args.root, configuration, args.step)
    elif not args.prepare_only:
        print("Demo su loopback; credenziali nel file privato della directory scelta.", flush=True)
        serve_cycle(args.root, configuration)
