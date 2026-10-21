"""Launch the authenticated local editor API with a deployment-owned token."""

import argparse
import os

from kajenn_public_site.application import create_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Private runtime directory outside the checkout")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    token = os.environ.get("KAJENN_PUBLIC_SITE_TOKEN")
    if not token or len(token) < 32:
        parser.error(
            "Set KAJENN_PUBLIC_SITE_TOKEN to a private random token of at least 32 characters"
        )
    server = create_server(
        args.root,
        auth={"bearer": {"local-admin": {"token": token, "tags": "editor"}}},
        grants={"local-admin": {"*": ["read", "write", "use", "create_site"]}},
    )
    server.serve(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
