# Phase 29 Workflow Coverage Matrix

Generated from `data/research/phase29/workflow_readiness.json` on 2026-11-10 by `ml/research/build_phase29_readiness.py`. Edit the builder, not this file.

This is the third question the project asks about its own features. Phase 26 asked *what may a claim say*, Phase 27 asked *which layers of a feature exist*, and this asks *can a user actually walk the question from a source to a rendered result, and where does the walk stop*. It supersedes `PHASE27_FEATURE_COVERAGE_MATRIX.md` without overwriting it: that file is the record of what was true then.

A workflow is **complete** only when all ten layers are present and a test file exercises the path. API-only and UI-only work is `partial` and is labelled so, because a route with no screen and a screen with no route are both unfinished products.

## Summary

**2 of 3 workflows complete.** Evidence classes: `water-demand` reference-calculation, `harvest-prediction` trained-model, `light-stress` measured-observation.

| # | Workflow | Answers | Evidence class | Layers | Status | Readiness |
|---|---|---|---|---|---|---|
| 1 | **Water demand and irrigation scheduling** `water-demand` | How much water does this canopy want today, and what happens if it is irrigated on this schedule? | `reference-calculation` | 10/10 | **complete** | `research-ready` |
| 2 | **Crop growth and harvest prediction** `harvest-prediction` | What fresh mass per square metre does the served model predict from this DLI and environment, and how much should that number be trusted? | `trained-model` | 5/10 | **removed** | `experimental` |
| 3 | **Light quality and environmental stress** `light-stress` | Under this spectral regime, what did the plants actually weigh and how did their photosystems behave? | `measured-observation` | 10/10 | **complete** | `research-ready` |

## What each workflow does not do

The negative statements are part of the contract: a workflow that lists what it cannot do is auditable, one that only lists what it can do is not.

### Water demand and irrigation scheduling

- **Changed in Phase 29:** an FAO-56 soil water balance added to the existing demand calculation: depletion, stress coefficient, deep percolation, stress days and an irrigation volume, all optional and all labelled as a reference calculation
- **Does not:** convert a transpiration deficit into a yield loss: that needs a crop yield-response factor this repository does not hold
- **Does not:** extrapolate the measured lettuce bench to tomato or radish: the study measured lettuce
- **Does not:** forecast weather: the schedule repeats the supplied single day across the cycle

### Crop growth and harvest prediction

- **Changed in Phase 29:** the served model was re-examined rather than replaced: the pipeline was audited, six candidates were scored on identical grouped folds, and the winner was taken to the holdout once. It failed the unchanged 30 % criterion at 39.28 % MAPE, so v3 stays in service and no v4 artefact exists.
- **Does not:** forecast: the independent holdout failed and the response says so above the number
- **Does not:** generalise outside the four training experiments: per-experiment bias runs from -635 to +505 g/m2
- **Does not:** guarantee interval coverage on a new site: the pooled out-of-fold 0.899 is descriptive, and coverage by experiment falls to 0.696 in EXP3

### Light quality and environmental stress

- **Changed in Phase 29:** new workflow: a measured comparison over four spectral regimes
- **Does not:** predict anything: there is no model on this path, by design
- **Does not:** respond to PPFD, photoperiod, CO2, temperature or humidity: the experiment held them constant, so no control exists to move
- **Does not:** separate spectrum from density in t3: that regime changes both
- **Does not:** compute a composite stress score: the indices are reported side by side

## Layer matrix

| Layer | `water-demand` | `harvest-prediction` | `light-stress` |
|---|---|---|---|
| `data` — the dataset, artefact or documented assumption the calculation reads | present | present | present |
| `method` — the model or closed-form calculation itself | present | **absent** | present |
| `service` — the backend module that assembles the result | present | present | present |
| `endpoint` — the HTTP route a client calls | present | **absent** | present |
| `inputCheck` — request validation that rejects impossible inputs | present | **absent** | present |
| `outputCheck` — validation that the result is coherent, or a stated absence | present | **absent** | present |
| `uncertainty` — a quantified spread, or an explicit statement that none exists | present | **absent** | present |
| `provenance` — the sources and their limits travel with the answer | present | present | present |
| `frontend` — a screen a user can reach and read | present | present | present |
| `tests` — automated tests covering the path | present | present | present |

## Feature readiness

Tiers are the Phase 26 vocabulary, unchanged: `production-ready` needs an independent evaluation whose result matches the stated limits, `research-ready` needs measured data and a committed evaluation even when the level is not identifiable, `experimental` means internally evaluated only, `data-blocked` means no obtainable dataset can move it, and `unsupported` means the product must not make the claim at all.

| Feature | Claim | Tier | Phase 29 movement |
|---|---|---|---|
| `measured-eta` | Predicted crop water use in litres per plant per day | `research-ready` | unchanged; an irrigation schedule now sits on top of the demand calculation, and the bench is still one lettuce study |
| `independent-et0` | The ET0 target is itself correct | `research-ready` | unchanged; no new independent ET0 source was acquired |
| `yield-labels` | Predicted harvest mass per plant | `research-ready` | the generalisation attempt failed: holdout MAPE 39.28 % against a 30 % criterion, so the tier did not move and the failure is recorded |
| `led-spectrum-response` | Response to specific LED spectra and photoperiods | `research-ready` | moved from experimental to research-ready for the comparison only: a measured four-regime workflow now exists with intervals, tests and verified provenance. The response surface is still absent, and photoperiod still has no data. |
| `fractional-gravity` | Effect of Mars or lunar gravity on crop growth | `data-blocked` | unchanged; no fractional-gravity dataset exists |
| `substrate-water` | Root-zone water status in a hydroponic system | `data-blocked` | unchanged; the irrigation balance models the root zone as a bucket, which is not a substrate measurement |
| `sub-daily-weather` | Heat-stress and VPD excursion claims | `research-ready` | unchanged |
| `cultivar-metadata` | Cultivar-specific growth parameters | `experimental` | unchanged; the new workflow is single-cultivar (Red Batavia) |
| `imagery` | Plant health or growth stage from imagery | `data-blocked` | unchanged |
| `mission-energy` | Energy and mass cost of a described mission | `experimental` | unchanged |
| `nutrient-balance` | Nutrient solution management | `experimental` | unchanged |
| `long-run-climate` | Siting for a future climate | `data-blocked` | unchanged |

## Still blocked

These are not to-do items. Each is blocked by the absence of data, and the product states the consequence rather than approximating around it.

| Capability | Blocked by | What the user sees instead |
|---|---|---|
| **A continuous response surface in spectral composition, PPFD, photoperiod, CO2, temperature or humidity** `environmental-stress-response-surface` | no open dataset varies any of these over a yield response in lettuce; the search that established this is data/research/phase29/environmental_stress_search.json | the workflow offers four named measured regimes and marks every other environmental factor as unsupported, in the response as well as in the UI |
| **Growth or yield under lunar or Martian gravity** `fractional-gravity` | no fractional-gravity crop dataset exists in any open repository | the simulator refuses the claim and the factor remains data-blocked |
| **Converting an irrigation deficit into a yield loss** `yield-from-water-deficit` | no crop yield-response factor (Ky) exists in this repository | the irrigation schedule reports stress days and a relative transpiration deficit, and explicitly declines the conversion |

## What was deliberately not built

- **A response surface for environmental stress.** Four regimes with unequal replicate counts, of which two hold a fixed spectrum and one changes density as well, cannot support a continuous surface. A surface fitted through them would be a curve drawn through four points with a confound among them, and it would be presented as a prediction.
- **A separate stress score.** Collapsing Fv'/Fm', PhiNO, NPQt and yield into one number requires weights nobody measured. The workflow reports the indices separately.
- **A yield-loss conversion for irrigation deficits.** The FAO-56 water balance yields a relative transpiration deficit. Turning that into lost biomass needs a crop-specific yield-response factor, and inventing one would be the exact failure mode this project exists to avoid.
- **A replacement harvest model.** Not built: the Phase 30 evaluation showed that no fitted candidate beat the mean baseline out of fold, and the sealed cross-study holdout returned 310.17 % MAPE. The forecast was removed instead of being given another candidate class.
- **A predictive response surface for PPFD, CO2 or temperature.** The Phase 30 wheat acquisition made the fit possible and the fit failed its sealed holdout at 297.46 % MAPE. The measured band comparison ships; the surface does not.

