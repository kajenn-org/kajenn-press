"""Plan-authored contracts exercised against real storage and installed engines."""

import importlib.util
import os
import subprocess
from copy import deepcopy

import pytest
from rendering.support import (
    BLOCKS,
    TEMPLATE,
    configured_worker,
    make_page,
    render_page,
    render_service,
)
from services.scenarios import create_service, record

from kajenn_public_site.catalog.local import Change
from kajenn_public_site.domain import DomainError
from kajenn_public_site.rendering.contract import RenderInput, canonical
from kajenn_public_site.rendering.service import RenderService


@pytest.mark.parametrize("engine", ["gramlot", "htmlbuilder"])
def test_both_installed_engines_render_source_and_data(tmp_path, engine):
    # wf:contract: Use the qualified installed Gramlot and HtmlBuilder APIs to render real templates with named Data blocks.
    # wf:contract: Each produces a valid complete static document with essential text, links and resource references without browser JavaScript.
    # wf:contract: Browser-only bindings needed for essential output fail with contextual diagnostics rather than silently losing content.
    editorial, renderer = render_service(tmp_path)
    try:
        page = make_page(editorial, engine)
        frozen, result = render_page(renderer, page)
        assert result["status"] == "succeeded", result
        html = result["html"]
        assert html.startswith('<!doctype html><html lang="it">') and html.endswith("</html>")
        assert '<h1 title="Una pagina">Una pagina</h1>' in html
        assert "Caffè &amp; tè" in html and "<strong>importante</strong>" in html
        assert '<a href="/it/dettagli/">Dettagli</a>' in html
        for asset in frozen.unpack()["data"]["resources"].values():
            assert asset["url"] in html
        bad = make_page(
            editorial,
            engine,
            source=TEMPLATE.replace('body.h1("^page.title"', 'body.h1("==browser.title"'),
        )
        _, failed = render_page(renderer, bad)
        assert failed["status"] == "failed"
        assert failed["diagnostics"][0]["code"] == "browser_binding"
        assert failed["diagnostics"][0]["path"]
        assert failed["diagnostics"][0]["resource_id"] == bad["template"]["record_id"]
    finally:
        editorial.catalog.close()


@pytest.mark.parametrize("engine", ["gramlot", "htmlbuilder"])
def test_plain_text_and_prepared_html_have_distinct_insertion_paths(
    tmp_path, engine
):
    # wf:contract: Plain text and attributes remain escaped, including ordinary text ending in the renderer raw-HTML marker.
    # wf:contract: Only HTML produced by the preparation boundary is inserted as markup by each renderer; attributes never gain raw privileges.
    editorial, renderer = render_service(tmp_path)
    try:
        blocks = deepcopy(BLOCKS)
        blocks["intro"]["source"] = '<b title="safe">Una volta &amp; bene</b>'
        page = make_page(editorial, engine, title='<img src=x>"&::HTML', blocks=blocks)
        _, result = render_page(renderer, page)
        assert result["status"] == "succeeded", result
        html = result["html"]
        assert '&lt;img src=x&gt;"&amp;::HTML</h1>' in html
        assert 'title="&lt;img src=x&gt;&quot;&amp;::HTML"' in html
        assert "<img src=x>" not in html
        assert '<b title="safe">Una volta &amp; bene</b></div>' in html
        assert 'title="&lt;b title=&quot;safe&quot;&gt;' in html
        assert "&amp;amp;" not in html.split("</h1>")[0]
    finally:
        editorial.catalog.close()


@pytest.mark.parametrize("engine", ["gramlot", "htmlbuilder"])
def test_markdown_embedded_html_uses_the_editorial_filter(tmp_path, engine):
    # wf:contract: Markdown tables, fenced code and embedded allowed HTML render alongside native HTML blocks through a versioned preparation profile.
    # wf:contract: Allowed formatting survives; script, event handlers and executable URLs do not become active content, with block-specific diagnostics.
    # wf:contract: Trusted template CSS and JavaScript remain separate exact dependencies rather than being accepted inside editorial fragments.
    editorial, renderer = render_service(tmp_path)
    try:
        hostile = (
            '<span class="accent" style="color:red;position:fixed" onclick="attack()">Sì</span>'
            '<script>attack()</script><iframe src="https://example.test"></iframe>'
            '<a href="javascript:attack()">Vai</a><img src="x" onerror="attack()">'
        )
        blocks = {
            "intro": {"format": "html", "source": hostile},
            "body": {
                "format": "markdown",
                "source": "| A | B |\n|---|---|\n| 1 | 2 |\n\n~~prima~~\n\n"
                "```py\nx < 2\n```\n\n" + hostile,
            },
        }
        page = make_page(editorial, engine, blocks=blocks)
        frozen, result = render_page(renderer, page)
        assert result["status"] == "succeeded", result
        html = result["html"]
        assert "<table>" in html and "<td>2</td>" in html and "<s>prima</s>" in html
        assert '<code class="language-py">x &lt; 2' in html
        assert '<span class="accent" style="color:red">Sì</span>' in html
        assert not any(
            term in html for term in ("attack()", "onclick", "onerror", "iframe", "javascript:")
        )
        assert {d["block"] for d in result["diagnostics"]} == {"intro", "body"}
        assert all(d["resource_id"] == page["variant"]["record_id"] for d in result["diagnostics"])
        resources = frozen.unpack()["data"]["resources"]
        assert resources[page["javascript"]["revision_id"]]["url"] in html
        assert "<script src=" in html and '<link rel="stylesheet"' in html
    finally:
        editorial.catalog.close()


def test_required_blocks_are_checked_after_preparation(tmp_path):
    # wf:contract: Incomplete drafts remain saveable, but rendering for publication reports required blocks that are missing or empty after preparation.
    # wf:contract: A script-only required fragment cannot pass because its raw source was nonempty; optional empty blocks remain allowed.
    editorial, renderer = render_service(tmp_path)
    try:
        for blocks in (
            {},
            {"intro": {"format": "html", "source": "<script>only()</script>"}},
            {"intro": {"format": "html", "source": "<p> &nbsp; </p>"}},
        ):
            page = make_page(editorial, blocks=blocks)
            assert page["variant"]["revision_id"]  # incomplete draft really persisted
            _, failed = render_page(renderer, page)
            assert failed["status"] == "failed"
            diagnostic = failed["diagnostics"][0]
            assert diagnostic["code"] == "not_ready"
            assert any(
                d["code"] == "required_block_empty" and d["block"] == "intro"
                for d in diagnostic["diagnostics"]
            )
        page = make_page(editorial, blocks={"intro": BLOCKS["intro"]})
        _, result = render_page(renderer, page)
        assert result["status"] == "succeeded", result
        assert "<div></div>" in result["html"]
    finally:
        editorial.catalog.close()


def test_rendering_preserves_sources_and_exact_dependencies(tmp_path):
    # wf:contract: HTML, Markdown, template and CSS/JS source bytes remain unchanged after rendering and restart.
    # wf:contract: Render inputs resolve exact variant, template and transitive resource revisions; later head edits cannot change an existing input snapshot.
    # wf:contract: Generic copies preserve independent identity and history; inaccessible or cross-site inputs cannot be read through rendering.
    editorial, renderer = render_service(tmp_path)
    try:
        page = make_page(editorial)
        frozen, before = render_page(renderer, page)
        assert before["status"] == "succeeded", before
        original = editorial.catalog.read()
        payloads = {
            (rid, name): editorial.catalog.read_payload(rid, name)
            for rid, rev in original.revisions.items()
            for name in rev["payloads"]
        }
        refs = frozen.unpack()["references"]
        assert set(refs) == {r["revision_id"] for r in page.values()}
        for kind in ("template", "css", "javascript"):
            old = page[kind]
            args = (
                {"engine": old["attributes"]["engine"], "blocks": old["attributes"]["blocks"]}
                if kind == "template"
                else {}
            )
            record(
                editorial,
                "resource_save",
                key="edit-" + kind,
                scope=old["scope"],
                kind=kind,
                name=old["attributes"]["name"],
                source=old["sources"]["source"]["text"] + "\n# edit",
                dependencies=old["attributes"]["dependencies"],
                record_id=old["record_id"],
                expected_generation=old["generation"],
                **args,
            )
        record(
            editorial,
            "draft_save",
            key="edit-block",
            variant_id=page["variant"]["record_id"],
            expected_generation=page["variant"]["generation"],
            template_revision=page["template"]["revision_id"],
            blocks={"intro": {"format": "html", "source": "<p>Nuovo</p>"}},
        )
        after = renderer.render("admin", frozen)
        assert after["html"] == before["html"] and after["digest"] == before["digest"]
        copied = record(
            editorial,
            "resource_copy",
            key="copy",
            source_revision=page["css"]["revision_id"],
            site_id=page["site"]["record_id"],
            name="copy",
        )
        assert copied["record_id"] != page["css"]["record_id"]
        changed = record(
            editorial,
            "resource_save",
            key="copy-edit",
            scope=copied["scope"],
            kind="css",
            name="copy",
            source="p {color: blue}",
            record_id=copied["record_id"],
            expected_generation=copied["generation"],
        )
        assert changed["attributes"]["copied_from"] == page["css"]["revision_id"]
        assert (
            editorial.catalog.read_payload(page["css"]["revision_id"], "source")
            == payloads[(page["css"]["revision_id"], "source")]
        )
        other = make_page(editorial)
        # A low-level corrupt graph must not bypass the renderer's scope boundary.
        badattrs = deepcopy(page["variant"]["attributes"])
        badattrs.update(
            template_revision=other["template"]["revision_id"],
            dependencies=[other["template"]["revision_id"]],
        )
        receipt = editorial.catalog.commit(
            principal="fixture",
            scope="fixture",
            key="cross-site",
            changes=[
                Change(
                    scope=page["variant"]["scope"],
                    data={"schema": 1, "kind": "variant", "attributes": badattrs},
                    payloads={"block.intro": b"text", "block.body": b"text"},
                )
            ],
            authorize=lambda *args: None,
        )
        with pytest.raises(DomainError, match="Cross-site"):
            renderer.freeze("admin", receipt["results"][0]["record_id"])
        editorial.policy.grants["limited"] = {page["variant"]["scope"]: ["read", "build", "use"]}
        with pytest.raises(DomainError, match="library"):
            renderer.render("limited", frozen)
        editorial.catalog.close()
        editorial = create_service(tmp_path)
        editorial.policy.grants["admin"]["*"].append("build")
        renderer = RenderService(editorial.catalog, editorial.policy, configured_worker())
        assert renderer.render("admin", frozen)["html"] == before["html"]
        for (rid, name), raw in payloads.items():
            assert editorial.catalog.read_payload(rid, name) == raw
    finally:
        editorial.catalog.close()


def test_trusted_worker_runs_only_for_explicit_rendering(tmp_path, monkeypatch):
    # wf:contract: Saving source or discovering/importing the management application does not execute template code.
    # wf:contract: Explicit rendering runs in a separate process receiving frozen inputs and a minimal environment without seeded management secrets.
    # wf:contract: The worker does not open a second catalog coordinator or receive unrelated site data; no hostile-code sandbox claim is made.
    editorial, renderer = render_service(tmp_path)
    try:
        sentinel = tmp_path / "executed"
        source = (
            "import os\nfrom pathlib import Path\n"
            f"Path({str(sentinel)!r}).write_text(str(os.getpid()))\n"
            'assert "KAJENN_ADMIN_TOKEN" not in os.environ\n'
            'assert "AWS_SECRET_ACCESS_KEY" not in os.environ\n'
            'assert "PYTHONPATH" not in os.environ\n'
            'assert not Path("current.json").exists()\n' + TEMPLATE
        )
        monkeypatch.setenv("KAJENN_ADMIN_TOKEN", "management-secret")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "storage-secret")
        page = make_page(editorial, source=source)
        other = make_page(editorial)
        assert not sentinel.exists()
        editorial.execute("admin", "capabilities")
        import kajenn_public_site.application  # noqa: F401

        assert not sentinel.exists()
        frozen = renderer.freeze("admin", page["variant"]["record_id"])
        assert not sentinel.exists()  # profile/discovery never loads template
        assert other["site"]["record_id"] not in frozen.encoded.decode()
        assert str(tmp_path).encode() not in canonical(frozen.unpack()["data"])
        result = renderer.render("admin", frozen)
        assert result["status"] == "succeeded", result
        assert int(sentinel.read_text()) != os.getpid()
        assert editorial.catalog.read().generation > 0
    finally:
        editorial.catalog.close()


def test_worker_failure_limits_and_invalid_outputs_do_not_succeed(tmp_path):
    # wf:contract: Worker timeout, oversized output, process failure and malformed output each produce a structured failed result.
    # wf:contract: No failed attempt becomes a successful render or changes editorial heads; coordinator ownership and subsequent valid work remain usable.
    editorial, renderer = render_service(tmp_path)
    try:
        cases = [
            ("import time; time.sleep(100)", {"timeout": 2}, "worker_timeout"),
            ('print("x" * 100000)', {"output_limit": 16384}, "output_limit"),
            ("import os; os._exit(7)", {}, "worker_exit"),
            ('import os; os.write(1, b"not-json"); os._exit(0)', {}, "invalid_output"),
            ('import os; os.write(1, b\'{"ok":true}\'); os._exit(0)', {}, "invalid_output"),
            ('def build(source, data): return "not Source"', {}, "invalid_template"),
        ]
        for source, limits, code in cases:
            page = make_page(editorial, source=source)
            frozen = renderer.freeze("admin", page["variant"]["record_id"])
            snapshot = editorial.catalog.read()
            result = configured_worker(**limits).render(frozen)
            assert result["status"] == "failed", result
            assert result["diagnostics"][0]["code"] == code, result
            assert "html" not in result and "digest" not in result
            assert editorial.catalog.read() == snapshot
        good = make_page(editorial)
        _, result = render_page(renderer, good)
        assert result["status"] == "succeeded", result
    finally:
        editorial.catalog.close()


def test_renderer_profile_and_output_are_reproducible(tmp_path):
    # wf:contract: Build inputs record exact renderer, preparation profile and dependency versions.
    # wf:contract: Two renders of the same deterministic template and frozen inputs produce identical artifact bytes; operational attempt IDs are not artifact inputs.
    # wf:contract: The optional rendering installation passes dependency checks while the editorial-only profile remains usable without Gramlot or SQL.
    editorial, renderer = render_service(tmp_path)
    try:
        page = make_page(editorial)
        frozen, first = render_page(renderer, page)
        second = renderer.render("admin", frozen)
        assert first["status"] == second["status"] == "succeeded"
        assert first["digest"] == second["digest"] and first["html"] == second["html"]
        assert first["attempt_id"] != second["attempt_id"]
        assert first["attempt_id"].encode() not in frozen.encoded
        profile = frozen.unpack()["profile"]
        assert profile["preparation"] == "editorial-html-v1"
        assert profile["versions"]["gramlot"] == "0.3.8"
        assert profile["versions"]["genro-builders"] == "0.30.0"
        assert profile["versions"]["nh3"] == "0.3.7"
        altered = frozen.unpack()
        altered["profile"]["preparation"] = "different"
        assert (
            renderer.render("admin", RenderInput(canonical(altered)))["diagnostics"][0]["code"]
            == "profile_mismatch"
        )
        check = subprocess.run(
            [renderer.worker.python, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert check.returncode == 0, check.stdout + check.stderr
        for module in ("gramlot", "asqueel", "sqlalchemy", "psycopg"):
            assert importlib.util.find_spec(module) is None
    finally:
        editorial.catalog.close()
