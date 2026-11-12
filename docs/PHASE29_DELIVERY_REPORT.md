# Phase 29 — Delivery Report

**Scope.** Harvest model generalisation, environmental-stress intelligence, and complete scientific
workflows, starting from verified remote `main` = `22df5de` (Phase 28).

This report is organised around the five questions the brief says must not be conflated. They have
five different answers, and only one of them is "yes" in full.

| Question | Answer |
|---|---|
| Did the software get built and tested? | **Yes.** Three complete workflows, 1151 backend tests on SQLite and 1175 on PostgreSQL 17.11 with zero skips, 123 Playwright journeys across three viewports. |
| Was the science validated? | **Partly, and one part failed.** W3's measured comparison is validated as a description of one experiment. The harvest model failed its pre-registered criterion at 39.28 % MAPE against 30 %. |
| Is any model newly production-eligible? | **No.** No v4 artefact was created, nothing was promoted, and the served model is unchanged at `trained-exploratory`. |
| Are the workflows complete? | **Yes, three of three**, where "complete" means all ten layers present with tests and a screen — and where one of the three contains no model at all, by design. |
| What remains blocked? | **A response surface for environmental stress**, fractional-gravity evidence, and any conversion of a water deficit into a yield loss. Each is blocked by missing data, not missing code. |

---

## 1. Software completion

### New and changed components

| Component | Change |
|---|---|
| `backend/app/workflows/light_stress.py` | new: measured-comparison workflow over four spectral regimes, 16 traits, bootstrap intervals, Welch tests, Hedges' g, provenance |
| `backend/app/simulation/irrigation.py` | new: FAO-56 soil water balance (eq. 80/83/84/85), depletion fraction table, explicit refusal of a Ky yield conversion |
| `backend/app/workflows/water_demand.py` | irrigation schedule wired in as an optional layer; three new comparison columns; two new limitations |
| `backend/app/routes/workflows.py` | `light-stress/{capability,run}`, four optional soil fields on the water request, workflow catalogue entry, gap renamed to `environmental-stress-response-surface` |
| `backend/app/workflows/units.py` | eight new units registered (water depth, per-plant mass, leaf area, counts, three concentration bases, SPAD index) |
| `frontend/src/pages/modules/GuidedWorkflows.jsx` | third tab: regime editor, day selector, trait chips, measured/results/comparison tables, provenance and unsupported-factor tables |
| `frontend/src/styles/platform.css` | scenario grid, chip row, fieldset — additive, no existing selector changed |
| `ml/training/phase29_harvest_{diagnosis,experiments,final}.py` | audit, six-candidate comparison, single holdout scoring |
| `ml/training/phase29_interval_audit.py` | interval calibration and coverage audit |
| `ml/research/build_light_stress_dataset.py` | reproducible rebuild of the Greenlight 2024 tables |
| `ml/research/build_phase29_readiness.py` | workflow coverage matrix and readiness table, with `--check` |
| `data/research/phase29/{workflow_readiness,environmental_stress_search}.py` | machine-readable readiness and search record |
| `data/research/dataset_catalog`, `DATASET_CATALOG.md` | green-light trial promoted B → A now that a workflow serves it |
| `data/research/dataset_gap_matrix`, `docs/DATASET_GAP_MATRIX.md` | gap 4 updated with Phase 29 evidence, severity unchanged |

### Verification

| Suite | Command | Result |
|---|---|---|
| Backend, SQLite | `python3 -m pytest backend/tests -q` | **1151 passed, 24 skipped** (skips are PostgreSQL-only cases) |
| Backend, PostgreSQL 17.11 | same, with `SPACEAGRISIM_TEST_POSTGRES_URL` set | **1175 passed, 0 failed, 0 skipped** |
| New Phase 29 tests | `test_phase29_{workflows,datasets,model_evidence}.py` | **50 tests**, all passing |
| Model audit | `python3 scripts/audit_models.py` | **141 checks, 0 failed** |
| Registry | `python3 scripts/build_registry.py --check` | clean |
| Coverage / gap / readiness / catalogue | `--check` on all four builders | all up to date |
| Frontend lint | `npm run lint` | clean |
| Frontend typecheck | `npm run typecheck` | clean |
| Frontend build | `npm run build` | succeeds |
| E2E, desktop + tablet + mobile | `npx playwright test` | **123 passed**, including full W1/W2 regression and the new W3 journeys |

The E2E baseline was 111 tests; the 12 added are the four new light-stress journeys across three
viewports. The existing W1 and W2 journeys were not modified and still pass, which is the regression
evidence for the "preserve working features" constraint.

### A defect found by building the tests

NPQt's control mean sits near zero by construction, so the workflow was reporting a **−1018 %
change** for `t1` — arithmetic rather than a finding, and it was being served. The response now carries
`relativeDifferenceMeaningful` and withholds the percentage when the control mean is small against its
own spread, with a note explaining why; the UI prints "not meaningful" in that cell. Two tests cover
both branches. This was found because a test asserted the *shape* of a comparison rather than a
specific number.

---

## 2. Scientific validation

### 2.1 Harvest model — failed, and that is the delivered result

| Quantity | Value |
|---|---|
| Candidates scored on identical grouped folds | 6 |
| Best out-of-fold MAE | 797.2 g/m² (`monotone-gbm`, a 4.6 % improvement over the v3 configuration) |
| Holdout MAPE | **39.28 %** |
| Criterion | **30 %**, unchanged |
| Passed | **false** |
| Versus v3 (41.594 %) | −2.31 points |
| Promoted | **false** |
| Artifacts created | none |

The diagnosis is more informative than the verdict: per-experiment bias runs from −635 to +505 g/m²,
and removing each experiment's mean bias *increases* error to 956 g/m². The model describes growth
within an experiment and cannot place a new one. Mechanistic candidates (saturating light response
with cardinal temperatures) fitted worse than boosting, which says the binding constraint is the data,
not the model class.

Full detail: `docs/PHASE29_HARVEST_GENERALIZATION_REPORT.md`.

### 2.2 The interval — descriptive, not a guarantee

| Check | Result |
|---|---|
| Served out-of-fold coverage | 0.8993, reproduced exactly from the committed residuals |
| Split-conformal width ratio | **0.429** (halves disagree) |
| Coverage by experiment | EXP1 0.887 · EXP2 0.988 · **EXP3 0.696** · EXP4 0.988 |
| Coverage at 1–5 DAT | **0.667** |
| Holdout observation covered | yes — and one observation is not evidence of 90 % coverage |

The platform now states `canClaimIndependentCoverage: false` in the artefact, and nothing in the
product repeats 0.899 as a guarantee.

Full detail: `docs/PHASE29_PREDICTION_INTERVAL_REPORT.md`.

### 2.3 Environmental stress — measured comparison validated, surface refused

| Item | Result |
|---|---|
| Source | Zenodo 20394352, CC BY 4.0, SHA-256 re-verified against the acquisition manifest |
| Records | 1552 harvest rows, 1476 photosynthesis rows, 168 pigment rows, 4 regimes |
| Exclusions | none; no imputation, no unit conversion, no outlier removal |
| Build reproducibility | re-running the builder reproduces identical CSV hashes (asserted) |
| Headline finding | no regime separates from the control on fresh mass; the photosystem indices do separate |
| Response surface | **not fitted**, and the search that establishes why is recorded as data |

Full detail: `docs/PHASE29_ENVIRONMENTAL_STRESS_RESEARCH_REPORT.md` and
`docs/PHASE29_ENVIRONMENTAL_STRESS_MODEL_REPORT.md`.

### 2.4 Water — an added reference calculation, no added claim

The FAO-56 balance gives a stress-day count, a relative transpiration deficit and an irrigation
volume. It does **not** convert that deficit into a yield loss, and a test asserts the refusal is in
the response. Full detail: `docs/PHASE29_WATER_INTELLIGENCE_REPORT.md`.

---

## 3. Model production eligibility

**No model became production-eligible in this phase.** Stated precisely, because the distinction
matters:

| Model | Status before | Status after | Eligible for production? |
|---|---|---|---|
| `lettuce-earth-growth-v3` | `trained-exploratory` | `trained-exploratory` | **no** — holdout failed at 41.594 %, unchanged |
| `lettuce-earth-growth-v4` | did not exist | **still does not exist** | n/a |
| W3 light-stress | n/a | no model | n/a — a measured comparison is not a model |
| W1 irrigation balance | n/a | reference calculation | not a model; labelled `isReferenceCalculation: true` |

A test asserts that `ml/artifacts/lettuce-earth-growth-v4.py` is absent and that the registry still
lists only v1–v3, so a future change that quietly registers a candidate fails the suite.

---

## 4. Workflow completion

| Workflow | Status | Evidence class | Readiness tier | Notes |
|---|---|---|---|---|
| W1 Water demand & irrigation | **complete** | reference calculation + one measured bench | `research-ready` | the bench is lettuce-only and `arbitrated: false` |
| W2 Crop growth & harvest | **complete** | trained model | `experimental` | holdout failed; not a forecast |
| W3 Light quality & stress | **complete** | measured observation | `research-ready` (comparison only) | no model, by design |

Generated matrix: `docs/PHASE29_WORKFLOW_COVERAGE_MATRIX.md`, from
`data/research/phase29/workflow_readiness`, with every evidence path verified by the builder.

"Complete" here means all ten layers — data, method, service, endpoint, input check, output check,
uncertainty, provenance, frontend, tests — not "API exists" and not "screen exists".

---

## 5. Remaining blockers

| Blocker | Why it cannot be closed now | What the product does |
|---|---|---|
| **Environmental-stress response surface** (PPFD, photoperiod, CO₂, temperature) | No openly licensed dataset varies these over a lettuce yield response at ≥ 3 levels. Three candidates were examined in this phase and rejected with reasons (`data/research/phase29/environmental_stress_search`). | Offers four named measured regimes; every other factor appears as unsupported with a stated reason, in the API and on screen. |
| **Fractional-gravity crop response** | No dataset exists in any open repository. | The simulator refuses the claim. |
| **Water deficit → yield loss** | No crop yield-response factor (`Ky`) exists in this repository. | Reports the deficit as a deficit. |
| **Harvest model generalisation** | Four experiments, one protocol family, one density, one photoperiod. No modelling choice fixes this. | Model stays `trained-exploratory`; the failed holdout is shown above the prediction. |
| **Interval coverage on a new site** | Calibration residuals come from the same four experiments the coverage was measured on. | Coverage is described, never guaranteed. |

None of these is a to-do item that more engineering closes. Each needs a measurement to be
commissioned, and the gap matrix says so at unchanged severity.

---

## 6. Constraints honoured

| Constraint | Evidence |
|---|---|
| No fabricated data, metrics or provenance | every number traces to a committed artefact; the holdout is one published observation, transcribed, not redistributed |
| No criterion moved, no failing evaluation hidden | 30 % criterion unchanged; `passed: false` in three artefacts and on screen |
| No holdout used for tuning | `holdoutReadHere: false`, and the prior inspection of the holdout is disclosed rather than denied |
| No unit silently converted | units registry extended, never converted; the leaf-area mm²/cm² caveat is carried forward, not "fixed" |
| No gap claimed closed without evidence | gap 4 severity unchanged (`major`); the response-surface gap remains `not-complete` |
| UI/UX and navigation preserved | third tab only; all W1/W2 journeys unchanged and passing |
| No Render deployment or config work | none performed |
| `--workers 1` retained | unchanged |

---

## 7. Honest summary

Phase 29 delivered three complete workflows, one of which is a measured comparison that predicts
nothing, and one of which is a model that failed the criterion set for it. The harvest work is a
negative result with a clear diagnosis: the data, not the model class, is the binding constraint, and
six candidates — three of them mechanistically motivated — converged on the same 40 % wall.

The phase's most useful products are arguably the three documents that say what the platform cannot
do, and the tests that keep those statements true. A model that fails and says so, a workflow that
reports measurements and refuses to extrapolate, and an irrigation balance that declines to invent a
yield factor are all more defensible than their more confident alternatives.
