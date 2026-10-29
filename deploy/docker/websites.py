"""websites in Docker: administration, site sources, render worker and per-page publication.

The operator account and the MCP token come from the private /secrets volume.
Loopback composition only; the user store is not a production identity store.
"""

import copy
import os
from pathlib import Path

import uvicorn
from kajenn.auth.user_store import UserStore

from kajenn_press.application import create_server

SECRETS = Path("/secrets")
PERMISSIONS = ["read", "write", "use", "create_site", "build", "preview_grant", "publish"]


def secret(name):
    return (SECRETS / name).read_text().strip()

def release_storage():
    """The versioned release bucket named by RELEASE_S3_*."""
    config = {
        "protocol": "s3",
        "bucket": os.environ["RELEASE_S3_BUCKET"],
        "endpoint_url": os.environ["RELEASE_S3_ENDPOINT"],
        "access_key": Path(os.environ["RELEASE_S3_ACCESS_FILE"]).read_text().strip(),
        "secret_key": Path(os.environ["RELEASE_S3_SECRET_FILE"]).read_text().strip(),
    }
    if os.environ.get("RELEASE_S3_BASE_PATH"):
        config["base_path"] = os.environ["RELEASE_S3_BASE_PATH"]
    return config


def site_sources():
    """The versioned site source bucket named by SOURCES_S3_*, or None when it is not set."""
    if not os.environ.get("SOURCES_S3_BUCKET"):
        return None
    return {
        "root": "/data/sites",
        "sources": {
            "protocol": "s3",
            "bucket": os.environ["SOURCES_S3_BUCKET"],
            "endpoint_url": os.environ["SOURCES_S3_ENDPOINT"],
            "access_key": Path(os.environ["SOURCES_S3_ACCESS_FILE"]).read_text().strip(),
            "secret_key": Path(os.environ["SOURCES_S3_SECRET_FILE"]).read_text().strip(),
        },
        # Per-page publication (N4) writes to the release bucket, which needs versioning.
        "releases": release_storage(),
        "render_python": "/opt/render/bin/python",
        "private_secret": (SECRETS / "private_link").read_text().strip().encode(),
    }


class OperatorUsers(UserStore):
    """One operator, `operator`, with the generated password in /secrets/operator_password."""

    def __init__(self, storage, **kwargs):
        self.record = {
            "identity": "operator",
            "password_hash": self.hash_password(secret("operator_password")),
            "tags": ["editor"],
            "enabled": True,
        }

    def load_all(self):
        return [copy.deepcopy(self.record)]

    def get(self, identity):
        return copy.deepcopy(self.record) if identity == "operator" else None

    def save(self, record):
        self.record = copy.deepcopy(record)

    def delete(self, identity):
        return False


def main():
    management_origin = os.environ["WEBSITES_MANAGEMENT_ORIGIN"]
    server = create_server(
        "/data",
        auth={"bearer": {"builder": {"token": secret("token"), "tags": "editor"}}},
        grants={"operator": {"*": PERMISSIONS}, "builder": {"*": PERMISSIONS}},
        administration={"origin": management_origin, "users": {"store_class": OperatorUsers}},
        sites=site_sources(),
    )
    # Scheme and client address from X-Forwarded-* only when sent by these addresses (a reverse proxy).
    uvicorn.run(
        server, host="0.0.0.0", port=8875, log_level="warning",
        proxy_headers=True, forwarded_allow_ips=os.environ["WEBSITES_FORWARDED_ALLOW_IPS"],
    )


if __name__ == "__main__":
    main()
