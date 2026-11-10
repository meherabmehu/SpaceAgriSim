# Phase 30 — Removed capabilities

Two capabilities were removed in Phase 30, and one predictive surface was attempted and refused.
None of them was removed because it was hard; each was removed because the evidence required to
keep it does not exist, or because the evidence that does exist says the model does not work.

A removal is only complete when nothing is left pointing at it. This document records, for each
capability: what it claimed, what was searched, why the evidence was insufficient, what was deleted
at every layer, and which test now proves the deletion.

---

## 1. Fractional-gravity growth response — removed

### What it claimed

The simulator accepted a gravity input in `g` (0–2), applied a linear growth penalty below 1 g
(15 % at 0 g, scaled by a per-crop sensitivity), exposed four gravity presets, and printed "reduced
gravity" as the limiting factor in the impact breakdown. `/api/compare` offered named scenarios
"Moon" and "Mars" whose only physical difference from Earth was that penalty.

### What was searched

| Source | Query | Outcome |
|---|---|---|
| NASA OSDR / GeneLab | graded gravity, fractional gravity, microgravity, clinostat, RPM, ALS | OSD-314 (0 g / 0.34 g / 1 g Arabidopsis), OSD-436, OSD-7, OSD-120, OSD-411 — transcriptomic, metabolic and morphological endpoints; no harvested edible mass per unit area at two or more gravity levels |
| NASA LSDA, NTRS | partial gravity plant growth, lunar/Martian gravity crop | Ground-chamber and orbital growth studies with a microgravity arm and a 1 g control; no graded yield response |
| ESA / JAXA / DLR repositories | graviperception, random positioning machine, crop yield | Morphology and gene expression under simulated microgravity; the analog is not partial gravity |
| Zenodo, Dryad, Figshare, Harvard Dataverse, PANGAEA, Mendeley Data | fractional gravity yield, Mars gravity crop biomass | Nothing with a measured yield at ≥ 2 gravity levels and the same cultivar |

### Why the evidence is insufficient

Three independent reasons, any one of which blocks a coefficient:

1. **Wrong response variable.** The recovered microgravity datasets measure transcripts, metabolites
   and morphology. A yield coefficient needs harvested mass, which none of them records.
2. **Analog contamination.** Clinostats and random positioning machines simulate *vector averaging*,
   not reduced gravitational acceleration. Treating them as fractional gravity is exactly the silent
   category error the brief forbids.
3. **Confounding.** The one orbital graded-gravity design available is a single flight run per level,
   with gravity crossed against light treatment, so a level effect cannot be separated from a run
   effect.

The 15 %-at-0 g number was therefore never a calibration. It was a placeholder written in Phase 1 and
carried forward as if it were knowledge.

### What was removed

| Layer | Change |
|---|---|
| Constant | `MICROGRAVITY_GROWTH_PENALTY`, `EARTH_REFERENCE_GRAVITY_G`, per-crop gravity sensitivity |
| Method | `factors.gravity_factor()` deleted; `combined_growth_factor()` no longer takes gravity |
| Engine | `SimulationInput.gravity`, `_run_scenario(gravity=...)`, gravity in `earth_reference_conditions()` |
| Impact | gravity step removed from the factor decomposition and its fixed order |
| API input | `SimulationRequest.gravity` deleted; `extra="forbid"` plus a model validator returns **422** naming the decision |
| API output | no `inputs.gravity`, no gravity warning, no gravity presets in `/api/config` |
| Compare | named cases are `Earth background` / `Lunar surface` / `Mars surface` / `Custom habitat`, differing in dose rate only |
| Frontend | gravity slider, presets, overview cell, insight labels, world presets and comparison readout removed |
| Docs and matrices | gap matrix, feature coverage, feature readiness, science classification, coverage table and assistant suggestions all record the removal |
| Tests | replaced, not deleted: they now assert the absence (`test_phase30_removed_capabilities.py`) |

### Proof the capability is gone

`backend/tests/test_phase30_removed_capabilities.py` asserts that `SimulationRequest` has no gravity
field, that constructing one raises with the word "removed" and the reason, that
`factors.gravity_factor` and the constants no longer exist, that `/api/simulate` returns 422 for a
request carrying the field, that no response body contains a `"gravity"` key, that the named compare
cases differ only in radiation, and that a stored scenario holding a legacy gravity field still
renders on the share path.

### What replaces it

Nothing. There is no gravity term, and `docs/DATASET_GAP_MATRIX.md` records the gap as permanent for
the current data landscape with the search trail attached. A future reintroduction has to break a
test on purpose and produce a dataset.

---

## 2. Operational harvest forecasting — removed

### What it claimed

`POST /api/workflows/harvest-prediction/run` returned a fresh-shoot-mass forecast per plant and per
square metre for lettuce, with a split-conformal interval, a record prediction from the previous
model, domain warnings and a scenario comparison. The catalogue listed the workflow as **complete**
with a model whose independent holdout had already failed the 30 % criterion at 41.59 %.

### What was searched and acquired

| Source | DOI | Outcome |
|---|---|---|
| Kilowatts to kilograms lettuce LUE compilation | 10.5281/zenodo.14640245 | **Acquired** — 53 published treatment means from 40 studies, CC BY 4.0. Used as the independent evaluation set. |
| Indoor wheat, fully controlled environment | 10.5281/zenodo.17764612 | **Acquired** — 39 chamber runs, 719 sub-plots. See the CEA report; the fitted surface also failed. |
| Piikkio2023 lettuce point cloud | 10.5281/zenodo.8410252 | Rejected — licence field null, not redistributable |
| Fertigation variability dataset | 10.5281/zenodo.20759414 | Rejected — 39 GB, and the varied factor is fertigation, not light or temperature |
| Light-environment measurements | 10.5281/zenodo.22004997 | Rejected — no crop response variable |
| Greenlight reanalysis | 10.5281/zenodo.20394352 | Rejected — duplicates a study already used, would double-count one experiment |
| Simulation output dataset | 10.5281/zenodo.17712088 | Rejected — model output, not measurement |
| Pak choi growth trial | 10.5281/zenodo.16271245 | Rejected — wrong species |
| Wheat SPAD series | 10.5281/zenodo.14529253 | Rejected — response variable is a chlorophyll index |
| Spinach far-red timing | 10.5281/zenodo.22280237 | Rejected — 22 KB, single series, no yield |
| Dryad UAV imagery | 10.5061/dryad.73n5tb3d4 | Rejected — 8 GB imagery only; download also returned 401 |

### Why the model could not be promoted

The Phase 30 evaluation protocol was fixed before scoring: leave-one-study-out over the development
studies, a single sealed scoring pass on eight studies chosen by SHA-256 of the study key, no random
split (sibling treatments of one study would leak), and the unchanged 30 % criterion.

The result was not a near miss:

| | Out of fold (39 records, 32 studies) | Sealed holdout (8 records, 8 studies) |
|---|---|---|
| Selected candidate | `baseline-mean` | `baseline-mean` |
| MAE | 1.9834 g/plant | 5.2309 g/plant |
| MAPE | 211.42 % | **310.17 %** |
| Median APE | 40.63 % | 84.49 % |
| R² | −0.2395 | −0.4831 |
| Criterion | 30 % | 30 % — **failed** |

The decisive finding is not the holdout number; it is that **no fitted candidate beat the mean
baseline out of fold**. Under the pre-registered 2 % simplicity rule the baseline was selected, which
means the covariates carry no usable between-study signal at this sample size. A wider interval would
be arithmetic, not uncertainty.

### What was removed

| Layer | Change |
|---|---|
| Service | `backend/app/workflows/harvest.py` rebuilt as an evidence-only module (capability, parity) |
| Route | `POST /api/workflows/harvest-prediction/run` → **410 Gone** with a reason and a pointer to the surviving records; request schema deleted |
| Catalogue | entry kept, `status: "unavailable"`, `operationalForecast: false`, `removedInPhase: 30`, no `run` endpoint advertised |
| Frontend | run tab replaced by an evidence panel: the decision, every evaluation that failed, and the measured-versus-modelled parity table. No inputs, no run button |
| Docs and matrices | gap matrix, feature coverage, feature readiness, workflow readiness, science classification and the assistant's own text all record the removal |
| Tests | Phase 28 harvest tests replaced one for one with removal tests; the Phase 29 contract test now asserts the 410 |

### What survives, and why

- `GET /api/workflows/harvest-prediction/capability` — the decision record, the criterion, and every
  evaluation including the ones that were not scored.
- `GET /api/workflows/harvest-prediction/parity` — 7 measured-versus-predicted points labelled
  `development` or `independent`, with `countsAsValidation` false for the development rows, and a
  caveat stating the model overpredicts.

A failed model is evidence about the data. Deleting it entirely would hide why the forecast is gone.

---

## 3. Controlled-environment response surface (wheat) — attempted, refused

The wheat acquisition answered half of the environmental-stress gap: 39 chamber runs varying PPFD
(235–1084 µmol m⁻² s⁻¹), photoperiod (6.1–22.6 h), CO₂ (400–1478 ppm) and air temperature
(21.1–28.0 °C), with measured grain yield.

A response surface was fitted under leave-one-experiment-out validation and scored once on six
experiments sealed by SHA-256. It failed: **297.46 % MAPE, R² −0.3673**, against the unchanged 30 %
criterion, and the best out-of-fold candidate was again a structured baseline rather than a fitted
surface.

So the surface is **not served**. What ships instead is a measured comparison: group summaries by
factor band, with a 95 % interval on the mean of the experiments in the band, the experiment
identifiers making up each band, and an explicit statement that no significance test is reported
because the experiments differ in several factors at once.

The artifact (`ml/evaluation/phase30_cea_wheat_response.json`) is retained and reachable from
`GET /api/workflows/light-stress/controlled-environment/capability`, because an attempt that failed
is part of the record.

---

## Why removal rather than a caveat

The pattern this phase was written to stop is a placeholder coefficient produced by a model, printed
in an API response, and explained in a footnote. A user reads the number, not the footnote. When the
evidence does not exist:

- a caveat turns an invented number into a documented invented number;
- a removal turns it into an absent one, which is a claim the artifacts can support.

Every removal above is therefore a deletion at all ten layers, with a test that asserts the absence,
and a written search trail so the next person does not repeat the search from scratch.
