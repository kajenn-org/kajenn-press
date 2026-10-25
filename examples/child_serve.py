"""Serve sites from release storage with StaticSiteServerApplication; no catalog, Gramlot or render worker.

The configuration file is private JSON written by the deployment:

    {
      "bindings": {"http://kajenn.localhost:8876": "<settings_id>"},
      "release_storage": {"protocol": "s3", "bucket": "releases",
                          "endpoint_url": "http://127.0.0.1:19000",
                          "access_key": "...", "secret_key": "..."},
      "cache_seconds": 5
    }

Use read-only storage credentials: the child never writes release storage.
"""

import argparse
import json

import uvicorn

from kajenn_press.child import create_static_site_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="Private JSON configuration file")
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    with open(args.config) as stream:
        config = json.load(stream)
    server = create_static_site_server(
        bindings=config["bindings"],
        release_storage=config["release_storage"],
        cache_seconds=config.get("cache_seconds", 5),
    )
    uvicorn.run(server, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
