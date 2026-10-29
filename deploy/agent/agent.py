"""The server agent as a service on a site server host (N7b, d-server-agent).

Configuration from the environment; secrets from files:
  AGENT_TOKEN_FILE  the manager's bearer token for this server
  AGENT_ALLOWED     client addresses allowed to call, comma separated
  AGENT_DRIVER      nginx, caddy or traefik
  AGENT_UPSTREAM    the site server, such as http://127.0.0.1:8877 (nginx, traefik)
  AGENT_NGINX_DIR, AGENT_ACME_WEBROOT, AGENT_ACME_EMAIL      (nginx)
  AGENT_TRAEFIK_DIR, AGENT_TRAEFIK_ENTRYPOINT, AGENT_TRAEFIK_RESOLVER  (traefik)
  AGENT_PORT        default 8890; AGENT_TLS_CERT and AGENT_TLS_KEY for https
"""

import os
from pathlib import Path

import uvicorn

from kajenn_press.agent.app import create_agent_server
from kajenn_press.agent.drivers import CaddyDriver, NginxDriver, TraefikDriver


def driver():
    name = os.environ["AGENT_DRIVER"]
    if name == "nginx":
        return NginxDriver(
            os.environ["AGENT_NGINX_DIR"],
            os.environ["AGENT_ACME_WEBROOT"],
            os.environ["AGENT_UPSTREAM"],
            os.environ["AGENT_ACME_EMAIL"],
        )
    if name == "caddy":
        return CaddyDriver()
    if name == "traefik":
        return TraefikDriver(
            os.environ["AGENT_TRAEFIK_DIR"],
            os.environ["AGENT_UPSTREAM"],
            os.environ.get("AGENT_TRAEFIK_ENTRYPOINT", "websecure"),
            os.environ.get("AGENT_TRAEFIK_RESOLVER", "letsencrypt"),
        )
    raise SystemExit(f"Unknown AGENT_DRIVER {name}: use nginx, caddy or traefik")


def main():
    server = create_agent_server(
        token=Path(os.environ["AGENT_TOKEN_FILE"]).read_text().strip(),
        driver=driver(),
        allowed=[a.strip() for a in os.environ["AGENT_ALLOWED"].split(",") if a.strip()],
    )
    tls = {}
    if os.environ.get("AGENT_TLS_CERT"):
        tls = {"ssl_certfile": os.environ["AGENT_TLS_CERT"], "ssl_keyfile": os.environ["AGENT_TLS_KEY"]}
    uvicorn.run(server, host="0.0.0.0", port=int(os.environ.get("AGENT_PORT", "8890")), **tls)


if __name__ == "__main__":
    main()
