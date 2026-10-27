# Phase 2 naming review

Status: all proposed names accepted by the user. All 100 markers removed without renames or Python AST changes. All 54 tests, lint, compile and clean-install demonstration pass.

Public types: `PublicSiteApplication`, `EditorialService`, `AccessPolicy`, `DomainError`. Each routed adapter method is required to expose a discoverable typed REST/MCP signature; business rules remain in the common service. Other helpers perform tested validation, authorization, revision inspection or lifecycle work; no unused callable was found.

| # | Proposed name | Kind | Necessity | File | Phase |
|---|---|---|---|---|---|
| 1 | `run` | free | | [examples/editorial.py:13](../../../examples/editorial.py#L13) | 2 |
| 2 | `run.call` | free | | [examples/editorial.py:30](../../../examples/editorial.py#L30) | 2 |
| 3 | `main` | free | | [examples/editorial.py:153](../../../examples/editorial.py#L153) | 2 |
| 4 | `main` | free | | [examples/serve.py:9](../../../examples/serve.py#L9) | 2 |
| 5 | `PublicSiteApplication.__init__` | framework: Python/Kajenn lifecycle | | [src/kajenn_public_site/application.py:25](../../../src/kajenn_public_site/application.py#L25) | 2 |
| 6 | `PublicSiteApplication.on_startup` | framework: Python/Kajenn lifecycle | | [src/kajenn_public_site/application.py:31](../../../src/kajenn_public_site/application.py#L31) | 2 |
| 7 | `PublicSiteApplication.on_shutdown` | framework: Python/Kajenn lifecycle | | [src/kajenn_public_site/application.py:39](../../../src/kajenn_public_site/application.py#L39) | 2 |
| 8 | `PublicSiteApplication._execute` | free | | [src/kajenn_public_site/application.py:44](../../../src/kajenn_public_site/application.py#L44) | 2 |
| 9 | `PublicSiteApplication.capabilities` | free | | [src/kajenn_public_site/application.py:79](../../../src/kajenn_public_site/application.py#L79) | 2 |
| 10 | `PublicSiteApplication.site_create` | free | | [src/kajenn_public_site/application.py:84](../../../src/kajenn_public_site/application.py#L84) | 2 |
| 11 | `PublicSiteApplication.sites_list` | free | | [src/kajenn_public_site/application.py:100](../../../src/kajenn_public_site/application.py#L100) | 2 |
| 12 | `PublicSiteApplication.site_configure` | free | | [src/kajenn_public_site/application.py:105](../../../src/kajenn_public_site/application.py#L105) | 2 |
| 13 | `PublicSiteApplication.records_list` | free | | [src/kajenn_public_site/application.py:130](../../../src/kajenn_public_site/application.py#L130) | 2 |
| 14 | `PublicSiteApplication.content_create` | free | | [src/kajenn_public_site/application.py:137](../../../src/kajenn_public_site/application.py#L137) | 2 |
| 15 | `PublicSiteApplication.variant_create` | free | | [src/kajenn_public_site/application.py:146](../../../src/kajenn_public_site/application.py#L146) | 2 |
| 16 | `PublicSiteApplication.draft_save` | free | | [src/kajenn_public_site/application.py:171](../../../src/kajenn_public_site/application.py#L171) | 2 |
| 17 | `PublicSiteApplication.resource_save` | free | | [src/kajenn_public_site/application.py:194](../../../src/kajenn_public_site/application.py#L194) | 2 |
| 18 | `PublicSiteApplication.media_save` | free | | [src/kajenn_public_site/application.py:227](../../../src/kajenn_public_site/application.py#L227) | 2 |
| 19 | `PublicSiteApplication.resource_copy` | free | | [src/kajenn_public_site/application.py:254](../../../src/kajenn_public_site/application.py#L254) | 2 |
| 20 | `PublicSiteApplication.record_read` | free | | [src/kajenn_public_site/application.py:265](../../../src/kajenn_public_site/application.py#L265) | 2 |
| 21 | `PublicSiteApplication.revision_history` | free | | [src/kajenn_public_site/application.py:274](../../../src/kajenn_public_site/application.py#L274) | 2 |
| 22 | `PublicSiteApplication.revision_compare` | free | | [src/kajenn_public_site/application.py:279](../../../src/kajenn_public_site/application.py#L279) | 2 |
| 23 | `PublicSiteApplication.revision_checkpoint` | free | | [src/kajenn_public_site/application.py:294](../../../src/kajenn_public_site/application.py#L294) | 2 |
| 24 | `PublicSiteApplication.revision_restore` | free | | [src/kajenn_public_site/application.py:310](../../../src/kajenn_public_site/application.py#L310) | 2 |
| 25 | `PublicSiteApplication.dependencies` | free | | [src/kajenn_public_site/application.py:331](../../../src/kajenn_public_site/application.py#L331) | 2 |
| 26 | `PublicSiteApplication.readiness` | free | | [src/kajenn_public_site/application.py:340](../../../src/kajenn_public_site/application.py#L340) | 2 |
| 27 | `create_server` | free | | [src/kajenn_public_site/application.py:349](../../../src/kajenn_public_site/application.py#L349) | 2 |
| 28 | `DomainError.__init__` | framework: Python/Kajenn lifecycle | | [src/kajenn_public_site/domain.py:40](../../../src/kajenn_public_site/domain.py#L40) | 2 |
| 29 | `DomainError.as_dict` | free | | [src/kajenn_public_site/domain.py:49](../../../src/kajenn_public_site/domain.py#L49) | 2 |
| 30 | `AccessPolicy.__init__` | framework: Python/Kajenn lifecycle | | [src/kajenn_public_site/domain.py:67](../../../src/kajenn_public_site/domain.py#L67) | 2 |
| 31 | `AccessPolicy.allows` | free | | [src/kajenn_public_site/domain.py:70](../../../src/kajenn_public_site/domain.py#L70) | 2 |
| 32 | `AccessPolicy.require` | free | | [src/kajenn_public_site/domain.py:74](../../../src/kajenn_public_site/domain.py#L74) | 2 |
| 33 | `EditorialService.__init__` | framework: Python/Kajenn lifecycle | | [src/kajenn_public_site/services/editorial.py:23](../../../src/kajenn_public_site/services/editorial.py#L23) | 2 |
| 34 | `EditorialService.execute` | free | | [src/kajenn_public_site/services/editorial.py:28](../../../src/kajenn_public_site/services/editorial.py#L28) | 2 |
| 35 | `EditorialService.execute.authorize` | free | | [src/kajenn_public_site/services/editorial.py:63](../../../src/kajenn_public_site/services/editorial.py#L63) | 2 |
| 36 | `EditorialService._result` | free | | [src/kajenn_public_site/services/editorial.py:91](../../../src/kajenn_public_site/services/editorial.py#L91) | 2 |
| 37 | `EditorialService._revision` | free | | [src/kajenn_public_site/services/editorial.py:100](../../../src/kajenn_public_site/services/editorial.py#L100) | 2 |
| 38 | `EditorialService._scope` | free | | [src/kajenn_public_site/services/editorial.py:112](../../../src/kajenn_public_site/services/editorial.py#L112) | 2 |
| 39 | `EditorialService._authorize` | free | | [src/kajenn_public_site/services/editorial.py:119](../../../src/kajenn_public_site/services/editorial.py#L119) | 2 |
| 40 | `EditorialService._view` | free | | [src/kajenn_public_site/services/editorial.py:159](../../../src/kajenn_public_site/services/editorial.py#L159) | 2 |
| 41 | `EditorialService._change` | free | | [src/kajenn_public_site/services/editorial.py:183](../../../src/kajenn_public_site/services/editorial.py#L183) | 2 |
| 42 | `EditorialService._text` | free | | [src/kajenn_public_site/services/editorial.py:213](../../../src/kajenn_public_site/services/editorial.py#L213) | 2 |
| 43 | `EditorialService._dependencies_checked` | free | | [src/kajenn_public_site/services/editorial.py:222](../../../src/kajenn_public_site/services/editorial.py#L222) | 2 |
| 44 | `EditorialService._unique` | free | | [src/kajenn_public_site/services/editorial.py:249](../../../src/kajenn_public_site/services/editorial.py#L249) | 2 |
| 45 | `EditorialService._capabilities` | free | | [src/kajenn_public_site/services/editorial.py:268](../../../src/kajenn_public_site/services/editorial.py#L268) | 2 |
| 46 | `EditorialService._site_create` | free | | [src/kajenn_public_site/services/editorial.py:284](../../../src/kajenn_public_site/services/editorial.py#L284) | 2 |
| 47 | `EditorialService._site_attributes` | free | | [src/kajenn_public_site/services/editorial.py:290](../../../src/kajenn_public_site/services/editorial.py#L290) | 2 |
| 48 | `EditorialService._sites_list` | free | | [src/kajenn_public_site/services/editorial.py:307](../../../src/kajenn_public_site/services/editorial.py#L307) | 2 |
| 49 | `EditorialService._site_configure` | free | | [src/kajenn_public_site/services/editorial.py:315](../../../src/kajenn_public_site/services/editorial.py#L315) | 2 |
| 50 | `EditorialService._records_list` | free | | [src/kajenn_public_site/services/editorial.py:350](../../../src/kajenn_public_site/services/editorial.py#L350) | 2 |
| 51 | `EditorialService._content_create` | free | | [src/kajenn_public_site/services/editorial.py:358](../../../src/kajenn_public_site/services/editorial.py#L358) | 2 |
| 52 | `EditorialService._variant_change` | free | | [src/kajenn_public_site/services/editorial.py:363](../../../src/kajenn_public_site/services/editorial.py#L363) | 2 |
| 53 | `EditorialService._variant_create` | free | | [src/kajenn_public_site/services/editorial.py:429](../../../src/kajenn_public_site/services/editorial.py#L429) | 2 |
| 54 | `EditorialService._draft_save` | free | | [src/kajenn_public_site/services/editorial.py:450](../../../src/kajenn_public_site/services/editorial.py#L450) | 2 |
| 55 | `EditorialService._resource_save` | free | | [src/kajenn_public_site/services/editorial.py:471](../../../src/kajenn_public_site/services/editorial.py#L471) | 2 |
| 56 | `EditorialService._media_save` | free | | [src/kajenn_public_site/services/editorial.py:536](../../../src/kajenn_public_site/services/editorial.py#L536) | 2 |
| 57 | `EditorialService._resource_copy` | free | | [src/kajenn_public_site/services/editorial.py:574](../../../src/kajenn_public_site/services/editorial.py#L574) | 2 |
| 58 | `EditorialService._record_read` | free | | [src/kajenn_public_site/services/editorial.py:596](../../../src/kajenn_public_site/services/editorial.py#L596) | 2 |
| 59 | `EditorialService._revision_history` | free | | [src/kajenn_public_site/services/editorial.py:599](../../../src/kajenn_public_site/services/editorial.py#L599) | 2 |
| 60 | `EditorialService._revision_compare` | free | | [src/kajenn_public_site/services/editorial.py:606](../../../src/kajenn_public_site/services/editorial.py#L606) | 2 |
| 61 | `EditorialService._revision_checkpoint` | free | | [src/kajenn_public_site/services/editorial.py:634](../../../src/kajenn_public_site/services/editorial.py#L634) | 2 |
| 62 | `EditorialService._revision_restore` | free | | [src/kajenn_public_site/services/editorial.py:655](../../../src/kajenn_public_site/services/editorial.py#L655) | 2 |
| 63 | `EditorialService._dependencies` | free | | [src/kajenn_public_site/services/editorial.py:686](../../../src/kajenn_public_site/services/editorial.py#L686) | 2 |
| 64 | `EditorialService._readiness` | free | | [src/kajenn_public_site/services/editorial.py:696](../../../src/kajenn_public_site/services/editorial.py#L696) | 2 |
| 65 | `client` | free | | [tests/api/support.py:21](../../../tests/api/support.py#L21) | 2 |
| 66 | `call` | free | | [tests/api/support.py:45](../../../tests/api/support.py#L45) | 2 |
| 67 | `record` | free | | [tests/api/support.py:62](../../../tests/api/support.py#L62) | 2 |
| 68 | `seed_http` | free | | [tests/api/support.py:68](../../../tests/api/support.py#L68) | 2 |
| 69 | `test_actual_rest_mcp_lifecycle_and_discovery_without_gramlot` | framework: pytest test_ prefix | | [tests/api/test_application.py:8](../../../tests/api/test_application.py#L8) | 2 |
| 70 | `test_actual_rest_mcp_lifecycle_and_discovery_without_gramlot.scenario` | free | | [tests/api/test_application.py:9](../../../tests/api/test_application.py#L9) | 2 |
| 71 | `test_authentication_and_post_only_mutations` | framework: pytest test_ prefix | | [tests/api/test_application.py:70](../../../tests/api/test_application.py#L70) | 2 |
| 72 | `test_authentication_and_post_only_mutations.scenario` | free | | [tests/api/test_application.py:71](../../../tests/api/test_application.py#L71) | 2 |
| 73 | `test_duplicate_application_startup_fails_closed_and_releases_on_shutdown` | framework: pytest test_ prefix | | [tests/api/test_application.py:97](../../../tests/api/test_application.py#L97) | 2 |
| 74 | `test_duplicate_application_startup_fails_closed_and_releases_on_shutdown.scenario` | free | | [tests/api/test_application.py:105](../../../tests/api/test_application.py#L105) | 2 |
| 75 | `test_private_payloads_have_no_public_route` | framework: pytest test_ prefix | | [tests/api/test_application.py:122](../../../tests/api/test_application.py#L122) | 2 |
| 76 | `test_private_payloads_have_no_public_route.scenario` | free | | [tests/api/test_application.py:123](../../../tests/api/test_application.py#L123) | 2 |
| 77 | `test_rest_and_mcp_share_domain_results` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:15](../../../tests/contracts/phase_2/test_contracts.py#L15) | 2 |
| 78 | `test_rest_and_mcp_share_domain_results.scenario` | free | | [tests/contracts/phase_2/test_contracts.py:18](../../../tests/contracts/phase_2/test_contracts.py#L18) | 2 |
| 79 | `test_authorization_is_shared_and_scoped` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:74](../../../tests/contracts/phase_2/test_contracts.py#L74) | 2 |
| 80 | `test_authorization_is_shared_and_scoped.scenario` | free | | [tests/contracts/phase_2/test_contracts.py:77](../../../tests/contracts/phase_2/test_contracts.py#L77) | 2 |
| 81 | `test_named_blocks_preserve_format_and_source` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:123](../../../tests/contracts/phase_2/test_contracts.py#L123) | 2 |
| 82 | `test_incomplete_draft_can_be_saved` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:147](../../../tests/contracts/phase_2/test_contracts.py#L147) | 2 |
| 83 | `test_shared_draft_conflict_preserves_history` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:182](../../../tests/contracts/phase_2/test_contracts.py#L182) | 2 |
| 84 | `test_generic_resource_copy_is_independent` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:225](../../../tests/contracts/phase_2/test_contracts.py#L225) | 2 |
| 85 | `test_languages_have_independent_draft_heads` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:289](../../../tests/contracts/phase_2/test_contracts.py#L289) | 2 |
| 86 | `test_filesystem_backend_has_no_asqueel_dependency` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:333](../../../tests/contracts/phase_2/test_contracts.py#L333) | 2 |
| 87 | `test_filesystem_backend_has_no_asqueel_dependency.scenario` | free | | [tests/contracts/phase_2/test_contracts.py:336](../../../tests/contracts/phase_2/test_contracts.py#L336) | 2 |
| 88 | `test_clients_can_discover_templates_and_read_sources` | framework: fixed contract | | [tests/contracts/phase_2/test_contracts.py:365](../../../tests/contracts/phase_2/test_contracts.py#L365) | 2 |
| 89 | `test_clients_can_discover_templates_and_read_sources.scenario` | free | | [tests/contracts/phase_2/test_contracts.py:368](../../../tests/contracts/phase_2/test_contracts.py#L368) | 2 |
| 90 | `create_service` | free | | [tests/services/scenarios.py:18](../../../tests/services/scenarios.py#L18) | 2 |
| 91 | `record` | free | | [tests/services/scenarios.py:23](../../../tests/services/scenarios.py#L23) | 2 |
| 92 | `seed` | free | | [tests/services/scenarios.py:27](../../../tests/services/scenarios.py#L27) | 2 |
| 93 | `test_named_sources_restart_and_exact_template_selection` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:10](../../../tests/services/test_editorial.py#L10) | 2 |
| 94 | `test_incomplete_validation_unknown_blocks_and_language_uniqueness` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:47](../../../tests/services/test_editorial.py#L47) | 2 |
| 95 | `test_revision_checkpoint_compare_restore_and_idempotency` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:103](../../../tests/services/test_editorial.py#L103) | 2 |
| 96 | `test_scoped_grants_copy_and_media` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:182](../../../tests/services/test_editorial.py#L182) | 2 |
| 97 | `test_concurrent_variant_creation_has_one_shared_head` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:239](../../../tests/services/test_editorial.py#L239) | 2 |
| 98 | `test_concurrent_variant_creation_has_one_shared_head.create` | free | | [tests/services/test_editorial.py:247](../../../tests/services/test_editorial.py#L247) | 2 |
| 99 | `test_copy_edits_preserve_provenance_and_original_dependencies` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:269](../../../tests/services/test_editorial.py#L269) | 2 |
| 100 | `test_invalid_source_command_never_changes_catalog` | framework: pytest test_ prefix | | [tests/services/test_editorial.py:320](../../../tests/services/test_editorial.py#L320) | 2 |
