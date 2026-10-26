"""websites in Docker: administration, internal installation, render worker, RustFS releases.

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
    """RELEASE_STORAGE=s3 (default): the RustFS bucket; local: the shared volume at /releases."""
    if os.environ.get("RELEASE_STORAGE", "s3") == "local":
        return {"protocol": "local", "base_path": "/releases"}
    return {
        "protocol": "s3",
        "bucket": "releases",
        "endpoint_url": "http://rustfs:9000",
        "access_key": secret("storage_access"),
        "secret_key": secret("storage_secret"),
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
        "/data/catalog",
        auth={"bearer": {"builder": {"token": secret("token"), "tags": "editor"}}},
        grants={"operator": {"*": PERMISSIONS}, "builder": {"*": PERMISSIONS}},
        publication={
            "management_origin": management_origin,
            "preview_origin": os.environ["WEBSITES_PREVIEW_ORIGIN"],
            "render_python": "/opt/render/bin/python",
            "preview_secret": bytes.fromhex(secret("preview_secret")),
            "release_storage": release_storage(),
        },
        administration={"origin": management_origin, "users": {"store_class": OperatorUsers}},
    )
    # Scheme and client address from X-Forwarded-* only when sent by these addresses (a reverse proxy).
    uvicorn.run(
        server, host="0.0.0.0", port=8875, log_level="warning",
        proxy_headers=True, forwarded_allow_ips=os.environ["WEBSITES_FORWARDED_ALLOW_IPS"],
    )


if __name__ == "__main__":
    main()
