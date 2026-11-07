# Production deployment verification

Verified on 2026-11-07 against the Vercel preview for commit `234de0d194b476ac3152cae86fff116d2e68f058` on `feat/phase3-production-ml`.

| Item | Observed result |
| --- | --- |
| Deployment | `READY`, Vercel LAMBDAS, region `iad1` |
| Preview URL | `https://space-agri-hccnizqzo-meherabmehus-projects.vercel.app` |
| `GET /api/ready` | 200; simulation available, SQLite database reachable |
| `GET /api/datasets` | 200; scientific registry returned |
| `GET /api/models` | 200; all three artifact-backed model records returned |
| `GET /api/scenarios` | 200; shared history endpoint returned an empty list |
| `POST /api/simulate`, `/compare`, `/optimize` | 200 in the same FastAPI application through an isolated local request smoke test |

The preview's readiness response reports `databaseDialect: sqlite`. On Vercel this is intentionally an ephemeral, read-only history deployment; it is **not** durable PostgreSQL and scenario writes remain disabled. A durable deployment requires the PostgreSQL configuration and operator runbook in `POSTGRESQL_OPERATIONS.md`.

The Vercel fetch mechanism is GET-only, so the three POST route results above are application-level smoke checks rather than authenticated remote POST checks. Browser workflows passed against the local integrated frontend/API test server. This preview has not been promoted to the production `main` deployment.
