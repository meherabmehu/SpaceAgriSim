# Phase 8 — Production Readiness

The point of this document is to be the opposite of a green checkmark. It states
what is verified, what is not, and what would have to be true before anyone calls
this platform production-ready.

---

## Verdict

**Not production-ready, and not close — but for reasons that are mostly about
credentials, data and scale, not about defects.**

The application is correct, tested, and safe to run locally or in a single-instance
research deployment. It is not a mission system, it does not claim to be, and
`/api/scientific-summary` says so in machine-readable form:
`platformMaturity: research-and-education`, `nasaEndorsed: false`,
`missionCertified: false`, `validatedModels: []`.

## Verified in this phase

| Area | Evidence |
|---|---|
| Backend correctness | **212 tests passed, 0 failed, 0 skipped** against a live PostgreSQL 17.11 cluster (UTF-8) |
| PostgreSQL round trip | Scenario write/read against a real server, not SQLite standing in for it |
| Deployment configuration | **21 / 21** checks, including live-database checks |
| Model registry | **32 / 32** checks; all six artifacts checksum-verified |
| Frontend | eslint clean, production build succeeds |
| Responsive UI | Playwright **15 / 15** across desktop, tablet and mobile |
| Security boundary | Probed by attack; see `PHASE8_SECURITY_REVIEW.md` |
| Engine invariants | 6480 scenarios, 0 violations |

## Not verified — blocked, with the precise blocker

| # | Item | Blocker | What would unblock it |
|---|---|---|---|
| 1 | Production PostgreSQL | No production database credentials. Verified only against a disposable local cluster on port 55432. | A real `SPACEAGRISIM_DATABASE_URL`, ideally with a read replica to test pool behaviour under failover. |
| 2 | TLS termination and HSTS | The terminator is outside this repository. `nginx.conf` listens on :80 and delegates TLS upstream. | Access to the actual ingress configuration. |
| 3 | Multi-instance deployment | Requires a shared signing secret and a shared revocation store. With the ephemeral fallback secret, a restart invalidates every token and replica B cannot validate replica A's tokens. | A durable `SPACEAGRISIM_AUTH_SECRET` in a secret manager, plus a shared revocation table. |
| 4 | Load behaviour | No load test was run. `POST /api/optimize` at 148 ms × concurrency will saturate a single worker quickly. | A load test against a deployed instance, and a decision on worker count vs. `/optimize` rate limiting. |
| 5 | Edge rate limiting | The in-process limiter is per-worker and, behind the bundled proxy, collapses to a single shared bucket (finding F1). | Edge limiting, or a trusted-proxy configuration with a shared counter store. |
| 6 | Backups and restore | `scripts/db_backup.py` and `db_restore_verify.py` exist; a restore was not exercised against production-sized data. | A restore drill on a copy of real data. |
| 7 | Truthful science at scale | Six models, four of them NASA-derived, all `experimental` at best. Nothing is validated for operational use, and no amount of deployment work changes that. | New measurements, not new infrastructure. |

## Deployment-shape risks

**Serverless (Vercel).** `database_url` falls back to `/tmp/...` and
`history_writes_enabled` defaults to `false`. That is the right default — it
refuses to pretend ephemeral storage is durable — but it means scenario history
silently does not persist unless a real database URL is supplied. The failure is
honest rather than silent, which is the important part.

**Single-container Compose.** `nginx` → `api` with a 64 KiB body cap on both sides
and consistent timeouts (10 s connect, 60 s read). Adequate for a research demo;
not sized for concurrent optimisation workload.

**Model cache and workers.** The LRU cache is per-process. With N workers, memory
scales at N × the parsed artifact set. At current sizes (largest 425 KB on disk)
this is negligible, but it is a per-process cache and should not be assumed shared.

## What Phase 8 changed in this area

Nothing in deployment configuration. The phase deliberately did not "harden"
anything that could not be verified afterwards — adding a CSP or a proxy-header
trust rule at the end of a phase is how deployments break quietly in production,
and both would have been unverifiable here.

The only production-relevant changes are:

1. **A cache sizing bug fixed**, which removes pointless disk I/O per request.
2. **A prediction withdrawn**, which means the deployed API no longer serves a
   scientifically unsupported number.
3. **A cache-regression test** so the sizing defect cannot return unnoticed.

## Honest summary

If someone asks "can we put this in front of real users", the answer is: as a
research and education tool with a clear disclaimer, yes, on a single instance
with a real database and a durable secret. As anything that informs a life-support
decision, no — and the interface says so on every screen that produces a number.
