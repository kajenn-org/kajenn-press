"""Terminate at real activation IO edges, leaving reopen to the owning parent."""

import os
from pathlib import Path

from publication.release_support import publisher

from kajenn_public_site.catalog import local


def interrupt_activation(root, settings_id, build_id, generation, stage):
    _, pub = publisher(root)
    original_publish, original_replace = local.publish_json, os.replace

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

    local.publish_json, os.replace = publish, replace
    pub.execute(
        "admin",
        "release_activate",
        settings_id=settings_id,
        build_id=build_id,
        expected_generation=generation,
        key="crash-activate",
    )
    os._exit(24)
