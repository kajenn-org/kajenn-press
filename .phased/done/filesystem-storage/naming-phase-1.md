# Phase 1 naming review

Status: all proposed names accepted by the user; markers removed without renaming.

Implemented and verified: 30 tests, lint, compile and isolated-install demonstration.
Public types: `LocalCatalog`, `Change`, `Snapshot`, `ObjectStore`, `ObjectRef`.

The table lists every new callable. Python lifecycle methods, pytest discovery prefixes and the ten approved contract test names are fixed interfaces. Other names are reviewable; no speculative or unused callable was found. Validation helpers isolate the versioned schema and conditional-write rules.

| # | Proposed name | Kind | Necessity | File | Phase |
|---|---|---|---|---|---|
| 1 | `authorize_demo` | free | | [examples/persistence.py:10](../../../examples/persistence.py#L10) | 1 |
| 2 | `main` | free | | [examples/persistence.py:16](../../../examples/persistence.py#L16) | 1 |
| 3 | `encode` | free | | [src/kajenn_public_site/catalog/filesystem.py:19](../../../src/kajenn_public_site/catalog/filesystem.py#L19) | 1 |
| 4 | `digest` | free | | [src/kajenn_public_site/catalog/filesystem.py:26](../../../src/kajenn_public_site/catalog/filesystem.py#L26) | 1 |
| 5 | `sync_file` | free | | [src/kajenn_public_site/catalog/filesystem.py:30](../../../src/kajenn_public_site/catalog/filesystem.py#L30) | 1 |
| 6 | `sync_directory` | free | | [src/kajenn_public_site/catalog/filesystem.py:38](../../../src/kajenn_public_site/catalog/filesystem.py#L38) | 1 |
| 7 | `private_directory` | free | | [src/kajenn_public_site/catalog/filesystem.py:46](../../../src/kajenn_public_site/catalog/filesystem.py#L46) | 1 |
| 8 | `contained_file` | free | | [src/kajenn_public_site/catalog/filesystem.py:63](../../../src/kajenn_public_site/catalog/filesystem.py#L63) | 1 |
| 9 | `read_json` | free | | [src/kajenn_public_site/catalog/filesystem.py:74](../../../src/kajenn_public_site/catalog/filesystem.py#L74) | 1 |
| 10 | `publish_json` | free | | [src/kajenn_public_site/catalog/filesystem.py:88](../../../src/kajenn_public_site/catalog/filesystem.py#L88) | 1 |
| 11 | `qualify_filesystem` | free | | [src/kajenn_public_site/catalog/filesystem.py:101](../../../src/kajenn_public_site/catalog/filesystem.py#L101) | 1 |
| 12 | `LocalCatalog.__init__` | framework: Python protocol | | [src/kajenn_public_site/catalog/local.py:61](../../../src/kajenn_public_site/catalog/local.py#L61) | 1 |
| 13 | `LocalCatalog.__enter__` | framework: Python protocol | | [src/kajenn_public_site/catalog/local.py:107](../../../src/kajenn_public_site/catalog/local.py#L107) | 1 |
| 14 | `LocalCatalog.__exit__` | framework: Python protocol | | [src/kajenn_public_site/catalog/local.py:111](../../../src/kajenn_public_site/catalog/local.py#L111) | 1 |
| 15 | `LocalCatalog.close` | free | | [src/kajenn_public_site/catalog/local.py:114](../../../src/kajenn_public_site/catalog/local.py#L114) | 1 |
| 16 | `LocalCatalog._ensure_open` | free | | [src/kajenn_public_site/catalog/local.py:125](../../../src/kajenn_public_site/catalog/local.py#L125) | 1 |
| 17 | `LocalCatalog._store_manifest` | free | | [src/kajenn_public_site/catalog/local.py:131](../../../src/kajenn_public_site/catalog/local.py#L131) | 1 |
| 18 | `LocalCatalog._load_manifest` | free | | [src/kajenn_public_site/catalog/local.py:141](../../../src/kajenn_public_site/catalog/local.py#L141) | 1 |
| 19 | `LocalCatalog._validate_manifest` | free | | [src/kajenn_public_site/catalog/local.py:161](../../../src/kajenn_public_site/catalog/local.py#L161) | 1 |
| 20 | `LocalCatalog._load_current` | free | | [src/kajenn_public_site/catalog/local.py:319](../../../src/kajenn_public_site/catalog/local.py#L319) | 1 |
| 21 | `LocalCatalog.read` | free | | [src/kajenn_public_site/catalog/local.py:323](../../../src/kajenn_public_site/catalog/local.py#L323) | 1 |
| 22 | `LocalCatalog.read_payload` | free | | [src/kajenn_public_site/catalog/local.py:339](../../../src/kajenn_public_site/catalog/local.py#L339) | 1 |
| 23 | `LocalCatalog.receipt` | free | | [src/kajenn_public_site/catalog/local.py:343](../../../src/kajenn_public_site/catalog/local.py#L343) | 1 |
| 24 | `LocalCatalog.commit` | free | | [src/kajenn_public_site/catalog/local.py:347](../../../src/kajenn_public_site/catalog/local.py#L347) | 1 |
| 25 | `LocalCatalog._command` | free | | [src/kajenn_public_site/catalog/local.py:462](../../../src/kajenn_public_site/catalog/local.py#L462) | 1 |
| 26 | `LocalCatalog._check_changes` | free | | [src/kajenn_public_site/catalog/local.py:507](../../../src/kajenn_public_site/catalog/local.py#L507) | 1 |
| 27 | `LocalCatalog.recover` | free | | [src/kajenn_public_site/catalog/local.py:538](../../../src/kajenn_public_site/catalog/local.py#L538) | 1 |
| 28 | `ObjectRef.__post_init__` | framework: Python protocol | | [src/kajenn_public_site/objects.py:25](../../../src/kajenn_public_site/objects.py#L25) | 1 |
| 29 | `ObjectStore.__init__` | framework: Python protocol | | [src/kajenn_public_site/objects.py:42](../../../src/kajenn_public_site/objects.py#L42) | 1 |
| 30 | `ObjectStore.qualify` | free | | [src/kajenn_public_site/objects.py:50](../../../src/kajenn_public_site/objects.py#L50) | 1 |
| 31 | `ObjectStore.prepare` | free | | [src/kajenn_public_site/objects.py:74](../../../src/kajenn_public_site/objects.py#L74) | 1 |
| 32 | `ObjectStore.read` | free | | [src/kajenn_public_site/objects.py:84](../../../src/kajenn_public_site/objects.py#L84) | 1 |
| 33 | `ObjectStore.reference` | free | | [src/kajenn_public_site/objects.py:97](../../../src/kajenn_public_site/objects.py#L97) | 1 |
| 34 | `workspace` | free | | [tests/catalog/support.py:14](../../../tests/catalog/support.py#L14) | 1 |
| 35 | `allow` | free | | [tests/catalog/support.py:19](../../../tests/catalog/support.py#L19) | 1 |
| 36 | `commit` | free | | [tests/catalog/support.py:24](../../../tests/catalog/support.py#L24) | 1 |
| 37 | `baseline` | free | | [tests/catalog/support.py:30](../../../tests/catalog/support.py#L30) | 1 |
| 38 | `crash_changes` | free | | [tests/catalog/support.py:39](../../../tests/catalog/support.py#L39) | 1 |
| 39 | `worker` | free | | [tests/catalog/support.py:53](../../../tests/catalog/support.py#L53) | 1 |
| 40 | `test_atomic_changes_history_and_reopen` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:10](../../../tests/catalog/test_catalog.py#L10) | 1 |
| 41 | `test_thread_conflict_and_authorization` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:34](../../../tests/catalog/test_catalog.py#L34) | 1 |
| 42 | `test_thread_conflict_and_authorization.update` | free | | [tests/catalog/test_catalog.py:38](../../../tests/catalog/test_catalog.py#L38) | 1 |
| 43 | `test_thread_conflict_and_authorization.deny` | free | | [tests/catalog/test_catalog.py:50](../../../tests/catalog/test_catalog.py#L50) | 1 |
| 44 | `test_coordinator_lifecycle_and_detached_reads` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:74](../../../tests/catalog/test_catalog.py#L74) | 1 |
| 45 | `test_committed_corruption_fails_closed` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:86](../../../tests/catalog/test_catalog.py#L86) | 1 |
| 46 | `test_authorization_cannot_mutate_or_release_ownership` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:96](../../../tests/catalog/test_catalog.py#L96) | 1 |
| 47 | `test_authorization_cannot_mutate_or_release_ownership.reentrant` | free | | [tests/catalog/test_catalog.py:100](../../../tests/catalog/test_catalog.py#L100) | 1 |
| 48 | `test_manifest_schema_and_references_fail_closed` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:122](../../../tests/catalog/test_catalog.py#L122) | 1 |
| 49 | `test_invalid_intent_is_reported_as_integrity_failure` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:150](../../../tests/catalog/test_catalog.py#L150) | 1 |
| 50 | `test_catalog_symlink_and_path_containment` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:161](../../../tests/catalog/test_catalog.py#L161) | 1 |
| 51 | `test_committed_reference_reuse_and_reject_orphan` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:178](../../../tests/catalog/test_catalog.py#L178) | 1 |
| 52 | `test_independent_records_and_receipt_scopes` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:197](../../../tests/catalog/test_catalog.py#L197) | 1 |
| 53 | `test_io_error_requires_reopen_and_receipt_reconciliation` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:219](../../../tests/catalog/test_catalog.py#L219) | 1 |
| 54 | `test_io_error_requires_reopen_and_receipt_reconciliation.lost_ack` | free | | [tests/catalog/test_catalog.py:227](../../../tests/catalog/test_catalog.py#L227) | 1 |
| 55 | `test_configured_parent_alias_is_resolved_but_root_link_rejected` | framework: pytest test_ prefix | | [tests/catalog/test_catalog.py:245](../../../tests/catalog/test_catalog.py#L245) | 1 |
| 56 | `test_public_storage_preserves_bytes_and_rejects_overwrite` | framework: pytest test_ prefix | | [tests/catalog/test_objects.py:9](../../../tests/catalog/test_objects.py#L9) | 1 |
| 57 | `test_object_containment_and_corruption` | framework: pytest test_ prefix | | [tests/catalog/test_objects.py:19](../../../tests/catalog/test_objects.py#L19) | 1 |
| 58 | `test_unsupported_flush_fails_closed` | framework: pytest test_ prefix | | [tests/catalog/test_objects.py:40](../../../tests/catalog/test_objects.py#L40) | 1 |
| 59 | `test_unsupported_flush_fails_closed.unavailable` | free | | [tests/catalog/test_objects.py:41](../../../tests/catalog/test_objects.py#L41) | 1 |
| 60 | `main` | free | | [tests/catalog/worker.py:16](../../../tests/catalog/worker.py#L16) | 1 |
| 61 | `main.publish` | free | | [tests/catalog/worker.py:42](../../../tests/catalog/worker.py#L42) | 1 |
| 62 | `main.replace` | free | | [tests/catalog/worker.py:51](../../../tests/catalog/worker.py#L51) | 1 |
| 63 | `main.prepare` | free | | [tests/catalog/worker.py:58](../../../tests/catalog/worker.py#L58) | 1 |
| 64 | `main.open_payload` | free | | [tests/catalog/worker.py:63](../../../tests/catalog/worker.py#L63) | 1 |
| 65 | `test_committed_catalog_survives_restart` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:18](../../../tests/contracts/phase_1/test_contracts.py#L18) | 1 |
| 66 | `test_historical_payload_is_immutable` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:34](../../../tests/contracts/phase_1/test_contracts.py#L34) | 1 |
| 67 | `test_stale_generation_does_not_overwrite` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:54](../../../tests/contracts/phase_1/test_contracts.py#L54) | 1 |
| 68 | `test_stale_generation_does_not_overwrite.update` | free | | [tests/contracts/phase_1/test_contracts.py:61](../../../tests/contracts/phase_1/test_contracts.py#L61) | 1 |
| 69 | `test_duplicate_coordinator_is_rejected` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:85](../../../tests/contracts/phase_1/test_contracts.py#L85) | 1 |
| 70 | `test_idempotent_retry_survives_restart` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:115](../../../tests/contracts/phase_1/test_contracts.py#L115) | 1 |
| 71 | `test_idempotency_key_payload_mismatch_is_rejected` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:132](../../../tests/contracts/phase_1/test_contracts.py#L132) | 1 |
| 72 | `test_interrupted_commit_has_one_visible_generation` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:143](../../../tests/contracts/phase_1/test_contracts.py#L143) | 1 |
| 73 | `test_uncommitted_payload_is_not_visible` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:184](../../../tests/contracts/phase_1/test_contracts.py#L184) | 1 |
| 74 | `test_coordinated_changes_commit_together` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:209](../../../tests/contracts/phase_1/test_contracts.py#L209) | 1 |
| 75 | `test_payload_access_uses_public_storage_api` | framework: fixed contract name | | [tests/contracts/phase_1/test_contracts.py:237](../../../tests/contracts/phase_1/test_contracts.py#L237) | 1 |
| 76 | `test_payload_access_uses_public_storage_api.tracked` | free | | [tests/contracts/phase_1/test_contracts.py:245](../../../tests/contracts/phase_1/test_contracts.py#L245) | 1 |
| 77 | `test_payload_access_uses_public_storage_api.forbidden` | free | | [tests/contracts/phase_1/test_contracts.py:249](../../../tests/contracts/phase_1/test_contracts.py#L249) | 1 |
| 78 | `test_payload_access_uses_public_storage_api.no_flush` | free | | [tests/contracts/phase_1/test_contracts.py:258](../../../tests/contracts/phase_1/test_contracts.py#L258) | 1 |
