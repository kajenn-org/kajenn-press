"""Cross-layer contract scenarios with real catalog, workers and HTTP transports."""

import asyncio
import base64
import time
from copy import deepcopy

import httpx
import pytest
from publication.support import CONFIG, TEMPLATE, built, candidate, services, site_fixture
from publication.test_gateway import exchange
from services.scenarios import record

from kajenn_press.catalog.local import Change
from kajenn_press.domain import DomainError
from kajenn_press.publication.artifacts import build_artifacts, verify_bundle
from kajenn_press.publication.gateway import PreviewGateway
from kajenn_press.publication.routes import localized_path, origin, request_path


def allow_fixture(*args):
    """Only test fixtures may write future-channel or intentionally malformed records."""


def route_contract(root):
    assert localized_path("it", "caffe\u0300") == "/it/caffè/"
    assert origin("https://ADMIN.test:443/") == "https://admin.test"
    assert origin("http://gramlot.localhost:19765") == "http://gramlot.localhost:19765"
    for value in ("http://localhost.evil.test", "http://notlocalhost", "http://192.0.2.1"):
        with pytest.raises(DomainError):
            origin(value)
    for path in ("../other", "a//b", "%2e%2e", "preview", "_releases", "a\\b"):
        with pytest.raises(DomainError):
            localized_path("it", path)
    for raw in (b"/it/%2e%2e/", b"/it/%2F", b"/it/%61/", b"/it//"):
        with pytest.raises(DomainError):
            request_path(raw)
    assert request_path(b"/it/caff%C3%A8/") == "/it/caffè/"
    editorial, pub = services(root)
    try:
        source = TEMPLATE.replace(
            '    head.title("^page.title")',
            '    head.title("^page.title")\n'
            '    head.link(rel="CANONICAL", href="https://obsolete.test/page/")\n'
            '    head.link(rel="  aLtErNaTe canonical  ", href="https://obsolete.test/en/")\n'
            '    head.meta(name="DESCRIPTION", content="OBSOLETE DESCRIPTION")',
        ).replace(
            '            head.link(rel="stylesheet", href=asset.get_item("url"))',
            '            head.link(rel="stylesheet", href=asset.get_item("url"))\n'
            '            head.link(rel="Alternate StyleSheet", title="Alternative", '
            'href=asset.get_item("url"))',
        )
        fixture = site_fixture(editorial, pub, source=source)
        other = record(
            editorial,
            "content_create",
            key="collision-content",
            site_id=fixture["site"]["record_id"],
            title="Other",
        )
        duplicate = record(
            editorial,
            "variant_create",
            key="collision-variant",
            content_id=other["record_id"],
            language="it",
            template_revision=fixture["template"]["revision_id"],
            blocks={"body": {"format": "markdown", "source": "body"}},
        )
        pub.execute(
            "admin",
            "publication_route_save",
            variant_id=duplicate["record_id"],
            path="",
            title="Other",
            description="",
            key="collision-route",
        )
        with pytest.raises(DomainError) as collision:
            pub.execute(
                "admin",
                "candidate_create",
                settings_id=fixture["settings"]["record_id"],
                variant_revisions=[
                    fixture["variants"]["it"]["revision_id"],
                    duplicate["revision_id"],
                ],
                key="collision",
            )
        assert collision.value.code == "route_collision"
        with pytest.raises(DomainError) as landing:
            pub.execute(
                "admin",
                "candidate_create",
                settings_id=fixture["settings"]["record_id"],
                variant_revisions=[fixture["variants"]["en"]["revision_id"]],
                key="landing",
            )
        assert landing.value.code == "missing_landing"
        selection = candidate(pub, fixture)
        job = built(pub, selection)
        revision = pub.catalog.read().revisions[job["revision_id"]]
        manifest = pub.sealed_manifest(revision)
        assert manifest["redirects"]["/"] in manifest["routes"]
        sitemap, _ = pub.artifact(revision, "public", "/sitemap.xml")
        assert b"https://one.test/it/" in sitemap and b"https://one.test/en/about/" in sitemap
        assert b"lastmod" not in sitemap and b"x-default" not in sitemap
        for path in manifest["routes"]:
            for context in ("public", "preview"):
                html, _ = pub.artifact(revision, context, path)
                assert html.lower().count(b'rel="canonical"') == 1
                assert html.lower().count(b'rel="alternate"') == 2
                assert html.lower().count(b'name="description"') == 1
                assert b"OBSOLETE" not in html and b"obsolete.test" not in html
                assert b'rel="stylesheet"' in html
                assert b'rel="Alternate StyleSheet"' in html
                assert ("https://one.test" + path).encode() in html
    finally:
        pub.close()
        editorial.catalog.close()


def frozen_contract(root):
    editorial, pub = services(root)
    try:
        fixture = site_fixture(editorial, pub)
        selection = candidate(pub, fixture)
        before = pub.catalog.read_payload(selection["revision_id"], "inputs")
        old_sources = {
            (rid, name): pub.catalog.read_payload(rid, name)
            for rid, rev in pub.catalog.read().revisions.items()
            for name in rev["payloads"]
        }
        job = built(pub, selection)
        # Phase 3 owns activation. Seed its planned pointer shape through the real
        # coordinator solely to verify carry-forward compatibility in this phase.
        channel = pub.catalog.commit(
            principal="fixture",
            scope="fixture",
            key="channel",
            changes=[
                pub.change(
                    "publication_channel",
                    {
                        "site_id": fixture["site"]["record_id"],
                        "settings_id": fixture["settings"]["record_id"],
                        "active_build": job["record_id"],
                        "active_revision": job["revision_id"],
                    },
                )
            ],
            authorize=allow_fixture,
        )
        assert channel["results"][0]["generation"] == 1
        en = fixture["variants"]["en"]
        record(
            editorial,
            "draft_save",
            key="new-en",
            variant_id=en["record_id"],
            expected_generation=en["generation"],
            template_revision=fixture["template"]["revision_id"],
            blocks={"body": {"format": "markdown", "source": "UNFINISHED DRAFT"}},
        )
        route = fixture["routes"]["en"]
        pub.execute(
            "admin",
            "publication_route_save",
            key="new-route",
            variant_id=en["record_id"],
            record_id=route["record_id"],
            expected_generation=route["generation"],
            path="unfinished",
            title="Unfinished",
            description="Unfinished",
        )
        settings = fixture["settings"]
        pub.execute(
            "admin",
            "publication_settings_save",
            key="new-settings",
            record_id=settings["record_id"],
            expected_generation=settings["generation"],
            site_id=fixture["site"]["record_id"],
            channel="main",
            public_origin="https://changed.test",
            primary_language="it",
            landing_variant=fixture["variants"]["it"]["record_id"],
        )
        next_selection = pub.execute(
            "admin",
            "candidate_create",
            key="carried",
            settings_id=settings["record_id"],
            variant_revisions=[fixture["variants"]["it"]["revision_id"]],
            base_build_id=job["record_id"],
        )
        frozen = pub.candidate_data(pub.catalog.read().revisions[next_selection["revision_id"]])
        carried = frozen["entries"][en["record_id"]]
        assert carried["variant_revision"] == en["revision_id"]
        assert (
            carried["route"]["path"] == "/en/about/"
            and carried["route_revision"] == route["revision_id"]
        )
        assert "UNFINISHED" not in str(carried)
        assert (
            frozen["base_channel_generation"] == 1
            and frozen["base_active_build"] == job["record_id"]
        )
        assert frozen["settings"]["public_origin"] == "https://changed.test"
        assert pub.catalog.read_payload(selection["revision_id"], "inputs") == before
        for (rid, name), source in old_sources.items():
            assert pub.catalog.read_payload(rid, name) == source
    finally:
        pub.close()
        editorial.catalog.close()


def invalid_outputs_contract(root):
    editorial, pub = services(root)
    try:
        fixture = site_fixture(editorial, pub)
        selection = candidate(pub, fixture)
        frozen = pub.candidate_data(pub.catalog.read().revisions[selection["revision_id"]])
        # Exact stable content/media IDs resolve through the frozen language map.
        media_id = fixture["media"]["revision_id"]
        from kajenn_press.publication.artifacts import LinkResolver

        resources = next(iter(frozen["entries"].values()))["input"]["data"]["resources"]
        resolver = LinkResolver(frozen, resources, "it", "/it/", "")
        assert resolver.resolve("/_content/" + fixture["content"]["record_id"] + "/") == "/it/"
        assert (
            resolver.resolve("/_media/" + media_id + "/", asset=True) == resources[media_id]["url"]
        )
        for target in ("/_content/missing/", "/_media/missing/", "/it/../elsewhere/"):
            with pytest.raises(DomainError):
                resolver.resolve(target)
        bad_media = deepcopy(frozen)
        for entry in bad_media["entries"].values():
            entry["input"]["references"][media_id]["sources"]["binary"] = base64.b64encode(
                b"<svg onload=alert(1)>"
            ).decode()
        with pytest.raises(DomainError) as media:
            build_artifacts(bad_media, "fixture", pub.worker, lambda: False)
        assert media.value.code == "invalid_input"
        from kajenn_press.publication.artifacts import verify_png

        with pytest.raises(DomainError) as png:
            verify_png(b"<svg onload=alert(1)>")
        assert png.value.code == "unsupported_media"
        cyclic = deepcopy(frozen)
        for entry in cyclic["entries"].values():
            entry["input"]["references"][media_id]["attributes"]["dependencies"] = [media_id]
        with pytest.raises(DomainError) as cycle:
            build_artifacts(cyclic, "fixture", pub.worker, lambda: False)
        assert cycle.value.code == "dependency_cycle"
        payloads, _ = build_artifacts(frozen, "fixture", pub.worker, lambda: False)
        import json

        manifest = json.loads(payloads["manifest"])
        bad_path = deepcopy(manifest)
        bad_path["artifacts"]["public"]["/../private"] = next(
            iter(manifest["artifacts"]["public"].values())
        )
        with pytest.raises(DomainError) as path:
            verify_bundle(bad_path, payloads)
        assert path.value.code == "invalid_path"
        # Missing and cross-site exact dependencies fail at candidate creation.
        other = site_fixture(editorial, pub, prefix="other")
        variant = fixture["variants"]["it"]
        for label, dependency in (
            ("missing", "absent-revision"),
            ("cross", other["template"]["revision_id"]),
        ):
            attrs = deepcopy(variant["attributes"])
            attrs["dependencies"] = [dependency]
            attrs["template_revision"] = dependency
            receipt = pub.catalog.commit(
                principal="fixture",
                scope="fixture",
                key=label,
                changes=[
                    Change(
                        variant["scope"],
                        variant["record_id"],
                        variant["generation"],
                        {"schema": 1, "kind": "variant", "attributes": attrs},
                        {"block.body": b"body"},
                    )
                ],
                authorize=allow_fixture,
            )
            variant = {**variant, **receipt["results"][0]}
            with pytest.raises(DomainError) as rejected:
                pub.execute(
                    "admin",
                    "candidate_create",
                    settings_id=fixture["settings"]["record_id"],
                    variant_revisions=[variant["revision_id"]],
                    key=label,
                )
            assert rejected.value.code in {"missing_dependency", "forbidden"}
        bad = site_fixture(
            editorial,
            pub,
            prefix="broken",
            source=TEMPLATE.replace('href="/en/about/"', 'href="/_content/unknown/"'),
        )
        bad_selection = candidate(pub, bad, key="broken-selection")
        start = pub.execute(
            "admin", "build_start", candidate_id=bad_selection["record_id"], key="broken-build"
        )
        pub._futures[start["record_id"]].result(30)
        failed = pub.execute("admin", "build_status", build_id=start["record_id"])
        assert (
            failed["attributes"]["state"] == "failed"
            and failed["attributes"]["diagnostics"][0]["code"] == "unresolved_reference"
        )
        assert pub.catalog.read().revisions[failed["revision_id"]]["payloads"] == {}
        with pytest.raises(DomainError):
            pub.execute(
                "admin",
                "preview_grant_create",
                build_id=start["record_id"],
                lifetime_seconds=30,
                key="unready",
            )
    finally:
        pub.close()
        editorial.catalog.close()


class FixtureHost:
    def __init__(self, publication):
        self.applications = {"press": type("App", (), {"publication": publication})()}

    async def __call__(self, scope, receive, send):
        raise AssertionError("Preview must never dispatch to management")


async def grant_contract(root):
    editorial, pub = await asyncio.to_thread(services, root)
    browser_cookies = None
    try:
        fixture = site_fixture(editorial, pub)
        other = site_fixture(editorial, pub, prefix="other")
        selected = candidate(pub, fixture)
        job = built(pub, selected)
        other_job = built(pub, candidate(pub, other, key="other-candidate"), key="other-build")
        same_site_job = built(pub, selected, key="same-site-build")
        grant = pub.execute(
            "admin",
            "preview_grant_create",
            build_id=job["record_id"],
            lifetime_seconds=2,
            key="short-grant",
        )
        secret = grant["url"].split("#")[1]
        gateway = PreviewGateway(
            FixtureHost(pub), CONFIG["management_origin"], CONFIG["preview_origin"]
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=gateway), base_url=CONFIG["preview_origin"]
        ) as browser:
            target = await exchange(browser, grant)
            assert (await browser.get(target + "it/")).status_code == 200
            manifest = pub.sealed_manifest(pub.catalog.read().revisions[job["revision_id"]])
            asset = next(p for p in manifest["artifacts"]["preview"] if p.endswith(".bin"))
            for forbidden in (other_job, same_site_job):
                # Even copying the credential to a different path/name cannot widen it.
                response = await browser.get(
                    "/preview/" + forbidden["record_id"] + "/it/",
                    headers={
                        "cookie": "preview_"
                        + forbidden["record_id"]
                        + "="
                        + grant["record_id"]
                        + "."
                        + secret
                    },
                )
                assert response.status_code == 404
            for rev in pub.catalog.read().revisions.values():
                assert secret not in str(rev)
                for name in rev["payloads"]:
                    assert secret.encode() not in pub.catalog.read_payload(rev["id"], name)
            browser_cookies = browser.cookies
        pub.close()
        editorial.catalog.close()
        editorial, pub = await asyncio.to_thread(services, root)
        delay = grant["attributes"]["expires_at"] - time.time() + 0.05
        if delay > 0:
            await asyncio.sleep(delay)
        gateway = PreviewGateway(
            FixtureHost(pub), CONFIG["management_origin"], CONFIG["preview_origin"]
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=gateway),
            base_url=CONFIG["preview_origin"],
            cookies=browser_cookies,
        ) as browser:
            for path in ("/it/", asset):
                for method in ("GET", "HEAD"):
                    assert (
                        await browser.request(method, target.rstrip("/") + path)
                    ).status_code == 404
            assert (await browser.get(asset)).status_code == 404
    finally:
        pub.close()
        editorial.catalog.close()
