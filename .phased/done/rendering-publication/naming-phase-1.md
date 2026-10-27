# Revisione nomi — Rendering/publication, fase 1

Tutti i 49 nomi accettati dall’utente, inclusa la composizione `RenderService.freeze`. Nessuna rinomina; marcatori rimossi.

Fase implementata e verificata: 76 test, lint, compileall, due engine installati.
`framework` indica un nome vincolato da Python, pytest, dal contratto del piano o dal renderer.
La riga con ⚠ rende esplicita la sola composizione sottile mantenuta come API del coordinatore.

| # | Nome proposto | Tipo | Necessità | File | Fase |
|---|---|---|---|---|---|
| 1 | `main` | free |  | [examples/qualify_renderers.py:19](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/examples/qualify_renderers.py:19) | 1 |
| 2 | `demonstrate` | free |  | [examples/static_rendering.py:16](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/examples/static_rendering.py:16) | 1 |
| 3 | `demonstrate.save` | free |  | [examples/static_rendering.py:29](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/examples/static_rendering.py:29) | 1 |
| 4 | `build` | framework — nome fisso |  | [examples/static_template.py:4](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/examples/static_template.py:4) | 1 |
| 5 | `RenderInput.unpack` | free |  | [src/kajenn_public_site/rendering/contract.py:26](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/contract.py:26) | 1 |
| 6 | `RenderInput.digest` | free |  | [src/kajenn_public_site/rendering/contract.py:30](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/contract.py:30) | 1 |
| 7 | `RenderProblem.__init__` | framework — nome fisso |  | [src/kajenn_public_site/rendering/contract.py:35](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/contract.py:35) | 1 |
| 8 | `installed_profile` | free |  | [src/kajenn_public_site/rendering/engines.py:114](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:114) | 1 |
| 9 | `make_builder` | free |  | [src/kajenn_public_site/rendering/engines.py:149](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:149) | 1 |
| 10 | `make_builder.FragmentRenderer.rendered_item` | framework — nome fisso |  | [src/kajenn_public_site/rendering/engines.py:156](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:156) | 1 |
| 11 | `make_builder.StaticHtmlBuilder.renderer_html` | framework — nome fisso |  | [src/kajenn_public_site/rendering/engines.py:172](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:172) | 1 |
| 12 | `make_builder.StaticGramlotBuilder.renderer_html` | framework — nome fisso |  | [src/kajenn_public_site/rendering/engines.py:177](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:177) | 1 |
| 13 | `populate_data` | free |  | [src/kajenn_public_site/rendering/engines.py:185](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:185) | 1 |
| 14 | `validate_static_source` | free |  | [src/kajenn_public_site/rendering/engines.py:194](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:194) | 1 |
| 15 | `render_template` | free |  | [src/kajenn_public_site/rendering/engines.py:238](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/engines.py:238) | 1 |
| 16 | `RenderInputs.__init__` | framework — nome fisso |  | [src/kajenn_public_site/rendering/inputs.py:10](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/inputs.py:10) | 1 |
| 17 | `RenderInputs.freeze` | free |  | [src/kajenn_public_site/rendering/inputs.py:14](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/inputs.py:14) | 1 |
| 18 | `RenderInputs.freeze.include` | free |  | [src/kajenn_public_site/rendering/inputs.py:42](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/inputs.py:42) | 1 |
| 19 | `RenderInputs.authorize` | free |  | [src/kajenn_public_site/rendering/inputs.py:135](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/inputs.py:135) | 1 |
| 20 | `MeaningfulHTML.__init__` | framework — nome fisso |  | [src/kajenn_public_site/rendering/preparation.py:75](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/preparation.py:75) | 1 |
| 21 | `MeaningfulHTML.handle_data` | framework — nome fisso |  | [src/kajenn_public_site/rendering/preparation.py:79](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/preparation.py:79) | 1 |
| 22 | `MeaningfulHTML.handle_starttag` | framework — nome fisso |  | [src/kajenn_public_site/rendering/preparation.py:83](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/preparation.py:83) | 1 |
| 23 | `filter_attribute` | free |  | [src/kajenn_public_site/rendering/preparation.py:88](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/preparation.py:88) | 1 |
| 24 | `prepare_blocks` | free |  | [src/kajenn_public_site/rendering/preparation.py:97](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/preparation.py:97) | 1 |
| 25 | `RenderWorker.__init__` | framework — nome fisso |  | [src/kajenn_public_site/rendering/process.py:18](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/process.py:18) | 1 |
| 26 | `RenderWorker._call` | free |  | [src/kajenn_public_site/rendering/process.py:32](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/process.py:32) | 1 |
| 27 | `RenderWorker._diagnostics_valid` | free |  | [src/kajenn_public_site/rendering/process.py:111](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/process.py:111) | 1 |
| 28 | `RenderWorker.profile` | free |  | [src/kajenn_public_site/rendering/process.py:119](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/process.py:119) | 1 |
| 29 | `RenderWorker.render` | free |  | [src/kajenn_public_site/rendering/process.py:130](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/process.py:130) | 1 |
| 30 | `RenderService.__init__` | framework — nome fisso |  | [src/kajenn_public_site/rendering/service.py:7](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/service.py:7) | 1 |
| 31 | `RenderService.freeze` | free | ⚠ Composizione sottile di profilo e snapshot; potrebbe essere inlined dal chiamante. | [src/kajenn_public_site/rendering/service.py:11](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/service.py:11) | 1 |
| 32 | `RenderService.render` | free |  | [src/kajenn_public_site/rendering/service.py:14](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/service.py:14) | 1 |
| 33 | `run_request` | free |  | [src/kajenn_public_site/rendering/worker.py:13](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/worker.py:13) | 1 |
| 34 | `main` | free |  | [src/kajenn_public_site/rendering/worker.py:46](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/src/kajenn_public_site/rendering/worker.py:46) | 1 |
| 35 | `test_both_installed_engines_render_source_and_data` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:26](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:26) | 1 |
| 36 | `test_plain_text_and_prepared_html_have_distinct_insertion_paths` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:57](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:57) | 1 |
| 37 | `test_markdown_embedded_html_uses_the_editorial_filter` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:81](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:81) | 1 |
| 38 | `test_required_blocks_are_checked_after_preparation` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:119](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:119) | 1 |
| 39 | `test_rendering_preserves_sources_and_exact_dependencies` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:147](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:147) | 1 |
| 40 | `test_trusted_worker_runs_only_for_explicit_rendering` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:256](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:256) | 1 |
| 41 | `test_worker_failure_limits_and_invalid_outputs_do_not_succeed` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:292](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:292) | 1 |
| 42 | `test_renderer_profile_and_output_are_reproducible` | framework — nome fisso |  | [tests/contracts/rendering_publication/phase_1/test_contracts.py:321](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/contracts/rendering_publication/phase_1/test_contracts.py:321) | 1 |
| 43 | `configured_worker` | free |  | [tests/rendering/support.py:41](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/support.py:41) | 1 |
| 44 | `render_service` | free |  | [tests/rendering/support.py:48](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/support.py:48) | 1 |
| 45 | `make_page` | free |  | [tests/rendering/support.py:55](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/support.py:55) | 1 |
| 46 | `render_page` | free |  | [tests/rendering/support.py:130](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/support.py:130) | 1 |
| 47 | `test_exact_transitive_graph_and_current_policy` | framework — nome fisso |  | [tests/rendering/test_inputs.py:11](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/test_inputs.py:11) | 1 |
| 48 | `test_timeout_is_explicit_positive_finite` | framework — nome fisso |  | [tests/rendering/test_limits.py:9](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/test_limits.py:9) | 1 |
| 49 | `test_output_limit_is_positive_bytes` | framework — nome fisso |  | [tests/rendering/test_limits.py:15](/Users/gporcari/Sviluppo/kajenn/kajenn-public-site/tests/rendering/test_limits.py:15) | 1 |
