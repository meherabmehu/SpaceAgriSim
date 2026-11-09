# Production Readiness Audit — SpaceAgriSim

Date: 2026-11-09
Scope: the hosted deployment (`spaceagrisim-api.onrender.com`, `spaceagrisim-web.onrender.com`),
its PostgreSQL schema lifecycle, its behaviour with more than one worker, and the diagnostics an
operator needs when any of that breaks.

Every claim below is marked with where it comes from:

* **[executed]** — a command was run and its output is quoted here.
* **[test]** — asserted by an automated test in this repository.
* **[doc]** — taken from a vendor's documentation, with the URL.
* **[not verified]** — believed, but not proven from this environment. Never stated as fact.

The distinction matters: a local suite passing does not prove the hosted service is healthy, and
this document does not claim it does. Production checks are reported separately, with their own
timestamps, in [Production verification](#7-production-verification).

---

## 1. What the deployment actually is

| Fact | Value | Source |
| --- | --- | --- |
| API service | Render web service `spaceagrisim-api`, Python, region Singapore, `plan: free` | `render.yaml` [executed] |
| Start command | `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT --workers 1 --timeout-graceful-shutdown 25` | `render.yaml` |
| Health check | `healthCheckPath: /api/ready` | `render.yaml` |
| Auto-deploy | `autoDeployTrigger: 'off'`, so a push to `main` does **not** deploy; a deploy must be started manually | `render.yaml` |
| Web client | Render static site `spaceagrisim-web`, `plan: free`, build `cd frontend && npm ci && npm run build` | `render.yaml` |
| Database | Render Postgres, **created in the dashboard, not in the blueprint** — `render.yaml` has no `databases:` block, so its plan, version and backup policy are not version-controlled | `render.yaml` [executed] |
| Backups on the database | See `docs/DATABASE_BACKUP_AND_RECOVERY.md`; on the Free compute plan: none | [doc] |

Two consequences follow immediately, and both are operational rather than code:

1. **The blueprint is not the whole deployment.** The database's existence, plan and settings live
   only in the Render dashboard. A rebuild from `render.yaml` alone would produce an API with no
   database URL (`SPACEAGRISIM_DATABASE_URL` is `sync: false`, i.e. entered by hand).
2. **Nothing deploys itself.** `autoDeployTrigger: 'off'` means the commit that fixes a production
   problem is inert until someone presses *Deploy* (or hits the deploy hook). Any verification
   performed on the live URL is only meaningful *after* that manual step.

## 2. What changed in this phase

Four backend files, one new test module, two operator scripts, two documents.

### 2.1 Schema bootstrap is serialised across workers (`backend/app/storage.py`)

Before this phase, every worker ran `metadata.create_all()` at startup with nothing but an
in-process `threading.Lock` for protection. That lock cannot see another process, and this project
had already paid for the gap once: two concurrent `create_all` calls produced
`duplicate key value violates unique constraint "pg_type_typname_nsp_index"`.

`_initialise_schema()` now takes a PostgreSQL **session advisory lock**
(`SCHEMA_LOCK_KEY = 0x5A5A2026`) with a bounded wait (`SPACEAGRISIM_MIGRATION_LOCK_TIMEOUT_S`,
default 30 s), runs the DDL while holding it, and releases it in a `finally`. If the lock cannot be
acquired, the worker raises `DatabaseConfigurationError("migration-lock-timeout")` instead of
starting half-migrated. SQLite falls through to the same code path without a lock, because a
single-file store in this deployment is served by exactly one process.

Evidence: **[test]** `test_schema_bootstrap_waits_for_a_lock_held_elsewhere_then_fails_clearly`
(second worker refuses with `migration-lock-timeout`, then succeeds once the holder releases) and
`test_concurrent_workers_bootstrap_the_schema_once` (eight engines, one barrier, one schema, no
error).

### 2.2 Migration registry (`backend/app/storage.py`)

`MIGRATIONS` lists every schema step this project has ever needed, each with the condition that
proves it applied:

| id | applies when | condition |
| --- | --- | --- |
| `0001-initial-schema` | first boot | all seven required tables exist |
| `0002-scenarios-owner-id` | per-account history | `scenarios.owner_id` exists |
| `0003-users-phase19-columns` | hosted accounts | `users.email_verified`, `users.password_changed_at` exist |
| `0004-scenarios-owner-index` | owner-scoped queries | `ix_scenarios_owner_id` exists |

`migration_state()` inspects the live schema and returns `{applied, pending, appliedCount,
pendingCount, total}`. It runs **no DDL** — that is what makes it safe to call from a readiness
probe: **[test]** `test_empty_database_reports_the_initial_migration_as_pending` asserts the
database is still empty after inspection.

### 2.3 Readiness refuses to green-light a half-migrated deployment (`backend/app/routes/workspace.py`)

`GET /api/ready` (also the Render health check) now answers in three distinct ways:

| condition | status | body |
| --- | --- | --- |
| schema complete, all migrations applied | 200 | `status: ready`, `databaseMigrations: {applied, total, pending}`, `databasePool` |
| server reachable, no schema at all | 503 | `error: database_schema_incomplete`, `missingTables`, `pendingMigrations`, `remedy` |
| schema present, an additive step missing | 503 | `error: database_migration_pending`, `pendingMigrations`, `missing`, `remedy` |
| cannot connect / misconfigured URL | 503 | `error: database_unavailable` / `database_misconfigured`, `reason`, SQLSTATE when the server answered, `remedy` |

The previous behaviour — reporting `ready` because `SELECT 1` succeeded — is exactly how a
deployment serves 500s on every account route while its health check stays green. The
schema-incomplete branch is checked before the migration list so the headline says "the schema was
never created" rather than listing four pending steps, while still including the pending ids.

### 2.4 Pool visibility (`backend/app/storage.py`)

`pool_status()` reports `{dialect, pooled, size, checkedOut, overflow, capacity, exhausted}` for
PostgreSQL and, for SQLite, `{dialect, pooled: false, note}` — it deliberately reports no capacity
figure for a single-file store, because inventing one invites a reader to treat it as a pool:
**[test]** `test_pool_status_describes_sqlite_without_inventing_capacity`.

`settings.database_pool_size` defaults to 5 and `settings.database_max_overflow` to 5, so the reported
capacity is **10** per worker. At `--workers 1` that is 10 concurrent database operations for the
whole service.

### 2.5 Diagnostics without secrets (`backend/app/observability.py`, `backend/app/middleware.py`)

* `record_db_slow_query(operation, elapsed_ms)` — counts statements that cross
  `SPACEAGRISIM_SLOW_QUERY_MS` (default 250 ms) by **SQL verb only**, and logs
  `slow database statement: SELECT took 412 ms`. Statement text and parameters are never logged,
  because parameters are where addresses, session hashes and free text live:
  **[test]** `test_slow_statement_is_counted_without_logging_sql_or_parameters` asserts the
  parameter value does not appear in the log.
* `record_db_failure(kind)` — counts `connect`, `pool-timeout`, `integrity`, `configuration`,
  `other`.
* `classify_db_failure(exc)` + the request middleware classify an *unhandled* database exception
  and count it before re-raising it unchanged, so no response contract moved:
  **[test]** `test_unhandled_database_error_is_counted_and_still_raised`.
* `GET /api/metrics` exposes the counters under `metrics.database`; `scope` states they are
  per-process and reset on restart, which is the truth at `--workers 1` and would become a
  limitation at any other worker count.

Nothing in these labels contains a URL, host, user id, email, token or SQL fragment:
**[test]** `test_readiness_counts_a_connection_failure_without_leaking_the_url` asserts the host
from the driver exception does not appear in the response.

## 3. Migration audit

### 3.1 How a migration runs in production

1. The container starts uvicorn. `app.main` **does not** connect to the database at import time;
   the engine is built lazily on first use (`database()` behind an `lru_cache` and `_ENGINE_LOCK`).
2. The first request — on Render, the `/api/ready` health check — builds the engine, which installs
   the slow-query listener and runs `_initialise_schema()`.
3. On PostgreSQL that takes the advisory lock, runs `create_all` plus the two additive migrations
   (`ALTER TABLE … ADD COLUMN` guarded by column inspection, and `CREATE INDEX IF NOT EXISTS`), and
   releases the lock.
4. `/api/ready` then inspects the result and reports `databaseMigrations: {applied: 4, total: 4,
   pending: 0}` on a healthy deployment.

Verified against a real PostgreSQL 17.11 server during this audit: `{'status': 'ready',
'databaseDialect': 'postgresql', 'databaseSchema': 'present', 'databaseMigrations': {'applied': 4,
'total': 4, 'pending': 0}}` [executed].

### 3.2 Are the migrations repeatable and non-destructive?

Yes, by construction and by test:

* `create_all` is `checkfirst=True`; both `ALTER`s are guarded by an inspector check; the index is
  `IF NOT EXISTS`. No `DROP`, no `TRUNCATE`, no column type change, no data rewrite.
* **[test]** `test_apply_schema_is_repeatable_and_non_destructive` inserts a row, applies the
  schema twice more, and asserts the row is still there with `pendingCount == 0`.
* The CI `postgres` job (`.github/workflows/ci.yml`) runs the persistence suite against a
  `postgres:16-alpine` service and fails if any of those tests skip, so "the tests passed because
  they were skipped" is not possible there. *(That job lives on `main`; the token used for pushes
  in this environment lacks the `workflow` scope, so no change to that file was made in this
  phase — see §8.)*

### 3.3 Can a deployment silently skip a required migration?

It can no longer do so silently. If the schema is behind, `/api/ready` returns 503 with the pending
ids, the missing objects and a remedy, and Render marks the deploy unhealthy because that endpoint
is the health check. The failure is visible both in the HTTP response and in the deploy log.

What is **not** true, and this document will not imply it: a migration is still applied lazily by
the *serving* process rather than by a separate release step. A truly dead database (no connection
at all) means the app boots and every request returns 503 — the process does not exit. That is the
deliberate trade at `--workers 1` on a free plan: a crash-looping service is harder to diagnose
than one that answers 503 with `reason: connection-failed` and a SQLSTATE.

## 4. Multi-worker and multi-instance review

| # | Risk | Status at `--workers 1` | Status at >1 worker / instance | Action taken |
| --- | --- | --- | --- | --- |
| 1 | Concurrent `create_all` → duplicate `pg_type` | Not reachable | **Blocking** before this change | Fixed: advisory lock (§2.1) + test with 8 threads |
| 2 | Rate limiter is an in-process `defaultdict(deque)` | Correct (one process) | Budget multiplies by worker count | **Not changed.** Documented; fixing needs a shared store (Redis), which is out of scope and unverifiable here |
| 3 | Auth tokens signed with `SPACEAGRISIM_AUTH_SECRET` | Shared, because the value is generated once and stored as a Render env var | Correct if the same value reaches every worker | No change; the app already refuses an ephemeral secret in production |
| 4 | Connection pool per worker | 10 connections | 10 × workers against the instance's direct-connection limit | Documented in `pool_status()`; **worker count not changed** |
| 5 | Concurrent writes to the same scenario | Last write wins; no ETag | Same | Out of scope: an optimistic-concurrency header would change the API contract |
| 6 | Retention sweep deleting across owners | Fixed in the previous phase (owner-scoped) | — | Already fixed |
| 7 | SQLite path | Single process by definition | Unsafe | No change; production uses PostgreSQL and `/api/ready` reports the dialect |

The worker count stays at 1. Nothing measured in this audit justifies changing it: the persistence
path is now safe for more than one worker, but the rate limiter is not, and raising the count
without fixing that would trade a solved problem for an unmeasured one.

## 5. Automated smoke test (`scripts/production_smoke.py`)

Purpose: prove the *deployed* service works end to end, not merely that it is up.

```bash
export SPACEAGRISIM_SMOKE_PASSWORD='<at least 16 characters>'
python3 scripts/production_smoke.py                        # default: the hosted API
python3 scripts/production_smoke.py --json                 # machine-readable
python3 scripts/production_smoke.py --base-url http://127.0.0.1:8011
```

It uses only the public HTTP API (`urllib`, no third-party client). Checks, in order:

| # | Check |
| --- | --- |
| 1–2 | `/api/health` 200; `/api/ready` reports `ready` |
| 3–6 | readiness dialect, schema present, `migrations applied` (applied == total, pending == 0), `durability matches dialect` |
| 7–11 | dedicated smoke account register/login, session accepted, unauthenticated request refused (401), invalid token refused (401) |
| 12–16 | scenario create, retrieve by id, update, re-read shows the update (durability, not just a 200), list contains it |
| 17–19 | second account: read/write/delete all refused (404), and the owner's row is unchanged afterwards |
| 20–21 | saved analysis via `POST /api/workflow/run-and-save` then `GET /api/analyses/{id}` |
| 22–23 | scenario delete (204), then 404 |

Safety properties, all deliberate:

* **One stable probe account** (`smoke-probe@spaceagrisim-smoke.invalid`) is reused: register, then
  fall back to login on 409. An earlier version created a per-run account, which accumulated a row
  in `users` on every run because no account-deletion endpoint exists — the kind of silent growth a
  smoke test must not cause.
* **Every created row is named `SMOKE-…`**, and `cleanup()` deletes only rows whose name carries
  that prefix. The script has no code path that deletes anything it did not create.
* **No secret is printed**: no password, no token, no database URL; tokens are held in memory only.
* Exit codes: `0` all checks passed, `1` a check failed, `2` refused to run (missing/short
  password).

Executed locally against a PostgreSQL-backed uvicorn (`127.0.0.1:8011`, database
`spaceagrisim_smoke`) [executed]:

```
23 passed, 0 failed, 0 skipped
```

A second run immediately afterwards also passed (`23 passed`), and the table counts after both runs
were `users 2, scenarios 0, analyses 0` — i.e. the two stable smoke accounts and **no leftover
scenarios or analyses**, which is what `cleanup()` is for.

## 6. Test evidence

Commands are reproduced exactly as run; the PostgreSQL DSN is a local server.

| Suite | Command | Result |
| --- | --- | --- |
| Backend, SQLite (default) | `SPACEAGRISIM_DATABASE_URL=sqlite:////tmp/x_sqlite_suite.db pytest -q` | **768 passed, 23 skipped** [executed] |
| Backend, PostgreSQL | `SPACEAGRISIM_DATABASE_URL=postgresql://…/spaceagrisim_suite SPACEAGRISIM_TEST_POSTGRES_URL=… pytest -q` | **791 passed, 0 skipped** [executed] |
| New module, SQLite | `pytest -q tests/test_multi_worker_readiness.py` | 17 passed, 3 skipped (the PostgreSQL-only lock, concurrency and pool tests) [executed] |
| New module, PostgreSQL | same file with both DSNs set | **20 passed** [executed] |
| Frontend lint / types / build | `npm ci && npm run lint && npm run typecheck && npm run build` | clean, `✓ built` [executed] |
| Browser E2E | `npx playwright test` (3 viewports) | **81 passed** [executed] on the final run; one earlier full run had a single mobile flake in `mission.spec.js` (see §9) |

The 23 skips on SQLite are the PostgreSQL-only tests; the count is unchanged from before this
phase (20) plus the three skipped in the new module.

## 7. Production verification

Filled in only from commands actually run against the live service. See the delivery report for the
same results; nothing here is inferred from local tests.

Baseline captured **before** this phase's code was deployed, against
`https://spaceagrisim-api.onrender.com/api/ready` [executed, 2026-11-09]:

```json
{"status": "ready", "database": "available", "databaseDialect": "postgresql",
 "databaseSchema": "present",
 "storage": {"dialect": "postgresql", "durable": true}, "emailDelivery": "unconfigured"}
```

No `databaseMigrations` or `databasePool` field is present in that payload, which is direct
evidence that the live service was still running the previous commit: the new fields appear only
after the deploy. **The production smoke test cannot report the new behaviour until the deploy is
triggered in the Render dashboard** (`autoDeployTrigger: 'off'`).

## 8. Remaining manual and out-of-scope items

| # | Item | Why it is not done here |
| --- | --- | --- |
| 1 | Trigger the API and static-site deploys in the Render dashboard after this push | `autoDeployTrigger: 'off'` in `render.yaml`; no Render API key is available in this environment, and the instruction was not to fabricate deployment success |
| 2 | Re-run `scripts/production_smoke.py` against the deployed API | Requires the deploy in (1) |
| 3 | Add the CI `postgres` job changes | The push token lacks the `workflow` scope; that job is already on `main` from the previous phase, unchanged here |
| 4 | Enable automated backups or PITR | Free compute plan has neither; see `docs/DATABASE_BACKUP_AND_RECOVERY.md` for the options and their cost |
| 5 | Move the rate limiter to a shared store before raising `--workers` | Needs a managed Redis/KV, which is not provisioned and cannot be tested from here |
| 6 | Database plan, version and region are dashboard-only | Not represented in `render.yaml`; recommended follow-up is to add a `databases:` block once the plan is decided |

## 9. Known limitations of this audit

* **PostgreSQL was exercised locally (17.11), not on Render.** The Render instance's server version
  was not queried, so "works on Render's version" is an inference from compatibility, not a
  measurement. The production smoke test is what will close that gap.
* **The rate-limiter and worker-count analysis is static.** No load test was run, so no claim is
  made about throughput or about behaviour at 2+ workers.
* **Counters are per-process.** At `--workers 1` they are complete; at any higher count they are
  per-worker and `/api/metrics` would under-report. The payload says so.
* **One flaky E2E test.** The first full Playwright run this session reported
  `[mobile] › e2e/mission.spec.js:11 › mission shell, real controls, and responsive navigation` as
  failed; it passed in isolation (5 passed) and in the subsequent full run (81 passed). It is a
  timing-sensitive browser test under three parallel viewports, unrelated to these backend changes,
  and it is recorded here rather than hidden.
* **No penetration or load testing** was performed; this audit covers correctness of the schema
  lifecycle, multi-worker safety of the bootstrap, diagnostics, and the smoke path.
