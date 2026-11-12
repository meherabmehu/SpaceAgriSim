# Deployment and operations

The repository provides a Docker demonstration stack and a Render API Blueprint. Frontend and API builds remain independent. Deployment is not proof of scientific validity; consult the model limitations and evaluation documents.

## Local containers

From the repository root:

```sh
docker compose up --build -d
docker compose ps
curl http://localhost:8080/api/health
curl http://localhost:8080/api/ready
```

Open `http://localhost:8080`. nginx serves the production Vite build and forwards `/api/` to the FastAPI service. The API image runs as an unprivileged user with one uvicorn worker and graceful termination. A named volume retains SQLite scenarios across container replacement. `docker compose down` retains this volume; do not use `--volumes` unless intentional deletion is desired.

Docker copies tracked registry/processed/model artifacts. Raw research downloads and local secrets are excluded. Run acquisition/training outside the image and commit only selected small, licensed reproducibility artifacts. Large future models/data need immutable versioned object-storage downloads and checksum verification before readiness; no such external artifact store is assumed provisioned.

## Vercel frontend and Render API

1. Promote reviewed commits to `main` through normal review. Use a feature-branch Vercel preview for pre-merge verification; the root `vercel.py` deploys the Vite frontend and FastAPI service together.
2. Create a Render Blueprint from the repository using `render.yaml`. Its API uses the repository root so `data/` and `ml/` resolve beside `backend/`.
3. Supply `SPACEAGRISIM_DATABASE_URL` using PostgreSQL with a `postgresql+psycopg://` URL, `SPACEAGRISIM_AUTH_SECRET` as a unique 32+-character secret, and `SPACEAGRISIM_CORS_ORIGINS` as a JSON list of exact frontend origins. Set values through the hosting secret UI, never Git.
4. Create a Vercel Vite project with root directory `frontend`, install command `npm ci`, build command `npm run build`, output `dist`, and build-time variable `VITE_API_BASE_URL=https://YOUR-API.onrender.com/api`.
5. Redeploy the API after setting the exact resulting Vercel origin in CORS. Add explicitly chosen preview origins when needed; do not use wildcard credentialed origins.
6. Check API health/readiness, actual simulation responses, dataset registry, model loading, scenario save/read and all report formats from the deployed frontend. Verify desktop and mobile operation.

The Blueprint selects a free web-service compute plan for a constrained demonstration and disables automatic deployment. It does not create a paid database, disk, worker or object store. Supply an existing PostgreSQL service or choose infrastructure separately. Free-plan cold starts and capacity are unsuitable for an operational mission system. Training must run separately from hosting inference.

`.python-version` selects the latest supported Python 3.12 patch on Render, consistent with CI and the Docker base minor version. This follows the [documented version-file behavior](https://render.com/docs/python-version); freeze a tested patch/image digest when preparing an immutable release.

The Blueprint can be structurally checked against [Render's public schema](https://render.com/schema/render.yaml.py), and platform-aware validation uses:

```sh
render blueprints validate render.yaml
```

The [Blueprint setup page](https://dashboard.render.com/blueprint/new?repo=https://github.com/meherabmehu/SpaceAgriSim) reads remote source. Select the branch containing this file; ensure it is pushed before applying. The active Render workspace must be confirmed before creating resources. `sync: false` prompts only during initial setup; later changes require explicit environment updates. These semantics were checked against the [current Blueprint reference](https://render.com/docs/blueprint-spec) and [environment guide](https://render.com/docs/configure-environment-variables) on 2026-11-06.

## Environment

| Variable | Purpose |
| --- | --- |
| `SPACEAGRISIM_DATABASE_URL` | SQLite locally or PostgreSQL through SQLAlchemy/psycopg |
| `SPACEAGRISIM_AUTH_SECRET` | High-entropy signing secret for expiring account bearer tokens; required to be stable in hosted deployments |
| `SPACEAGRISIM_AUTH_TOKEN_MINUTES` | Token lifetime; default 60 minutes |
| `SPACEAGRISIM_CORS_ORIGINS` | JSON array of permitted browser origins |
| `SPACEAGRISIM_MAX_HISTORY` | Bounded shared history size; default 200 |
| `SPACEAGRISIM_HISTORY_WRITES_ENABLED` | Enables authenticated scenario writes; Blueprint disables writes until deployment access controls are configured |
| `VITE_API_BASE_URL` | Public API base including `/api`; compiled into frontend, not a secret |
| `VITE_BACKEND_URL` | Local Vite proxy target; default `http://127.0.0.1:8000` |
| `PORT` | Container/Render listener; bind `0.0.0.0` |

Keep `.env` files, database credentials, provider tokens and raw secret output outside version control. Browser `VITE_*` values are public by definition.

## Production safeguards still required

The current app is a research demonstration with private account scenario history. `SPACEAGRISIM_HISTORY_WRITES_ENABLED=false` returns 403 for scenario creation; this is the Blueprint default. Scenario read/write endpoints require an authenticated bearer token and are filtered by owner. Local development generates an ephemeral signing secret if none is supplied; hosted deployments must set a durable secret through the provider UI. Before using it as a public multi-user service, add email verification/password-reset operations, write quotas and gateway rate limits, backup/restore procedures, retention controls, resource monitoring and load testing. Provision PostgreSQL and its initial migration with a separate migration identity where possible. Do not depend on ephemeral host SQLite or serverless filesystem writes for durable scenarios. CORS does not prevent non-browser API calls.

The API request guard caps bodies at 64 KiB and uses per-process, per-client rolling limits of 180 general requests/minute and 12 optimization requests/minute. It adds request IDs and logs method/path/status/duration without logging request bodies or secrets. These in-memory limits reset on restart, do not coordinate between workers or instances, and can aggregate clients behind a proxy. Configure trusted proxy handling deliberately and add a distributed gateway limit for public production. A 429 response has a `Retry-After` header; the limits do not supply authentication or tenant isolation.

Use CI to gate backend tests, frontend lint/type checking/build, dependency audits and Playwright browser checks before promotion. Runtime dependency ranges are constrained but not a fully hashed lockfile; release engineering should freeze a tested environment and publish its software inventory. Avoid training and heavy downloads during service startup. The ordinary simulation and optimization are bounded by request schema limits; monitor real resource use before increasing them.

## Rollback

Record the Git commit, dataset manifest checksum, model version and provider deployment ID for every release. Keep the preceding tested image/build. Roll back the frontend and API together when their contracts change. In Render, redeploy the preceding known-good commit; in Vercel, promote the preceding tested deployment. Restore database backups only after assessing whether a schema change requires reversal; do not drop scenario tables as a rollback step. Recheck readiness, default simulation, saved history and exports after rollback.

## Verification status

Configuration files are reviewable source; they do not by themselves prove a live deployment. The Vercel branch-preview results and API smoke checks are recorded in `PRODUCTION_DEPLOYMENT_VERIFICATION.md`. Render connectivity exists, but no target workspace was selected/confirmed and no new paid resources were provisioned. Actual validation and deployment outcomes are recorded in `TEST_REPORT.md`, `IMPLEMENTATION_PROGRESS.md`, and the phase reports as work completes.

The Render Blueprint passed validation against the downloaded public JSON schema (zero errors), and `docker compose config --quiet` passed. The Render CLI is not installed, so platform-aware Blueprint validation was not executed. Docker Desktop's Linux daemon was unavailable (`dockerDesktopLinuxEngine` pipe absent), so container build/start was not executed. These are verification limits, not application pass results.
