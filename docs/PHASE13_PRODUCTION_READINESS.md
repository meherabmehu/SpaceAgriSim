# Phase 13 — Production Readiness (without deploying)

This project was **not deployed** in Phase 13, and nothing in this document claims a deployed
system was verified. It records what would need to be true, what has been checked locally, and what
is knowingly missing.

The distinction matters because "production ready" is a claim about a running service. What exists
here is a service that fails loudly when misconfigured, bounds its own resource use, and documents
the operational steps it has not performed.

---

## 1. Configuration contract

Everything is configured through `SPACEAGRISIM_*` environment variables and validated at startup by
Pydantic; a bad value is a startup failure, not a runtime surprise.

| Variable | Required in production | Default | Notes |
|---|---|---|---|
| `SPACEAGRISIM_AUTH_SECRET` | **yes** | ephemeral per process | ≥32 chars, ≥12 distinct, not a placeholder. Startup fails if absent in production. |
| `SPACEAGRISIM_AUTH_SECRET_PREVIOUS` | no | unset | Rotation window; remove after the longest token lifetime. |
| `SPACEAGRISIM_ENVIRONMENT` | no | `production` when `VERCEL` is set, else `development` | Selects the strict settings. |
| `SPACEAGRISIM_CORS_ORIGINS` | no | localhost dev origins | Explicit origins only; wildcards rejected; non-local must be HTTPS. |
| `SPACEAGRISIM_DATABASE_URL` | recommended | SQLite under `/tmp` on Vercel | Must be `sqlite:///` or `postgresql+psycopg://`. |
| `SPACEAGRISIM_AUTH_TOKEN_MINUTES` | no | 60 | 5–1440. |
| `SPACEAGRISIM_MAX_ANALYSES_PER_USER` | no | 200 | Enforced in-transaction. |
| `SPACEAGRISIM_MAX_ANALYSIS_BYTES_PER_USER` | no | 20 MB | Enforced in-transaction. |
| `SPACEAGRISIM_ANALYSIS_RETENTION_DAYS` | no | 0 (keep) | 0 disables the sweep, so enabling it is an explicit decision. |
| `SPACEAGRISIM_LLM_PROVIDER` | no | `disabled` | `disabled \| echo \| http`. Disabled is the benchmarked configuration. |
| `SPACEAGRISIM_LLM_API_KEY` | only with `http` | unset | Never logged, never returned; reported only as a boolean. |

`GET /api/ready` reports database reachability and the scientific status; `GET /api/health` is the
liveness probe; `GET /api/metrics` exposes per-process counters (documented as resetting on
deployment); `GET /api/assistant/provider` reports whether narration is configured.

## 2. Secret rotation, step by step

1. Generate a new secret: `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.
2. Set `SPACEAGRISIM_AUTH_SECRET_PREVIOUS` to the current value and `SPACEAGRISIM_AUTH_SECRET` to
   the new one, in the host's secret manager, then redeploy. Both verify; new tokens sign with the
   new secret.
3. Wait longer than `AUTH_TOKEN_MINUTES` (60 minutes by default) so every old token expires.
4. Remove `SPACEAGRISIM_AUTH_SECRET_PREVIOUS` and redeploy.

Verified by `test_rotation_window_accepts_the_previous_secret`, including the assertion that the
same token is refused once the previous secret is removed.

## 3. Data and persistence

* **Schema** is created with `metadata.create_all` on startup. There is no destructive migration in
  this project; a restart or a migration run does not drop rows, and
  `test_existing_analyses_survive_schema_initialisation` re-runs `create_all` over live data and
  asserts the rows are still present and counted.
* **Backup/restore** scripts exist (`scripts/db_backup.py`, `scripts/db_restore_verify.py`) and are
  exercised by `test_db_backup.py`.
* **Retention** is opt-in. With `analysis_retention_days > 0`, listing an account's analyses runs
  the sweep; accounts can also erase all their own analyses (`DELETE /api/analyses`).
* **Growing data**: the `revoked_tokens` table accumulates one row per logout and is never pruned.
  Known gap; the fix is a periodic delete of rows whose `expires_at` has passed.

## 4. Verification performed locally

| Gate | Result |
|---|---|
| Backend suite | 535 passed, 1 skipped |
| Model registry checksums | 40/40 |
| Model audit | 114 checks, 0 failures, 17 documented gaps |
| Assistant benchmark | 32 items, every expectation met; status accuracy 1.000 vs 0.750 at the Phase 12 commit |
| Frontend lint / typecheck / build | clean; chunks 599.5 kB (184 kB gzip) and 922.2 kB lazy (248 kB gzip) |
| Playwright | 69 tests across desktop, tablet, mobile |
| Demo | `scripts/demo_phase12.py` passes |
| API benchmark | 12 routes measured; slowest p95 19.1 ms (in-process) |

## 5. Not verified, and not claimed

1. **No deployment.** No Render, Vercel or other host was created, modified or contacted.
2. **No production load test.** The API benchmark is in-process on one sandbox CPU.
3. **No multi-worker test.** The auth-secret logic is designed for multi-process use and the quota
   lock is written for PostgreSQL row locking, but a real two-worker deployment was not run here.
4. **Rate limiting is per process**, not distributed. An edge limiter is required at scale.
5. **TLS, HSTS, security headers and compression** are the platform's responsibility and are not
   configured here.
6. **No MFA, no email verification, no password reset flow.** Passwords are Argon2-hashed and
   length-validated; the account lifecycle beyond register/login/logout is out of scope.
7. **The LLM provider has never been exercised against a real endpoint.** Its guards are tested
   against hostile fakes; its quality is unmeasured.
8. **Database tuning** (pool sizing beyond the defaults, index review at volume) has not been done.

## 6. If this were to be deployed tomorrow

1. Provision PostgreSQL, set `SPACEAGRISIM_DATABASE_URL` and `SPACEAGRISIM_AUTH_SECRET` in the
   host's secret manager.
2. Pin CORS to the real frontend origin.
3. Set `SPACEAGRISIM_ENVIRONMENT=production` and confirm the service **starts** (it will refuse to
   if the secret is missing).
4. Put a distributed rate limiter and TLS termination at the edge.
5. Run the smoke path: register, run a model, save, export, list with pagination.
6. Watch `/api/ready` and `/api/metrics` for the first hour.
7. Leave narration disabled until a real provider has been benchmarked against the same 32-item
   set; enabling it unmeasured would trade a validated answer path for an unvalidated one.
