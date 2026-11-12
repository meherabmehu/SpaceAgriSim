# Implementation progress

## Delivered

- Scientific-data acquisition, file checksums, preprocessing, model registries and offline training artifacts.
- FastAPI scientific endpoints, simulation extensions, validated request models, reporting, scenario history and optimizer endpoints.
- Responsive mission-control experience, research explorer, analysis/advisor views, comparison views, interactive growth chamber (SVG, since Phase 33) and accessible fallbacks.
- Docker/Compose, CI checks, Vercel multi-service configuration and runtime scientific-data packaging.
- Documentation of architecture, API, provenance, methodology, gaps, evaluation, limitations and verification.

## Phase 35 — final completion, evidence verdicts and one responsive fix

- **One evidence verdict per model, carried to every surface.** `ml/research/phase35_evidence_verdicts.py`
  derives `passes-independent-check` / `fails-independent-check` / `no-independent-check` per model
  from committed evaluation files; `decisionGrade` is true only for the first. Every prediction route
  returns it with the number, the registry cards and the status panel render it, and 34 audit checks
  plus 11 tests keep the surfaces from disagreeing. Current state: 1 decision-grade model
  (mizuna-microbial-relative-load-v2), 3 failed independent checks (lettuce v1–v3), 3 never
  independently checked (radiation ×2, tomato), 2 withdrawn.
- **The one status change is a derivation.** mizuna v2's card already carried the rule for
  `validated-exploratory`; three terms were true and the fourth — cross-campaign conformal coverage —
  was measured in Phase 34 at 0.8943 against a nominal 0.90, inside the rule's own ±5-point tolerance.
  The artifact records which file supplied the number.
- **Responsive defect fixed.** `/#benchmarks` overflowed by 83 px at tablet and 114 px at mobile
  (118-character citation in a `min-width: auto` grid track). Fixed with `min-width: 0` +
  `overflow-wrap: anywhere`; both properties measured to be necessary.
- **Visual gate widened** from 12 to 18 captures (predictions and benchmarks routes) and made
  deterministic: integer-clipped captures, parent rebuilt and captured identically first, 18/18 PASS
  at 0.000 % differing pixels.
- **Accessibility measured**: contrast (worst 4.97:1), reduced motion and a keyboard-only journey at
  three viewports, all passing on the parent as well — the properties were true and unmeasured.
- **No new dataset, no new model.** Every acquisition candidate was rejected with a reason
  (`docs/PHASE35_DATA_ACQUISITION.md`); nothing was trained because no candidate cleared the
  volume/grouping/validation bar.

## Hosted runtime design

The Vercel API service packages a small checksum-verified read-only copy of the data/model assets at build time. On serverless Vercel deployments, history writes are intentionally marked read-only unless a durable database and enabled write policy are configured. Local and container deployments can enable durable scenario history through `SPACEAGRISIM_DATABASE_URL`.

## Phase 22 — backup automation, restore validation and monitoring

- **Encrypted daily backup in CI.** `.github/workflows/db-backup.yml` dumps production with
  `pg_dump -Fc` (client 18, because pg_dump cannot dump a newer server), verifies every archive with
  `pg_restore --list`, records table names and row counts in a manifest, encrypts with GPG AES-256,
  proves the ciphertext decrypts back to the same SHA-256, and uploads **only** the ciphertext as an
  artifact (retention 14 days). Runs daily at 02:17 UTC and on `workflow_dispatch`. The connection
  string reaches libpq through a 0600 `.pgpass`; it never appears on a command line, in a manifest or
  in a log. Setup, secret names and limits: `docs/DATABASE_BACKUP_AUTOMATION.md`.
- **Restore validation.** `scripts/restore_validate.py` + `.github/workflows/db-restore-verify.yml`
  restore a backup into a throwaway `postgres:18` service container and verify schema, required
  columns/index, per-table row counts against the manifest, six ownership edges, and account rows —
  refusing production URL, production database name, remote hosts and non-empty targets first.
  **Executed offline on PostgreSQL 18.6: 17/17 checks passed**, and the application read the restored
  database correctly (schema present, 4/4 migrations, both accounts, the owner's scenario).
- **Monitoring.** `scripts/monitor_production.py` + `.github/workflows/production-monitor.yml` poll
  `/api/health`, `/api/ready` and `/api/metrics` every 30 minutes and print a remedy per failure
  (database failure classes, pool exhaustion, pending migrations, non-durable storage). `/api/metrics`
  gained `startedAt` and `uptimeSeconds` — additive, aggregate, no client data — so a crash loop is
  visible from outside. Live run against production: **12/12 checks passed**, three warnings
  (`rateLimitIdentity: socket`, `emailDelivery: unconfigured`, uptime field not yet deployed).
- **Render configuration reconciled.** The dashboard reports auto-deploy **on** with a commit trigger
  for both services; `render.yaml` said `'off'`, which would have silently disabled deploys on the
  next blueprint sync. Corrected to `autoDeployTrigger: 'commit'` for both services; see
  `docs/PRODUCTION_READINESS_AUDIT.md` §10.4. No production setting was changed from here.
- **Multi-worker safety documented, worker count unchanged.** `docs/MULTI_WORKER_RATE_LIMITING.md`
  records why `--workers 1` stands: the limiter's state is a per-process `defaultdict(deque)`, so the
  budget scales with worker count, and a shared Redis/KV store plus a fail-closed degrade path is the
  prerequisite. No Redis or paid infrastructure was added.
- **Tests.** 25 new tests in `backend/tests/test_phase22_backup_automation.py` (restore safety gates,
  manifest secrecy, libpq-mode argument handling, monitor verdicts against a real local HTTP server,
  remediation text, uptime fields). Suite: **793 passed / 23 skipped** (SQLite), **816 passed**
  (PostgreSQL **18.6**).
- **Not done, deliberately.** Nothing was pushed or deployed from here (no GitHub credential in this
  environment), so no Render deployment id changed in this phase; the workflows need two repository
  secrets before their first run.

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
- **Observed discrepancy (resolved in Phase 22).** `render.yaml` said `autoDeployTrigger: 'off'`
  while the live service was serving the new build. The dashboard reports auto-deploy on with a
  commit trigger, so the file was corrected to match.
- **Not done, deliberately.** Worker count unchanged (still `--workers 1`): the in-process rate
  limiter is the next blocker, not the database. Vendor-side backups not enabled (needs a paid
  plan); Phase 22 added an encrypted off-platform backup in CI instead.

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
- **Registry.** `ml/artifacts/registry` gains an `independentValidation` block per model;
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
  transcribed in `data/literature/nasa_air_and_water`. Ethylene stays out of the growth
  equations by design and a test enforces that.
- Obtain sufficiently large, compatible mission and ground yield datasets before recalibrating the simulator.
  For the lettuce model specifically, `docs/DATASET_GAP_ANALYSIS.md` now states the acquisition
  requirements as acceptance criteria: per-observation rows with root-zone temperature, at least two
  labelled cultivars and three light levels each, including one below ~350 µmol m⁻² s⁻¹.
- Add calibrated uncertainty before any model leaves exploratory status.
- Close the external-validation gap the check exposed: the served lettuce model has no cultivar
  input and no non-monotonic light response, so no amount of recalibration will fit the PeerJ
  observations. A replacement would need both features before it could be scored again.
- External validation of the lettuce model: **attempted, improved, still failed.** Wicharuck et al.
  2024 (PeerJ 12:e17085, CC BY 4.0) was transcribed verbatim into
  `data/literature/external_lettuce_peerj17085` (six observations: two cultivars x three
  canopy levels, fresh weight at 28 DAT, source SHA-256 recorded) and served at
  `GET /api/external-validation` with predictions computed live rather than stored. The first
  scoring, on `lettuce-earth-growth-v2`, overpredicted every observation by x1.67 to x5.38 (median
  x3.21), a mean absolute percentage error of 232 %. Phase 20 rebuilt the model as
  `lettuce-earth-growth-v3` (daily light integral, per-area target, density identity), which scores
  42.7 % MAPE with a mean bias of +2.6 g on the same six rows, and 41.6 % on the independent
  Touliatos 2016 holdout. That is a large improvement and still a failure against the pre-registered
  30 % criterion, so the model stays `trained-exploratory`. Its R2 describes interpolation within
  four experiments by one group and must not be read as transferable accuracy.
- **Managed database: configured and verified.** A live check on 2026-11-09 found database-backed
  routes failing on the hosted instance (login 500, share links 503) while `/api/health` stayed
  green. URL aliases are now normalised, `/api/ready` reports a `reason` code, and
  `SPACEAGRISIM_DATABASE_URL` is set on the host. Re-verified after the Phase 21 deploy:
  `/api/ready` reports `databaseDialect postgresql`, `databaseSchema present`,
  `databaseMigrations {applied: 4, total: 4, pending: 0}` and `storage.durable true`, and
  `scripts/production_smoke.py` passes 23/23 against the live API. What remains is operational, not
  code: no automated backup or point-in-time recovery exists on the current plan (see
  `docs/DATABASE_BACKUP_AND_RECOVERY.md`).
- Profile and split the large WebGL bundle further if field performance requires it.
