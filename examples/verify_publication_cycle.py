"""Optional browser qualification; owns and stops only its loopback demo server."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def api(config, operation, **arguments):
    request = urllib.request.Request(
        config["management_origin"] + "/" + operation,
        data=json.dumps(arguments).encode(),
        headers={
            "Authorization": "Bearer " + config["admin_token"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        result = json.load(response)
    assert result["ok"], result.get("error", {}).get("code")
    return result["result"]


def verify(root, output, server_python, render_python, port):
    root, output = Path(root), Path(output)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (root / "demo-credentials.json").exists():
        raise ValueError("Use a fresh private demo directory")
    output.mkdir(parents=True, exist_ok=True)
    demo = Path(__file__).with_name("publication_cycle.py")
    arguments = [
        server_python,
        str(demo),
        "--root",
        str(root),
        "--python",
        render_python,
        "--port",
        str(port),
    ]
    report = {"installed_parent": server_python, "sites": []}
    processes = []
    with (root / "server.log").open("w") as log:

        def start():
            process = subprocess.Popen(arguments, stdout=log, stderr=log)
            processes.append(process)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                assert process.poll() is None, "Demo exited; inspect its private server log"
                try:
                    config = json.loads((root / "demo-credentials.json").read_text())
                    assert api(config, "capabilities")["publication"]
                    return process, config
                except (OSError, urllib.error.URLError, json.JSONDecodeError):
                    time.sleep(0.1)
            raise AssertionError("Demo startup deadline exceeded")

        def step(action):
            result = subprocess.run(
                arguments + ["--step", action],
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
            )
            assert result.returncode == 0, "Demo step failed: " + action
            return json.loads((root / "demo-credentials.json").read_text())

        try:
            process, config = start()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                public = browser.new_context(
                    java_script_enabled=False, viewport={"width": 1150, "height": 850}
                )
                preview = browser.new_context()
                for grant in config["grants"]:
                    page = preview.new_page()
                    page.goto(grant["url"])
                    page.wait_for_url("**/preview/*/it/")
                    assert page.locator("table").count() == 1
                    page.close()
                preview.close()
                for origin in config["public_origins"]:
                    assert public.request.get(origin + "/it/").status == 404
                config = step("activate")
                pages = []
                for index, (origin, settings_id) in enumerate(config["public_origins"].items()):
                    page = public.new_page()
                    response = page.goto(origin + "/")
                    assert response.status == 200 and page.url.endswith("/it/")
                    assert page.locator("table").count() == 1
                    assert page.locator("strong").inner_text() == "già renderizzato"
                    assert (
                        page.locator("link[rel=canonical]").get_attribute("href") == origin + "/it/"
                    )
                    assert page.locator("link[rel=alternate]").count() == 2
                    assert (
                        page.locator("h1").evaluate("e => getComputedStyle(e).color")
                        == "rgb(33, 118, 132)"
                    )
                    assert page.locator("img").evaluate("e => e.complete && e.naturalWidth === 1")
                    old = public.request.get(origin + "/it/").body()
                    asset = page.locator("img").get_attribute("src")
                    page.get_by_role("link", name="English").click()
                    assert page.url.endswith("/en/about/")
                    page.screenshot(
                        path=str(output / f"site-{index + 1}-initial.png"), full_page=True
                    )
                    pages.append((page, origin, settings_id, old, asset))
                assert public.cookies() == []
                config = step("update")
                for index, (page, origin, settings_id, old, asset) in enumerate(pages):
                    page.goto(origin + "/it/")
                    assert "AGGIORNAMENTO PUBBLICO" in page.locator("body").inner_text()
                    assert asset != page.locator("img").get_attribute("src")
                    assert public.request.get(origin + asset).status == 200
                    assert (
                        "UNFINISHED ENGLISH" not in public.request.get(origin + "/en/about/").text()
                    )
                    assert (
                        public.request.get(origin + "/it/").headers["cache-control"] == "no-store"
                    )
                    page.screenshot(
                        path=str(output / f"site-{index + 1}-updated.png"), full_page=True
                    )
                config = step("rollback")
                for index, (page, origin, settings_id, old, asset) in enumerate(pages):
                    assert public.request.get(origin + "/it/").body() == old
                    assert len(api(config, "release_history", settings_id=settings_id)) == 3
                    assert (
                        api(config, "channel_read", settings_id=settings_id)
                        == config["cycle"][settings_id]["rollback"]
                    )
                    report["sites"].append(
                        {
                            "site": index + 1,
                            "preview": True,
                            "public_without_js": True,
                            "language_only_update": True,
                            "retained_assets": True,
                            "exact_rollback": True,
                        }
                    )
                process.terminate()
                process.wait(timeout=30)
                process, config = start()
                for page, origin, settings_id, old, asset in pages:
                    assert public.request.get(origin + "/it/").body() == old
                    assert (
                        api(config, "channel_read", settings_id=settings_id)
                        == config["cycle"][settings_id]["rollback"]
                    )
                report["restart_preserves_channel_ids_and_bytes"] = True
                browser.close()
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=30)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server-python", required=True)
    parser.add_argument("--render-python", required=True)
    parser.add_argument("--port", type=int, default=19765)
    args = parser.parse_args()
    verify(args.root, args.output, args.server_python, args.render_python, args.port)
