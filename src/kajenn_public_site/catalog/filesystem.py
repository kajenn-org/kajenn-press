"""Explicit local catalog primitives, also used for payload directory metadata.

Roots are private and application owned. Concurrent hostile filesystem mutation,
network filesystems and multiple hosts are outside this execution profile.
"""

import fcntl
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from uuid import uuid4

from .errors import IntegrityError, UnsupportedProfile


def encode(value):
    """Canonical UTF-8 metadata; NaN and non-JSON values are rejected."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sync_file(stream):
    stream.flush()
    os.fsync(stream.fileno())
    if sys.platform == "darwin":
        # fsync alone does not request the drive-cache flush on macOS.
        fcntl.fcntl(stream.fileno(), fcntl.F_FULLFSYNC)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_directory(path):
    """Create missing ancestors durably; reject symlinks below the configured root."""
    path = Path(path).absolute()
    # Administrator-selected ancestors may use OS aliases such as /tmp on macOS.
    # The final configured directory (and each managed child) must not be a link.
    path = path.parent.resolve() / path.name
    if path.is_symlink():
        raise IntegrityError(f"Symlink directory: {path}")
    if not path.exists():
        private_directory(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
        sync_directory(path.parent)
    if not path.is_dir():
        raise IntegrityError(f"Not a directory: {path}")
    return path.resolve()


def contained_file(root, name):
    if not isinstance(name, str) or not name or Path(name).name != name or name in (".", ".."):
        raise IntegrityError("Invalid local file name")
    if root.is_symlink() or not root.is_dir():
        raise IntegrityError("Configured directory was replaced")
    path = root / name
    if path.is_symlink() or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
        raise IntegrityError("Expected a regular file, not a link or device")
    return path


def read_json(root, name):
    path = contained_file(root, name)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read()
    try:
        value = json.loads(raw)
        if encode(value) != raw:
            raise ValueError("Noncanonical JSON")
        return value, raw
    except (ValueError, TypeError) as exc:
        raise IntegrityError(f"Invalid metadata: {name}") from exc


def publish_json(root, name, value, staging):
    """Durable temp + same-filesystem replace; used only for catalog metadata."""
    destination = contained_file(root, name)
    temporary = contained_file(staging, uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(encode(value))
        sync_file(stream)
    os.replace(temporary, destination)
    sync_directory(root)
    if staging != root:
        sync_directory(staging)


def qualify_filesystem(root, staging):
    name = uuid4().hex + ".probe"
    try:
        publish_json(root, name, {"value": 1}, staging)
        publish_json(root, name, {"value": 2}, staging)
        if read_json(root, name)[0] != {"value": 2}:
            raise ValueError("Replacement readback failed")
        (root / name).unlink()
        sync_directory(root)
    except (OSError, ValueError) as exc:
        raise UnsupportedProfile("Local catalog needs durable same-filesystem replacement") from exc
