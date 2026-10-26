"""Phase 2 of kpress-deployment: deploy/docker/nginx-kpress.conf in front of websites.

nginx 1.24 (the server's version) runs the example configuration on the composition
network, with a self-signed certificate in place of the certbot ones. Needs Docker:
set KAJENN_DOCKER=1. Removes the composition's volumes first.
"""

import http.client
import os
import ssl
import subprocess
import time

import pytest
from docker.test_docker_composition_contract import COMPOSE, ROOT

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1", reason="Set KAJENN_DOCKER=1 to drive Docker"
)
NGINX = "nginx@sha256:77e5d4a6ad906c5d3793764085706577fa705b1dc6f244ea0241c4b5e2155385"
NAMES = ("kpress.genro.org", "preview.kpress.genro.org")
SERVER = {
    "KPRESS_SCHEME": "https",
    "KPRESS_MANAGEMENT_HOST": NAMES[0],
    "KPRESS_PREVIEW_HOST": NAMES[1],
    "KPRESS_TRUSTED_PROXIES": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
}
CONTAINER = "kpress-test-nginx"


def compose(*arguments, check=True):
    return subprocess.run(
        [*COMPOSE, *arguments], capture_output=True, text=True, check=check, timeout=900,
        env={**os.environ, **SERVER},
    )


def request(port, host, path, tls):
    if tls:
        context = ssl.create_default_context()
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
        connection = http.client.HTTPSConnection("127.0.0.1", port, timeout=10, context=context)
    else:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("GET", path, headers={"Host": host})
        response = connection.getresponse()
        return response.status, response.getheader("location"), response.read()
    finally:
        connection.close()


@pytest.fixture(scope="module")
def proxied(tmp_path_factory):
    work = tmp_path_factory.mktemp("nginx")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
         "-subj", "/CN=" + NAMES[0], "-addext", "subjectAltName=DNS:{},DNS:{}".format(*NAMES),
         "-keyout", str(work / "privkey.pem"), "-out", str(work / "fullchain.pem")],
        capture_output=True, check=True, timeout=60,
    )
    # On the server nginx runs on the host; here it shares the composition network.
    example = (ROOT / "deploy/docker/nginx-kpress.conf").read_text()
    (work / "kpress.conf").write_text(example.replace("127.0.0.1:8875", "websites:8875"))
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, check=False)
    compose("--profile", "demo", "down", "-v", check=False)
    compose("up", "-d", "--build")
    mounts = ["-v", f"{work / 'kpress.conf'}:/etc/nginx/conf.d/default.conf:ro"]
    for name in NAMES:
        mounts += ["-v", f"{work}:/etc/letsencrypt/live/{name}:ro"]
    subprocess.run(
        ["docker", "run", "-d", "--name", CONTAINER, "--network", "kajenn-websites_default",
         "-p", "127.0.0.1:18080:80", "-p", "127.0.0.1:18443:443", *mounts, NGINX],
        capture_output=True, text=True, check=True, timeout=120,
    )
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            if request(18443, NAMES[0], "/admin/", True)[0] == 200:
                break
        except OSError:
            pass
        time.sleep(2)
    yield
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, check=False)
    compose("down", "-v", check=False)


def test_example_configuration_is_valid_for_nginx_1_24(proxied):
    checked = subprocess.run(
        ["docker", "exec", CONTAINER, "nginx", "-t"], capture_output=True, text=True, check=False
    )
    assert checked.returncode == 0, checked.stderr


def test_administration_is_reached_over_https_through_nginx(proxied):
    status, _, body = request(18443, NAMES[0], "/admin/", True)
    assert status == 200 and body


def test_http_redirects_to_https(proxied):
    for name in NAMES:
        status, location, _ = request(18080, name, "/admin/", False)
        assert status == 301 and location == f"https://{name}/admin/"


def test_preview_name_reaches_the_preview_origin_not_the_administration(proxied):
    status, _, body = request(18443, NAMES[1], "/admin/", True)
    assert status == 404 and body == b"Preview unavailable"
