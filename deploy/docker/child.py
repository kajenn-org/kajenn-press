"""A child in Docker: StaticSiteServerApplication with read-only RustFS credentials.

Bindings come from /config/child.json, written by the builder after publishing.
"""

import json
import os
from pathlib import Path

import uvicorn

from kajenn_press.child import create_static_site_server


def release_storage():
    """RELEASE_STORAGE=s3 (default): the bucket named by RELEASE_S3_*; local: the shared volume at /releases."""
    if os.environ.get("RELEASE_STORAGE", "s3") == "local":
        return {"protocol": "local", "base_path": "/releases"}
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


def main():
    config = json.loads(Path("/config/child.json").read_text())
    server = create_static_site_server(
        bindings=config["bindings"],
        release_storage=release_storage(),
        cache_seconds=int(os.environ.get("CHILD_CACHE_SECONDS", "5")),
    )
    uvicorn.run(server, host="0.0.0.0", port=8876, log_level="warning")


if __name__ == "__main__":
    main()
