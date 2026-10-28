"""Site sources and releases on external S3 buckets (deploy/docker/compose.external-s3.yaml).

The disposable S3 server named by KAJENN_RELEASE_S3 stands in for Hetzner Object Storage;
containers reach it through host.docker.internal. Needs Docker: set KAJENN_DOCKER=1.
Removes the composition's volumes first.
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest
from docker.test_docker_composition_contract import ADDRESSES, COMPOSE, ROOT
from publication.storage_support import bucket_objects, s3_credentials, versioned_bucket

sys.path.insert(0, str(ROOT / "examples/kajenn_press_site"))

from publish import Mcp

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1" or "KAJENN_RELEASE_S3" not in os.environ,
    reason="Set KAJENN_DOCKER=1 and KAJENN_RELEASE_S3 to drive Docker with an external bucket",
)
EXTERNAL = [*COMPOSE, "-f", str(ROOT / "deploy/docker/compose.external-s3.yaml")]


def manager_ready():
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                "http://127.0.0.1:8875/admin/", headers={"Host": "127.0.0.1:8875"}
            ),
            timeout=5,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


@pytest.fixture(scope="module")
def external(tmp_path_factory):
    releases, sources = versioned_bucket(), versioned_bucket()
    credentials = tmp_path_factory.mktemp("s3-credentials")
    (credentials / "access").write_text(s3_credentials()["access_key"])
    (credentials / "secret").write_text(s3_credentials()["secret_key"])
    endpoint = releases["endpoint_url"].replace("127.0.0.1", "host.docker.internal")
    environment = {
        **os.environ,
        **ADDRESSES,
        "KPRESS_S3_ENDPOINT": endpoint,
        "KPRESS_S3_BUCKET": releases["bucket"],
        "KPRESS_S3_BASE_PATH": "kpress",
        "KPRESS_SOURCES_BUCKET": sources["bucket"],
        "KPRESS_S3_CREDENTIALS_DIR": str(credentials),
    }

    def compose(*arguments, check=True):
        return subprocess.run(
            [*EXTERNAL, *arguments],
            capture_output=True,
            text=True,
            check=check,
            timeout=900,
            env=environment,
        )

    compose("--profile", "rustfs", "down", "-v", check=False)
    compose("up", "-d", "--build")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline and not manager_ready():
        time.sleep(2)
    yield compose, releases, sources
    compose("--profile", "rustfs", "down", "-v", check=False)


def test_sources_and_releases_go_to_the_external_buckets(external):
    compose, releases, sources = external
    running = compose("ps", "--format", "{{.Service}}").stdout.split()
    assert "rustfs" not in running and "websites" in running
    token = compose("exec", "-T", "websites", "cat", "/secrets/token").stdout.strip()
    mcp = Mcp("http://127.0.0.1:8875", "127.0.0.1:8875", token)
    site = mcp("site_new", key="external-site", name="External")["site_id"]
    mcp("publish", site_id=site, key="external-publish", selected=[])

    assert any(key.startswith(f"sites/{site}/") for key in bucket_objects(sources))
    assert f"kpress/sites/{site}/index.json" in bucket_objects(releases)
