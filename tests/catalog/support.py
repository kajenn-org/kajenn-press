"""Real filesystem/process scenarios shared by contract tests and the crash worker."""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from kajenn_public_site.catalog.local import Change, LocalCatalog


@contextmanager
def workspace():
    with TemporaryDirectory(prefix="kajenn-persistence-") as root:
        yield Path(root)


def allow(principal, snapshot, changes):
    if principal != "admin":
        raise PermissionError("No grant")


def commit(catalog, key, *changes):
    return catalog.commit(
        principal="admin", scope="installation", key=key, changes=changes, authorize=allow
    )


def baseline(root):
    with LocalCatalog(root) as c:
        return commit(
            c,
            "baseline",
            Change("site:one", data={"title": "First"}, payloads={"body": b"old\r\n"}),
        )


def crash_changes(c):
    first = c.receipt("admin", "installation", "baseline")["results"][0]
    return [
        Change(
            "site:one",
            first["record_id"],
            1,
            {"title": "Next"},
            {"body": b"<p>new exact source</p>\r\n" * 1000},
        ),
        Change("library", data={"kind": "css"}, payloads={"source": b"p {color:red}"}),
    ]


def worker(root, action, stage=""):
    env = dict(os.environ)
    project = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join([str(project / "src"), str(project / "tests")])
    return subprocess.run(
        [sys.executable, str(Path(__file__).with_name("worker.py")), str(root), action, stage],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
