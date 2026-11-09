# Database persistence test report

Everything below was executed, not planned. Commands and their output are reproduced as they ran.
The PostgreSQL figures come from a real PostgreSQL **17.11** server on the same host as the tests,
with the suite pointed at it through `SPACEAGRISIM_DATABASE_URL`; CI runs the same job against
`postgres:16-alpine` (`.github/workflows/ci.yml`, job `postgres`).

## 1. Test methodology

### Isolation

`backend/tests/test_postgresql_persistence.py` never touches a production database and never
touches the server's `public` schema:

1. read the DSN from `SPACEAGRISIM_TEST_POSTGRES_URL`; skip the module if it is unset;
2. generate a schema name `persistence_test_<random>`;
3. `CREATE SCHEMA` it with an admin connection;
4. build the application URL for that schema via `options=-csearch_path=<schema>`, so `create_all`
   and every query land inside it;
5. drop only that schema (`DROP SCHEMA ... CASCADE`), and only if its name carries the test prefix.

The schema is **function-scoped**: rows written by one test are not visible to the next. A
module-scoped schema was tried first and produced a false failure in the retention test, which is
how the isolation requirement made itself obvious.

### Why the restart test is the one that matters

`test_records_survive_engine_disposal_and_reconnection`:

1. write a scenario and a saved analysis through the current engine;
2. record `pg_backend_pid()` — the identity of the server backend that served the write;
3. call `storage.dispose_database()`: dispose the pool, drop the memoised engine;
4. build a fresh engine, and assert it is a different object **and** lands on a different
   `pg_backend_pid`;
5. read both records back and assert their field values;
6. read the scenario's `name` with raw SQL, so the value is shown to come from a row rather than a
   cached response.

A row held in a connection-local buffer, a `TEMP` table or a process dictionary cannot survive
steps 3–4. `test_scenario_history_endpoint_reads_after_restart` repeats the check through HTTP,
including `/api/auth/me` for the account that was created before the restart.

### Coverage map

| Requirement | Test |
| --- | --- |
| Create | `test_create_read_update_delete_round_trip`, `test_create_then_retrieve_by_id` |
| Retrieve by id | `test_create_read_update_delete_round_trip`, `test_create_then_retrieve_by_id` |
| Update and verify | `test_update_changes_the_name_and_the_configuration` |
| Delete and verify | `test_delete_removes_the_scenario_from_every_read` |
| Ownership / access control | `test_ownership_is_enforced_on_read_update_and_delete`, `test_another_account_cannot_read_update_or_delete`, `test_listing_returns_only_the_callers_rows`, `test_another_account_cannot_read_or_delete_an_analysis` |
| Simulation result persistence | `test_saved_analysis_round_trip`, `test_a_saved_analysis_can_be_retrieved_after_being_written` |
| Session close / recreate | `test_records_survive_engine_disposal_and_reconnection`, `test_scenario_history_endpoint_reads_after_restart` |
| PostgreSQL is really used | `test_the_application_connects_to_postgresql_not_sqlite`, `test_sqlite_is_not_in_the_url_the_server_sees` |
| Connection failure | `test_connection_failure_is_reported_without_leaking_credentials`, existing `test_phase19_database_configuration.py` |
| Missing configuration | `test_phase19_database_configuration.py` (blank URL, unsupported scheme, ephemeral durability) |
| Session cleanup | `test_sessions_are_returned_to_the_pool` |
| Transaction rollback | `test_transaction_rolls_back_when_a_write_fails`, `test_quota_rejection_persists_nothing` |
| Concurrent creation | `test_concurrent_creates_are_all_persisted` (10 threads) |
| Migrations safe and repeatable | `test_migrations_are_repeatable_and_non_destructive`, `test_owner_index_exists_for_scoped_queries` |
| Readiness reflects connectivity *and* schema | `test_missing_schema_is_not_reported_as_available`, `test_readiness_reports_the_schema_state_not_only_connectivity` |
| Share links are rows and die with their scenario | `test_deleting_a_scenario_removes_its_share_links`, `test_a_share_link_survives_and_dies_with_its_scenario` |

## 2. Results

### 2.1 PostgreSQL persistence module — 19 passed

```
tests/test_postgresql_persistence.py::test_the_application_connects_to_postgresql_not_sqlite PASSED
tests/test_postgresql_persistence.py::test_sqlite_is_not_in_the_url_the_server_sees PASSED
tests/test_postgresql_persistence.py::test_create_read_update_delete_round_trip PASSED
tests/test_postgresql_persistence.py::test_ownership_is_enforced_on_read_update_and_delete PASSED
tests/test_postgresql_persistence.py::test_listing_returns_only_the_callers_rows PASSED
tests/test_postgresql_persistence.py::test_deleting_a_scenario_removes_its_share_links PASSED
tests/test_postgresql_persistence.py::test_retention_trims_only_the_owners_history PASSED
tests/test_postgresql_persistence.py::test_saved_analysis_round_trip PASSED
tests/test_postgresql_persistence.py::test_another_account_cannot_read_or_delete_an_analysis PASSED
tests/test_postgresql_persistence.py::test_records_survive_engine_disposal_and_reconnection PASSED
tests/test_postgresql_persistence.py::test_scenario_history_endpoint_reads_after_restart PASSED
tests/test_postgresql_persistence.py::test_missing_schema_is_not_reported_as_available PASSED
tests/test_postgresql_persistence.py::test_transaction_rolls_back_when_a_write_fails PASSED
tests/test_postgresql_persistence.py::test_quota_rejection_persists_nothing PASSED
tests/test_postgresql_persistence.py::test_sessions_are_returned_to_the_pool PASSED
tests/test_postgresql_persistence.py::test_concurrent_creates_are_all_persisted PASSED
tests/test_postgresql_persistence.py::test_connection_failure_is_reported_without_leaking_credentials PASSED
tests/test_postgresql_persistence.py::test_migrations_are_repeatable_and_non_destructive PASSED
tests/test_postgresql_persistence.py::test_owner_index_exists_for_scoped_queries PASSED
19 passed
```

### 2.2 Full backend suite

| Configuration | Result |
| --- | --- |
| Default (scratch SQLite file, PostgreSQL tests skipped) | **751 passed, 20 skipped** |
| `SPACEAGRISIM_DATABASE_URL` = PostgreSQL 17.11 | **771 passed, 0 skipped** |

The 20 skips in the default configuration are the PostgreSQL-only tests (19 in the persistence
module plus the legacy round-trip). A skip is not a pass, which is why CI fails the `postgres` job
if anything skips there.

### 2.3 API-level persistence module (runs everywhere) — 15 passed

```
15 passed
```

### 2.4 Frontend

| Check | Result |
| --- | --- |
| `npm run lint` | clean |
| `npm run typecheck` | clean |
| `npm run build` | built |
| `npx playwright test` (desktop, tablet, mobile) | **81 passed** |

### 2.5 Regression checks specific to this change

* `/api/scenarios`, `POST /api/scenarios` and the scenario row shape are unchanged: the new routes
  return the same raw row shape the listing already returned (`id`, `name`, `created_at`,
  `configuration`, `model_version`, `owner_id`).
* `/api/ready` gains `databaseSchema` and can now answer 503 `schema-incomplete`. Its 200 payload
  keeps every pre-existing key.
* `storage.database_health()` gained `schema` and `missingTables`. The one existing assertion that
  compared the whole dict (`tests/test_postgres_integration.py`) was updated to assert the fields it
  actually cares about.
* `storage.database.cache_clear()` still exists (now disposes the pool too), so no existing test or
  tool needed editing.

## 3. What is proven, and what is not

**Proven**, against a real PostgreSQL server:

* a configured PostgreSQL URL is what the application uses, with no SQLite fallback;
* created, updated and deleted scenarios behave correctly and are owner-scoped;
* a saved model result persists and is readable back with its payload intact;
* records survive disposing the engine and reconnecting on a different server backend;
* a failed transaction leaves no partial row; a quota rejection stores nothing;
* connections are returned to the pool; ten concurrent writers all persist;
* migrations are additive, repeatable and non-destructive;
* a reachable database with missing tables is reported as *not ready*, not as available.

**Not proven / not claimed:**

* durability against loss of the database itself (no backup or PITR is configured — a platform
  setting);
* multi-process first-creation safety (the deployment runs one worker; the in-process lock covers
  threads only);
* that the production Render deployment has run these tests — it has not; CI runs them, production
  runs the application.

## 4. Known limitations (test-side)

1. The PostgreSQL module skips without a DSN. CI provisions a server and fails if anything skips; a
   local run without `SPACEAGRISIM_TEST_POSTGRES_URL` does not exercise persistence against
   PostgreSQL, and the skip message says so.
2. Concurrency is tested with ten threads inside one process, not across processes or hosts.
3. `test_sessions_are_returned_to_the_pool` asserts `pool.checkedout() == 0` after ordinary accessor
   use; it does not simulate a connection dropped mid-transaction by the server.
4. Retention, quota and share-link caps are exercised by lowering the settings in the test rather
   than by writing thousands of rows.
