# Phase 35 — Security audit

Audit, not redesign. Every control below was read in the source and exercised by the existing
suites; the two suites ran green on this branch (SQLite 1 235 passed / 24 skipped, PostgreSQL 17.11
1 259 passed / 0 skipped). Nothing in this phase weakened a control, and no control was added that
would change the API contract.

## Controls verified

| Area | Implementation | Evidence |
|---|---|---|
| Password storage | Argon2 via `argon2.PasswordHasher` (`backend/app/auth.py`) | `test_auth.py`, `test_phase13_security.py` |
| Token authentication | signed JWT, `jti` checked against a revocation table on every request (`auth.py:93`) | revocation and expiry tests |
| Token revocation | `storage.token_is_revoked` + admin revocation list (`routes/admin.py`) | covered by auth tests |
| Share links | per-scenario cap, expiry, wholesale revoke (`routes/workspace.py`) | `test_phase12_*`, PG persistence suite |
| Ownership / authorisation | every scenario and analysis read, write and delete is scoped to the caller's id | SQLite and PG suites, including `test_ownership_is_enforced_on_read_update_and_delete` |
| Rate limiting | per-address per-minute budgets, separate buckets for auth and general traffic (`backend/app/middleware.py`) | security tests; budget raised **only** in the Playwright web server via env var, so the guard stays live in production |
| Proxy handling | `trusted_proxy_hops` defaults to **0**; a caller-supplied `X-Forwarded-For` is ignored unless an operator opts in | documented in the middleware docstring and default |
| Secret handling | ephemeral per-process secret when `SPACEAGRISIM_AUTH_SECRET` is unset, with a startup warning; low-entropy and placeholder values rejected by `_validate_auth_secret` | settings module, startup log |
| CORS | explicit `allow_origins` from settings, not `*` | `backend/app/main.py:65` |
| Security headers | `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`, `permissions-policy` denying geolocation/microphone/camera, `x-request-id` on every response; `cache-control: no-store` on auth and scenario responses | `middleware.py:110-118` |
| SQL injection | SQLAlchemy Core/ORM with bound parameters throughout; no string-built SQL in the application layer | code read; PG suite exercises the same statements |
| Error disclosure | database exceptions classified, logged with a request id, and re-raised without leaking credentials; a connection failure is reported without echoing the DSN | `test_postgresql_persistence.py::test_connection_failure_is_reported_without_leaking_credentials` |
| Request size / validation | Pydantic models with bounded fields on every write route; unknown transcriptomic features rejected with 422 | `test_auth.py`, radiation 422 tests |
| Workers | `--workers 1` in `render.yaml` and the `Dockerfile`, because the rate limiter and the SQLite path are in-process | configuration read, not changed |

## Findings

**No new vulnerability was found in application code this phase.** Two things are worth recording
because they are the security-relevant consequences of this phase's own work:

1. **The evidence verdict is now part of the API contract.** A caller that ignores it is not exposed
   to anything — it is additive — but the contract tests assert it is present on every prediction
   route, so a future handler cannot silently drop it. That is a correctness property with a
   disclosure consequence: a number without its verdict would be a misleading number.
2. **No secret, token or DSN appears in any file committed this phase.** The SQLite/PG test URLs used
   `postgres:pgpass@127.0.0.1` on a throwaway local cluster; no production credential was read,
   written or echoed, and no `.env` file was created.

## Deliberate non-changes

* **No new dependency.** Nothing was added to either the front-end or the back-end dependency tree,
  so the supply-chain surface is unchanged. In particular no accessibility rule engine was added —
  the Phase 35 accessibility checks are hand-written assertions instead.
* **No Content-Security-Policy was added.** The application serves a static bundle and a JSON API;
  a CSP that is tight enough to matter would need a nonce pipeline through Vite, which is a
  build-system change this phase did not need to make. Recorded as a known hardening opportunity
  rather than as a fix.
* **No rate-limit storage change.** Moving to a shared store (Redis) would be the prerequisite for
  more than one worker; until that exists, one worker is the correct configuration and the
  deployment keeps it.
