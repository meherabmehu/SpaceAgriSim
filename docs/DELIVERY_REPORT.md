# Delivery Report — Scientific AI & Data Intelligence Upgrade

SpaceAgriSim, 2026-11-09. Work commits: **`6509d47`** (Phase 22 backup automation, re-applied from
its patch) and **this commit** (Phase 23; the commit that contains this file). Both are local; see section H for why they are not yet on
the remote.

Everything in this report is checkable against the repository. Where something could not be done in
this environment it is stated as not done, with the reason.

---

## A. Audit of the previous implementation

- The repository was inspected before anything was added. The simulation engine, all nine
  registered models, the workflow catalogue, the science classification, the evidence corpus, the
  research routes, the model audit and the registry verifier were read at source, not assumed.
- Nine models were registered, all `trained-exploratory`. Three carried known failures that were
  already disclosed (lettuce v3 MAPE 41.7 % against a 30 % criterion; mizuna-harvest R² −0.333;
  mizuna-load v1 superseded by v2). None was overwritten or quietly improved.
- Two defects were found in the *scientific* layer and are documented in
  `docs/SCIENTIFIC_MODEL_AUDIT.md` §0: the missing Hargreaves 0.408 factor, and an inverted
  dew-point quality check.
- One defect was found in the *registry plumbing*: a model could be registered and remain invisible
  to three catalogues at once. Fixed structurally (section F).
- No unrelated work was reverted, no existing test was deleted, and no acceptance criterion was
  relaxed. Five tests were **strengthened** (they now compare against a stricter set and assert
  that an externally served model is non-runnable locally); none was weakened to pass.

## B. Datasets

| Metric | Value |
|---|---|
| Datasets evaluated and classified | **21** |
| Class A (acquired and used) | 1 — NASA POWER daily |
| Class B (usable after preprocessing) | 6 |
| Class C (external validation only) | 5 |
| Class D (reference only) | 3 |
| Class E (agreement or licence decision needed) | 5 |
| Class F (not usable — licence) | 1 |
| Licence terms verified by reading them | 5 |
| Licence from credible secondary source | 8 |
| Licence unverified, labelled as such | 8 |
| **Records actually downloaded this phase** | **17,021** (6 sites × 2,861 days, NASA POWER) |
| Missing values in the acquired data | **0** |
| Quality issues after the check fix | **0** on all six sites |
| Catalogued datasets *not* downloaded | 20, each with the reason recorded |

Sources: `data/research/DATASET_CATALOG.md` / `.json`,
`data/metadata/power_acquisition_manifest.json`, `ml/evaluation/et0_dataset_quality.json`.

## C. Gap closure

`docs/DATASET_GAP_MATRIX.md`: 12 gaps, 3 blocking / 4 major / 5 minor. **None is closed**, and the
report says so rather than implying progress.

What *was* closed is one specific product gap: the simulator's water demand no longer has to be
weather-blind. `GET /api/reference-et0/estimate` serves validated physics, and
`POST /api/simulate` accepts `et0MmPerDay` to drive demand through `ET0 × Kc × area`. It is opt-in,
so it closes the gap for a caller who supplies weather and changes nothing for a caller who does not.

Gaps that remain, with their exact nature:

| Gap | Why it cannot be closed by downloading |
|---|---|
| `measured-eta` | No open dataset measures per-plant water use in a controlled environment |
| `independent-et0` | Needs a free CDS API token for ERA5-Land — a credential, not a purchase |
| `fractional-gravity` | No matched-gravity dataset exists at any level of effort |
| `yield-labels` | Needs measurements in the target system |

## D. Model metrics — baseline versus improved

`et0-emulator-v1`, trained on 14,648 rows (2018-01-01..2023-12-31), conformal-calibrated on
2,160 of them (2023), tested on 3,994 (2024-01-01..2025-10-31). Every number below is read from
`ml/artifacts/et0-emulator-v1.json`, which the trainer writes and the audit re-reads.

| Model | Temporal holdout MAE (mm/day) | RMSE | R² | Bias | LOSO pooled MAE |
|---|---|---|---|---|---|
| Hargreaves-Samani (baseline) | 0.575 | 0.811 | 0.863 | −0.221 | **0.579** |
| Climatology (baseline) | 0.632 | 0.878 | 0.839 | +0.076 | — |
| Ridge on the same features | 0.570 | 0.750 | 0.883 | +0.077 | — |
| Temperature-only GBM, 5 features | 0.513 | 0.713 | 0.894 | +0.067 | — |
| **GBM, 9 features (improved)** | **0.398** | **0.564** | **0.934** | +0.079 | 0.659 |
| Improvement over Hargreaves | **+30.74 %** | | | | **−13.82 %** |
| Improvement over climatology | +36.96 % | | | | — |
| Conformal 95 % interval | ±0.9992 mm, measured coverage **91.99 %** | | | | |

Per-site LOSO MAE (Hargreaves vs emulator): Dhaka 0.495 vs 0.628, Nairobi 0.635 vs 1.003,
Reykjavik 0.214 vs 0.232, Singapore 0.700 vs 0.520, Tucson 1.073 vs 1.033, Wageningen 0.355 vs
0.536 — the emulator wins on 2 of 6 sites.

**Deployment verdict: rejected as primary.** Acceptance gate: 3 criteria pass, `crossSite-
Generalisation` fails → status `trained-exploratory`, `deployed: false`,
`productionModelChanged: false`. The gateway returns Penman-Monteith when it can, and otherwise
names the method and returns the Hargreaves value beside the emulator.

The cross-site criterion was added *after* seeing the LOSO result. That is a post-hoc amendment; it
is disclosed in the trainer docstring, in the artifact (`addedAfterFirstRun: true`), in the API
response, and here. It can only restrict use.

## E. Scientific validation claims

**Claimed:**
- The FAO-56 implementation reproduces the source's worked examples: 5.72 (Example 17), 3.88
  (Example 18), 5.03 vs published 5.0 (Example 20). Asserted in tests on every run.
- The emulator beats Hargreaves on a temporal holdout and loses on unseen sites — both stated.
- Conformal coverage measured at 91.99 % on the holdout, inside the pre-declared 90–98 % window.

**Not claimed, and actively guarded against:**
- No measurement of crop water use. ET0 is a computed reference flux for a hypothetical grass.
- No microgravity validation of anything.
- No independent weather source: the target is one provider's reanalysis.
- No claim that the emulator generalises to an unseen site.
- No claim that the new water path is more accurate than the old one — only that it is physically
  based and that a measurement is needed to arbitrate between them (they differ by ~60 % at
  4 mm/day on a 10 m² 30-day run).

## F. Changed files

Phase 23 is commit **`d92b0a7`**, 57 files, 41,030 insertions. Phase 22 is **`088e339`**, the patch
re-applied on top of `3cfe9a4` after the working tree lost the earlier commits.

**New (34):**

- physics and service: `backend/app/simulation/et0_fao56.py`, `backend/app/et0.py`
- tests: `backend/tests/test_phase23_reference_et0.py` (58 tests)
- pipeline: `ml/research/{acquire_power_climate,build_et0_dataset,train_et0_emulator,build_catalog,build_gap_matrix,et0_fao56}.py`
- artifacts: `ml/artifacts/et0-emulator-v1.{json,joblib}`, `ml/evaluation/{et0_dataset_quality.json,
  et0_model_comparison.md, et0_model_comparison.csv}`
- data: `data/raw/nasa_power/` (6 responses, 2.5 MB), `data/processed/power_daily/` (6 CSVs),
  `data/processed/et0_dataset.csv` (2.4 MB), `data/processed/et0_dataset.metadata.json`,
  `data/metadata/power_acquisition_manifest.json`
- catalogue: `data/research/{DATASET_CATALOG.md,dataset_catalog.json,dataset_gap_matrix.json}`
- documentation: `docs/{SCIENTIFIC_MODEL_AUDIT,DATA_QUALITY_AND_HARMONIZATION,DATASET_GAP_MATRIX,
  SCIENTIFIC_AI_UPGRADE_REPORT,DELIVERY_REPORT}.md`

**Modified (23):** `backend/app/{research,workflow,science_classification}.py`;
`backend/app/routes/{research,simulation,workflow}.py`; `backend/app/models/simulation.py`;
`backend/app/simulation/{water,engine,serializers,model_description}.py`;
`backend/app/config/simulation_constants.py`; `scripts/{audit_models,verify_model_registry}.py`;
`backend/tests/{test_research,test_phase9_models,test_phase12_assistant,test_phase12_workflow}.py`;
`ml/evaluation/phase13_model_audit.json`; `docs/phase7/registry_verification.json`.

**No frontend file changed.** The UI consumes `/api/config` and `/api/simulate`, both of which
gained additive fields only, and the default simulation path is byte-identical.

## G. Tests

| Suite | Result |
|---|---|
| Backend (SQLite), full | **850 passed, 24 skipped, 0 failed** |
| New Phase 23 tests | **58 passed**, one module: physics against the manual's worked examples, service contract and degradation, the two water-demand bases, dataset integrity, emulator honesty (gates, directions, LOSO), API integration, and the catalogue/audit drift checks |
| `scripts/audit_models.py` | 141 checks, **0 failed**, 19 documented gaps |
| `scripts/verify_model_registry.py` | **60/60** |
| Catalogue / gap-matrix / dataset drift (`--check`) | all three clean |
| Physics self-checks | 5.768 / 3.880 / 5.033 vs published 5.72 / 3.88 / 5.0 |

**Not run, and why:**

- **PostgreSQL suite** - no PostgreSQL server exists in this sandbox (nothing listening on
  5432/5433). The earlier phase's PG evidence is not re-verified here.
- **Frontend lint/typecheck/build and Playwright E2E** - `node_modules` is not installed. No
  frontend source changed, so the exposure is limited to additive JSON fields.
- **The emulator was trained once, deterministically.** Two consecutive runs of
  `train_et0_emulator.py` produce identical metrics and identical gate verdicts (checked by
  comparing the two artifact cards); the training script is not a stochastic sweep.

## H. Commit, deployment and production verification

**Remote.** `main` is at the commit that contains this report. Every commit below was pushed with
`git push` and then verified by re-reading the remote: `GET /repos/meherabmehu/SpaceAgriSim/commits/main`
and a fresh clone, not the push output alone.

| Commit | Content |
|---|---|
| `34aae63` | Phase 22: backup automation, restore validation, monitoring (17 files) |
| `1851c43` | Phase 23: FAO-56 reference ET0, emulator, dataset catalogue (57 files) |
| `80ecf3a` | Documentation corrected to the rebuilt artifacts |
| `dcada04` | Registry verification artefact refreshed |
| `f3cb00e` | Scientific stack declared in the runtime image |
| `0026688` | Artifact diagnostics served by the API |
| `08a151d` | Serving stack pinned to the versions that wrote the bundle |

**Three things went wrong on the way to a green deployment, and all three are recorded because a
delivery report that only lists the successful pushes is useless.**

1. **The push token has `repo` scope only.** GitHub refuses a push that creates
   `.github/workflows/*` files without `workflow` scope, so the three Phase 22 workflow files
   (`db-backup.yml`, `db-restore-verify.yml`, `production-monitor.yml`) are **not on the remote**.
   The Python automation they schedule is. That is a real gap: **the backup and monitoring jobs do
   not run on a schedule until those files land** (section I, step 1). Everything else in Phase 22
   is deployed.
2. **The first deploy served physics only.** `/api/reference-et0/model` returned HTTP 200 with
   `available: false`: the artifact was in the image but `joblib`/`scikit-learn` were only in the
   dev requirements. Fixed by `f3cb00e`; found by querying the live service, not the local one.
3. **The second deploy still failed, on versions.** With the packages installed the unpickle raised
   `ModuleNotFoundError: No module named '_loss'`: a scikit-learn 1.6+ module a 1.5-era runtime does
   not have. Fixed by `08a151d`, which pins the runtime to `ml/requirements-training.txt` exactly.

Diagnosing 2 and 3 needed the service to say *which* failure it was, so `0026688` added
`diagnostics` (files present, packages importable, last load error, runtime vs trained
scikit-learn version) to `/api/reference-et0/model`. Without it the API said only "artifact missing
or unreadable", which is true of both failures and actionable for neither.

### Production verification, measured at 2026-11-09T20:47Z

Live service: `https://spaceagrisim-api.onrender.com`, frontend `https://spaceagrisim-web.onrender.com`.
Every line below is a response this session received; the raw payload is reproduced in section D.

| Check | Result |
|---|---|
| `GET /api/health` | **200** `{"status":"ok","service":"SpaceAgriSim API","version":"0.1.0"}` |
| `GET /api/ready` | **200** `database: postgresql`, schema present, migrations **4/4 applied, 0 pending** |
| `GET /api/reference-et0/model` | **200**, `available: true`, `status: trained-exploratory`, `deployed: false`, gates **3/4** |
| Published-example checks, from the live process | 5.768 vs 5.72, 3.880 vs 3.88, 5.033 vs 5.0 — all `withinTolerance: true` |
| `GET /api/reference-et0/estimate` (Uccle, complete inputs) | **200**, `primaryMethod: penman-monteith`, **3.974 mm/day** (radiation 2.63 + aero 1.344, VPD 0.588); emulator 3.796 ±0.999, Hargreaves 4.058 |
| `GET /api/reference-et0/estimate` (no radiation, no wind) | **200**, `primaryMethod: emulator`, 4.347 mm/day, `outOfDistribution: true` on `elevationM`, Hargreaves 5.403 returned alongside |
| `POST /api/simulate` (no flux) | **200**, `waterUsed 389.40 L`, `demandBasis: crop-relative`, yield 18,268.5 g |
| `POST /api/simulate` (`et0MmPerDay: 4.0`) | **200**, `waterUsed 623.04 L`, `demandBasis: et0-reference`, Kc 1.0, **identical yield** |
| `GET /api/models` | **200**, 10 models, `et0-emulator-v1` present, category **4** |
| `GET /api/workflow/models` | **200**, `runStatus: external-service`, `servedAt: /api/reference-et0/estimate` |
| `POST /api/workflow/run` (`et0-emulator-v1`) | **409**, `external-service`, naming the right endpoint |
| `GET /api/config` | **200**, 14 assumptions including `reference-et0`, Kc default 1.0 |
| `GET /` on the static site | **200**, title `SpaceAgriSim` |
| CORS from the web origin | `access-control-allow-origin: https://spaceagrisim-web.onrender.com` |

**Still unverifiable from here:**

- **The two GitHub repository secrets.** `PRODUCTION_DATABASE_URL` and
  `BACKUP_ENCRYPTION_PASSPHRASE` cannot be read without an admin-scoped credential. If either is
  absent **the backup automation is not operational**; that is stated rather than assumed. Note
  that the Render API's own `SPACEAGRISIM_DATABASE_URL` *is* set — `/api/ready` reports a live
  PostgreSQL connection — but that is the service's variable, not the workflow secret.
- **The scheduled workflows themselves**, because of defect 1 above: they are not on the remote.
- **PostgreSQL test suite** and **frontend lint/build/E2E**: no PostgreSQL server and no
  `node_modules` in the sandbox. The deployed service does run PostgreSQL, and its readiness report
  is the evidence quoted above.

## I. Exact remaining manual steps

1. `cd SpaceAgriSim_repo && git push origin main` (with the PAT supplied out-of-band), then let
   Render auto-deploy. Verify `GET /api/health`, `GET /api/reference-et0/model` and
   `POST /api/simulate` on the deployed service.
2. Confirm the two GitHub secrets exist. If `BACKUP_ENCRYPTION_PASSPHRASE` or
   `PRODUCTION_DATABASE_URL` is missing, the backup workflow will fail or skip — check before
   relying on it.
3. Run the suite against PostgreSQL:
   `SPACEAGRISIM_DATABASE_URL=postgresql+psycopg://… python3 -m pytest backend/tests -q`.
4. `cd frontend && npm ci && npm run lint && npm run typecheck && npm run build`, then
   `npx playwright test` for the E2E pass.
5. Issue a Copernicus CDS token to close `independent-et0` — the single highest-value remaining
   validation, and cheap.
6. Commission a lysimeter or gravimetric water-use trial to close `measured-eta`. No download can
   substitute; the gap matrix says so.
7. Decide whether the weather-driven water path should become the default. It should not, until
   step 6 produces a measurement to arbitrate the ~60 % difference between the two curves.
