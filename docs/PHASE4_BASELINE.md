# Phase 4 baseline

Established on 2026-11-07 from `main` commit `4ceba2ac34b2228dfd32e672133f8434bd39b21a`.

| Check | Result |
| --- | --- |
| Backend tests | 97 passed, 1 skipped optional PostgreSQL integration test |
| Frontend checks | Must be run from `frontend/`; root has no `package.json` |
| Existing persistence | SQLAlchemy SQLite/PostgreSQL URL guard, pooled pre-ping and readiness check; scenarios are shared and unauthenticated |
| Existing request guard | In-process body size limit, general/optimization rate limits and request ID logging |
| Hosting posture | Vercel preview uses ephemeral SQLite with history writes disabled; no managed PostgreSQL credential has been supplied |

Phase 4 changes must preserve the public scientific explorer and simulation routes while making account and scenario data private.
