# Phase 32 — final report

**Zero-actionable-gap finalization, scientific integrity, complete feature cleanup and
production-ready verification.**

| | |
| --- | --- |
| Repository | `meherabmehu/SpaceAgriSim` |
| Branch | `phase32/finalization`, based on verified `main` at `3bb675441535a8d3e1638f94f777105325a750a3` |
| Phase 32 commits | `d0e74a5`, `dd35581`, `0d31388` (working tree contains the documentation set this file belongs to) |
| Delivery SHA | `a00b32dbeba4269045ef28a153e2f7e53f618b53` (fast-forward into `main`, pushed and verified with `git ls-remote`) |
| Final SHA | recorded in `docs/PHASE32_DELIVERY.txt` — the commit that pins the record |
| Production deploy | **not performed by this phase.** No Render resources, settings, environment variables, migrations, workers or paid plans were touched |

The report separates five things that a single "done" would blur: **code completeness**,
**scientific validation**, **model serving eligibility**, **user-facing completeness** and
**production deployment status**. A phase can be complete on the first and fourth and still have
open scientific limitations; that is the honest shape of this one.

---

## 1. What was actually verified before anything was changed

Phase 31 left a report claiming a set of fixes. The first action of this phase was to check the
repository rather than the report:

* `git ls-remote` confirmed `main` at `3bb6754…` before the branch was cut;
* the audit was re-run from source (`scripts/audit_models.py`), not read from its JSON;
* `ml/artifacts/registry.json` checksums were recomputed from the artifacts on disk;
* every evidence path named in the feature matrices was re-checked for existence;
* the OSD-46 raw file was re-downloaded and its SHA-256 compared with the pinned value;
* the PostgreSQL suite and the browser suite were both re-run from scratch.

**What that verification found:** the Phase 31 code state matched its report on the withdrawals and
the provenance repairs, but the audit still carried **19 documented gaps**, two of them
**high-severity** (the OSD-46 classifiers had no calibration analysis at all), and the coverage
matrix still described eight features as `data-blocked` — a state that reads as a roadmap.

## 2. Code completeness

| Workstream | Outcome |
| --- | --- |
| Audit gaps (19) | **0 high-severity, 5 documented non-actionable limitations, 2 closed with a measurement.** 161 checks, 0 failed |
| Harvest serving contradiction | Closed. Every prediction response carries `operationalForecast: false`, `harvestForecastClaim: null` and `scopeStatement`; `evidence.corpus()` appends `Served scope:` to every model passage; 11 tests walk routes, OpenAPI, catalogue, request schemas, assistant corpus and docs |
| Feature coverage matrix | Closed. 12 features re-scored layer by layer from the code: **3 complete, 1 comparison-only, 8 removed**. No feature is left `data-blocked` |
| Skipped tests | 24 skips on SQLite are **all PostgreSQL-gated**; the PostgreSQL run executes every one of them (**1236 passed, 0 skipped**). See `docs/PHASE32_SKIPPED_TESTS.md` |
| Frontend build | Circular chunk **fixed**. The 500 kB warning **cannot** be removed while the 3D twin is a three.js scene (measured: 807 kB for `{WebGLRenderer, Scene}` alone); `chunkSizeWarningLimit` is unchanged and nothing suppresses it. `npm run build:check` enforces the property that matters — no oversized chunk on the initial path. See `docs/PHASE32_FRONTEND_BUNDLE.md` |
| Retained calculations | Reference ET0 gains an output-plausibility gate; VPD and the light integral gain provenance; water demand stays rank-only; the ET0 emulator stays withdrawn |
| Dataset acquisition | OSD-46 re-verified by checksum; the seven remaining blocked features were searched and refused. See `docs/PHASE32_DATASET_ACQUISITION.md` |
| API/UI/security | 120 browser tests across three viewports, all passing; auth, CORS, validation and rate limits unchanged |

## 3. Scientific validation

### 3.1 Probability calibration for the OSD-46 classifiers (the high-severity gap)

`ml/research/phase32_radiation_calibration.py` measures whether a served probability is a
probability. The rule that governs the whole measurement: **never calibrate and evaluate on the same
observations.**

* Every scored probability is **out of fold** under leave-one-biological-group-out, the same split
  the published accuracy uses. The script recomputes the hard-label accuracy from those same
  out-of-fold predictions and **stops** unless it equals the committed artifact (0.9318 for both),
  so the calibration cannot describe a different model than the one that ships.
* **Nothing is fitted to the scored predictions.** The one fitted quantity — a temperature — is
  chosen **nested**: for each outer held-out group, the temperature is fitted on predictions from
  models that excluded both that group and the group being predicted. Cost: 22 × 21 extra fits.
* Intervals resample **whole biological groups**, not rows, because the two arrays inside a group
  are replicates.

| Model | Accuracy | Log loss (95 % CI) | Brier (95 % CI) | ECE, 10 bins (95 % CI) | Nested temperature helps? |
| --- | --- | --- | --- | --- | --- |
| `radiation-quality-osd46-v1` (3-class) | 0.9318 | **0.2228** [0.0698, 0.4178] | **0.1252** [0.0290, 0.2552] | **0.0926** [0.0495, 0.1743] | No (0.2228 raw vs 0.4358 scaled) |
| `radiation-exposure-osd46-v1` (binary) | 0.9318 | **0.1208** [0.0282, 0.2362] | **0.0788** [0.0105, 0.1701] | **0.0750** [0.0241, 0.1455] | No (0.1208 raw vs 0.1911 scaled) |

**What ships:** `calibrated: false`, `servedScaling: "none"`, the measured numbers, the scope
("within OSD-46 only"), and a statement telling the reader to treat the value as a ranking rather
than as the probability that the class is correct. The intervals, not the point estimates, are the
reportable quantity: 22 groups over 44 arrays is a small sample and the report says so.

The nested temperature *did not help*, which is itself the finding: these scores are not
over-confident in the direction a temperature correction fixes, so shipping a scaling factor would
have added a parameter without evidence. No scaling is applied.

**Campaign specificity is preserved.** The served statement for the microbial models says the
measured coverage is *within* the VEG-04A campaigns and that no second campaign exists against
which across-campaign coverage could be measured. That is deliberately not upgraded into a
cross-campaign claim — the audit records it as a documented limitation, and a test asserts the
wording survives.

### 3.2 Withdrawn models keep a record, not a claim

`mizuna-harvest-v1` (held-out R² −0.333) and the ET0 emulator (≈19 % worse than
Hargreaves–Samani under leave-one-site-out) remain on disk, checksummed, with their failed
evaluations. `backend/tests/test_phase32_no_forecast.py` proves no route, workflow, catalogue row,
request schema, OpenAPI operation or assistant passage offers a harvest forecast.

### 3.3 The lettuce models keep their published failures

* **v1** — reproducibility only, superseded on every held-out experiment.
* **v2** — LOSO R² 0.870 is *interpolation between four WUR experiments*. The independent check
  **failed**: Wicharuck et al. 2024 (PeerJ 12:e17085), median **3.2×** overprediction, range
  1.7×–5.4×.
* **v3** — missed its pre-registered 30 % MAPE criterion at **41.6 %**.

None of the three asserts an operational forecast, and the scope text in the response says exactly
this.

### 3.4 Output plausibility, the layer the audit found missing

`MAX_PLAUSIBLE_ET0_MM = 30.0`. The reference ET0 result now carries `outputCheck` with
`plausible`, the failures, the rule and the ceiling. The value is **returned, never clamped**: a
swapped-temperature day (`tmax` 18, `tmin` 30) returns its number *and*
`plausible: false` with the reason; an extreme day returns **40.374 mm/day** flagged over the
ceiling rather than a corrected 30.

## 4. Model serving eligibility

| Model | Status | Basis |
| --- | --- | --- |
| `reference-et0` (calculation) | **Served** | FAO-56 + Hargreaves–Samani fallback, worked examples pass, output gate added in Phase 32 |
| `lettuce-earth-growth-v1` | Served, reproducibility only | Superseded |
| `lettuce-earth-growth-v2` | Served, research surface | Independent check failed (3.2× median), stated |
| `lettuce-earth-growth-v3` | Served, research surface | Missed the pre-registered 30 % criterion at 41.6 %, stated |
| `mizuna-microbial-relative-load-v2` | Served, within-campaign only | Measured coverage 0.9919 within VEG-04A, no across-campaign claim |
| `radiation-quality-osd46-v1` | Served, measured calibration | Log loss 0.2228, Brier 0.1252, ECE 0.0926, uncalibrated and said so |
| `radiation-exposure-osd46-v1` | Served, measured calibration | Log loss 0.1208, Brier 0.0788, ECE 0.0750; batch confound published |
| `tomato-flight-response-v1` | Served, uncalibrated | No calibration study; the card says so |
| `mizuna-harvest-v1` | **Withdrawn** | R² −0.333, no reachable surface |
| `mizuna-microbial-load-v1` | **Withdrawn** (superseded by v2) | Kept as a record |
| `et0-emulator-v1` | **Withdrawn** | Worse than the equation it approximates |

Registry verification: **60/60 checks passed.** Model audit: **161 checks, 0 failed, 5 documented
limitations, 0 high severity.**

### Provenance and licence closure

`ml/training/phase32_provenance.py` declares, for all nine artifacts, the source URL, source type,
licence, licence/terms URL, citation, retrieval date, checksum where one exists, served scope and
archival status. The values are copied from `data/metadata/dataset_manifest.json` and the dataset
catalogue — the records that already held them — rather than inferred from a model name. Every one
of the 19 audit gaps that concerned a missing `sourceUrl` / `sourceType` / `license` is closed, and
`scripts/nasa_pipeline.save_json()` applies the table on write, so a retrain cannot drop it again.

## 5. User-facing completeness

* Every screen a user can reach renders real data or a stated absence. Eight features were removed
  from every layer — frontend, backend, routes, registries, catalogues, request schemas, input
  families, navigation and docs — keeping only non-serving archival records.
* Every visible control does something or was removed. Verified by 120 browser tests across
  desktop (1440×1100), tablet (820×1180) and mobile (Pixel 7), including API outage and retry,
  out-of-domain refusal, and viewport containment.
* The new `outputCheck`, `units` map, `probabilityCalibration`, `servedScope` and
  `operationalForecast` fields are additive; existing clients are unaffected, asserted by a test.

## 6. Gate results (all run in this phase)

| Gate | Command | Result |
| --- | --- | --- |
| SQLite suite | `pytest backend/tests -q -p no:randomly -rs` | **1212 passed, 24 skipped, 0 failed**. With the PostgreSQL 17 client binaries on `PATH` the `pg_restore` skip also runs: **1213 passed, 23 skipped** |
| PostgreSQL 17.11 suite | same, with `SPACEAGRISIM_TEST_POSTGRES_URL` | **1236 passed, 0 skipped, 0 failed** |
| Skip accounting | `-rs`, every reason classified | 24 PostgreSQL-gated, 0 unexplained (`docs/PHASE32_SKIPPED_TESTS.md`) |
| Model audit | `python scripts/audit_models.py --write` | **161 checks, 0 failed, 0 high-severity gaps** |
| Registry verification | `python scripts/verify_model_registry.py` | **60/60** |
| Coverage generation | `python ml/research/build_feature_coverage.py` | 12 features written |
| Coverage `--check` | `python ml/research/build_feature_coverage.py --check` | **up to date** |
| Readiness generation | `python ml/research/build_feature_readiness.py` | 12 features, 8 removed / 4 research-ready |
| Calibration measurement | `python ml/research/phase32_radiation_calibration.py` | both models reproduced and scored |
| Provenance check | `python ml/training/phase32_provenance.py --check` | **complete for 9 artifacts** |
| Lint | `npm run lint` | **0 problems** |
| Typecheck | `npm run typecheck` | **0 errors** |
| Production build | `npm run build` | clean, **no circular chunk** |
| Bundle graph check | `npm run build:check` | **passed** — no cycles, no oversized chunk on the initial path (240 kB / 3 modules) |
| Browser suite | `npx playwright test` | **120 passed** across three viewports |
| API/OpenAPI consistency | audit `workflow-endpoint-mounted:*` checks | pass — every advertised endpoint is mounted |
| Artifact checksums | audit `checksum:*` checks | pass — every artifact matches its registry SHA-256 |

## 7. Removed capabilities (complete list)

Removed from every layer, with a retained non-serving record:
`predicted harvest mass and every harvest forecast`, `nutrient solution management`,
`cultivar-specific growth parameters`, `mission energy and mass cost`, `partial-gravity crop
response`, `root-zone water status`, `plant health from imagery`, `future-climate siting`.

The record of *why* each was removed — including the searches that were run — is in
`docs/PHASE31_REMOVED_MODELS.md`, `docs/PHASE30_REMOVED_CAPABILITIES.md`,
`data/research/phase26/feature_readiness.json` (`phase32.reason`, `phase32.searched`) and
`docs/PHASE32_DATASET_ACQUISITION.md`.

## 8. Unresolved, non-actionable limitations

These are stated in the product, not hidden here:

1. **Two water paths, no arbiter.** Undecidable without per-day weather and pot geometry for the
   measured trial; neither is published, and inventing one would decide the answer before the
   comparison ran.
2. **No measured-ET0 station benchmark bundled.** The calculation is validated against FAO-56
   worked examples only. Acquisition failed for environmental reasons (see §9).
3. **Calibration is measured within campaigns.** It does not transfer to other radiation qualities,
   doses, organisms or platforms.
4. **Small samples.** 22 biological groups / 44 arrays and 14 harvest samples: the intervals, not the
   point estimates, are the reportable quantity.
5. **Array-batch confound.** Controls do not appear on the array batch holding 20 of the 44 arrays;
   the exposure model publishes the batch-controlled supplementary figure as the one to quote.
6. **three.js exceeds the 500 kB chunk budget by construction** (measured floor 807 kB). The 3D twin
   is a working feature and is lazy-loaded; the enforced guarantee is that it is not on the initial
   path.

## 9. Environment notes

* Python 3.13.16, numpy 2.3.5, **pandas 2.2.3** (pinned to match the training environment), sklearn
  1.6.1, scipy 1.17.1, pyarrow 26.0.1.
* PostgreSQL 17.11, UTF-8 cluster, password authentication on TCP (needed for the
  credential-leak test to be meaningful).
* Playwright chromium-headless-shell 158, with the system libraries unpacked into a local prefix.
* `data/raw/OSD-46/` is git-ignored by design; `train_radiation_osd46.py` and the calibration script
  both name the exact URL and expected SHA-256, and the calibration script refuses to run without
  the file rather than silently skipping.

## 10. Production deployment status

**Not deployed.** No Render service, environment variable, worker, instance or paid resource was
touched, no production database was accessed and no migration was applied. That remains with the
owner. What this phase delivers is a branch whose gates pass, ready to fast-forward `main`.
