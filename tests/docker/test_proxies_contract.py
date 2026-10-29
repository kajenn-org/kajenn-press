"""The proxy drivers against real proxies in Docker (N7b Phase 3, N7b-D4).

No public CA and no real DNS: Caddy uses its internal CA, Traefik's resolver points to
an unreachable CA, and nginx only checks its configuration.
"""

import json
import os
import subprocess
import time

import pytest
from docker.test_docker_composition_contract import Mcp, compose, press_get, secret

from kajenn_press.agent.drivers import NginxDriver, TraefikDriver

pytestmark = pytest.mark.skipif(
    os.environ.get("KAJENN_DOCKER") != "1", reason="Set KAJENN_DOCKER=1 to drive Docker"
)
NGINX = "nginx@sha256:77e5d4a6ad906c5d3793764085706577fa705b1dc6f244ea0241c4b5e2155385"
CADDY = "caddy@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d"  # 2.10.2-alpine
TRAEFIK = "traefik@sha256:d6be8725d21b45bdd84b93ea01438256e0e3c94aa8fa51834fe87f37cd5d4af8"  # v3.5.3
NETWORK = "kajenn-websites_default"
NAME = "www.bottega.example"


def docker(*arguments, check=True, timeout=180):
    return subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, check=check, timeout=timeout
    )


class Recorder:
    def __call__(self, command, timeout=300):
        return ""


def test_the_nginx_configuration_passes_nginx_t(tmp_path):
    conf = tmp_path / "conf"
    conf.mkdir()
    driver = NginxDriver(
        conf, "/var/www/acme", "http://127.0.0.1:8877", "ops@example.org", runner=Recorder()
    )
    driver.add([NAME, "bottega.example"])
    live = tmp_path / "live"
    live.mkdir()
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=" + NAME,
         "-keyout", str(live / "privkey.pem"), "-out", str(live / "fullchain.pem")],
        capture_output=True, check=True, timeout=60,
    )  # fmt: skip
    checked = docker(
        "run", "--rm", "-v", f"{conf}:/etc/nginx/conf.d:ro",
        "-v", f"{live}:/etc/letsencrypt/live/{NAME}:ro", NGINX, "nginx", "-t", check=False,
    )  # fmt: skip
    assert checked.returncode == 0, checked.stderr


def test_traefik_loads_the_router_of_a_site(tmp_path):
    driver = TraefikDriver(tmp_path, "http://site-server:8877")
    driver.add([NAME])
    name = "kpress-test-traefik"
    docker("rm", "-f", name, check=False)
    docker(
        "run", "-d", "--name", name, "-p", "127.0.0.1:18089:8080", "-v", f"{tmp_path}:/dynamic:ro",
        TRAEFIK, "--api.insecure=true", "--providers.file.directory=/dynamic",
        "--entrypoints.websecure.address=:443", "--entrypoints.web.address=:80",
        "--certificatesresolvers.letsencrypt.acme.email=ops@example.org",
        "--certificatesresolvers.letsencrypt.acme.storage=/tmp/acme.json",
        "--certificatesresolvers.letsencrypt.acme.caserver=https://127.0.0.1:1/directory",
        "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web",
    )  # fmt: skip
    try:
        routers = []
        for _ in range(30):
            try:
                found = subprocess.run(
                    ["curl", "-s", "http://127.0.0.1:18089/api/http/routers"],
                    capture_output=True, text=True, timeout=10, check=False,
                )  # fmt: skip
                routers = json.loads(found.stdout or "[]")
            except ValueError:
                routers = []
            if any(r["name"].startswith("kpress-www-bottega-example") for r in routers):
                break
            time.sleep(1)
        router = next(r for r in routers if r["name"].startswith("kpress-www-bottega-example"))
        assert router["status"] == "enabled" and router["rule"] == f"Host(`{NAME}`)"
    finally:
        docker("rm", "-f", name, check=False)


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
            pass
        time.sleep(2)
    yield
    compose("down", "-v", check=False)


def test_caddy_serves_a_bound_name_over_https_without_restart(composition, tmp_path):
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text(
        "{\n\ton_demand_tls {\n\t\task http://site-server:8877/_kpress/ask\n\t}\n}\n"
        "https:// {\n\ttls internal {\n\t\ton_demand\n\t}\n\treverse_proxy site-server:8877\n}\n"
    )
    name = "kpress-test-caddy"
    docker("rm", "-f", name, check=False)
    docker(
        "run", "-d", "--name", name, "--network", NETWORK, "-p", "127.0.0.1:18444:443",
        "-v", f"{caddyfile}:/etc/caddy/Caddyfile:ro", CADDY,
    )  # fmt: skip

    def https(host):
        return subprocess.run(
            ["curl", "-sk", "-o", "/dev/null", "-w", "%{http_code}",
             "--resolve", f"{host}:18444:127.0.0.1", f"https://{host}:18444/"],
            capture_output=True, text=True, timeout=30, check=False,
        )  # fmt: skip

    try:
        before = https("press.localhost")
        mcp = Mcp("http://127.0.0.1:8875", "127.0.0.1:8875", secret("websites", "token"))
        (site,) = [s["site_id"] for s in mcp("site_list") if s["name"] == "Kajenn Press"]
        mcp("site_open", site_id=site, force=True)
        root = next(p["id"] for p in mcp("site_read", site_id=site)["pages"] if p["url"] == "/")
        mcp("page_seo_set", site_id=site, key="caddy-origin", page_id=root,
            fields={"origin": "https://press.localhost:18444"})  # fmt: skip
        mcp("publish", site_id=site, key="caddy-publish", selected=[root])
        time.sleep(3)
        after = https("press.localhost")
        unbound = https("nobody.localhost")
        assert before.stdout != "200"
        assert after.stdout == "200", after.stderr
        assert unbound.stdout != "200"
    finally:
        docker("rm", "-f", name, check=False)
