"""Durable exact-release grants; only keyed digests leave the private deployment."""

import hashlib
import hmac
import time
from secrets import token_hex

from ..domain import DomainError


class PreviewGrants:
    def grant_token(self, grant):
        attrs = grant["data"]["attributes"]
        message = (
            grant["record_id"] + ":" + attrs["nonce"] + ":" + attrs["build_revision"]
        ).encode()
        return hmac.new(self.preview_secret, message, hashlib.sha256).hexdigest()

    def grant_link(self, grant):
        return self.preview_origin + "/open/" + grant["record_id"] + "#" + self.grant_token(grant)

    def _preview_grant_create(
        self, snapshot, identity, build_id, lifetime_seconds, key
    ):
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= self.preview_max_age:
            raise DomainError(
                "invalid_input", "Preview lifetime exceeds the configured positive limit"
            )
        job = self.record(snapshot, build_id, "publication_job")
        self.sealed_manifest(job)
        candidate = snapshot.revisions[job["data"]["attributes"]["candidate_revision"]]
        self.authorize_candidate(identity, candidate)
        return self.change(
            "publication_grant",
            {
                "site_id": job["data"]["attributes"]["site_id"],
                "build_id": build_id,
                "build_revision": job["id"],
                "candidate_revision": candidate["id"],
                "expires_at": time.time() + lifetime_seconds,
                "revoked": False,
                "nonce": token_hex(24),
            },
        )

    def _preview_grant_revoke(
        self, snapshot, identity, grant_id, expected_generation, key
    ):
        grant = self.record(snapshot, grant_id, "publication_grant")
        return self.change(
            "publication_grant",
            {**grant["data"]["attributes"], "revoked": True},
            record_id=grant_id,
            expected_generation=expected_generation,
        )

    def preview_access(self, grant_id, token, build_id=None):
        with self._lock:
            if self._closed:
                raise DomainError("unavailable", "Preview coordinator is closed")
            snapshot = self.catalog.read()
            grant = self.record(snapshot, grant_id, "publication_grant")
            attrs = grant["data"]["attributes"]
            if (
                attrs["revoked"]
                or attrs["expires_at"] <= time.time()
                or build_id is not None
                and attrs["build_id"] != build_id
                or not isinstance(token, str)
                or len(token) != 64
                or not hmac.compare_digest(token, self.grant_token(grant))
            ):
                raise DomainError("forbidden", "Preview access denied")
            job = snapshot.revisions[attrs["build_revision"]]
            self.sealed_manifest(job)
            return grant, job
