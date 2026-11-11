# Phase 31 — models and surfaces removed from the platform

This file is the retained record for every model and capability Phase 31 withdrew. Its purpose is
narrow: if a later reader asks *why* something is not in the product, the reason and the number are
here, and the artifact that produced them is still in the repository.

Removal here means **removal**, not retirement:

* no row in `GET /api/models`, no row in `GET /api/workflow/models`;
* no prediction route, no capability endpoint, no workflow catalogue entry;
* no dashboard card, tab, form or button;
* no entry in `backend/app/science_classification.py` (the served-surface classification).

What stays, deliberately:

* the artifact under `ml/artifacts/` and its recorded SHA-256 in `ml/artifacts/registry.json`
  (checksum verification still runs over it, and `GET /api/science/checksums` lists it with
  `"served": false`);
* the evaluation files under `ml/evaluation/`, so every number below can be re-derived;
* `research.RETIRED_MODEL_IDS` in `backend/app/research.py`, which is the single place naming these
  artifacts, with the reason attached, and which `scripts/audit_models.py` and
  `scripts/verify_model_registry.py` assert against.

`scripts/audit_models.py` fails the build if any of them reappears in a served surface
(`retained-not-served`, `retained-not-served-by-api`, `retained-not-routed`), and
`backend/tests/test_research.py::test_withdrawn_models_are_gone_from_every_served_surface` fails if
a route comes back.

---

## 1. `mizuna-microbial-load-v1` — absolute leaf microbial load (NASA OSD-780, VEG-04A/B)

**Why it is gone.** It does not transfer to an unseen campaign. Leave-one-campaign-out R² is **−0.55**
(VEG-04A held out) and **−0.58** (VEG-04B held out) — worse than predicting the training mean on
both. Phase 7 established that the campaign offset, not the flight/ground contrast, is the component
that fails to transfer.

**What was wrong with the previous treatment.** Phase 8 answered `410 Gone` with the evidence instead
of a number, and the model stayed in `GET /api/models` labelled `retired`. A 410 and a retired card
are still a public statement that the surface exists and is worth asking about; the dashboard also
counted it in the model-source pills. Phase 31 deleted the route, the request model, the registry
row, the workflow input family and the classification entry.

**The target was also frequently misread.** `freshWeightG` in the model is the mass of the assay
subsample, not harvest biomass. That caveat is retained in the artifact's own `limitations`.

**What replaced it.** `mizuna-microbial-relative-load-v2`, which models the within-campaign
standardised load: held-out R² **+0.444 / +0.373**, permutation p = 0.000, positive on every held-out
campaign. It returns standard deviations within a campaign and refuses to emit an absolute log10 CFU/g
figure unless the caller supplies that campaign's own measured mean and sd.

**Records:** `ml/artifacts/mizuna-microbial-load-v1.json`, `ml/evaluation/phase6_*`,
`ml/evaluation/phase7_*`, `docs/PHASE7_FINAL_REPORT.md`.

---

## 2. `mizuna-harvest-v1` — harvest fresh mass per pillow (NASA OSD-655)

**Why it is gone.** Held-out R² is **−0.333** against a training-mean baseline of **−0.138**: the model
is worse than predicting the mean. It was trained on **14 usable samples over 10 groups from a single
experiment**, and its two arms differ in target definition (see `docs/DATA_HARMONIZATION.md` H1).

**What was wrong with the previous treatment.** It was still exposed as a live *Predict* form in the
AI prediction centre — a form that returns a number, with an uncalibrated interval, for a model that
fails its own evaluation. It was also pinned at `baseline-only` in the registry rather than withdrawn.

**Records:** `ml/artifacts/mizuna-harvest-v1.json`, `ml/evaluation/phase10_*`,
`docs/PHASE10_WEAK_MODEL_AUDIT.md`.

---

## 3. `et0-emulator-v1` — fitted surrogate of FAO-56 reference ET0

**Why it is gone.** Three reasons, in order of severity:

1. **It could become the primary answer.** When solar radiation or wind speed was missing,
   Penman-Monteith could not be computed and the emulator was returned as `primaryMethod` — in
   preference to Hargreaves-Samani, the equation that generalises better.
2. **It lost the only independent test.** On leave-one-site-out it was about **19 % worse** than
   Hargreaves-Samani (the emulator was validated against FAO-56 ET0 *derived* from NASA POWER
   reanalysis at six sites — a computed target, never a lysimeter, sap-flow or flux-tower
   measurement).
3. **It added error and no information.** FAO-56 Penman-Monteith is computable from the same inputs
   the emulator consumes. A regression fitted to the output of an equation you can evaluate exactly
   is approximation for its own sake.

**What is served instead.** `app.simulation.et0_fao56` — FAO-56 Penman-Monteith (eq. 6) when
radiation and wind are supplied, Hargreaves-Samani when they are not, with the method, the missing
inputs and the reason named in every response. The implementation is checked against the manual's own
worked examples on every call (`GET /api/reference-et0/model`); no measured-ET0 station benchmark is
bundled, and the API says so instead of implying one exists.

**Records:** `ml/artifacts/et0-emulator-v1.json` + `.joblib`, `ml/evaluation/phase23_*`,
`data/processed/et0_dataset.csv`.

---

## 4. The lettuce harvest forecast workflow (`/api/workflows/harvest-prediction/*`)

**Why it is gone.** No harvest model met the project's unchanged 30 % independent-error criterion:
**41.7 % MAPE** on the Phase 28 holdout, **39.3 %** on the single published holdout in
`phase29_harvest_final.json`, and a cross-study evaluation over 35 published lettuce studies that was
worse again (`phase30_harvest_crossstudy.json`).

**What was wrong with the previous treatment.** Phase 30 removed the forecast itself but kept a
*catalogue entry*, *three endpoints* (`capability`, `parity`, and a `410` tombstone at `run`) and a
dedicated UI tab whose only content was the explanation that the feature no longer ran. Phase 31
deleted all of it: `backend/app/workflows/harvest.py`, the routes, the catalogue entry, the guided
workflow tab, and the frontend panel.

**Records (unchanged, still committed):** `ml/evaluation/phase28_harvest_holdout.json`,
`phase29_harvest_final.json`, `phase29_harvest_diagnosis.json`, `phase29_harvest_experiments.json`,
`phase30_harvest_crossstudy.json`, `ml/artifacts/lettuce-earth-growth-v3.json`, and the Phase 29/30
reports under `docs/`.

---

## 5. Dead frontend surface removed in Phase 31

`frontend/src/pages/DashboardPage.jsx` was never routed (`App.jsx` renders `MissionPlatform.jsx`), and
it was the only importer of twelve components. Anything reachable only through it was dead code shown
to nobody. Deleted:

`DashboardPage.jsx`, `MissionHeader`, `MissionOverview`, `MissionControls`, `MetricSummary`,
`EarthSpaceComparison`, `MissionInsight`, `GrowthPanel`, `LifeSupportPanel`, `ModelAssumptions`,
`SystemAlert`, `Footer`, plus the components and helpers that survived only because those files
imported them: `ControlGroup`, `CropSelector`, `DurationSelector`, `ImpactBreakdown`, `MetricCard`,
`MissionTimeline`, `ParameterSlider`, `ScenarioSelector`, `SegmentedToggle`, `Starfield`,
`SystemStatus`, `charts/GrowthChart.jsx`, `charts/LifeSupportChart.jsx`, `charts/chartTheme.js` and
`services/a11y.js`.

`GrowthPlot.jsx` stays: the simulation lab renders it.

---

## What did **not** change, and why

* **`lettuce-earth-growth-v1/v2/v3`** stay. They are external measured data with experiment-aware
  cross-validation (`ML_EVALUATION.md`); v2 and v3 beat their baselines on identical folds. Their
  external and cross-study failures are recorded on the card, not removed from it.
* **`tomato-flight-response-v1`, `radiation-quality-osd46-v1`, `radiation-exposure-osd46-v1`** stay.
  They answer a classification question about experimental context that their NASA measurement sets
  support, with leave-one-biological-group-out validation and a stated domain.
* **`mizuna-microbial-relative-load-v2`** stays, with `evidenceStatus: experimental` — never
  "validated", and never a calibrated probability.
  *Update (Phase 35):* the status is now `validated-exploratory`. Its card already carried the rule
  for that status; three of the four terms were true and the fourth — conformal coverage within five
  points of nominal — was unmeasured until Phase 34 measured it at 0.8943 against a nominal 0.90.
  The promotion is derived from that measurement, recorded in
  `ml/evaluation/phase35_model_evidence.json`, and it still binds the number to a campaign that
  supplies its own baseline samples. Nothing in this phase's reasoning about the withdrawn models
  changed.
* **The demand-curve comparison** stays as a *relative* comparison. The trial publishes neither pot
  diameter nor plant spacing, so the absolute level is not identifiable from it; the panel and the API
  now state that as the scope of the claim (`identification.levelIdentified = false`) rather than as a
  warning attached to a quantitative match.
