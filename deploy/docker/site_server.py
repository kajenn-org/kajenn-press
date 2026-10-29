"""A site server in Docker: published sites from the release bucket, read-only credentials.

Site addresses come from `bindings.json` in the release bucket, written by Publish, so
a new address needs no restart. Pages with resolvers are not part of the demo, so no
render worker is configured here.
"""

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
    server = create_site_server(
        release_storage=release_storage(),
        cache_root="/cache",
        cache_seconds=float(os.environ.get("SITE_CACHE_SECONDS", "5")),
        private_secret=Path(os.environ["PRIVATE_LINK_SECRET_FILE"]).read_text().strip().encode(),
        # The registered name of this server; the demo's site server is the default one.
        server=os.environ.get("SITE_SERVER_NAME", "default"),
    )
    uvicorn.run(server, host="0.0.0.0", port=8877, log_level="warning")


if __name__ == "__main__":
    main()
