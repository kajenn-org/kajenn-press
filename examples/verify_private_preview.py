"""Optional Playwright check of a running private_preview demo; revokes its grants."""

import argparse
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def verify(root, output):
    config = json.loads((Path(root) / "demo-credentials.json").read_text())
    report = {"sites": []}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        contexts = []
        for index, grant in enumerate(config["grants"]):
            context = browser.new_context(viewport={"width": 1150, "height": 850})
            page = context.new_page()
            failures = []
            page.on("pageerror", lambda error, failures=failures: failures.append(str(error)))
            page.goto(grant["url"])
            page.wait_for_url("**/preview/*/it/")
            assert page.locator("h1").inner_text().endswith("· it")
            assert page.locator("table").count() == 1
            assert page.locator("strong").inner_text() == "già renderizzato"
            assert page.locator("img").evaluate("(img) => img.complete && img.naturalWidth === 1")
            assert (
                page.locator("h1").evaluate("(el) => getComputedStyle(el).color")
                == "rgb(33, 118, 132)"
            )
            assert page.locator("link[rel=canonical]").get_attribute("href").endswith("/it/")
            assert not page.url.split("/it/")[1]
            assert all(
                c["name"].startswith("preview_") and c["httpOnly"] for c in context.cookies()
            )
            page.screenshot(path=str(output / f"site-{index + 1}-it.png"), full_page=True)
            page.get_by_role("link", name="English").click()
            page.wait_for_url("**/en/about/")
            assert page.locator("h1").inner_text().endswith("· en")
            assert not failures, failures
            # Essential output also works without JS after the scoped bootstrap exchange.
            inert = browser.new_context(
                java_script_enabled=False, storage_state=context.storage_state()
            )
            inert_page = inert.new_page()
            response = inert_page.goto(page.url)
            assert response.status == 200 and inert_page.locator("table").count() == 1
            assert inert_page.locator("img").evaluate("(img) => img.naturalWidth") == 1
            asset = page.locator("img").get_attribute("src")
            contexts.append((context, page, inert, asset))
            report["sites"].append(
                {
                    "site": index + 1,
                    "navigation": True,
                    "css": True,
                    "png": True,
                    "essential_without_js": True,
                }
            )
        for grant in config["grants"]:
            body = json.dumps(
                {
                    "grant_id": grant["record_id"],
                    "expected_generation": grant["generation"],
                    "key": "browser-revoke-" + grant["record_id"],
                }
            ).encode()
            request = urllib.request.Request(
                config["management_origin"] + "/preview_grant_revoke",
                data=body,
                headers={
                    "Authorization": "Bearer " + config["admin_token"],
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request) as response:
                assert json.load(response)["ok"]
        for index, (context, page, inert, asset) in enumerate(contexts):
            response = page.reload()
            assert response.status == 404
            response = context.request.get(config["preview_origin"] + asset)
            assert response.status == 404
            response = context.request.head(config["preview_origin"] + asset)
            assert response.status == 404
            page.screenshot(path=str(output / f"site-{index + 1}-revoked.png"), full_page=True)
            inert.close()
            context.close()
        report["revoked_pages_assets_get_head"] = True
        browser.close()
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.root, args.output)
