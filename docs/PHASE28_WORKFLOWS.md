# Phase 28 — End-to-end scientific workflows

**Scope:** build workflows that a real user can operate, not features that merely exist. Two are
complete. The third candidate is documented as blocked, with the reason, rather than dressed up.

| # | Workflow | Status | Model / method status | Measured evidence |
|---|----------|--------|-----------------------|-------------------|
| 1 | Water demand and irrigation intelligence | **Complete** | FAO-56 Penman-Monteith reference ET0, plus the platform's own crop-relative assumption | Yes — greenhouse lettuce pot evapotranspiration, 11 dates |
| 2 | Crop growth and harvest prediction (lettuce) | **Complete** | `lettuce-earth-growth-v3`, status `trained-exploratory` | Yes — 1 648 training harvests, 7 external observations |
| 3 | Environmental stress and growth simulation | **Not complete — blocked** | none | none |

"A workflow is complete" here means every applicable layer below is implemented, exercised by an
automated test, and reachable from the browser.

---

## 1. Coverage matrix

Legend: **present** = implemented and tested; **explicit** = the workflow states that it cannot be
provided and why; **n/a** = does not apply to this workflow.

| Layer | W1 Water demand | W2 Harvest prediction | W3 Environmental stress |
|-------|-----------------|------------------------|--------------------------|
| Frontend input interface | present | present | absent |
| Units, ranges and a scientific explanation on every control | present (12 fields) | present (6 fields) | absent |
| Backend API + scientific service | present `app/workflows/water_demand.py` | present `app/workflows/harvest.py` | absent |
| Actual calculation / model execution | present (FAO-56 + 2 demand equations) | present (served artefact, byte-verified) | absent |
| Input validation and error handling | present (422 on crop, area, humidity, count) | present (422 on missing/unknown fields, domain flags) | absent |
| Inputs genuinely change outputs | present, and the one that does not is stated | present | absent |
| Results visualisation | present (table + interval bars) | present (table + interval bars) | absent |
| Scenario comparison | present (up to 4) | present (up to 4) | absent |
| Comparison against a reference calculation | present (ET0 recomputable from returned terms) | present (mean and ridge baselines on identical folds) | absent |
| Comparison against measured observations | present (lettuce bench, 3 denominators) | present (7 external points, both labelled by set) | absent |
| Source, DOI, licence, provenance | present | present | absent |
| Methodology, assumptions, limitations | present | present | absent |
| Uncertainty | present — measured between-pot spread; no invented interval | present — conformal interval + failed holdout | absent |
| Measured / reference / prediction / exploratory labels | present (4 labelled layers) | present (4 labelled layers) | absent |
| Unit-aware machine-readable output | present (`units` map, registered vocabulary) | present | absent |
| Backend automated tests | 21 | 17 | absent |
| Frontend E2E (desktop, tablet, mobile) | 3 tests × 3 viewports | 3 tests × 3 viewports | absent |
| Documented methodology and evidence | this file + `/api/workflows/water-demand/capability` | this file + `/api/workflows/harvest-prediction/capability` | blocker recorded |

Test counts are the tests in `backend/tests/test_phase28_workflows.py` attributed to each workflow;
the file holds 34 tests in total including the catalogue, units and cross-workflow checks.

---

## 2. Workflow 1 — water demand and irrigation intelligence

### The user journey

1. Open **Guided workflows → Water demand & irrigation**.
2. Choose a crop, an area, a growth stage and the site climate. Every control shows its unit, its
   permitted range and one sentence explaining what the calculation does with it.
3. Press **Run water demand**. The page calls `POST /api/workflows/water-demand/run`.
4. Read the results: reference ET0 with the method that produced it, the crop demand under both of
   the platform's equations, the remaining-cycle volume, the deltas against the first scenario, and
   the measured lettuce bench beside the estimate.
5. Add up to three more scenarios to compare sites, seasons or growth stages.

### Equations, and why two are returned

| Route | Equation | Evidence class |
|-------|----------|----------------|
| ET0-reference | `ET0 [mm/day] × Kc × area [m²] × canopyScale` | reference calculation + model prediction |
| Crop-relative | `peak_water [L/m²/day] × area × lightScale × canopyScale` | exploratory simulation |

`canopyScale = 0.15 + 0.85 × growthFraction`, where `growthFraction` is the platform's logistic
growth curve. `1 mm` over `1 m²` is `1 L`, so the millimetre and litre-per-square-metre columns are
the same number and the response states that.

The two routes disagree, and the response says so rather than picking one: on the default Dhaka
scenario the crop-relative figure is **0.58×** the ET0-reference figure. Nothing in the repository
arbitrates between them, and the measured bench cannot settle it (below).

The crop-relative equation takes **no climate input**. Two scenarios differing only in temperature,
humidity, radiation or wind therefore produce an identical crop-relative number. That is reported in
`demand.climateSensitivity` and in the comparison note, and a test asserts it stays true — so if
anyone later wires climate into that path, the claim in the response fails loudly instead of quietly
becoming false.

### Crop coefficients

| Crop | Kc | Source |
|------|----|--------|
| lettuce | 1.00 | FAO-56 tabulated leafy-vegetable mid-season range 0.95–1.05 |
| tomato | 1.05 | FAO-56 tabulated garden-fruit mid-season range 1.00–1.15 |
| radish | 0.90 | FAO-56 tabulated root-vegetable mid-season range 0.85–0.95 |

These are **tabulated standard values, not fitted here and not measured in a controlled
environment**. The response carries the source string next to the number, and the user may override
the coefficient.

### Measured evidence

Schröder C, Häfner F, Larsen OC, Krause A (2021), *Urban Organic Waste for Urban Farming: Growing
Lettuce Using Vermicompost and Thermophilic Compost*, Agronomy 11(6):1175.
DOI `10.5281/zenodo.5550230`, CC BY 4.0. Eleven measurement dates, gravimetric pot weighing,
greenhouse, Earth gravity. The served table is hash-verified at request time (`hashVerified: true`).

The bench is shown on three denominators at once because the study does not publish the pot surface
area that would decide the answer. On the pot-surface assumption the measured flux is far above the
scenario's reference flux; on a canopy-area denominator it is far below. The sign of the discrepancy
depends on geometry the study does not report, which is exactly why this bench cannot calibrate the
model, and the response says that in `measuredBench.comparisonCaveat`.

**Refusal:** tomato and radish get a computed demand and `measuredBench.applies: false` with a
statement that no measurement exists for that crop. The lettuce measurement is never extrapolated.

### Uncertainty

There is no invented confidence interval. What is returned is the between-pot standard deviation the
experiment actually measured (labelled `isConfidenceInterval: false` in the source bench) and the
measured series' own noise: a recorded 2.3× step between two consecutive weighings one day apart.
The response states that this is a spread, not an interval on the model.

### API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/workflows` | catalogue: both workflows, statuses, documented gaps |
| GET | `/api/workflows/units` | unit vocabulary with dimensions; converts nothing |
| GET | `/api/workflows/water-demand/capability` | 12 fields with units, ranges and reasons; crops; limits |
| POST | `/api/workflows/water-demand/run` | 1–4 scenarios → ET0, demand, comparison, bench, evidence |

---

## 3. Workflow 2 — crop growth and harvest prediction

### The user journey

1. Open **Guided workflows → Crop growth & harvest**.
2. Set growth stage, air temperature, root-zone temperature, PPFD, photoperiod and planting density.
3. Press **Run harvest prediction** → `POST /api/workflows/harvest-prediction/run`.
4. Read fresh yield per square metre, fresh mass per plant, the 90 % conformal interval, the
   out-of-domain warnings, the delta table against the first scenario, and the validation record.
5. Compare with the predecessor model, which is returned alongside on every call.

### The model

`lettuce-earth-growth-v3`: gradient boosting on `daysAfterTransplant`, `airTemperature`,
`rootTemperature` and the daily light integral, fitted on `log(fresh yield per m²)`, trained on
1 648 rows from 4 experiments (Batavia Othilie, plant factory).

* Daily light integral `= PPFD × photoperiod × 3600 / 1e6` (mol/m²/day) — declared in the artefact
  and returned in every response.
* Per-plant mass `= per-area yield ÷ stated plants per m²`. Density is not a learned feature; it
  enters only through this identity, which is why the workflow warns outside 10–200 plants/m².
* Interval: conformal residual quantiles on the log target (5 %/95 %), carried through the density
  division. Out-of-fold coverage **0.899**, and the artefact itself says that coverage is measured on
  the same predictions the quantiles come from, so it is descriptive rather than independent.

### What the validation says — including the failure

| Check | Data | Result | Counts as validation? |
|-------|------|--------|-----------------------|
| Internal | 1 648 rows, leave-one-experiment-out, 4 folds | MAE 835.5 g/m², R² 0.861 | Yes, internal only |
| Development | PeerJ 12:e17085, 6 observations (Baby Cos, Green Oak) | used to choose the DLI feature | **No** — `countsAsValidation: false` |
| Independent | Touliatos et al. 2016, 1 observation | **41.6 % MAPE against a 30 % criterion fixed in advance → failed** | Yes |

The workflow therefore returns `workflowComplete: true` **and**
`modelValidatedForForecasting: false`, and the results card carries the badge
"holdout failed · not a forecast" above the numbers. The predecessor `lettuce-earth-growth-v2` is
returned on every call with `ignoresInputs: ["photoperiodHours", "plantDensityPerM2"]`, because its
232 % external MAPE is the reason v3 exists and deleting a failing record once a better model
arrives would erase the evidence.

### Inputs that genuinely change the output

| Control | Effect on the served prediction |
|---------|-------------------------------|
| days after transplant | yes |
| air temperature | yes |
| root-zone temperature | yes (separately measured in training) |
| PPFD | yes, through the DLI |
| photoperiod | yes, through the DLI |
| planting density | changes per-plant mass through the identity; does not change per-area yield |

Controls the model cannot use — cultivar, CO₂, water, nutrients, gravity, radiation, substrate — are
listed in `method.notUsed` with a note that a form control in that list could not move the
prediction. None of them is rendered as an input.

### Scenario comparison

Deltas are reported against the first scenario in both absolute and percentage terms, and each delta
carries `intervalsOverlap`. Where intervals overlap the response states that the model cannot
distinguish the scenarios at its own stated coverage, and the UI shows that reading next to the
number. A difference of point estimates is never presented as a finding.

### API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/workflows/harvest-prediction/capability` | 6 fields with units, ranges, reasons; model id |
| GET | `/api/workflows/harvest-prediction/parity` | the 7 measured-vs-predicted points, served from the artefact |
| POST | `/api/workflows/harvest-prediction/run` | 1–4 scenarios → prediction, interval, warnings, comparison, validation |

---

## 4. Workflow 3 — environmental stress: blocker

This candidate was audited and **not built**. It is not an engineering gap.

The platform's habitat simulator exposes light spectrum, CO₂, irradiance and gravity controls. Where
a user changes those, the simulator changes a **warning string** and, for some parameters, a
multiplier drawn from an assumption table in `backend/app/config/simulation_constants.py`. There is
no response surface fitted to measured stress data, no experiment in this repository where a
spectrum or CO₂ treatment was measured against biomass, and no external dataset authorised for that
use.

A workflow built on those controls would take user input, run a calculation, and return a number
whose only scientific status is "multiplied by a number someone chose". Presenting that as a stress
simulation is the failure mode this phase exists to prevent. The exact blocker is carried in the API
at `GET /api/workflows` → `documentedGaps[0].blocker`, so it is visible to the interface and not
only to this document.

To unblock it, one of these is required: a published, citable spectrum/CO₂ stress response with
per-treatment measurements covering at least two crops, or a measured stress experiment acquired and
validated in this repository. Neither exists today. Designing the UI first would produce a workflow
that is complete in shape and empty in content.

---

## 5. Units as a machine-readable contract

`backend/app/workflows/units.py` registers every unit the workflows return, with its dimension, its
description and any caution a reader could otherwise get wrong (a millimetre depth is not a volume;
`g/m²` is an areal yield, not a per-plant mass; PAR is not total solar radiation). Each response
carries a `units` map from field name to unit metadata, so a chart can label an axis or a CSV export
can carry a header without parsing prose.

Nothing in the module converts. A value is always reported in the unit its producer used, and a test
asserts that every unit a workflow returns is registered — an unregistered unit fails the suite
rather than reaching a client as an unknown string.

---

## 6. Test evidence

| Suite | Command | Result |
|-------|---------|--------|
| Phase 28 backend | `pytest backend/tests/test_phase28_workflows.py` | 34 passed |
| Full backend, SQLite | `pytest backend/tests` | 1103 passed, 24 skipped |
| Full backend, PostgreSQL 17 | see §6.1 | see §6.1 |
| E2E, guided workflows, 3 viewports | `npx playwright test e2e/guided-workflows.spec.js` | 18 passed |
| E2E, full suite, 3 viewports | `npx playwright test` | see §6.1 |
| Lint / typecheck / build | `npm run lint`, `npm run typecheck`, `npm run build` | clean |

### 6.1 Verification run, this commit

| Suite | Command | Result |
|-------|---------|--------|
| Phase 28 backend | `pytest backend/tests/test_phase28_workflows.py` | **34 passed** |
| Full backend, SQLite | `pytest backend/tests` | **1103 passed, 24 skipped** |
| Full backend, PostgreSQL 17.11 | `SPACEAGRISIM_DATABASE_URL=postgresql://… pytest backend/tests` | **1103 passed, 24 skipped** |
| E2E, full suite, 3 viewports | `npx playwright test` | **111 passed** (93 pre-existing + 18 new) |
| Lint | `npm run lint` | clean |
| Typecheck | `npm run typecheck` | clean |
| Build | `npm run build` | clean |

The PostgreSQL and SQLite runs agree test for test, which is the check that the new routes do not
depend on the storage engine (they do not read the database at all).

*Environment note, not a code defect:* the first PostgreSQL run this phase produced 84 failures in
unrelated persistence tests with `TypeError: cannot use a string pattern on a bytes-like object`
inside SQLAlchemy's server-version parser. The cause was the locally initialised cluster running
`SQL_ASCII`; `initdb --encoding=UTF8` gave the result above. Nothing in the repository changed for
it.

### 6.2 Screenshots

Captured from the running application by a Playwright script at the three viewport sizes, after
pressing the run button in each workflow:

| File | What it shows |
|------|----------------|
| `docs/phase28/water-demand-desktop.png` | W1 inputs, results table, both equations, deltas, measured bench, evidence layers |
| `docs/phase28/water-demand-tablet.png` | the same at 820 px, with the plot scrolling rather than shrinking |
| `docs/phase28/water-demand-mobile.png` | the same at Pixel 7 size, navigation drawer opened by hand |
| `docs/phase28/harvest-desktop.png` | W2 inputs, results with interval bars, failed-holdout badge, parity table |
| `docs/phase28/harvest-tablet.png` | the same at 820 px |
| `docs/phase28/harvest-mobile.png` | the same at Pixel 7 size |

---

## 7. Files

**Backend**

* `backend/app/workflows/__init__.py` — package
* `backend/app/workflows/units.py` — unit vocabulary and `units` maps
* `backend/app/workflows/water_demand.py` — W1 service
* `backend/app/workflows/harvest.py` — W2 service
* `backend/app/routes/workflows.py` — `/api/workflows/*`
* `backend/app/simulation/water.py` — `canopy_scale()` extracted so the response can expose the term
* `backend/tests/test_phase28_workflows.py` — 34 tests

**Frontend**

* `frontend/src/pages/modules/GuidedWorkflows.jsx` — both workflows, end to end
* `frontend/src/pages/PlatformModules.jsx` — lazy route `workflows`
* `frontend/src/pages/MissionPlatform.jsx` — one new navigation entry, "Guided workflows"
* `frontend/src/styles/platform.css` — scenario strip, field layout, interval plot, warning block
* `frontend/e2e/guided-workflows.spec.js` — 6 journeys × 3 viewports

**Unchanged:** no existing route, response shape, model artefact, dataset, threshold or acceptance
criterion was modified. `water.canopy_scale()` is a pure extraction of an expression that was
already inline, with identical arithmetic.
