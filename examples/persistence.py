"""Run twice on a private directory to demonstrate durable, idempotent revisions."""

import argparse
import json
from pathlib import Path

from kajenn_public_site.catalog.local import Change, LocalCatalog


def authorize_demo(principal, snapshot, changes):
    """Explicit trusted local example context, never an HTTP authentication bypass."""
    if principal != "local-demo":
        raise PermissionError("Only the local demonstration principal is admitted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Private local data directory outside the checkout")
    args = parser.parse_args()
    with LocalCatalog(args.root) as catalog:
        created = catalog.commit(
            principal="local-demo",
            scope="installation",
            key="demo-create",
            changes=[
                Change(
                    "site:demo",
                    data={"kind": "content", "language": "it"},
                    payloads={"body": b"<p>Prima versione.</p>\r\n"},
                )
            ],
            authorize=authorize_demo,
        )
        first = created["results"][0]
        updated = catalog.commit(
            principal="local-demo",
            scope="installation",
            key="demo-update",
            changes=[
                Change(
                    "site:demo",
                    first["record_id"],
                    1,
                    {"kind": "content", "language": "it"},
                    {"body": b"<p>Seconda versione.</p>\r\n"},
                )
            ],
            authorize=authorize_demo,
        )
    with LocalCatalog(args.root) as reopened:
        assert reopened.read_payload(first["revision_id"], "body") == b"<p>Prima versione.</p>\r\n"
        assert reopened.receipt("local-demo", "installation", "demo-update") == updated
        print(
            json.dumps(
                {
                    "catalog_generation": reopened.read().generation,
                    "record_id": first["record_id"],
                    "first_revision": first["revision_id"],
                    "current_revision": updated["results"][0]["revision_id"],
                    "historical_source": reopened.read_payload(
                        first["revision_id"], "body"
                    ).decode(),
                    "restart": "verified",
                    "idempotent_replay": "same IDs and generation on repeat",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
