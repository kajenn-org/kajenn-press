"""Proxy drivers of the server agent (N7b, d-tls-proxy).

Each driver makes the proxy installed on a server serve a site's names, with TLS from
that proxy: nginx with certbot, Caddy with on-demand TLS, Traefik with its certificate
resolver. Names are validated host names; commands are lists built here and run without
a shell, through `sudo` where the configuration says so.
"""

import re
import subprocess
from pathlib import Path

from ..domain import DomainError

HOST = re.compile(r"(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


def checked_names(names):
    """Lower-case host names, one to two (the address and its alias)."""
    if not isinstance(names, list) or not 1 <= len(names) <= 2:
        raise DomainError("invalid_input", "Give the address and, optionally, its alias")
    found = []
    for name in names:
        if not isinstance(name, str) or not HOST.fullmatch(name.lower()):
            raise DomainError("invalid_input", f"{name!r} is not a host name")
        found.append(name.lower())
    return found


def run(command, timeout=300):
    """Run one command; its failure is reported with the tail of its output."""
    done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout).strip().splitlines()[-5:]
        raise DomainError("unavailable", f"{command[0]} failed: " + " | ".join(tail))
    return done.stdout


class NginxDriver:
    """A server block per site in nginx's configuration directory; certificates by certbot."""

    name = "nginx"

    def __init__(self, conf_dir, webroot, upstream, email, sudo=("sudo",), runner=run):
        self.conf_dir, self.webroot = Path(conf_dir), webroot
        self.upstream, self.email = upstream, email
        self.sudo, self.runner = list(sudo), runner

    def path(self, names):
        return self.conf_dir / f"kpress-{names[0]}.conf"

    def block(self, names, tls):
        server_names = " ".join(names)
        http = (
            "server {\n    listen 80;\n    listen [::]:80;\n"
            f"    server_name {server_names};\n"
            f"    location /.well-known/acme-challenge/ {{ root {self.webroot}; }}\n"
        )
        if not tls:
            return (
                http
                + f"    location / {{ proxy_pass {self.upstream}; proxy_set_header Host $host; }}\n}}\n"
            )
        live = f"/etc/letsencrypt/live/{names[0]}"
        return (
            http
            + "    location / { return 301 https://$host$request_uri; }\n}\n\n"
            + "server {\n    listen 443 ssl;\n    listen [::]:443 ssl;\n"
            + f"    server_name {server_names};\n"
            + f"    ssl_certificate {live}/fullchain.pem;\n"
            + f"    ssl_certificate_key {live}/privkey.pem;\n"
            + "    location / {\n"
            + f"        proxy_pass {self.upstream};\n"
            + "        proxy_set_header Host $host;\n"
            + "        proxy_set_header X-Forwarded-Proto $scheme;\n"
            + "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            + "    }\n}\n"
        )

    def reload(self):
        self.runner([*self.sudo, "nginx", "-t"])
        self.runner([*self.sudo, "systemctl", "reload", "nginx"])

    def add(self, names):
        names = checked_names(names)
        # First plain http, so certbot's challenge is answered; then the https block.
        self.path(names).write_text(self.block(names, tls=False))
        self.reload()
        domains = [part for name in names for part in ("-d", name)]
        self.runner(
            [*self.sudo, "certbot", "certonly", "--webroot", "-w", self.webroot,
             "--non-interactive", "--agree-tos", "-m", self.email, *domains]
        )  # fmt: skip
        self.path(names).write_text(self.block(names, tls=True))
        self.reload()
        return self.status(names)

    def remove(self, names):
        names = checked_names(names)
        self.path(names).unlink(missing_ok=True)
        self.reload()
        return {"names": names, "configured": False}

    def status(self, names):
        names = checked_names(names)
        configured = self.path(names).exists()
        text = self.path(names).read_text() if configured else ""
        return {"names": names, "configured": configured, "certificate": "ssl_certificate" in text}


class CaddyDriver:
    """Caddy with on-demand TLS: it asks the site server whether a name is bound."""

    name = "caddy"

    def __init__(self, sudo=("sudo",), runner=run):
        self.sudo, self.runner = list(sudo), runner

    def reload(self):
        self.runner([*self.sudo, "systemctl", "reload", "caddy"])

    def add(self, names):
        # Nothing to write: the binding is the configuration (the `ask` endpoint).
        return {"names": checked_names(names), "configured": True, "certificate": "on demand"}

    def remove(self, names):
        return {"names": checked_names(names), "configured": False}

    def status(self, names):
        return {"names": checked_names(names), "configured": True, "certificate": "on demand"}


class TraefikDriver:
    """One dynamic configuration file per site, watched by Traefik's file provider."""

    name = "traefik"

    def __init__(self, dynamic_dir, upstream, entrypoint="websecure", resolver="letsencrypt"):
        self.dynamic_dir, self.upstream = Path(dynamic_dir), upstream
        self.entrypoint, self.resolver = entrypoint, resolver

    def path(self, names):
        return self.dynamic_dir / f"kpress-{names[0]}.yml"

    def document(self, names):
        key = "kpress-" + names[0].replace(".", "-")
        rule = " || ".join(f"Host(`{name}`)" for name in names)
        return (
            "http:\n  routers:\n"
            f"    {key}:\n"
            f'      rule: "{rule}"\n'
            f"      entryPoints: [{self.entrypoint}]\n"
            f"      service: {key}\n"
            f"      tls:\n        certResolver: {self.resolver}\n"
            "  services:\n"
            f"    {key}:\n      loadBalancer:\n        passHostHeader: true\n"
            f'        servers:\n          - url: "{self.upstream}"\n'
        )

    def reload(self):
        # Traefik's file provider watches the directory: nothing to reload.
        return None

    def add(self, names):
        names = checked_names(names)
        self.path(names).write_text(self.document(names))
        return self.status(names)

    def remove(self, names):
        names = checked_names(names)
        self.path(names).unlink(missing_ok=True)
        return {"names": names, "configured": False}

    def status(self, names):
        names = checked_names(names)
        return {
            "names": names,
            "configured": self.path(names).exists(),
            "certificate": "by Traefik",
        }
