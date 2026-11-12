# Phase 30 — Workflow coverage across the ten layers

Phase 28 introduced the completion gate: a workflow is complete only when data, method, service,
endpoint, input validation, output validation, uncertainty, provenance, frontend and tests are all
present. Phase 30 re-audits every retained workflow against that gate, states the outcome for the two
capabilities that were removed, and records where each remaining workflow still stops.

`arbitrated` remains **false** throughout. No validated arbitration between models exists.

---

## 1. Status after Phase 30

| Workflow | Status | Evidence class | `arbitrated` |
|---|---|---|---|
| W1 — Water demand and irrigation intelligence | **complete** | computed (reference ET0 + crop demand) | false |
| W3 — Light quality and stress (spectral comparison) | **complete** | measured observation | false |
| W3b — Controlled-environment wheat (measured panel) | **complete** (measured panel) | measured observation | false |
| W2 — Harvest prediction | **removed** | n/a — no model served | n/a |

---

## 2. W1 — Water demand (complete, unchanged in shape)

| Layer | Where | Note |
|---|---|---|
| Data | ERA5-Land / NASA POWER climate inputs; measured lettuce water-use bench (`hashVerified: true`) | climate is reanalysis, not station measurement |
| Method | FAO-56 reference ET0, crop coefficients, daily water balance, irrigation scheduling | Ky-yield conversion deliberately **not** implemented (no crop-specific Ky exists) |
| Service | `backend/app/workflows/water_demand.py` | |
| Endpoint | `GET /api/workflows/water-demand/capability`, `POST /api/workflows/water-demand/run` | |
| Input validation | typed ranges per field, `extra="forbid"`, ≤ 4 scenarios | unsupported crop rejected |
| Output validation | unit registry check, finite checks, per-plant figure withheld unless density supplied | |
| Uncertainty | interval on the measured bench only; the computed demand carries an explicit "no interval" statement | |
| Provenance | dataset, licence and raw-file hash travel with each response | |
| Frontend | `frontend/src/pages/modules/GuidedWorkflows.jsx` → water tab | |
| Tests | `test_phase28_workflows.py`, `test_phase29_workflows.py`, `test_phase30_removed_capabilities.py` | |

**Where it stops.** No yield-loss claim. `docs/DATASET_GAP_MATRIX.md` gap 13 records that no
measured water-supply gradient with a harvest exists for lettuce, tomato or radish, and that Ky must
never be transferred between crops.

---

## 3. W3 — Light quality and stress (complete, measured)

Nine layers as in Phase 29, unchanged. Phase 30 added a regression test that the factor names
advertised by the capability document are the factor names the API accepts (`publicName` vs the
internal column name), and moved the unit registry to include `kg/m2` for the new wheat panel.

**Where it stops.** Four spectral regimes at one PPFD and one photoperiod is a comparison, not a
response surface. No PPFD, photoperiod, CO₂ or temperature control is offered here.

---

## 4. W3b — Controlled-environment wheat (new measured panel)

| Layer | Where | Note |
|---|---|---|
| Data | `data/processed/phase30/cea_wheat_experiments.csv` (39 runs), `_subplots.csv` (719 rows) from Zenodo 17764612 | CC BY 4.0, hash in provenance |
| Method | measured group summaries over whole experiments; 95 % interval on the band mean from between-experiment spread | no fitted surface is served |
| Service | `backend/app/workflows/cea_evidence.py` | |
| Endpoint | `GET /api/workflows/light-stress/controlled-environment/capability`, `POST .../run` | |
| Input validation | factor and band are closed literals; ≤ 6 selections; `extra="forbid"` | a band outside the measured partitions cannot be requested |
| Output validation | band experiment counts must sum to the dataset experiment count; interval must bracket the mean | |
| Uncertainty | between-experiment interval per band; **no significance test across bands**, stated with the reason | |
| Provenance | DOI, licence, citation, raw-file SHA-256, processed files, `verifiedAgainstManifest` | |
| Frontend | `GuidedWorkflows.jsx` → "Controlled environment (wheat)" tab | shows the failed surface above the measured results |
| Tests | `test_phase28_workflows.py` (CEA block), `test_phase30_datasets.py` | |

**Where it stops.** No prediction. The attempted surface is recorded in
`ml/evaluation/phase30_cea_wheat_response` and reported as `predictiveModel.served: false`.

---

## 5. W2 — Harvest prediction (removed)

| Layer | State |
|---|---|
| Data | kept — `data/processed/phase30/lettuce_multistudy.csv` (evaluation corpus) |
| Method | removed — no served model |
| Service | `backend/app/workflows/harvest.py` is evidence-only (capability + parity) |
| Endpoint | `POST .../run` → **410**; `GET .../capability` and `GET .../parity` remain |
| Input validation | removed with the schema |
| Output validation | removed |
| Uncertainty | removed — the interval spanned a factor of 29 and is no longer offered |
| Provenance | kept — every evaluation, including failures, and the removal reason |
| Frontend | run tab replaced by an evidence panel; no inputs, no run button |
| Tests | `test_phase28_workflows.py`, `test_phase30_removed_capabilities.py` assert the absence |

---

## 6. The three global gaps that remain

| Gap | Status after Phase 30 | Why |
|---|---|---|
| Environmental response surface (PPFD, CO₂, temperature) | **open** — measured comparison ships, surface does not | the fitted surface missed the 30 % criterion at 297.46 % |
| Crop-specific water-deficit yield loss | **open** — no claim is made | no measured water gradient with harvest for the supported crops; Ky not transferred |
| Calibrated prediction intervals with measured coverage | **open** — descriptive intervals only | 6–8 independent evaluation points cannot support a coverage estimate |

`docs/DATASET_GAP_MATRIX.md` carries all fourteen gaps, including the two that were closed by
decision (fractional gravity, harvest forecasting) with the search trail attached to each.
