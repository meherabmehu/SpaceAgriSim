# Phase 27 — PostgreSQL Reliability

**Result: the 24 tests that used to skip now execute and pass. 1012 passed, 0 skipped, 0 failed**
against a real PostgreSQL 17.11 server.

## 1. The problem this phase found

The `backend` CI job ran the suite with `SPACEAGRISIM_DATABASE_URL: 'sqlite:///:memory:'`. Under
SQLite, every PostgreSQL test skips by design — `test_postgresql_persistence.py` carries a
module-level `skipif` on `SPACEAGRISIM_TEST_POSTGRES_URL`. The consequence was structural: **24
persistence, transaction, constraint and connection-failure tests were green by absence on every CI
run since they were written.** A skip rendered as a pass in the one number anyone reads.

That is the exact failure mode this project is otherwise careful about — an unevaluated claim
reading as an evaluated one — so it is fixed by making the skips impossible, not by documenting them
more clearly.

## 2. What was added

A third CI job, `postgres`, with a real service container:

```yaml
services:
  postgres:
    image: postgres:17
    env: { POSTGRES_USER: spaceagrisim, POSTGRES_PASSWORD: ci-only-test-password,
           POSTGRES_DB: spaceagrisim_test }
    ports: ['5432:5432']
    options: >-
      --health-cmd "pg_isready -U spaceagrisim -d spaceagrisim_test"
      --health-interval 5s --health-timeout 5s --health-retries 10
```

Three properties were deliberate:

* **The container is disposable and the URL names it.** `127.0.0.1:5432/spaceagrisim_test` in a
  throwaway job container. No workflow step reads a deployment secret, and no value resembles a
  production DSN. The restrictions on touching production are respected by construction rather than
  by care.
* **Skips are converted into failures.** The full suite runs with `-rs`, tees to a log, and the step
  exits non-zero if the word `skipped` appears. This is what stops the previous situation from
  returning silently.
* **`postgresql-client` is installed**, because `pg_restore` is what the backup/restore-verification
  test shells out to. Without it that test skips, which the skip-gate would (correctly) fail on.

The SQLite `backend` job is preserved unchanged. SQLite remains the fast path and the only one that
runs without a server; it is not replaced, it is supplemented.

## 3. Local reproduction, and what it proved

The service container was reproduced outside CI with a real PostgreSQL 17.11 on this machine, so the
numbers below are measured rather than inferred from a workflow file:

```
initdb -D /tmp/pgdata -U postgres -E UTF8
# pg_hba: scram-sha-256 for host connections - see §4
psql -c "ALTER USER postgres PASSWORD '...'"
psql -c "CREATE DATABASE spaceagrisim_test"

SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://...@127.0.0.1:5432/spaceagrisim_test \
  python3 -m pytest -q backend/tests -rs
```

| Run | SQLite only | With PostgreSQL |
| --- | --- | --- |
| Result | 988 passed, **24 skipped** | **1012 passed, 0 skipped** |
| PostgreSQL-specific files | 0 executed | **87 passed** |

Every one of the 24 previously-skipped tests now runs. No test was edited, no assertion relaxed, no
threshold moved.

## 4. The one PostgreSQL-specific failure found, and its cause

```
FAILED test_postgresql_persistence.py::test_connection_failure_is_reported_without_leaking_credentials
  Failed: DID NOT RAISE <class 'Exception'>
```

**This was my test server's fault, not the product's.** `initdb --auth=trust` accepts any password,
so a deliberately wrong password still authenticated and the test — which asserts that a bad
credential produces a typed, secret-free error — could not observe the failure it was written to
observe. The fix was to configure the server the way the CI container is configured, with
`scram-sha-256` for host connections, and set a real password. The test then passed unmodified.

It is recorded here because the alternative reading — "the test is flaky, skip it" — would have
removed the only check that a wrong password does not leak into a traceback or an API response. A
test that cannot fail is worth less than no test, and the wrong response is to relax it.

## 5. What is now guaranteed by an executed test, not by documentation

The files that ran in the `postgres` job cover:

| Guarantee | Where |
| --- | --- |
| A scenario written to PostgreSQL is readable back through the API | `test_postgres_integration.py` |
| Restart-equivalent reads: a second engine sees the first engine's rows | `test_postgresql_persistence.py` |
| Each test is isolated in a throwaway schema, `search_path`-redirected, `public` never touched | `test_postgresql_persistence.py` fixtures |
| Teardown drops only a schema it created, by prefix | same |
| `create_all` builds the schema and `database_health()` reports `schema: present` | same |
| A connection failure is typed and carries no credentials | same |
| Concurrent writers do not corrupt the scenario table | same |
| Scenario persistence through the HTTP API | `test_scenario_persistence_api.py`, `test_workspace.py` |
| DSN alias resolution (`postgres://` → `postgresql+psycopg://`) | `test_phase19_database_configuration.py` |
| Backup and restore-verification round trip | `test_phase22_backup_automation.py` |

## 6. Production safety

No production database was contacted. No migration was written or run. No Render operation of any
kind was performed and `render.yaml` is unmodified. The `postgres` job's credentials are literals for
a disposable container; they are not secrets and they unlock nothing outside that job.
