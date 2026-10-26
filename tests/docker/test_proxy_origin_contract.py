"""Phase 1 of kpress-deployment: addresses from the environment and a trusted reverse proxy.

Drives the composition without the demo profile, as on the server. Needs Docker: set
KAJENN_DOCKER=1. Removes the composition's volumes first.
"""

import http.client
import os
import subprocess
import time

import pytest
from docker.test_docker_composition_contract import COMPOSE

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1", reason="Set KAJENN_DOCKER=1 to drive Docker"
)
PYTHON = "python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
# A server origin behind TLS; every container on the composition network may act as the proxy.
SERVER = {
    "KPRESS_SCHEME": "https",
    "KPRESS_MANAGEMENT_HOST": "kpress.example",
    "KPRESS_PREVIEW_HOST": "preview.kpress.example",
    "KPRESS_TRUSTED_PROXIES": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
}
PROBE = """
import http.client, sys
for host, proto in (sys.argv[1], sys.argv[2]), (sys.argv[1], ""), ("other.example", sys.argv[2]):
    connection = http.client.HTTPConnection("websites", 8875, timeout=10)
    headers = {"Host": host}
    if proto:
        headers["X-Forwarded-Proto"] = proto
    connection.request("GET", "/admin/", headers=headers)
    print(connection.getresponse().status)
"""


def compose(*arguments, check=True):
    return subprocess.run(
        [*COMPOSE, *arguments], capture_output=True, text=True, check=check, timeout=900,
        env={**os.environ, **SERVER},
    )


def listening():
    connection = http.client.HTTPConnection("127.0.0.1", 8875, timeout=5)
    try:
        connection.request("GET", "/admin/")
        return connection.getresponse().status > 0
    except OSError:
        return False
    finally:
        connection.close()


@pytest.fixture(scope="module")
def manager_only():
    compose("--profile", "demo", "down", "-v", check=False)
    compose("up", "-d", "--build")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline and not listening():
        time.sleep(2)
    yield
    compose("down", "-v", check=False)


def test_without_profile_only_the_manager_runs(manager_only):
    services = compose("ps", "-a", "--format", "{{.Service}}").stdout.split()
    assert "websites" in services and "rustfs" in services
    assert "builder" not in services and "child" not in services


def test_forwarded_https_from_a_trusted_proxy_reaches_the_administration(manager_only):
    probe = subprocess.run(
        ["docker", "run", "--rm", "--network", "kajenn-websites_default", PYTHON,
         "python", "-c", PROBE, "kpress.example", "https"],
        capture_output=True, text=True, check=True, timeout=120,
    )
    configured, plain_http, wrong_host = probe.stdout.split()
    assert configured == "200"
    # Without the forwarded scheme the request is http, which is not the configured origin.
    assert plain_http == "404"
    assert wrong_host == "404"
