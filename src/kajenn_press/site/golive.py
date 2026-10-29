"""Putting a site online on its server (N7b, proposal section First publication).

`go_live` checks the DNS records, publishes the site, asks the server's agent to serve
the site's names with TLS, and checks the address answers. Each step reports its
outcome; the first failing step stops the others. Agent tokens are secret files of the
manager, one per server (`<tokens dir>/<server>.token`), never in Bags or buckets.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

from ..domain import DomainError
from .dns import host


class AgentClient:
    """Calls the agents of the registered servers with their tokens (N7b-D1)."""

    def __init__(self, tokens_dir, timeout=600):
        self.tokens_dir, self.timeout = Path(tokens_dir), timeout

    def call(self, server_name, server, action, names):
        token_file = self.tokens_dir / f"{server_name}.token"
        if not token_file.exists():
            raise DomainError("unavailable", f"No agent token for server {server_name}")
        request = urllib.request.Request(
            f"{server['agent_url']}/{action}",
            data=json.dumps({"names": names}).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + token_file.read_text().strip(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.load(response)
        except urllib.error.HTTPError as exc:
            reply = json.loads(exc.read() or b"{}")
        except OSError as exc:
            raise DomainError("unavailable", f"The agent of {server_name} does not answer") from exc
        if not reply.get("ok"):
            message = reply.get("error", {}).get("message", "the agent refused")
            raise DomainError("unavailable", f"{server_name}: {message}")
        return reply["result"]


def address_answers(address, timeout=30):
    """Whether the site's address answers 200 over its own scheme."""
    try:
        with urllib.request.urlopen(address + "/", timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def go_live(service, identity, site_id, publish):
    """Run the steps; `publish` publishes every changed page and returns its result."""
    steps = []

    def step(name, ok, detail=None):
        steps.append({"step": name, "ok": ok, "detail": detail})
        return ok

    site = service.site(identity, site_id)
    plan = service.site_dns_plan(identity, site_id)
    checked = service.dns_check_plan(plan)
    if not step("dns", checked["ok"], checked):
        return {"ok": False, "steps": steps}
    result = publish()
    if not step("publish", not result["failed"], result):
        return {"ok": False, "steps": steps}
    address = service.publisher.site_address(site)
    names = [host(origin) for origin in service.publisher.site_origins(site, address)]
    server_name = site.bag.get_node("info").attr["server"]
    try:
        served = service.agents.call(
            server_name, service.servers.get(server_name), "domain_add", names
        )
    except DomainError as exc:
        step("certificate", False, str(exc))
        return {"ok": False, "steps": steps}
    step("certificate", True, served)
    online = service.address_answers(address)
    step("online", online, address)
    return {"ok": online, "steps": steps, "address": address}
