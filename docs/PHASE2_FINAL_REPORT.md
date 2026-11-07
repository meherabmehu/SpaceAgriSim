# Phase 2 final status report

## Completed

- Repository baseline audit, scientific inventory audit, external-source policy and harmonization specification.
- Official OSD-895 NASA OSDR metadata acquisition: archive checksum, safe extraction, 19-row normalized biomass-summary preview and runtime packaging.
- Model-registry transparency: artifact hash, observed domain, evidence status and baseline comparison are exposed without executable artifact internals.
- Existing model reassessment: mizuna is `baseline-only`; tomato molecular context and Earth-only lettuce remain `experimental`.
- Scientific simulation invariants for water accounting, recovery bounds, VPD behavior and finite/non-negative public outputs.
- Workspace module lazy loading, reducing the main minified JavaScript bundle to 606.11 kB.
- Full backend/frontend/browser/security/configuration verification documented below.

## Verification evidence

| Item | Result |
| --- | --- |
| Backend test suite | 97 passed |
| Frontend lint / typecheck / build | passed |
| Browser workflows | 15 passed: 5 desktop, 5 tablet, 5 mobile |
| Python dependency audit | no known vulnerabilities |
| npm audit | 0 known vulnerabilities |
| Docker Compose schema | passed |
| Vercel branch preview | ready endpoint, OSD-895 registry query and model registry returned HTTP 200 |

## Production status

The Vercel preview built from commit `61b78b0` is live and its serverless API loads verified model assets and OSD-895 metadata successfully. In the serverless configuration, scenario history is intentionally read-only unless a durable database is configured.

## Explicit constraints, not completed claims

- No managed PostgreSQL resource was provisioned: this requires an external database/account choice and production connection secret. The code already supports `SPACEAGRISIM_DATABASE_URL` and migrations, but durable hosted persistence is not enabled without that configuration.
- No verified public real-time plant telemetry source was found; see `PHASE2_TELEMETRY_STATUS.md`.
- No new ML artifact was trained because the newly reviewed NASA data do not provide a defensible, independent general-purpose target table.
- Moon/Mars growth, radiation response, water recovery, gas exchange and mission safety remain assumption-driven or unsupported rather than claimed as validated predictions.

## Handoff

All Phase 2 changes are pushed on `feat/phase2-scientific-validation`. Merge into `main` is intentionally left to the repository workflow.
