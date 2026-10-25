"""One owned worker slot, durable attempts and conditional artifact sealing."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from ..catalog.errors import Conflict
from ..catalog.filesystem import digest
from ..domain import DomainError
from .artifacts import build_artifacts, verify_bundle


class BuildJobs:
    def start_jobs(self):
        self._stopping = Event()
        self._futures = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kajenn-publication")
        snapshot = self.catalog.read()
        for head in snapshot.records.values():
            revision = snapshot.revisions[head["revision_id"]]
            if revision["data"].get("kind") == "publication_job" and revision["data"]["attributes"][
                "state"
            ] in {"queued", "running"}:
                attrs = {
                    **revision["data"]["attributes"],
                    "state": "interrupted",
                    "diagnostics": [
                        {
                            "code": "process_interrupted",
                            "message": "Previous coordinator did not complete this attempt",
                        }
                    ],
                }
                self._transition(revision, attrs)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stopping.set()
        # Finish/cancel the bounded active subprocess before the caller closes catalog.
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _schedule(self, build_id):
        existing = self._futures.get(build_id)
        if self._closed or existing is not None and not existing.done():
            return
        if (
            self.record(self.catalog.read(), build_id, "publication_job")["data"]["attributes"][
                "state"
            ]
            == "queued"
        ):
            self._futures[build_id] = self._executor.submit(self._run_build, build_id)

    def _build_start(self, snapshot, identity, candidate_id, key):
        candidate = self.record(snapshot, candidate_id, "publication_candidate")
        self.authorize_candidate(identity, candidate)
        return self.change(
            "publication_job",
            {
                "site_id": candidate["data"]["attributes"]["site_id"],
                "candidate_id": candidate_id,
                "candidate_revision": candidate["id"],
                "state": "queued",
                "attempt_id": uuid4().hex,
                "actor": identity,
                "diagnostics": [],
            },
        )

    def _build_retry(
        self, snapshot, identity, build_id, expected_generation, key
    ):
        job = self.record(snapshot, build_id, "publication_job")
        attrs = job["data"]["attributes"]
        if attrs["state"] not in {"failed", "interrupted"}:
            raise DomainError("conflict", "Only failed or interrupted builds can be retried")
        candidate = snapshot.revisions[attrs["candidate_revision"]]
        self.authorize_candidate(identity, candidate)
        return self.change(
            "publication_job",
            {
                **attrs,
                "state": "queued",
                "attempt_id": uuid4().hex,
                "actor": identity,
                "diagnostics": [],
            },
            record_id=build_id,
            expected_generation=expected_generation,
        )

    def _build_status(self, snapshot, identity, build_id):
        return self._result(snapshot, identity, self.record(snapshot, build_id, "publication_job"))

    def _transition(self, expected, attrs, payloads=None, candidate=None):
        def authorize(principal, snapshot, changes):
            current = self.record(snapshot, expected["record_id"], "publication_job")
            if (
                current["id"] != expected["id"]
                or current["data"]["attributes"]["attempt_id"] != attrs["attempt_id"]
            ):
                raise DomainError("stale_attempt", "Attempt no longer owns completion")
            if attrs["state"] == "succeeded":
                if self._stopping.is_set() or current["data"]["attributes"]["state"] != "running":
                    raise DomainError("interrupted", "Coordinator cannot accept this completion")
                self.authorize_candidate(attrs["actor"], candidate)
                verify_bundle(json.loads(payloads["manifest"]), payloads)

        try:
            receipt = self.catalog.commit(
                principal="publication-coordinator",
                scope="publication-jobs",
                key=uuid4().hex,
                changes=[
                    self.change(
                        "publication_job",
                        attrs,
                        payloads,
                        expected["record_id"],
                        expected["generation"],
                    )
                ],
                authorize=authorize,
            )
        except Conflict as exc:
            raise DomainError("stale_attempt", "Another attempt changed this job") from exc
        return self.catalog.read().revisions[receipt["results"][0]["revision_id"]]

    def _run_build(self, build_id):
        with self._lock:
            if self._stopping.is_set():
                return
            job = self.record(self.catalog.read(), build_id, "publication_job")
            if job["data"]["attributes"]["state"] != "queued":
                return
            job = self._transition(job, {**job["data"]["attributes"], "state": "running"})
            candidate = self.catalog.read().revisions[
                job["data"]["attributes"]["candidate_revision"]
            ]
        try:
            self.authorize_candidate(job["data"]["attributes"]["actor"], candidate)
            data = self.candidate_data(candidate)
            if (
                digest(self.catalog.read_payload(candidate["id"], "inputs"))
                != candidate["data"]["attributes"]["input_digest"]
            ):
                raise DomainError("invalid_input", "Candidate digest differs")
            payloads, diagnostics = build_artifacts(
                data, build_id, self.worker, self._stopping.is_set
            )
            with self._lock:
                if self._stopping.is_set():
                    return
                self._transition(
                    job,
                    {
                        **job["data"]["attributes"],
                        "state": "succeeded",
                        "manifest_digest": digest(payloads["manifest"]),
                        "diagnostics": diagnostics,
                    },
                    payloads,
                    candidate,
                )
        except Exception as exc:  # noqa: BLE001 — durable job boundary retains failures
            with self._lock:
                if self._stopping.is_set():
                    return
                current = self.record(self.catalog.read(), build_id, "publication_job")
                if current["id"] != job["id"]:
                    return
                diagnostic = (
                    exc.as_dict()
                    if isinstance(exc, DomainError)
                    else {"code": "build_failed", "message": str(exc)[:2048]}
                )
                self._transition(
                    job,
                    {**job["data"]["attributes"], "state": "failed", "diagnostics": [diagnostic]},
                )

    def sealed_manifest(self, revision):
        if (
            revision["data"]["kind"] != "publication_job"
            or revision["data"]["attributes"]["state"] != "succeeded"
        ):
            raise DomainError("not_ready", "Build is not a sealed release")
        raw = self.catalog.read_payload(revision["id"], "manifest")
        if digest(raw) != revision["data"]["attributes"]["manifest_digest"]:
            raise DomainError("invalid_output", "Sealed manifest digest differs")
        return json.loads(raw)

    def artifact(self, revision, context, path):
        manifest = self.sealed_manifest(revision)
        item = manifest["artifacts"][context].get(path)
        if item is None:
            raise DomainError("not_found", "Artifact absent from sealed manifest")
        raw = self.catalog.read_payload(revision["id"], item["payload"])
        if digest(raw) != item["sha256"] or len(raw) != item["size"]:
            raise DomainError("invalid_output", "Artifact integrity failure")
        return raw, item["media_type"]
