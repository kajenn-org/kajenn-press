"""The server agent and its proxy drivers (N7b Phase 3)."""

import asyncio

import httpx
import pytest

from kajenn_press.agent.app import create_agent_server
from kajenn_press.agent.drivers import CaddyDriver, NginxDriver, TraefikDriver, checked_names
from kajenn_press.domain import DomainError


class Recorder:
    def __init__(self):
        self.commands = []

    def __call__(self, command, timeout=300):
        self.commands.append(command)
        return ""


@pytest.mark.parametrize(
    "names",
    [
        [],
        ["a.example", "b.example", "c.example"],
        ["-bad.example"],
        ["a.example; rm -rf /"],
        ["localhost"],
        [7],
    ],
)
def test_names_are_host_names(names):
    with pytest.raises(DomainError):
        checked_names(names)


def test_nginx_writes_http_then_https_and_runs_certbot(tmp_path):
    runner = Recorder()
    driver = NginxDriver(
        tmp_path, "/var/www/acme", "http://127.0.0.1:8877", "ops@example.org", runner=runner
    )
    status = driver.add(["www.bottega.example", "bottega.example"])
    text = (tmp_path / "kpress-www.bottega.example.conf").read_text()
    assert "server_name www.bottega.example bottega.example;" in text
    assert "ssl_certificate /etc/letsencrypt/live/www.bottega.example/fullchain.pem;" in text
    assert runner.commands[0] == ["sudo", "nginx", "-t"]
    certbot = runner.commands[2]
    assert certbot[:3] == ["sudo", "certbot", "certonly"]
    assert certbot[-4:] == ["-d", "www.bottega.example", "-d", "bottega.example"]
    assert status == {
        "names": ["www.bottega.example", "bottega.example"],
        "configured": True,
        "certificate": True,
    }
    driver.remove(["www.bottega.example", "bottega.example"])
    assert not (tmp_path / "kpress-www.bottega.example.conf").exists()


def test_traefik_writes_one_router_per_site(tmp_path):
    driver = TraefikDriver(tmp_path, "http://site-server:8877")
    driver.add(["bottega.example"])
    text = (tmp_path / "kpress-bottega.example.yml").read_text()
    assert 'rule: "Host(`bottega.example`)"' in text and "certResolver: letsencrypt" in text
    assert driver.status(["bottega.example"])["configured"] is True


def test_caddy_needs_no_file():
    driver = CaddyDriver(runner=Recorder())
    assert driver.add(["bottega.example"])["certificate"] == "on demand"


def calls(app, *requests):
    """Run (action, token, body) requests against one running agent."""

    async def scenario():
        transport = httpx.ASGITransport(app=app, client=("10.0.0.1", 1234))
        incoming, outgoing = asyncio.Queue(), asyncio.Queue()
        lifespan = {"type": "lifespan", "asgi": {"version": "3.0"}}
        task = asyncio.create_task(app(lifespan, incoming.get, outgoing.put))
        await incoming.put({"type": "lifespan.startup"})
        await outgoing.get()
        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://agent") as http:
                return [
                    await http.post(
                        "/" + action, json=body, headers={"Authorization": "Bearer " + token}
                    )
                    for action, token, body in requests
                ]
        finally:
            await incoming.put({"type": "lifespan.shutdown"})
            await outgoing.get()
            await task

    return asyncio.run(scenario())


def test_the_agent_answers_only_its_token_from_allowed_addresses(tmp_path):
    driver = TraefikDriver(tmp_path, "http://site-server:8877")
    allowed = create_agent_server(token="agent-token", driver=driver, allowed=["10.0.0.1"])
    added, wrong, invalid = calls(
        allowed,
        ("domain_add", "agent-token", {"names": ["bottega.example"]}),
        ("domain_add", "wrong", {"names": ["bottega.example"]}),
        ("domain_add", "agent-token", {"names": ["bad name"]}),
    )
    assert added.status_code == 200 and added.json()["result"]["proxy"] == "traefik"
    assert wrong.status_code == 401
    assert invalid.status_code == 422 and invalid.json()["ok"] is False
    other = create_agent_server(token="agent-token", driver=driver, allowed=["10.0.0.9"])
    (refused,) = calls(other, ("domain_status", "agent-token", {"names": ["bottega.example"]}))
    assert refused.status_code == 403
