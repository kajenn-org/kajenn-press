"""A site server in Docker: published sites from the release bucket, read-only credentials.

Bindings come from /config/sites.json, written by the site publisher. Pages with
resolvers are not part of the demo, so no render worker is configured here.
"""

import json
import os
from pathlib import Path

import uvicorn

from kajenn_press.site.serving import create_site_server


def release_storage():
    return {
        "protocol": "s3",
        "bucket": os.environ["RELEASE_S3_BUCKET"],
        "endpoint_url": os.environ["RELEASE_S3_ENDPOINT"],
        "access_key": Path(os.environ["RELEASE_S3_ACCESS_FILE"]).read_text().strip(),
        "secret_key": Path(os.environ["RELEASE_S3_SECRET_FILE"]).read_text().strip(),
    }


def main():
    config = json.loads(Path("/config/sites.json").read_text())
    server = create_site_server(
        bindings=config["bindings"],
        release_storage=release_storage(),
        cache_root="/cache",
        cache_seconds=float(os.environ.get("SITE_CACHE_SECONDS", "5")),
    )
    uvicorn.run(server, host="0.0.0.0", port=8877, log_level="warning")


if __name__ == "__main__":
    main()
