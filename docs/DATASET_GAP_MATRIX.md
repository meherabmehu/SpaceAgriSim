# SpaceAgriSim Dataset Gap Matrix

Generated from `data/research/dataset_gap_matrix.json` on 2026-11-10 by `ml/research/build_gap_matrix.py`. Edit the JSON, not this file.

Every capability SpaceAgriSim claims or is asked about, matched against the data that would actually be needed to support it. A gap here is a statement about evidence, not a to-do list: several will stay open on purpose because the data does not exist at any price.

**14 gaps recorded: blocking: 3, major: 6, minor: 5.**

A few are closed by decision rather than by data - the capability was removed instead of being kept behind a placeholder - and each of those says so and says what was searched first. The point of the matrix is that every gap, open or closed, has a named consequence for what the product is allowed to claim, and the product states that consequence rather than papering over it.

## Severity

| Severity | Meaning | Count |
|---|---|---|
| **blocking** | a claim in the product cannot be supported at all without this | 3 |
| **major** | the claim is supportable only with a stated limitation that a user would notice | 6 |
| **minor** | the claim is supportable; this would improve accuracy or resolution | 5 |

## Matrix

| # | Capability | What is needed | Severity | Gap type | Status |
|---|---|---|---|---|---|
| 1 | Predicted crop water use in litres per plant per day | Measured evapotranspiration or sap-flow/lysimeter water use for the modelled crops at plant scale | **blocking** | partially-addressed | open and blocking on its original terms, with its first measured evidence bench. The comparison artefact (ml/evaluation/phase26_measured_et_validation.json) shows the seasonal shape is broadly right (Spearman 0.7909 across 11 measurement days) while the level cannot be identified: on a pot-surface denominator the platform's flux is 0.247x the measurement, on a canopy-area denominator it is 2.7x. Because the study publishes neither pot diameter nor spacing, the sign of the discrepancy depends on an assumption, and no constant was changed. |
| 2 | The claim that the ET0 target is itself correct | A weather or ET0 source that does not share MERRA-2 lineage with POWER, and a measured latent-heat series to convert mutual agreement into physical truth | **major** | partially-addressed | open, partially addressed: disagreement now decomposed into formulation (0.273 mm/d), forcing (0.519) and implementation (+0.009) - the residual is weather, not code - but every leg is either a reanalysis or a temperature-only point method, so nothing here is field validation of the ET0 magnitude |
| 3 | Effect of Mars or lunar gravity on crop growth | Yield or growth measurements at gravity levels other than 1 g, with the same cultivar and protocol as the terrestrial baseline | **blocking** | no-data | closed by decision, not by data: Phase 30 removed the fractional-gravity input, factor, control, API field and tests. The gap is permanent - no open dataset measures crop yield or biomass across fractional gravity, ISS graded-gravity work measures gene expression and morphology, and a ground clinostat or reorientation is not partial gravity - so the capability was withdrawn rather than left as a placeholder coefficient. |
| 4 | Response to specific LED spectra and photoperiods | Biomass or yield response surfaces across spectra, PPFD and photoperiod for each supported crop | **major** | insufficient | open for the predictive surface, served for two measured comparisons: the light-stress workflow compares four spectral regimes at one PPFD and photoperiod, and Phase 30 added a controlled-environment panel over the wheat series (PPFD, photoperiod, CO2, air temperature bands with measured grain yield). A response surface was fitted to that series and failed its sealed holdout (297.46 % MAPE against the 30 % criterion), so no predictive light, CO2 or temperature control is offered. |
| 5 | Root-zone water status in a hydroponic or substrate system | Substrate water content, irrigation schedule and drainage fraction at high temporal resolution | **major** | no-data | open |
| 6 | Heat-stress and VPD excursion claims | Hourly temperature, humidity and radiation at the site | **minor** | too-coarse | open |
| 7 | Cultivar-specific growth parameters | Cultivar identity and calibrated growth parameters per cultivar | **major** | insufficient | open |
| 8 | Plant health or growth stage from imagery | Labelled canopy imagery from the platform's own camera geometry | **minor** | no-data | open and deliberately not addressed |
| 9 | Predicted harvest mass per plant | Measured harvest mass with the same covariates the model uses | **blocking** | insufficient | closed by decision, not by data: Phase 30 removed operational harvest forecasting. A leave-one-study-out evaluation over 40 published lettuce studies returned 310.17 % MAPE against the unchanged 30 % criterion, and the best out-of-fold candidate was the mean baseline, so no model in this repository can forecast harvest mass. The measured-versus-model parity record is retained |
| 10 | Energy and mass cost of a described mission | Power draw per fixture, thermal load and resupply mass figures for real flight hardware | **minor** | no-data | open and out of scope |
| 11 | Nutrient solution management | Ion concentrations, uptake rates and EC/pH response per crop | **minor** | no-data | open and out of scope |
| 12 | Siting for a future climate rather than the observed recent past | Downscaled climate projections at the candidate sites | **minor** | no-data | open |
| 13 | Yield loss from crop water deficit (crop-specific Ky) | Measured yield at two or more water-supply levels for the same crop and cultivar, with enough levels to fit a Ky slope and an independent study to validate it | **major** | no-data | open |
| 14 | Calibrated prediction intervals with measured coverage | Enough independent evaluation points to estimate coverage per crop and per experiment group without reusing the selection data | **major** | insufficient | open |

## Detail

### Predicted crop water use in litres per plant per day  `measured-eta`

- **Needed:** Measured evapotranspiration or sap-flow/lysimeter water use for the modelled crops at plant scale
- **Available:** Reference ET0 computed from reanalysis (FAO-56 Penman-Monteith, cross-validated against four sources), a learned emulator of that computed quantity, an 18-check ingestion validator, and — new in Phase 26 — one third-party measured dataset: gravimetric per-pot evapotranspiration of greenhouse lettuce (Schröder et al. 2021, 35 published pots, 380 usable pot-days), acquired, hashed and preprocessed in-repo with an out-of-sample comparison against the platform's water path.
- **Gap type:** partially-addressed
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** A lysimeter or gravimetric water-use trial in the target growth system. No open dataset measures per-plant water use in a controlled-environment facility for lettuce or mizuna; this is a measurement to commission, not a download. New ingestion apparatus does not change the status: a validator can reject a bad measurement, it cannot create one.
- **Current status:** open and blocking on its original terms, with its first measured evidence bench. The comparison artefact (ml/evaluation/phase26_measured_et_validation.json) shows the seasonal shape is broadly right (Spearman 0.7909 across 11 measurement days) while the level cannot be identified: on a pot-surface denominator the platform's flux is 0.247x the measurement, on a canopy-area denominator it is 2.7x. Because the study publishes neither pot diameter nor spacing, the sign of the discrepancy depends on an assumption, and no constant was changed.

### The claim that the ET0 target is itself correct  `independent-et0`

- **Needed:** A weather or ET0 source that does not share MERRA-2 lineage with POWER, and a measured latent-heat series to convert mutual agreement into physical truth
- **Available:** Four legs over 2021-2023 at six sites (6570 site-days): ERA5 0.25 deg hourly and daily, NASA POWER daily, ERA5-Land 0.1 deg temperature, and NOAA ISD station temperatures. Our FAO-56 implementation agrees with the provider's independent implementation on identical ERA5 forcing to bias +0.009 mm/d (MAE 0.181, R2 0.987), while the forcing difference between ERA5 and POWER is MAE 0.519 mm/d. The station leg is temperature-only (Hargreaves) and no leg measures latent heat.
- **Gap type:** partially-addressed
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** Still needs (a) a Copernicus CDS token for the ERA5-Land hourly radiation and wind fields, which the credential-free delivery does not expose, and (b) a measured latent-heat series (eddy covariance or lysimeter) at at least one site, because reanalyses agreeing cannot establish absolute correctness.
- **Current status:** open, partially addressed: disagreement now decomposed into formulation (0.273 mm/d), forcing (0.519) and implementation (+0.009) - the residual is weather, not code - but every leg is either a reanalysis or a temperature-only point method, so nothing here is field validation of the ET0 magnitude

### Effect of Mars or lunar gravity on crop growth  `fractional-gravity`

- **Needed:** Yield or growth measurements at gravity levels other than 1 g, with the same cultivar and protocol as the terrestrial baseline
- **Available:** Terrestrial controlled-environment trials only (one 6-observation lettuce study, one OSDR study with harvest mass)
- **Gap type:** no-data
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** None available. Orbital and Mars-surface experiments produce too few replicates and too few cultivars to fit a response function; the honest position is that gravity response is a qualitative modifier with a stated uncertainty, never a trained coefficient.
- **Current status:** closed by decision, not by data: Phase 30 removed the fractional-gravity input, factor, control, API field and tests. The gap is permanent - no open dataset measures crop yield or biomass across fractional gravity, ISS graded-gravity work measures gene expression and morphology, and a ground clinostat or reorientation is not partial gravity - so the capability was withdrawn rather than left as a placeholder coefficient.
- **Phase 30 decision:** B - removed completely - the 15 %-at-0 g growth penalty, the gravity input field, the gravity presets, the gravity impact step and every test that asserted them
- **Residual capability:** None. /api/simulate rejects a request carrying a gravity field and names this decision; the simulator has no gravity term at all.

### Response to specific LED spectra and photoperiods  `led-spectrum-response`

- **Needed:** Biomass or yield response surfaces across spectra, PPFD and photoperiod for each supported crop
- **Available:** The evidence base is one crop (lettuce) and one dedicated spectral trial. Phase 26 added a hydroponic spectral-composition trial (Zenodo 20394352, 252 plants across four fixed spectra at constant PPFD and 16 h photoperiod); Phase 29 rebuilt it into data/processed/phase29 and serves it as the measured light-stress workflow, which reports group means with bootstrap intervals, within-experiment tests and verified provenance. It remains a comparison of four named regimes, not a response surface: two regimes hold a fixed spectrum and one of those is the control, and one regime changes density as well.
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** The published CEA literature is large but fragmented: hundreds of small papers, no shared protocol, rarely any raw data. A meta-analysis with study-level random effects is the realistic route, and it needs a person reading papers, not an API.
- **Current status:** open for the predictive surface, served for two measured comparisons: the light-stress workflow compares four spectral regimes at one PPFD and photoperiod, and Phase 30 added a controlled-environment panel over the wheat series (PPFD, photoperiod, CO2, air temperature bands with measured grain yield). A response surface was fitted to that series and failed its sealed holdout (297.46 % MAPE against the 30 % criterion), so no predictive light, CO2 or temperature control is offered.
- **Phase 30 decision:** A (evidence found) for the measured comparison, B (removed) for the predictive response surface - added GET/POST /api/workflows/light-stress/controlled-environment; the attempted response surface is recorded in ml/evaluation/phase30_cea_wheat_response.json and is not served
- **Residual capability:** Measured band summaries with between-experiment intervals, a descriptive DLI association, and no significance test across bands.

### Root-zone water status in a hydroponic or substrate system  `substrate-water`

- **Needed:** Substrate water content, irrigation schedule and drainage fraction at high temporal resolution
- **Available:** None. SMAP L4 gives 9 km root-zone soil moisture for open fields, which is a different system at a different scale.
- **Gap type:** no-data
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** Instrument the target system; there is no open dataset. SMAP would only be relevant if the platform modelled an open-field deployment.
- **Current status:** open; the simulator models a water balance from demand, not from substrate state, and says so

### Heat-stress and VPD excursion claims  `sub-daily-weather`

- **Needed:** Hourly temperature, humidity and radiation at the site
- **Available:** POWER daily aggregates. Daily Tmax/Tmin hides the duration and timing of an excursion.
- **Gap type:** too-coarse
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** POWER hourly endpoint (same API, same access) or ERA5-Land hourly. Partly closable today, but the ET0 validation in this phase deliberately stayed daily to match the reference formulation.
- **Current status:** open; no heat-stress claim is made that depends on intra-day timing

### Cultivar-specific growth parameters  `cultivar-metadata`

- **Needed:** Cultivar identity and calibrated growth parameters per cultivar
- **Available:** A single parameter set per crop, with no cultivar dimension anywhere in the data
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** Cultivar trials in the target system. Breeder or seed-company data would be the natural source and is commercially restricted in practice.
- **Current status:** open; the product exposes one parameter set per crop and does not offer a cultivar selector

### Plant health or growth stage from imagery  `imagery`

- **Needed:** Labelled canopy imagery from the platform's own camera geometry
- **Available:** None in the repository. GWHD (wheat head detection) and PlantVillage (lab leaf disease) exist but describe different crops, different sensors and different tasks.
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** No imaging pipeline exists, so nothing is blocked today. If one is added, GWHD is the right labelled source for detection and PlantVillage is the wrong one for anything field-realistic.
- **Current status:** open and deliberately not addressed; recorded so a future contributor does not train a lab-disease classifier and call it a capability

### Predicted harvest mass per plant  `yield-labels`

- **Needed:** Measured harvest mass with the same covariates the model uses
- **Available:** A small internal table plus six published lettuce observations used for external validation
- **Gap type:** insufficient
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** More measured harvests with recorded light, temperature and duration. Until then the model's MAPE (41.7 %) is the honest number and the acceptance criterion is not met.
- **Current status:** closed by decision, not by data: Phase 30 removed operational harvest forecasting. A leave-one-study-out evaluation over 40 published lettuce studies returned 310.17 % MAPE against the unchanged 30 % criterion, and the best out-of-fold candidate was the mean baseline, so no model in this repository can forecast harvest mass. The measured-versus-model parity record is retained; no prediction is served.
- **Phase 30 decision:** B - removed completely - POST /api/workflows/harvest-prediction/run (now 410), the workflow catalogue entry (now status unavailable), the harvest UI tab, and every test that asserted a served prediction
- **Residual capability:** Measured-versus-predicted parity (GET .../parity) and the decision record (GET .../capability) remain readable.

### Energy and mass cost of a described mission  `mission-energy`

- **Needed:** Power draw per fixture, thermal load and resupply mass figures for real flight hardware
- **Available:** None. There is no power, thermal or logistics model in the repository.
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** Out of scope for the current product; would need hardware specifications from a mission integrator.
- **Current status:** open and out of scope; no energy claim is made anywhere in the API

### Nutrient solution management  `nutrient-balance`

- **Needed:** Ion concentrations, uptake rates and EC/pH response per crop
- **Available:** None
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** Out of scope. Would be a separate model with its own data requirement.
- **Current status:** open and out of scope

### Siting for a future climate rather than the observed recent past  `long-run-climate`

- **Needed:** Downscaled climate projections at the candidate sites
- **Available:** Observed reanalysis 2018-2025 only
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** NASA NEX-GDDP-CMIP6 is the standard product and is open; it was outside this phase's scope because the reference ET0 study needed observed weather, not projections.
- **Current status:** open; the product makes no future-climate claim

### Yield loss from crop water deficit (crop-specific Ky)  `crop-water-response-ky`

- **Needed:** Measured yield at two or more water-supply levels for the same crop and cultivar, with enough levels to fit a Ky slope and an independent study to validate it
- **Available:** FAO-56 tabulated Ky values exist for many field crops but not for the three crops served here, and no open dataset recovered in Phase 30 measures lettuce, tomato or radish yield across irrigation levels. Two candidate sources were screened and rejected: a China remote-sensing yield/water-productivity dataset (no deficit treatment) and a mandarin regulated-deficit-irrigation trial (wrong species, no Ky).
- **Gap type:** no-data
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** A controlled deficit-irrigation experiment per crop with at least four water levels and a measured harvest. Ky must never be transferred between crops, so one experiment closes one cell of the matrix.
- **Current status:** open; the FAO-56 water balance and the irrigation schedule remain, and no yield-loss claim is made anywhere in the platform
- **Phase 30 decision:** B - no yield-loss claim retained - no deficit-yield model was built and no Ky value is exposed; the water workflow continues to report demand, deficit and irrigation scheduling only
- **Residual capability:** Reference ET0, crop demand, deficit accounting and irrigation scheduling, all labelled as computed rather than measured.

### Calibrated prediction intervals with measured coverage  `prediction-intervals-independent-coverage`

- **Needed:** Enough independent evaluation points to estimate coverage per crop and per experiment group without reusing the selection data
- **Available:** The two Phase 30 evaluations produce intervals, but with 6 and 8 independent holdout points: a coverage estimate from eight points has a binomial half-width of roughly +/-0.3, so it cannot support a coverage guarantee.
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** More independent experiments, or an external evaluation set with documented protocol. Neither exists for the crops served here.
- **Current status:** open; intervals are reported as descriptive and no coverage is advertised. The removed harvest workflow's interval spanned a factor of 29, which is a measured statement about how little the data supports. Phase 34 measured the question instead of leaving it open-ended: every served interval was held against a campaign no fit saw, two of five models covered none of it, and the cards now state their own coverage instead of implying it. The interval is still descriptive and no coverage guarantee is offered.
- **Phase 30 decision:** documented, not closed - train/selection/holdout separation was enforced and recorded in both Phase 30 artifacts; the harvest workflow was removed rather than given a wider interval
- **Residual capability:** Descriptive intervals on measured group means.
- **Phase 34 decision:** measured, not closed - The coverage question was answered by measurement rather than by more data: each served 90 % interval was held against a campaign no fit saw, and the mizuna conformal radius was calibrated on one flight campaign and evaluated on the other in both directions. Evidence: ml/evaluation/phase34_cross_campaign_coverage.json.
    - `lettuce-earth-growth-v1`: 0 of 6 independent PeerJ 2024 treatment means covered, ratio median 3.655 (1.905-5.493)
    - `lettuce-earth-growth-v2`: 0 of 6 covered, ratio median 3.212 (1.674-5.375)
    - `lettuce-earth-growth-v3`: 6 of 6 covered, ratio median 1.163 (0.606-1.863) - coverage, not accuracy; its Touliatos holdout still fails the 30 % criterion
    - `mizuna-microbial-load-v1`: 107 of 123 samples covered across both directions, pooled 0.8699 (nominal 0.90)
    - `mizuna-microbial-relative-load-v2`: 110 of 123 covered, pooled 0.8943 (nominal 0.90)
- **Why this is still open:** Coverage of six correlated greenhouse means is not a coverage guarantee, two flight campaigns do not estimate a campaign-offset distribution, and two of the five models fail the check outright. The interval stays descriptive; the cards now state the measurement instead of leaving the scope unstated.

## The two that matter most

**`measured-eta`** and **`independent-et0`** decide how much the ET0 work is worth. The first says the platform computes a reference flux and cannot measure a crop's actual water use. The second says the target it validates against is one provider's reanalysis. Fixing the second is cheap and mechanical (an ERA5-Land token). Fixing the first requires an experiment.
