import json
from copy import deepcopy

import pytest
from publication.support import built, candidate, services, site_fixture

from kajenn_public_site.domain import DomainError
from kajenn_public_site.publication.artifacts import verify_bundle


def test_complete_build_and_integrity(tmp_path):
    editorial, pub = services(tmp_path)
    try:
        fixture = site_fixture(editorial, pub)
        selection = candidate(pub, fixture)
        job = built(pub, selection)
        revision = pub.catalog.read().revisions[job["revision_id"]]
        manifest = pub.sealed_manifest(revision)
        assert manifest["redirects"] == {"/": "/it/"}
        html, mime = pub.artifact(revision, "public", "/it/")
        assert mime.startswith("text/html")
        assert b'<link rel="canonical" href="https://one.test/it/">' in html
        assert b'hreflang="en" href="https://one.test/en/about/"' in html
        preview, _ = pub.artifact(revision, "preview", "/it/")
        assert ('href="/preview/' + job["record_id"] + '/en/about/"').encode() in preview
        payloads = {
            v["payload"]: pub.catalog.read_payload(revision["id"], v["payload"])
            for c in manifest["artifacts"].values()
            for v in c.values()
        }
        verify_bundle(manifest, payloads)
        broken = deepcopy(payloads)
        broken[next(iter(broken))] += b"corrupt"
        with pytest.raises(DomainError, match="verification"):
            verify_bundle(manifest, broken)
        broken_map = deepcopy(manifest)
        del broken_map["artifacts"]["public"]["/it/"]
        with pytest.raises(DomainError, match="missing"):
            verify_bundle(broken_map, payloads)
        assert json.loads(pub.catalog.read_payload(revision["id"], "manifest")) == manifest
        with pytest.raises(DomainError) as stale:
            pub._transition(
                revision,
                revision["data"]["attributes"],
                {"manifest": b"{}"},
                pub.catalog.read().revisions[selection["revision_id"]],
            )
        assert stale.value.code == "interrupted"
    finally:
        pub.close()
        editorial.catalog.close()
