"""Release storage on an external S3 bucket (deploy/docker/compose.external-s3.yaml).

The disposable S3 server named by KAJENN_RELEASE_S3 stands in for Hetzner Object Storage;
containers reach it through host.docker.internal. Needs Docker: set KAJENN_DOCKER=1.
Removes the composition's volumes first.
"""

import os
import subprocess
import time

import pytest
from docker.test_docker_composition_contract import ADDRESSES, COMPOSE, ROOT, child_get
from publication.storage_support import bucket_objects, release_bucket, s3_credentials

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1" or "KAJENN_RELEASE_S3" not in os.environ,
    reason="Set KAJENN_DOCKER=1 and KAJENN_RELEASE_S3 to drive Docker with an external bucket",
)
EXTERNAL = [*COMPOSE, "-f", str(ROOT / "deploy/docker/compose.external-s3.yaml"), "--profile", "demo"]


@pytest.fixture(scope="module")
def external(tmp_path_factory):
    config = release_bucket()
    credentials = tmp_path_factory.mktemp("s3-credentials")
    (credentials / "access").write_text(s3_credentials()["access_key"])
    (credentials / "secret").write_text(s3_credentials()["secret_key"])
    endpoint = config["endpoint_url"].replace("127.0.0.1", "host.docker.internal")
    environment = {
        **os.environ, **ADDRESSES,
        "KPRESS_S3_ENDPOINT": endpoint,
        "KPRESS_S3_BUCKET": config["bucket"],
        "KPRESS_S3_BASE_PATH": "kpress",
        "KPRESS_S3_CREDENTIALS_DIR": str(credentials),
    }

    def compose(*arguments, check=True):
        return subprocess.run(
            [*EXTERNAL, *arguments], capture_output=True, text=True, check=check, timeout=900,
            env=environment,
        )

    compose("--profile", "rustfs", "down", "-v", check=False)
    compose("up", "-d", "--build")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            if child_get("/_health/health")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(2)
    yield compose, config
    compose("--profile", "rustfs", "down", "-v", check=False)


def test_releases_go_to_the_external_bucket_under_its_base_path(external):
    compose, config = external
    running = compose("ps", "--format", "{{.Service}}").stdout.split()
    assert "rustfs" not in running and {"websites", "child"} <= set(running)
    assert "published build" in compose("logs", "builder").stdout
    for path in ("/en/", "/en/concepts/", "/sitemap.xml"):
        assert child_get(path)[0] == 200, path
    stored = bucket_objects(config)
    assert stored and all(key.startswith("kpress/") for key in stored)
