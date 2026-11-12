# Production Readiness — Phase 6

Assessed 2026-11-07. This document separates what is **verified working**, what
is **blocked by infrastructure**, and what is **deliberately not enabled**.

---

## 1. Security posture (Phase 4, preserved and re-verified)

| Control | Status | Evidence |
|---|---|---|
| Argon2id password hashing | ✅ Present | `backend/app/auth.py`; `test_auth.py` |
| Signed, expiring bearer tokens | ✅ Present | `auth.py`, `settings.auth_token_minutes` |
| Server-side logout revocation | ✅ Present | `auth.py`, `test_auth.py` |
| Account-scoped scenario history | ✅ Present | `routes/workspace.py`, `test_workspace.py` |
| Strict CORS (wildcards rejected) | ✅ Present | `settings.explicit_cors_origins` validator |
| Request-size limits | ✅ Present | `middleware.py::RequestGuard` |
| Auth rate limiting | ✅ Present | `middleware.py`, `settings.auth_rate_limit_per_minute` |
| Security response headers | ✅ Present | `middleware.py` |
| Sanitised errors | ✅ Present | `routes/errors.py` |
| Privacy-safe audit logging | ✅ Present | `observability.py` |
| `/api/metrics` | ✅ Present | `routes/health.py` |

**No Phase 4 control was weakened.** All 169 backend tests pass, including the
authentication and cross-user isolation suites.

> One operational caveat that must be resolved by the owner before multi-instance
> deployment: `auth_secret` falls back to an ephemeral random value when
> `SPACEAGRISIM_AUTH_SECRET` is unset. That is correct for local development but
> invalidates every token on restart and prevents multiple instances from
> validating each other. **Set a durable high-entropy secret.**

## 2. Database

| Item | Status | Detail |
|---|---|---|
| SQLite path | ✅ Verified | Full suite + seeded backup/restore drill |
| Schema migration script | ✅ Present | `backend/migrations/001_scenarios.sql` |
| PostgreSQL code path | ✅ Present, ⚠️ untested here | `test_postgres_integration.py` skips without `SPACEAGRISIM_TEST_POSTGRES_URL` |
| PostgreSQL integration test | ⛔ **Blocked (infra)** | No managed PostgreSQL instance or credentials were supplied |
| Backup script | ✅ **New** | `scripts/db_backup.py` — SQLite online-backup API + `pg_dump -Fc` |
| Restore verification | ✅ **New** | `scripts/db_restore_verify.py` — integrity + inventory + row counts |
| Backup/restore tests | ✅ **New** | 7 tests, incl. tamper and row-loss detection |

**Verified end-to-end on SQLite:** seed → backup (SHA-256 + manifest) → restore into
throwaway DB → integrity `ok`, inventory identical, row counts identical → exit 0.
Tampering with the file, or deleting rows and re-stamping the checksum, both fail
the drill as they must.

**Not done, by design:** production scenario writes remain gated behind
`history_writes_enabled` (false on serverless). Do not enable durable production
writes until the PostgreSQL round-trip has actually been run.

## 3. Monitoring & observability

| Item | Status | Detail |
|---|---|---|
| Structured request logs | ✅ | `observability.py` emits `request_complete` with method, path, status, elapsed_ms |
| `/api/health`, `/api/ready` | ✅ | `routes/health.py`; used as the Render health check |
| `/api/metrics` | ✅ | Counters + latency |
| API latency measurement | ✅ | `elapsed_ms` per request |
| Error tracking (third-party) | ⛔ **Blocked (infra)** | No Sentry/OTel DSN supplied; not configured rather than faked |
| Alerting configuration | ⛔ **Blocked (infra)** | Requires a monitoring provider account and a notification target |
| Retention policy | ⚠️ Documented only | Log retention must be set on the hosting provider; no code-side enforcement |

## 4. Deployment configuration

| Item | Status | Detail |
|---|---|---|
| Frontend production build | ✅ Verified | `vite build` succeeds; 58.7 kB CSS, main chunk 598 kB, 3D scene lazy-loaded at 922 kB |
| Frontend lint | ✅ Clean | `eslint .` — no findings |
| Frontend typecheck | ✅ Clean | `tsc --noEmit` |
| Root `Dockerfile` | ✅ Present | multi-stage API image |
| `docker-compose.yml` | ✅ Valid | API + nginx web, named volume for scenarios, health-gated `depends_on` |
| `vercel.py` | ✅ Present | services + `/api/*` rewrite |
| `render.yaml` | ✅ Present | API web service, `/api/ready` health check, `autoDeployTrigger` (was `off` here; corrected to `commit` in Phase 22 to match the dashboard) |
| **Phase 6 evidence in runtime bundle** | ✅ **Fixed** | `package_runtime_data.py` now packages `docs/phase6/*.py` into `scientific_data/phase6/`, so `/api/science/calibration` returns real data on serverless |

### Deployment gap found and fixed

The new Phase 6 endpoints read evidence from `docs/phase6/`. On a serverless
deploy only `backend/scientific_data/` ships, so those endpoints would have
silently degraded to `{"status": "not-run"}`. The packaging script now copies the
four Phase 6 artifacts into the bundle and fails loudly if they are missing. All
are < 214 kB (largest: `simulation_calibration`, 213 kB), within the
existing 2 MB per-asset guard. Verified by loading the app against the bundle only.

## 5. Test status — actual results from this run

| Suite | Result |
|---|---|
| Backend `pytest` | **169 passed, 1 skipped** |
| PostgreSQL integration | 1 skipped (no DSN) |
| Frontend `eslint` | clean |
| Frontend `tsc --noEmit` | clean |
| Frontend `vite build` | success |
| Playwright desktop (1440×1100) | 5 passed |
| Playwright tablet (820×1180) | 5 passed |
| Playwright mobile (Pixel 7) | 5 passed |
| **Playwright total** | **15 passed** |
| Scientific invariants (pytest) | 55 passed |
| Simulation sweep invariants | 1,170 checks, all pass |
| Dataset integrity | 28 + 5 files, all SHA-256 verified |

## 6. Blockers requiring operator action

| # | Blocker | Type | Required action |
|---|---|---|---|
| 1 | No managed PostgreSQL | infra | Provision a database; set `SPACEAGRISIM_DATABASE_URL`; then run `SPACEAGRISIM_TEST_POSTGRES_URL=<dsn> pytest backend/tests/test_postgres_integration.py` |
| 2 | No durable `auth_secret` | infra | Set `SPACEAGRISIM_AUTH_SECRET` to a high-entropy value in the secret manager |
| 3 | Error tracking / alerting | infra | Choose a provider, set its DSN, configure alert routes |
| 4 | Production scenario writes | policy | Keep `history_writes_enabled=false` until blocker 1 is cleared |
| 5 | CORS origins for the deployed frontend | config | Set `SPACEAGRISIM_CORS_ORIGINS` to the exact production origin(s) — wildcards are rejected by design |
| 6 | ML environment pinning | engineering | Pin `scikit-learn` exactly before regenerating artifacts (see `docs/ML_TRAINING_REPORT.md` §2) |

## 7. Explicitly not enabled

* **No promotion to `main`.** All Phase 6 work sits on
  `feat/phase6-nasa-ai-completion`. Merging requires owner authorisation.
* **No production scenario writes.**
* **No paid infrastructure created.** No database, monitoring or storage resource
  was provisioned.
* **No model declared mission-ready.** `/api/scientific-summary` reports
  `validatedModels: []`, `nasaEndorsed: false`, `missionCertified: false`.
