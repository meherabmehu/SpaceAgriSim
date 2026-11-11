# API documentation

Run from `backend`: `python -m uvicorn app.main:app --reload --port 8000`. Interactive OpenAPI: `/api/docs`; machine schema `/api/openapi.json`.

## Scientific inputs

All scientific POST operations below accept the same `SimulationRequest`: crop (`lettuce`, `tomato`, `radish`), gravity, radiation, waterAvailability, lightHours, co2Level, simulationDays, growingArea, earthComparisonMode (`matched` or `baseline`), lightIntensity, temperature, humidity, waterRecyclingEfficiency and lightSpectrum (`balanced`, `red-blue`, `white`). `GET /api/config` is the authoritative numeric range/default/unit contract. Unknown fields, non-finite numbers, invalid crops and bounds are rejected with HTTP 422 and a per-field error map. Spectrum is an annotation, not a calibrated response.

| Endpoint | Actual behavior |
| --- | --- |
| GET `/api/health` | Process liveness |
| GET `/api/ready` | Database connectivity and simulator availability; HTTP 503 on database failure |
| GET `/api/config` | Parameter bounds, defaults, crops, assumptions and model status |
| GET `/api/crops` | Assumed crop baselines |
| GET `/api/assumptions` | Original formula descriptions and constants |
| POST `/api/simulate` | Full daily growth, water, gas data; standing/harvested distinction, Earth comparison, provenance and warnings |
| POST `/api/compare` | `scenarios: [{name,result}]` for Earth, Moon, Mars and custom habitat, plus limitations |
| POST `/api/advisor` | `insights: [{title,severity,text,source}]`, underlying result and limitations; deterministic numerical explanations |
| POST `/api/optimize` | 81-candidate Pareto frontier, baseline, recommendation, sensitivity, explicit constraints and limitations |
| GET `/api/scenarios` | Newest shared saved configurations, bounded by `SPACEAGRISIM_MAX_HISTORY` |
| POST `/api/scenarios` | `{name,configuration}`; stores validated config, timestamp and model version; HTTP 201 |
| GET `/api/scenarios/{id}` | One saved scenario, owner-scoped. 404 for another account's id rather than 403, so the API is not an existence oracle |
| PATCH `/api/scenarios/{id}` | Rename and/or replace the configuration of one owned scenario. A partial update keeps the field it was not given |
| DELETE `/api/scenarios/{id}` | Delete one owned scenario and every share link that pointed at it, in the same transaction. 204, or 404 when the id is not the caller's |
| POST `/api/reports/json` | Reproducible simulation output and configuration as JSON attachment |
| POST `/api/reports/csv` | Configuration/comment rows then daily growth, supplied/recovered water and gases with units |
| POST `/api/reports/pdf` | Actual generated PDF with configuration, outputs, method and limitations |

Dataset/model registry routes are documented by the research pipeline and live OpenAPI. Scientific inference training never runs inside a request.

Example:

```sh
curl -X POST http://localhost:8000/api/simulate -H 'Content-Type: application/json' -d '{"crop":"lettuce","simulationDays":35,"gravity":0.38,"temperature":22,"waterRecyclingEfficiency":90}'
```

The simulator response retains all original chart fields. Added fields: `provenance` (mode/version/validation/uncertainty), `warnings`, `stress` (factor deficits, not measured health classes), and `environment` (VPD, daily light integral and spectrum annotation). There is no empirical confidence interval for mathematical outputs.

Set `SPACEAGRISIM_HISTORY_WRITES_ENABLED=false` to reject shared history saves with HTTP 403 on public deployments. This is an operator write gate, not user authentication.

History is a shared demonstration workspace with bounded retention, not a private per-user account system. PostgreSQL deployment and initial schema are described in `backend/migrations/README.md`. This API contains no secrets and must not receive sensitive user data. The API caps request bodies at 64 KiB and uses per-process IP limits of 180 requests/minute (12/minute for optimization). HTTP 429 includes Retry-After. These limits are local to each worker; distributed edge limits remain appropriate for scaled deployments. Request IDs and method/path/status/duration are logged without scientific payloads or credentials. Optimization is intentionally a bounded 81-point grid. CORS origins are configured by `SPACEAGRISIM_CORS_ORIGINS`; no wildcard credential mode is used.

## Phase 19: accounts, sharing, benchmarks and operator routes

These are the routes added for the competitive build. All of them are also in `/api/openapi.json`;
this table adds what a schema cannot say — the refusal behaviour and what each number means.

| Endpoint | Behaviour |
| --- | --- |
| POST `/api/auth/register` | Creates an account; emails a verification token when SMTP is configured, otherwise writes a development outbox entry (non-production) or returns 503 with an explicit message (production) |
| POST `/api/auth/verify/confirm` | Consumes a verification token; single use, expires |
| POST `/api/auth/verify/request` | Re-sends verification; rate-limited per identity |
| POST `/api/auth/login` | Issues a session token; failed attempts are counted per identity and reported through `/api/auth/activity` |
| POST `/api/auth/password/forgot` | Always answers the same way whether or not the address exists — the response is not an account oracle |
| POST `/api/auth/password/reset` | Consumes a reset token and **invalidates every existing session for that account** |
| GET `/api/auth/me` | The calling account; 401 for a missing, expired or revoked session, and for the operator token, which is not an account |
| GET `/api/auth/activity` | The caller's own recent authentication events |
| POST `/api/auth/logout` | Revokes the presented session |
| POST `/api/scenarios/{id}/share` | Mints a share token for an owned scenario, bounded by `SPACEAGRISIM_MAX_SHARE_LINKS_PER_SCENARIO` |
| DELETE `/api/scenarios/{id}/share` | Revokes share tokens for that scenario |
| GET `/api/shared/{token}` | Public, read-only view of a shared scenario. Re-runs the stored configuration against the current model, so a shared page always shows what the model produces now, not a frozen result |
| GET `/api/benchmarks` | Measured-versus-modelled numbers from pinned artifacts: the closed-chamber comparison, the NASA leafy anchor, and the CO₂ response factor with its measured optimum |
| GET `/api/closed-loop` | Measured closed-loop numbers: ethylene production per crop and the lettuce dry-weight dose response from NASA's Biomass Production Chamber, a no-leak accumulation bound checked against that chamber's own measurement, and the ISS water recovery figure (98 %, up from 93–94 %) that bounds the recycling control |
| GET `/api/external-validation` | Screening of independent sources for the lettuce model, the external check that was run and failed for v2, and the v3 block: development metrics (232.2 % → 42.7 % on the same six observations, computed live, explicitly not validation), the independent holdout verdict read from the artifact (41.6 % against a 30 % criterion, `passed: false`) and the refused source. Nothing here is a stored result |
| POST `/api/predict/lettuce-earth-growth-v3` | Current Earth lettuce yield. Inputs: daysAfterTransplant, airTemperature, rootTemperature, ppfd, photoperiodHours (default 16), plantDensityPerM2 (default 25). Returns per-plant prediction, per-area yield, the derived daily light integral, a conformal interval marked `calibrated: false`, the model version and the whole `validationStatus` block including the failed independent check |
| GET `/api/metrics` | Prometheus-style counters for the gateway rate limiter |
| GET `/api/datasets/live-status` | Last OSDR re-sync verdict per study, with the timestamp it was checked |
| GET `/api/ready` | Extends the original readiness payload with storage durability, email delivery mode, share-link availability, the rate-limit identity ("socket" behind a gateway means every caller shares one budget), whether the operator console is configured, and — when the database fails — a `reason` code plus the SQLSTATE when the server answered at all It also reports `databaseMigrations` (`applied`/`total`/`pending` from the read-only migration registry) and `databasePool` (size, checked out, overflow, capacity, exhausted; SQLite reports `pooled: false` rather than an invented capacity). A reachable database whose schema is behind returns **503** — `database_schema_incomplete` when no schema exists at all, `database_migration_pending` when an additive step is missing — with `pendingMigrations`, the missing objects, and a remedy. The probe never runs DDL. |
| GET `/api/admin/summary` | Operator console summary. **404 when `SPACEAGRISIM_ADMIN_TOKEN` is unset, 401 for a missing or wrong token**, compared in constant time. Account identifiers are SHA-256 prefixes, not addresses |
| GET `/api/admin/audit` | Recent activity by kind, failed logins and live share links, pseudonymised the same way |

## Phase 32: output checks, units and stated scope

These are additive. A client written before Phase 32 receives the same fields it did before, plus
the ones below.

| Endpoint / field | Behaviour |
| --- | --- |
| GET `/api/reference-et0/validate` | Reference ET0 for one day, plus `outputCheck`: `plausible`, the `failures` that made it implausible, the `rule` (`0 <= ET0 <= 30 mm/day` and `tmax >= tmin`) and `physicalCeilingMmPerDay`. The value is **never clamped** — a swapped-temperature day returns the number *and* the verdict that it is not a physical day |
| POST `/api/reference-et0/validate` | The same check for a whole day supplied as a JSON payload, so a batch read from a file can be validated. Unknown fields are rejected (422) |
| `POST /api/simulate` → `units` | A map from dotted field path to unit for every headline scalar (`cropYield`, `waterUsed`, `environment.vaporPressureDeficitKpa`, …). A unit in a field name is a convention; this is the contract |
| `POST /api/simulate` → `environment.vaporPressureDeficit` | `method`, `inputsAreAssumptions`, `propagatedError` (null) and a sentence stating that the value describes the scenario, not a place or a day |
| `POST /api/simulate` → `environment.dailyLightIntegral` | The same shape, stating that the integral is the scenario's setting rather than a measurement |
| Every prediction response | `operationalForecast: false`, `harvestForecastClaim: null` and `scopeStatement`, copied from the artifact's `servedScope`. A prediction is served under a stated scope and never as an operational forecast |
| Transcriptomic predictions | `probabilityCalibration`: whether the probabilities are calibrated (`false` for both OSD-46 classifiers), what was measured (log loss, Brier, 10-bin ECE over 22 biological groups), the scope it holds in, and `servedScaling: "none"` |
| `GET /api/models` rows | `probabilityCalibration` per model, and `servedScope` / `operationalForecast` on every served row |
