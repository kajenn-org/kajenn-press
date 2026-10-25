"""A child in Docker: StaticSiteServerApplication with read-only RustFS credentials.

Bindings come from /config/child.json, written by the builder after publishing.
"""

import json
import os
from pathlib import Path

import uvicorn

from kajenn_public_site.child import create_static_site_server


def secret(name):
    return (Path("/secrets") / name).read_text().strip()


def main():
    config = json.loads(Path("/config/child.json").read_text())
    server = create_static_site_server(
        bindings=config["bindings"],
        release_storage={
            "protocol": "s3",
            "bucket": "releases",
            "endpoint_url": "http://rustfs:9000",
            "access_key": secret("storage_access"),
            "secret_key": secret("storage_secret"),
        },
        cache_seconds=int(os.environ.get("CHILD_CACHE_SECONDS", "5")),
    )
    uvicorn.run(server, host="0.0.0.0", port=8876, log_level="warning")


if __name__ == "__main__":
    main()
