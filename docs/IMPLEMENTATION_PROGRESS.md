# Implementation progress

## Delivered

- Scientific-data acquisition, file checksums, preprocessing, model registries and offline training artifacts.
- FastAPI scientific endpoints, simulation extensions, validated request models, reporting, scenario history and optimizer endpoints.
- Responsive mission-control experience, research explorer, analysis/advisor views, comparison views, 3D greenhouse and accessible fallbacks.
- Docker/Compose, CI checks, Vercel multi-service configuration and runtime scientific-data packaging.
- Documentation of architecture, API, provenance, methodology, gaps, evaluation, limitations and verification.

## Hosted runtime design

The Vercel API service packages a small checksum-verified read-only copy of the data/model assets at build time. On serverless Vercel deployments, history writes are intentionally marked read-only unless a durable database and enabled write policy are configured. Local and container deployments can enable durable scenario history through `SPACEAGRISIM_DATABASE_URL`.

## Phase 21 — production deployment verification and database reliability

- **Schema bootstrap is serialised.** On PostgreSQL the startup DDL takes a session advisory lock with
  a bounded wait and refuses to start half-migrated (`migration-lock-timeout`) instead of racing; this
  closes the class of failure behind the duplicate `pg_type` error seen earlier under concurrency.
- **Migration registry.** `MIGRATIONS` records the four additive steps with the condition that proves
  each applied; `migration_state()` inspects the live schema **without running DDL**. `/api/ready` now
  reports `databaseMigrations` and `databasePool`, and returns 503 `database_schema_incomplete` /
  `database_migration_pending` instead of `ready` when the schema is behind — the health check Render
  uses is therefore honest.
- **Diagnostics without secrets.** Slow statements are counted and logged by SQL verb and duration
  only (threshold `SPACEAGRISIM_SLOW_QUERY_MS`, default 250 ms); database failures are counted by
  class (`connect`, `pool-timeout`, `integrity`, `configuration`, `other`), including unhandled
  exceptions classified in the request middleware and re-raised unchanged. `/api/metrics` exposes
  them per process.
- **Smoke test.** `scripts/production_smoke.py` — 23 checks over the public API (readiness and
  migration count, accounts and sessions, scenario create/read/update/re-read/list, ownership
  enforcement from a second account, saved-analysis round trip, delete, cleanup limited to `SMOKE-`
  rows). One stable probe account is reused so runs do not accumulate undeletable user rows. Local
  PostgreSQL run: **23 passed, 0 failed** twice, with no rows left behind.
- **Backup reality.** Render's Free compute plan provides no backups and no PITR; the database is
  dashboard-created and absent from `render.yaml`. Documented in
  `docs/DATABASE_BACKUP_AND_RECOVERY.md`, together with a manual dump/restore procedure and an
  **executed** restore drill (`scripts/restore_drill.sh`: 3 users / 1 scenario restored into a
  separate database with identical counts, then the API answered `ready` against it, logged the
  account in, and listed the restored scenario).
- **Tests.** 20 new tests in `backend/tests/test_multi_worker_readiness.py` (advisory lock refusal and
  release, eight concurrent workers producing one schema, registry integrity, empty-database
  inspection staying read-only, repeatable non-destructive schema application, SQLite pool honesty,
  PostgreSQL pool capacity, slow-statement logging without text or parameters, failure
  classification, readiness 503 paths). Suite: **768 passed / 23 skipped** (SQLite), **791 passed**
  (PostgreSQL); 81 e2e passed; lint/typecheck/build clean.
- **Production verification.** After the push (`68aaead..62daaf6`), the live API reported
  `databaseMigrations {applied: 4, total: 4, pending: 0}` and `databasePool {capacity: 10,
  exhausted: false}`; `scripts/production_smoke.py` passed **23/23 twice** against
  `https://spaceagrisim-api.onrender.com` and left no scenarios or analyses behind; `/api/health`,
  `/api/metrics` and the static site all answered. CI run on `62daaf6` succeeded.
- **Observed discrepancy.** `render.yaml` still says `autoDeployTrigger: 'off'` while the live
  service is serving the new build; the file and the dashboard setting disagree and should be
  reconciled.
- **Not done, deliberately.** Worker count unchanged (still `--workers 1`): the in-process rate
  limiter is the next blocker, not the database. Backups not enabled (needs a paid plan). Deployment
  after the push is a manual Render dashboard action because `autoDeployTrigger` is `off`.

## Phase 20 — scientific audit, correction and independent validation

- **Audit.** Every model inspected for mathematics, assumptions, units, data, algorithm, limitations
  and existing validation; findings and verdicts in `docs/SCIENTIFIC_AUDIT.md`. Criteria and split
  rules were written down before measurement in `docs/SCIENTIFIC_VALIDATION_PLAN.md`.
- **Lettuce correction (the 232 % investigation).** Root cause: v2 had no photoperiod input (light
  dose is flux × time) and no density input (per-plant mass = per-area yield ÷ density). v3 targets
  log(fresh yield per m²), enters light as daily light integral, and serves per-plant mass through the
  stated density. Development MAPE 232.2 % → **42.7 %**, bias +246.6 g → **+2.6 g**.
- **Independent validation: failed, and reported as failed.** Touliatos et al. 2016 (untouched during
  fitting and selection) gives MAPE **41.6 %** against a 30 % criterion fixed in advance; one source
  (1000 plants/m², stacked) is refused rather than scored because the per-area identity breaks there.
  v3 stays `trained-exploratory`; the criterion was not relaxed and the holdout was not re-used.
- **Serving.** `POST /api/predict/lettuce-earth-growth-v3` takes `photoperiodHours` and
  `plantDensityPerM2`, returns the derived DLI, the per-area yield, a conformal interval, and a
  `validationStatus` block carrying the model version, both evaluation results and their verdicts.
  v2 remains callable and byte-identical. The log target is inverted through one declared
  `targetTransform` in `research.inverse_target_transform`, not per route.
- **Guard tightened.** A Moon/Mars yield question may no longer be answered with a model card: model
  passages are excluded from that premise unless they themselves state the absence. This surfaced
  because v3's name contains "fresh yield" and started winning the lexical match, turning a correct
  refusal into a partial answer.
- **Registry.** `ml/artifacts/registry.json` gains an `independentValidation` block per model;
  `scripts/verify_model_registry.py` now cross-checks it against the artifact, verifies the pass flag
  against its own criterion, and fails if a failed evaluation carries a validated-style status.
  `docs/DATASET_REGISTRY.md` is generated from the data files by `scripts/generate_dataset_registry.py`.
- **Tests.** 36 new scientific tests in `backend/tests/test_lettuce_v3_scientific.py` (DLI derivation,
  density identity and mass conservation across densities, refusal above 200 plants/m², exact-once log
  inversion, artifact checksum and provenance, prediction reproducibility against the published
  development values, criterion immutability, input validation). Suite: **734 passed, 1 skipped**.

## Phase 20 — PostgreSQL persistence audit

- **Audit.** Every persisted resource mapped to its table and route; in-memory state in production
  paths enumerated and classified. `docs/DATABASE_PERSISTENCE_AUDIT.md`.
- **Defects fixed.** Scenario read/update/delete did not exist (added, owner-scoped, share links
  deleted with their scenario); retention trimmed history across *all* accounts (now per-owner);
  `owner_id` had no index on migrated databases (`CREATE INDEX IF NOT EXISTS`); engine construction
  raced under concurrency and duplicated `create_all` (now serialised); `/api/ready` reported a
  reachable-but-unmigrated database as available (now inspects the seven required tables and returns
  503 `schema-incomplete`).
- **Tests.** 19 PostgreSQL tests on a real server in a throwaway schema, including the
  restart-equivalent test that disposes the engine, reconnects on a different server backend and
  reads the rows back. 15 API-level persistence tests run on every suite. CI gained a `postgres`
  job with a `postgres:16-alpine` service; it fails if any persistence test skips.
- **Results.** 751 passed / 20 skipped (SQLite default), 771 passed (PostgreSQL), 81 e2e passed.
  `docs/DATABASE_PERSISTENCE_TEST_REPORT.md`.

## Follow-up work

- Features without a dataset dropped from the UI rather than shown with a caveat: the gravity and
  radiation dose-rate sliders are gone from the simulation form, and the water-recovery control is
  capped at the measured ISS 98 %.
- Closed-loop measurements added: `GET /api/closed-loop` serves NASA's measured ethylene
  production and lettuce dose response (Wheeler et al. 1996) and the ISS 98 % water recovery figure;
  transcribed in `data/literature/nasa_air_and_water.json`. Ethylene stays out of the growth
  equations by design and a test enforces that.
- Obtain sufficiently large, compatible mission and ground yield datasets before recalibrating the simulator.
  For the lettuce model specifically, `docs/DATASET_GAP_ANALYSIS.md` now states the acquisition
  requirements as acceptance criteria: per-observation rows with root-zone temperature, at least two
  labelled cultivars and three light levels each, including one below ~350 µmol m⁻² s⁻¹.
- Add calibrated uncertainty before any model leaves exploratory status.
- Close the external-validation gap the check exposed: the served lettuce model has no cultivar
  input and no non-monotonic light response, so no amount of recalibration will fit the PeerJ
  observations. A replacement would need both features before it could be scored again.
- External validation of the lettuce model: **attempted and failed**. Wicharuck et al. 2024 (PeerJ
  12:e17085, CC BY 4.0) was transcribed verbatim into
  `data/literature/external_lettuce_peerj17085.json` (six observations: two cultivars × three
  canopy levels, fresh weight at 28 DAT, source SHA-256 recorded) and served at
  `GET /api/external-validation` with predictions computed live rather than stored. The model
  overpredicts every observation, by ×1.67 to ×5.38, with a median of ×3.21 and a mean absolute
  percentage error of 232 %. Probing the one unmeasured input (root temperature, 20–32 °C) moves
  the median ratio only between ×2.28 and ×3.21, so the assumption does not explain the gap. The
  model stays exploratory: its R² describes interpolation within four experiments by one group and
  must not be read as transferable accuracy.
- Configure a managed database and explicit CORS policy before enabling hosted history writes.
  Live check 2026-11-09: database-backed routes were failing on the hosted instance (login 500,
  share links 503) while `/api/health` stayed green. URL aliases are now normalised and `/api/ready`
  reports a `reason` code; the remaining step is setting `SPACEAGRISIM_DATABASE_URL` on the host.
- Profile and split the large WebGL bundle further if field performance requires it.
