# Phase 7 — PostgreSQL Verification and Deployment Configuration

Part D asks for PostgreSQL integration on a **disposable local instance**, plus
deployment-configuration verification that does not weaken Phase 4's security
posture.

**Scope statement, first and plainly:** everything below was verified against a
throwaway local cluster. Nothing here is production verification, and this
document does not claim any. `PRODUCTION_DEPLOYMENT_VERIFICATION.md` remains the
authoritative statement about what is and is not verified in production, and its
conclusions are unchanged by Phase 7.

---

## 1. The instance that was actually used

| Property | Value |
|---|---|
| Server | PostgreSQL **17.11** (Debian 17.11-0+deb13u1), installed from apt |
| Cluster | `initdb -E UTF8 --locale=C.UTF-8`, **port 55432**, `listen_addresses=127.0.0.1` |
| Database | `spaceagrisim_test` (integration test), `spaceagrisim_test2` (deployment verification) |
| Role | `sasim` / `sasim_test`, TCP-authenticated |
| Durability | none — `/tmp` data directory, disposable by design |

No Docker was available in the environment (`docker` absent), so the cluster was
created directly rather than through a container. That is a *difference from the
documented production path*, not an improvement on it.

### The Phase 6 blocker this clears

Phase 6 ran `backend/tests/test_postgres_integration.py` and **skipped** it, because
no PostgreSQL instance was reachable. A skipped test proves nothing about a
database path. That is now executed for real:

```
SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://sasim:sasim_test@127.0.0.1:55432/spaceagrisim_test \
    pytest tests/test_postgres_integration.py -v
→ 1 passed
```

The test is still gated on the environment variable, so a developer without
PostgreSQL keeps the skip rather than a false failure — but the skip can no longer
be mistaken for coverage, because the result is recorded here as executed.

## 2. What was verified against the live database

`scripts/verify_deployment_config.py` runs 21 checks; it asserts nothing from
documentation and exits non-zero on any failure, so it is CI-usable.

| Group | Check | Result |
|---|---|---|
| Encoding | server encoding is UTF-8 | PASS |
| Encoding | client encoding is UTF-8 | PASS |
| Migration | `001_scenarios.sql` applies cleanly | PASS |
| Migration | creates `scenarios`, `users`, `revoked_tokens` | PASS |
| Migration | `scenarios` has all six ORM columns | PASS |
| Migration | `scenarios_owner_created_idx` exists | PASS |
| Migration | second application is a no-op (idempotent) | PASS |
| Storage | scenario write reaches PostgreSQL | PASS |
| Storage | scenario reads back through the API layer | PASS |
| Storage | `database_health()` reports dialect `postgresql` | PASS |
| Parity | every ORM column appears in the SQL migration | PASS |
| Security | 7 Phase 4 invariants (see §3) | PASS |

**21/21 passed.** Evidence artifact: `docs/phase7/deployment_verification.json`.

The idempotence check matters more than it looks: deployments re-run migrations,
and `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` are what make that
safe. The run produced only `NOTICE` lines, no errors.

## 3. Phase 4 security invariants, re-verified

Part D requires that the PostgreSQL work does not weaken earlier security. These
are asserted programmatically by loading the settings object under each
environment configuration:

| Invariant | Verified behaviour |
|---|---|
| CORS origins are explicit | `["http://localhost:5173", "http://127.0.0.1:5173"]` |
| Wildcard CORS is rejected | `["*"]` raises `ValidationError` |
| Plaintext non-local origin is rejected | `["http://example.com"]` raises `ValidationError` |
| Auth secret meets the 32-char floor | generated secret is 64 chars |
| Token lifetime is bounded | 60 minutes (range 5–1440) |
| Rate limiting is on | 30 requests/minute (range 1–60) |
| History writes off on Vercel | `False` with `VERCEL=1` |
| Vercel DB path is `/tmp` only | `sqlite:////tmp/spaceagrisim/scenarios.db` |
| Local history writes enabled | `True` |
| Local default is not a public persistent store | `sqlite:///.spaceagrisim/scenarios.db` |

The last row is the Phase 4 "no public persistent writes without a durable
database and verified authorization" rule, expressed as a test: the default local
configuration must never quietly point at a shared PostgreSQL instance.

## 3a. Cluster encoding — a defect this verification caught

Re-running the whole matrix on a **clean environment** reproduced two failures
that had not appeared during the original Phase 7 work:

```
pytest backend/tests/test_postgres_integration.py → 1 failed
TypeError: cannot use a string pattern on a bytes-like object
```

The traceback named neither the database nor the fix. The actual cause:

**The cluster had been initialised with `SQL_ASCII`**, because `initdb` ran
without an explicit encoding under an unset locale. psycopg then returns `bytes`
instead of `str` for text results, SQLAlchemy's dialect does
`re.match(pattern, value)` on that value during connection setup, and the
PostgreSQL path fails before it can execute a single statement.

| Attempted fix | Result |
|---|---|
| Downgrade SQLAlchemy to 2.0.57 / psycopg to 3.2.13 | **still failed** — version was not the cause |
| Restore SQLAlchemy 2.1.8 / psycopg 3.3.8 | fails only on `SQL_ASCII`; **passes on UTF-8** |
| Recreate cluster with `-E UTF8 --locale=C.UTF-8` | **all tests pass, 0 skipped** |

So **no dependency pin was changed** — capping library versions would have hidden
an environment defect behind a false fix. Instead:

- the verifier gained a **server/client encoding preflight** that fails with an
  actionable message and aborts before the unrelated SQLAlchemy errors;
- the guard was proven to work by creating a `SQL_ASCII` database on purpose:
  the verifier exits **1** with the diagnostic, and **0** against a UTF-8 database;
- the reproduce instructions above now carry `-E UTF8 --locale=C.UTF-8`.

**Why this matters beyond the test harness:** a production PostgreSQL cluster
created with a non-UTF-8 locale would fail exactly this way, and the error it
emits points nowhere near the cause. Any managed instance must be provisioned as
UTF-8. This is now an explicit deployment requirement rather than an assumption.

## 4. What is still not verified — and must not be described as though it were

| Item | Status | Why |
|---|---|---|
| Production PostgreSQL | **not verified** | No production database or credentials exist in this environment |
| Connection pooling under load | **not verified** | Pool settings (`size=5`, `max_overflow=5`) are configuration, not measurements; no load test was run |
| Multi-instance token revocation | **not verified** | `revoked_tokens` is created and the table exists, but cross-instance behaviour needs more than one instance |
| Backup/restore on real data | **not verified** | `test_db_backup.py` covers the local path only |
| Managed-host migration path | **not verified** | Requires the host's console |
| Managed-host cluster encoding | **not verified** | Must be provisioned UTF-8; see §3a. Not checkable without the host |
| TLS to the database | **not verified** | The local cluster used `trust` authentication on loopback; production must use TLS and this run says nothing about it |

`trust` authentication over loopback is appropriate for a disposable test cluster
and would be a serious defect in production. It is called out here so the test
harness is not mistaken for a deployment template.

## 5. Reproducing this

```bash
sudo -u postgres mkdir -p /tmp/pgdata /tmp/pgrun
# -E UTF8 is REQUIRED, not cosmetic. See "Cluster encoding" below.
sudo -u postgres /usr/lib/postgresql/17/bin/initdb -D /tmp/pgdata -A trust \
    -E UTF8 --locale=C.UTF-8
sudo -u postgres /usr/lib/postgresql/17/bin/pg_ctl -D /tmp/pgdata \
    -o "-p 55432 -k /tmp/pgrun -c listen_addresses=127.0.0.1" -l /tmp/pg.log start
psql -h 127.0.0.1 -p 55432 -U postgres -c \
    "CREATE ROLE sasim LOGIN PASSWORD 'sasim_test'; CREATE DATABASE spaceagrisim_test OWNER sasim; CREATE DATABASE spaceagrisim_test2 OWNER sasim;"

export SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://sasim:sasim_test@127.0.0.1:55432/spaceagrisim_test
python -m pytest backend/tests/test_postgres_integration.py

export SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://sasim:sasim_test@127.0.0.1:55432/spaceagrisim_test2
python scripts/verify_deployment_config.py
```

Shutting the cluster down (`pg_ctl stop`) leaves no trace outside `/tmp`; no
project file references the test DSN, and none may be committed.
