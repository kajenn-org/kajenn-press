#!/bin/bash
# Regenerate the hashed requirement locks of the three images from pyproject.toml.
set -euo pipefail
cd "$(dirname "$0")/../.."
compile() {
  uv pip compile pyproject.toml --generate-hashes --python-version 3.12 \
    --python-platform aarch64-unknown-linux-gnu --no-header -q "$@"
}
compile --extra admin --extra release-s3 --extra help --extra publish -o deploy/docker/requirements-websites.txt
compile --extra render -o deploy/docker/requirements-render.txt
compile --extra release-s3 -o deploy/docker/requirements-child.txt
