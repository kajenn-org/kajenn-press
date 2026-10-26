"""Plan-owned behavior contracts; implement only the copied test bodies.

They drive the real composition in deploy/docker and need Docker: set KAJENN_DOCKER=1.
They remove the composition's volumes first, so they always start from nothing.
"""

import http.client
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
sys.path.insert(0, str(ROOT / "examples/kajenn_org"))

from build import Mcp


def compose(*arguments, check=True, addresses=ADDRESSES):
    return subprocess.run(
        [*COMPOSE, "--profile", "demo", *arguments], capture_output=True, text=True,
        check=check, timeout=900, env={**os.environ, **addresses},
    )


def child_get(path):
    """GET without following redirects, as a browser on kajenn.localhost would send it."""
    connection = http.client.HTTPConnection("127.0.0.1", 8876, timeout=10)
    try:
        connection.request("GET", path, headers={"Host": "kajenn.localhost:8876"})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def secret(service, name):
    return compose("exec", "-T", service, "cat", "/secrets/" + name).stdout.strip()


@pytest.fixture(scope="module")
def composition():
    compose("down", "-v", check=False)
    compose("up", "-d", "--build")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            if child_get("/_health/health")[0] == 200:
                break
        except OSError:
            # Docker's port forward accepts and drops connections until the child listens.
            pass
        time.sleep(2)
    yield
    compose("down", "-v", check=False)


def test_composition_serves_kajenn_org_from_the_child(composition):
    # wf:contract: From a clean checkout the composition builds kajenn.org in websites through
    # wf:contract: MCP, activates it, and the child serves it on kajenn.localhost.
    built = compose("logs", "builder").stdout
    assert "published build" in built and "kajenn.localhost:8876" in built
    for path in ("/en/", "/en/concepts/", "/en/get-started/", "/sitemap.xml"):
        status, body = child_get(path)
        assert status == 200, path
    status, body = child_get("/en/")
    assert b'aria-current="page">Overview' in body and b"A <em>spicy</em> ASGI" in body
    assert child_get("/")[0] == 307
    mcp = Mcp("http://127.0.0.1:8875", "127.0.0.1:8875", secret("websites", "token"))
    (child,) = mcp("child_list")
    assert child["attributes"]["name"] == "kajenn-org"
    assert child["deployment"]["state"] == "up_to_date"


def test_child_container_cannot_write_release_storage(composition, tmp_path):
    # wf:contract: The child's storage credentials cannot write the release bucket; websites is
    # wf:contract: its only writer, and no credential is committed or written to release storage.
    hosts = {
        "MC_HOST_c": "http://{}:{}@rustfs:9000".format(
            secret("child", "storage_access"), secret("child", "storage_secret")
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
        ("child", ("storage_access", "storage_secret")),
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


def test_update_and_rollback_reach_the_child_within_the_cache_interval(composition):
    """Done criterion: an update and a rollback in websites reach the child within its cache."""
    update_and_rollback()


def update_and_rollback():
    mcp = Mcp("http://127.0.0.1:8875", "127.0.0.1:8875", secret("websites", "token"))
    (child,) = mcp("child_list")
    settings_id = child["attributes"]["settings_id"]
    channel = mcp("channel_read", settings_id=settings_id)
    first = channel["attributes"]["active_build"]
    variants = [
        mcp("record_read", record_id=r["record_id"])
        for r in mcp("records_index", scope="site:" + child["attributes"]["site_id"])
        if r["kind"] == "variant"
    ]
    changed = []
    for variant in variants:
        blocks = {
            name.removeprefix("block."): {"format": "html", "source": payload["text"]}
            for name, payload in variant["sources"].items()
        }
        if "A <em>spicy</em> ASGI" in blocks["hero"]["source"]:
            blocks["hero"]["source"] = blocks["hero"]["source"].replace(
                "A <em>spicy</em> ASGI", "A <em>very spicy</em> ASGI"
            )
        saved = mcp(
            "draft_save", key="docker-update-" + variant["record_id"],
            variant_id=variant["record_id"], expected_generation=variant["generation"],
            template_revision=variant["attributes"]["template_revision"], blocks=blocks,
        )
        changed.append(saved["records"][0]["revision_id"])
    candidate = mcp("candidate_create", key="docker-update", settings_id=settings_id,
                    variant_revisions=changed)
    job = mcp("build_start", key="docker-update-build", candidate_id=candidate["record_id"])
    while mcp("build_status", build_id=job["record_id"])["attributes"]["state"] in {"queued", "running"}:
        time.sleep(0.5)
    mcp("release_activate", key="docker-update-activate", settings_id=settings_id,
        build_id=job["record_id"], expected_generation=channel["generation"])
    assert within(lambda body: b"very spicy" in body, 8)
    mcp("release_rollback", key="docker-rollback", settings_id=settings_id, build_id=first,
        expected_generation=channel["generation"] + 1)
    assert within(lambda body: b"very spicy" not in body and b"spicy</em> ASGI" in body, 8)


def within(accept, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, body = child_get("/en/")
        if status == 200 and accept(body):
            return True
        time.sleep(0.5)
    return False
