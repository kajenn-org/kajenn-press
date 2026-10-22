"""One catalog snapshot selects public bytes; only publication history admits old assets."""

from urllib.parse import quote

from kajenn.response import Response

from ..domain import DomainError

PUBLIC_HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


class PublicServing:
    def public_response(self, binding, path, method):
        if method not in {"GET", "HEAD"}:
            return Response(
                "Method not allowed",
                status_code=405,
                headers={**PUBLIC_HEADERS, "allow": "GET, HEAD"},
            )
        if self._closed:
            raise DomainError("unavailable", "Publication service is closed")
        snapshot = self.catalog.read()
        settings_id = self.public_origins[binding]
        channel = self.find(snapshot, "publication_channel", settings_id=settings_id)
        if channel is None or not channel["data"]["attributes"].get("active_revision"):
            raise DomainError("not_found", "No active release")
        revision = snapshot.revisions[channel["data"]["attributes"]["active_revision"]]
        if path.startswith("/_releases/"):
            # History is immutable and local. No draft/build listing confers public eligibility.
            revision = None
            for activation in reversed(self.activations(snapshot, settings_id)):
                eligible = snapshot.revisions[activation["data"]["attributes"]["build_revision"]]
                manifest = self.sealed_manifest(eligible)
                if (
                    path in manifest["artifacts"]["public"]
                    and self.release_origin(snapshot, eligible) == binding
                ):
                    revision = eligible
                    break
            if revision is None:
                raise DomainError("not_found", "Asset was never publicly eligible here")
        elif self.release_origin(snapshot, revision) != binding:
            raise DomainError("not_found", "Release targets another origin")
        manifest = self.sealed_manifest(revision)
        if path in manifest["redirects"]:
            return Response(
                status_code=307,
                headers={
                    **PUBLIC_HEADERS,
                    "location": quote(manifest["redirects"][path], safe="/"),
                },
            )
        raw, mime = self.artifact(revision, "public", path)
        headers = dict(PUBLIC_HEADERS)
        if path.startswith("/_releases/"):
            headers["cache-control"] = "public, max-age=31536000, immutable"
        headers["content-security-policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
        )
        return Response(raw, media_type=mime, headers=headers)

    def release_origin(self, snapshot, job):
        candidate = snapshot.revisions[job["data"]["attributes"]["candidate_revision"]]
        return self.candidate_data(candidate)["settings"]["public_origin"]
