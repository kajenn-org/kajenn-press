"""Plan-owned behavior contracts; implement only the copied test bodies.

The Phase 4 cycle on a shared Docker volume (deploy/docker/compose.volume.yaml).
Needs Docker: set KAJENN_DOCKER=1. Removes the composition's volumes first.
"""

import os
import subprocess
import time

import pytest
from docker.test_docker_composition_contract import (
    ADDRESSES,
    COMPOSE,
    ROOT,
    child_get,
    secret,
    update_and_rollback,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1", reason="Set KAJENN_DOCKER=1 to drive Docker"
)
VOLUME = [*COMPOSE, "-f", str(ROOT / "deploy/docker/compose.volume.yaml"), "--profile", "demo"]


def volume_compose(*arguments, check=True):
    return subprocess.run(
        [*VOLUME, *arguments], capture_output=True, text=True, check=check, timeout=900,
        env={**os.environ, **ADDRESSES},
    )


@pytest.fixture(scope="module")
def shared_volume():
    volume_compose("--profile", "s3", "down", "-v", check=False)
    volume_compose("up", "-d", "--build")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            if child_get("/_health/health")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(2)
    yield
    volume_compose("--profile", "s3", "down", "-v", check=False)


def test_shared_volume_backend_needs_configuration_only(shared_volume):
    # wf:contract: Switching release storage from RustFS to a shared Docker volume changes only
    # wf:contract: deployment configuration, and the Phase 4 cycle passes unchanged.
    # wf:contract: The startup qualification result for the local mount is recorded.
    running = volume_compose("ps", "--format", "{{.Service}}").stdout.split()
    assert "rustfs" not in running and {"websites", "child"} <= set(running)
    # websites started, so the startup qualification accepted the local mount.
    started = volume_compose("logs", "websites").stdout
    assert "Cannot open" not in started and "partially replaced" not in started
    assert "published build" in volume_compose("logs", "builder").stdout
    for path in ("/en/", "/en/concepts/", "/en/get-started/", "/sitemap.xml"):
        assert child_get(path)[0] == 200, path
    assert child_get("/")[0] == 307
    stored = volume_compose(
        "exec", "-T", "websites", "sh", "-c", "find /releases -type f | wc -l"
    ).stdout.strip()
    assert int(stored) > 0
    denied = volume_compose(
        "exec", "-T", "child", "python", "-c", "open('/releases/intruder', 'w')", check=False
    )
    assert denied.returncode != 0 and "Read-only file system" in denied.stderr
    content = subprocess.run(
        [*VOLUME, "exec", "-T", "websites", "sh", "-c", "cat /releases/*/*"],
        capture_output=True, check=True, timeout=120, env={**os.environ, **ADDRESSES},
    ).stdout
    for name in ("token", "operator_password", "storage_secret"):
        assert secret("websites", name).encode() not in content
    update_and_rollback()
