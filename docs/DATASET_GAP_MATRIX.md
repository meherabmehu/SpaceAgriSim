# SpaceAgriSim Dataset Gap Matrix

Generated from `data/research/dataset_gap_matrix.json` on 2026-11-09 by `ml/research/build_gap_matrix.py`. Edit the JSON, not this file.

Every capability SpaceAgriSim claims or is asked about, matched against the data that would actually be needed to support it. A gap here is a statement about evidence, not a to-do list: several will stay open on purpose because the data does not exist at any price.

**12 gaps recorded: blocking: 3, major: 4, minor: 5.**

None of them is closed. The point of the matrix is that each open gap has a named consequence for what the product is allowed to claim, and the product states that consequence rather than papering over it.

## Severity

| Severity | Meaning | Count |
|---|---|---|
| **blocking** | a claim in the product cannot be supported at all without this | 3 |
| **major** | the claim is supportable only with a stated limitation that a user would notice | 4 |
| **minor** | the claim is supportable; this would improve accuracy or resolution | 5 |

## Matrix

| # | Capability | What is needed | Severity | Gap type | Status |
|---|---|---|---|---|---|
| 1 | Predicted crop water use in litres per plant per day | Measured evapotranspiration or sap-flow/lysimeter water use for the modelled crops at plant scale | **blocking** | no-data | open and blocking. The ingestion pipeline and the pre-registered protocol exist and are tested |
| 2 | The claim that the ET0 target is itself correct | A weather or ET0 source that does not share MERRA-2 lineage with POWER, and a measured latent-heat series to convert mutual agreement into physical truth | **major** | partially-addressed | open, partially addressed: disagreement now decomposed into formulation (0.273 mm/d), forcing (0.519) and implementation (+0.009) - the residual is weather, not code - but every leg is either a reanalysis or a temperature-only point method, so nothing here is field validation of the ET0 magnitude |
| 3 | Effect of Mars or lunar gravity on crop growth | Yield or growth measurements at gravity levels other than 1 g, with the same cultivar and protocol as the terrestrial baseline | **blocking** | no-data | open and permanently so for the current data landscape |
| 4 | Response to specific LED spectra and photoperiods | Biomass or yield response surfaces across spectra, PPFD and photoperiod for each supported crop | **major** | insufficient | open |
| 5 | Root-zone water status in a hydroponic or substrate system | Substrate water content, irrigation schedule and drainage fraction at high temporal resolution | **major** | no-data | open |
| 6 | Heat-stress and VPD excursion claims | Hourly temperature, humidity and radiation at the site | **minor** | too-coarse | open |
| 7 | Cultivar-specific growth parameters | Cultivar identity and calibrated growth parameters per cultivar | **major** | insufficient | open |
| 8 | Plant health or growth stage from imagery | Labelled canopy imagery from the platform's own camera geometry | **minor** | no-data | open and deliberately not addressed |
| 9 | Predicted harvest mass per plant | Measured harvest mass with the same covariates the model uses | **blocking** | insufficient | open |
| 10 | Energy and mass cost of a described mission | Power draw per fixture, thermal load and resupply mass figures for real flight hardware | **minor** | no-data | open and out of scope |
| 11 | Nutrient solution management | Ion concentrations, uptake rates and EC/pH response per crop | **minor** | no-data | open and out of scope |
| 12 | Siting for a future climate rather than the observed recent past | Downscaled climate projections at the candidate sites | **minor** | no-data | open |

## Detail

### Predicted crop water use in litres per plant per day  `measured-eta`

- **Needed:** Measured evapotranspiration or sap-flow/lysimeter water use for the modelled crops at plant scale
- **Available:** Reference ET0 computed from reanalysis (FAO-56 Penman-Monteith, now cross-validated against four sources), plus a learned emulator of that same computed quantity, plus a schema and an 18-check ingestion validator for a future water-use trial. Still no measured crop water use of any kind.
- **Gap type:** no-data
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** A lysimeter or gravimetric water-use trial in the target growth system. No open dataset measures per-plant water use in a controlled-environment facility for lettuce or mizuna; this is a measurement to commission, not a download. New ingestion apparatus does not change the status: a validator can reject a bad measurement, it cannot create one.
- **Current status:** open and blocking. The ingestion pipeline and the pre-registered protocol exist and are tested; zero measurements exist, so the ~60 % difference between the two water paths remains unarbitrated by data.

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
- **Current status:** open and permanently so for the current data landscape; the product must not present a gravity response as calibrated

### Response to specific LED spectra and photoperiods  `led-spectrum-response`

- **Needed:** Biomass or yield response surfaces across spectra, PPFD and photoperiod for each supported crop
- **Available:** One study, six observations, one crop (lettuce), light intensity and temperature axes only
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** The published CEA literature is large but fragmented: hundreds of small papers, no shared protocol, rarely any raw data. A meta-analysis with study-level random effects is the realistic route, and it needs a person reading papers, not an API.
- **Current status:** open; DLI is computed from measured irradiance and the light-response coefficient is a literature estimate with a stated range

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
- **Current status:** open; the model is registered as trained-exploratory and the failed criterion is exposed through the API

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

## The two that matter most

**`measured-eta`** and **`independent-et0`** decide how much the ET0 work is worth. The first says the platform computes a reference flux and cannot measure a crop's actual water use. The second says the target it validates against is one provider's reanalysis. Fixing the second is cheap and mechanical (an ERA5-Land token). Fixing the first requires an experiment.
