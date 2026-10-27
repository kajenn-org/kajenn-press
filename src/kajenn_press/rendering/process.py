"""Bounded disposable process supervision; the parent alone owns persistence."""

import json
import math
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from uuid import uuid4

from genro_bag import Bag

from .contract import CONTRACT, RenderProblem, canonical, sha256


class RenderWorker:
    def __init__(self, python, *, timeout=15.0, output_limit=8 * 1024 * 1024):
        if (
            not isinstance(timeout, (float, int))
            or isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite positive number")
        if type(output_limit) is not int or output_limit <= 0:
            raise ValueError("output_limit must be a positive integer")
        self.python = str(Path(python).absolute())
        self.timeout = timeout
        self.output_limit = output_limit

    def _call(self, request):
        encoded = canonical(request)
        if len(encoded) > 48 * 1024 * 1024:
            raise RenderProblem("input_limit", "Encoded worker request exceeds 48 MiB")
        with TemporaryDirectory(prefix="kajenn-render-") as cwd, TemporaryFile() as incoming:
            incoming.write(encoded)
            incoming.seek(0)
            environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "TZ": "UTC"}
            try:
                process = subprocess.Popen(
                    [self.python, "-I", "-m", "kajenn_press.rendering.worker"],
                    stdin=incoming,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    env=environment,
                    close_fds=True,
                    start_new_session=True,
                )
            except OSError as exc:
                raise RenderProblem("worker_unavailable", "Cannot start configured worker") from exc
            output = bytearray()
            total = 0
            deadline = time.monotonic() + self.timeout
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ, True)
                    selector.register(process.stderr, selectors.EVENT_READ, False)
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise RenderProblem("worker_timeout", "Worker deadline exceeded")
                        for key, _ in selector.select(min(remaining, 0.1)):
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            total += len(chunk)
                            if total > self.output_limit:
                                raise RenderProblem("output_limit", "Worker output exceeds limit")
                            if key.data:
                                output.extend(chunk)
                try:
                    code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired as exc:
                    raise RenderProblem("worker_timeout", "Worker deadline exceeded") from exc
                if code != 0:
                    raise RenderProblem(
                        "worker_exit", "Worker exited unsuccessfully", exit_code=code
                    )
            finally:
                # Also close descendants that inherited pipes or outlived their parent.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                process.stdout.close()
                process.stderr.close()
            try:
                response = json.loads(output)
                if (
                    not isinstance(response, dict)
                    or type(response.get("ok")) is not bool
                    or (
                        not response["ok"]
                        and (
                            set(response) != {"ok", "diagnostics"}
                            or not response["diagnostics"]
                            or not self._diagnostics_valid(response["diagnostics"])
                        )
                    )
                ):
                    raise ValueError("invalid envelope")
            except (ValueError, UnicodeError) as exc:
                raise RenderProblem("invalid_output", "Malformed worker response") from exc
            return response

    @staticmethod
    def _diagnostics_valid(diagnostics):
        return isinstance(diagnostics, list) and all(
            isinstance(item, dict)
            and isinstance(item.get("code"), str)
            and isinstance(item.get("message"), str)
            for item in diagnostics
        )

    def profile(self):
        response = self._call({"action": "profile"})
        if (
            not response["ok"]
            or set(response) != {"ok", "profile"}
            or not isinstance(response["profile"], dict)
            or response["profile"].get("contract") != CONTRACT
        ):
            raise RenderProblem("unqualified_profile", "Worker did not report a qualified profile")
        return response["profile"]

    def plain_template(self, engine, python_source):
        """The plain Source Bag of a Python template, built in the worker."""
        response = self._call(
            {"action": "plain_template", "engine": engine, "source": python_source}
        )
        if not response["ok"]:
            raise RenderProblem(
                "invalid_template", "Template did not build", diagnostics=response["diagnostics"]
            )
        return Bag.from_tytx(response["template"])

    def render_page(self, request):
        """Render a page request built by `kajenn_press.site.render.page_request`."""
        response = self._call({"action": "render_page", **request})
        if not response["ok"]:
            return {"status": "failed", "diagnostics": response["diagnostics"]}
        if (
            set(response) != {"ok", "html", "digest", "diagnostics"}
            or not isinstance(response["html"], str)
            or not response["html"].lower().startswith("<!doctype html><html")
            or response["digest"] != sha256(response["html"].encode())
            or not self._diagnostics_valid(response["diagnostics"])
        ):
            raise RenderProblem("invalid_output", "Worker result failed validation")
        return {
            "status": "succeeded",
            "html": response["html"],
            "diagnostics": response["diagnostics"],
        }

    def render(self, frozen):
        """Coordinator-internal execution. Public callers use RenderService authorization."""
        attempt = {"attempt_id": uuid4().hex, "input_digest": frozen.digest}
        try:
            response = self._call(
                {"action": "render", "input": frozen.unpack(), "input_digest": frozen.digest}
            )
            if not response["ok"]:
                return {**attempt, "status": "failed", "diagnostics": response["diagnostics"]}
            if (
                set(response) != {"ok", "profile", "input_digest", "html", "digest", "diagnostics"}
                or not isinstance(response["html"], str)
                or not response["html"].lower().startswith("<!doctype html><html")
                or not response["html"].lower().endswith("</html>")
                or response["digest"] != sha256(response["html"].encode())
                or response["input_digest"] != frozen.digest
                or response["profile"] != frozen.unpack()["profile"]
                or not self._diagnostics_valid(response["diagnostics"])
            ):
                raise RenderProblem("invalid_output", "Worker result failed validation")
            return {
                **attempt,
                "status": "succeeded",
                "html": response["html"],
                "digest": response["digest"],
                "profile": response["profile"],
                "diagnostics": response["diagnostics"],
            }
        except RenderProblem as exc:
            return {**attempt, "status": "failed", "diagnostics": [exc.diagnostic]}
