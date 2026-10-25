"""Subprocess fault injection: terminate without Python cleanup at real IO edges."""

import os
import sys
from pathlib import Path

from genro_storage import StorageNode

from catalog.support import commit, crash_changes
from kajenn_press.catalog import local
from kajenn_press.catalog.errors import OwnershipError
from kajenn_press.catalog.local import LocalCatalog
from kajenn_press.objects import ObjectStore


def main():
    root, action, stage = sys.argv[1:]
    try:
        with LocalCatalog(root) as c:
            if action == "probe":
                print(c.read().generation)
                return
            if action == "hold":
                print("owned", flush=True)
                sys.stdin.read()
                return
            if action == "read":
                print(c.read().generation)
                assert (
                    c.read_payload(
                        c.receipt("admin", "installation", "baseline")["results"][0]["revision_id"],
                        "body",
                    )
                    == b"old\r\n"
                )
                return
            original_publish = local.publish_json
            original_replace = os.replace
            original_prepare = ObjectStore.prepare
            original_open = StorageNode.open

            def publish(root, name, value, staging):
                original_publish(root, name, value, staging)
                if (
                    (stage == "intent" and root.name == "intents")
                    or (stage == "manifest" and root.name == "manifests")
                    or (stage == "head_durable" and name == "current.json")
                ):
                    os._exit(86)

            def replace(source, destination):
                if stage == "head_before" and Path(destination).name == "current.json":
                    os._exit(86)
                original_replace(source, destination)
                if stage == "head_replaced" and Path(destination).name == "current.json":
                    os._exit(86)

            def prepare(store, ref, data):
                original_prepare(store, ref, data)
                if stage == "payload_complete":
                    os._exit(86)

            def open_payload(node, mode="r", *args, **kwargs):
                stream = original_open(node, mode, *args, **kwargs)
                if stage == "payload_partial" and mode == "xb":
                    stream.write(b"partial")
                    stream.flush()
                    os.fsync(stream.fileno())
                    os._exit(86)
                return stream

            local.publish_json = publish
            os.replace = replace
            ObjectStore.prepare = prepare
            StorageNode.open = open_payload
            commit(c, "crash", *crash_changes(c))
    except OwnershipError:
        sys.exit(23)


if __name__ == "__main__":
    main()
