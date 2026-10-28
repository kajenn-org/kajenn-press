"""Plan-owned behavior contracts; implement only the copied test bodies.

They drive the real composition in deploy/docker and need Docker: set KAJENN_DOCKER=1.
They remove the composition's volumes first, so they always start from nothing.
"""

import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1", reason="Set KAJENN_DOCKER=1 to drive Docker"
)

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", str(ROOT / "deploy/docker/compose.yaml")]
# Fixed addresses for the tests; they take precedence over a developer's deploy/docker/.env.
ADDRESSES = {
    "KPRESS_SCHEME": "http",
    "KPRESS_MANAGEMENT_HOST": "127.0.0.1:8875",
    "KPRESS_PREVIEW_HOST": "localhost:8875",
    "KPRESS_TRUSTED_PROXIES": "127.0.0.1",
}
MC ="minio/mc@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727"
sys.path.insert(0, str(ROOT / "examples/kajenn_press_site"))

from publish import Mcp


def compose(*arguments, check=True, addresses=ADDRESSES):
    return subprocess.run(
        [*COMPOSE, "--profile", "demo", *arguments], capture_output=True, text=True,
        check=check, timeout=900, env={**os.environ, **addresses},
    )


def secret(service, name):
    return compose("exec", "-T", service, "cat", "/secrets/" + name).stdout.strip()


@pytest.fixture(scope="module")
def composition():
    compose("down", "-v", check=False)
    compose("up", "-d", "--build")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            if press_get("/_health/health")[0] == 200:
                break
        except OSError:
            # Docker's port forward accepts and drops connections until the server listens.
            pass
        time.sleep(2)
    yield
    compose("down", "-v", check=False)


def test_site_server_cannot_write_release_storage(composition, tmp_path):
    """The site server's credentials cannot write releases; no credential reaches storage or git."""
    hosts = {
        "MC_HOST_c": "http://{}:{}@rustfs:9000".format(
            secret("site-server", "storage_access"), secret("site-server", "storage_secret")
        ),
        "MC_HOST_w": "http://{}:{}@rustfs:9000".format(
            secret("websites", "storage_access"), secret("websites", "storage_secret")
        ),
    }
    attempt = mc(hosts, "pipe", "c/releases/intruder.txt", stdin="x")
    assert attempt.returncode != 0 and "Insufficient permissions" in attempt.stdout + attempt.stderr
    copied = mc(hosts, "cp", "--recursive", "w/releases/", "/out/", mount=tmp_path)
    assert copied.returncode == 0, copied.stderr
    stored = [path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()]
    assert stored and not any(path.name == "intruder.txt" for path in tmp_path.rglob("*"))
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    committed = [(ROOT / path).read_bytes() for path in tracked if path and (ROOT / path).is_file()]
    for service, names in (
        ("websites", ("storage_access", "storage_secret", "token", "operator_password")),
        ("site-server", ("storage_access", "storage_secret")),
    ):
        for name in names:
            value = secret(service, name).encode()
            assert not any(value in raw for raw in stored)
            assert not any(value in raw for raw in committed)


def mc(hosts, *arguments, stdin=None, mount=None):
    """Run mc on the composition network; credentials travel in the environment, not in argv."""
    command = ["docker", "run", "--rm", "-i", "--network", "kajenn-websites_default"]
    for name in hosts:
        command += ["-e", name]
    if mount is not None:
        command += ["-v", f"{mount}:/out"]
    return subprocess.run(
        [*command, MC, *arguments],
        input=stdin, capture_output=True, text=True, timeout=120, check=False,
        env={**os.environ, **hosts},
    )


def test_site_sources_are_versioned_and_hidden_from_the_site_server(composition, tmp_path):
    """N3: websites saves and restores a site source; the site server cannot read sources."""
    mcp = Mcp("http://127.0.0.1:8875", "127.0.0.1:8875", secret("websites", "token"))
    site = mcp("site_new", key="docker-site", name="Docker")["site_id"]
    mcp("content_add", site_id=site, key="c", name="Hero", format="html", text="<p>hi</p>")
    first = mcp("site_save", site_id=site)["version_id"]
    mcp("content_add", site_id=site, key="d", name="Later", format="html", text="<p>x</p>")
    mcp("site_save", site_id=site)
    mcp("site_restore", site_id=site, version_id=first)

    assert len(mcp("site_versions", site_id=site)) == 4
    assert [c["name"] for c in mcp("site_read", site_id=site)["contents"]] == ["Hero"]
    hosts = {
        "MC_HOST_c": "http://{}:{}@rustfs:9000".format(
            secret("site-server", "storage_access"), secret("site-server", "storage_secret")
        )
    }
    denied = mc(hosts, "ls", "--recursive", "c/sources/")
    assert denied.returncode != 0 and "Access Denied" in denied.stdout + denied.stderr
    assert mc(hosts, "ls", "c/releases/").returncode == 0


def press_get(path):
    connection = http.client.HTTPConnection("127.0.0.1", 8877, timeout=10)
    try:
        connection.request("GET", path, headers={"Host": "press.localhost:8877"})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_site_server_serves_the_site_published_page_by_page(composition):
    """N4: the example site is published page by page and served by the site server."""
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            if press_get("/_health/health")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(2)
    assert "published site" in compose("logs", "site-publisher").stdout
    status, home = press_get("/")
    assert status == 200 and b"Write it. Review it." in home
    assert press_get("/features/")[0] == 200 and press_get("/get-started/")[0] == 200
    assert b"http://press.localhost:8877/features/" in press_get("/sitemap.xml")[1]

    sites = compose("exec", "-T", "site-server", "cat", "/config/sites.json").stdout
    (site,) = json.loads(sites)["bindings"].values()
    mcp = Mcp("http://127.0.0.1:8875", "127.0.0.1:8875", secret("websites", "token"))
    mcp("maintenance_set", site_id=site, key="docker-maintenance-on", on=True)
    time.sleep(2)
    assert press_get("/")[0] == 503
    mcp("maintenance_set", site_id=site, key="docker-maintenance-off", on=False)
    time.sleep(2)
    assert press_get("/")[0] == 200
