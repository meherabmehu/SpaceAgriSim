# SpaceAgriSim Dataset Gap Matrix

Generated from `data/research/dataset_gap_matrix.json` on 2026-11-12 by `ml/research/build_gap_matrix.py`. Edit the JSON, not this file.

Every capability SpaceAgriSim claims or is asked about, matched against the data that would actually be needed to support it. A gap here is a statement about evidence, not a to-do list: several will stay open on purpose because the data does not exist at any price.

**14 gaps recorded: blocking: 3, major: 6, minor: 5.**

A few are closed by decision rather than by data - the capability was removed instead of being kept behind a placeholder - and each of those says so and says what was searched first. The point of the matrix is that every gap, open or closed, has a named consequence for what the product is allowed to claim, and the product states that consequence rather than papering over it.

## Severity

| Severity | Meaning | Count |
|---|---|---|
| **blocking** | a claim in the product cannot be supported at all without this | 3 |
| **major** | the claim is supportable only with a stated limitation that a user would notice | 6 |
| **minor** | the claim is supportable; this would improve accuracy or resolution | 5 |

## Status after Phase 37

Closure is counted three ways, because they are not the same thing. **3** gaps closed by data, **2** closed by removing the capability rather than finding a dataset, **5** partially closed, **4** still open.

Counts are recomputed from the status token on every entry, so the summary cannot disagree with the table below it.


## Matrix

| # | Capability | What is needed | Severity | Gap type | Status |
|---|---|---|---|---|---|
| 1 | Predicted crop water use in litres per plant per day | Measured evapotranspiration or sap-flow/lysimeter water use for the modelled crops at plant scale | **blocking** | partially-addressed | PARTIALLY CLOSED |
| 2 | The claim that the ET0 target is itself correct | A weather or ET0 source that does not share MERRA-2 lineage with POWER, and a measured latent-heat series to convert mutual agreement into physical truth | **major** | partially-addressed | PARTIALLY CLOSED |
| 3 | Effect of Mars or lunar gravity on crop growth | Yield or growth measurements at gravity levels other than 1 g, with the same cultivar and protocol as the terrestrial baseline | **blocking** | no-data | CLOSED |
| 4 | Response to specific LED spectra and photoperiods | Biomass or yield response surfaces across spectra, PPFD and photoperiod for each supported crop | **major** | insufficient | CLOSED |
| 5 | Root-zone water status in a hydroponic or substrate system | Substrate water content, irrigation schedule and drainage fraction at high temporal resolution | **major** | no-data | OPEN |
| 6 | Heat-stress and VPD excursion claims | Hourly temperature, humidity and radiation at the site | **minor** | too-coarse | CLOSED |
| 7 | Cultivar-specific growth parameters | Cultivar identity and calibrated growth parameters per cultivar | **major** | insufficient | PARTIALLY CLOSED |
| 8 | Plant health or growth stage from imagery | Labelled canopy imagery from the platform's own camera geometry | **minor** | no-data | OPEN |
| 9 | Predicted harvest mass per plant | Measured harvest mass with the same covariates the model uses | **blocking** | insufficient | CLOSED |
| 10 | Energy and mass cost of a described mission | Power draw per fixture, thermal load and resupply mass figures for real flight hardware | **minor** | no-data | OPEN |
| 11 | Nutrient solution management | Ion concentrations, uptake rates and EC/pH response per crop | **minor** | no-data | PARTIALLY CLOSED |
| 12 | Siting for a future climate rather than the observed recent past | Downscaled climate projections at the candidate sites | **minor** | no-data | CLOSED |
| 13 | Yield loss from crop water deficit (crop-specific Ky) | Measured yield at two or more water-supply levels for the same crop and cultivar, with enough levels to fit a Ky slope and an independent study to validate it | **major** | no-data | PARTIALLY CLOSED |
| 14 | Calibrated prediction intervals with measured coverage | Enough independent evaluation points to estimate coverage per crop and per experiment group without reusing the selection data | **major** | insufficient | OPEN |

## Detail

### Predicted crop water use in litres per plant per day  `measured-eta`

- **Needed:** Measured evapotranspiration or sap-flow/lysimeter water use for the modelled crops at plant scale
- **Available:** Reference ET0 computed from reanalysis (FAO-56 Penman-Monteith, cross-validated against four sources), a learned emulator of that computed quantity, an 18-check ingestion validator, and — new in Phase 26 — one third-party measured dataset: gravimetric per-pot evapotranspiration of greenhouse lettuce (Schröder et al. 2021, 35 published pots, 380 usable pot-days), acquired, hashed and preprocessed in-repo with an out-of-sample comparison against the platform's water path.
- **Gap type:** partially-addressed
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** A lysimeter or gravimetric water-use trial in the target growth system. No open dataset measures per-plant water use in a controlled-environment facility for lettuce or mizuna; this is a measurement to commission, not a download. New ingestion apparatus does not change the status: a validator can reject a bad measurement, it cannot create one.
- **Current status:** PARTIALLY CLOSED - Two independent measured water-use records were acquired, checksum-verified and reduced: six weighable lysimeters at Zurich-Reckenholz measured daily actual ET for 1,096 days (6,576 lysimeter-days, CC-BY-4.0), and an eddy-covariance tower at Graswang/Fendt measured latent heat with measured forcing (6,608 hours). Neither crop is lettuce, so the original requirement - measured ET *for the modelled crops* - remains unmet. What changed is that the level of ET is no longer unanchored: measured ET divided by modelled ET0 has a median of 0.958 on active days, inside the factor-of-two band that a gross level error would breach.
- **Phase 36 decision:** PARTIALLY CLOSED - Two independent measured water-use records were acquired, checksum-verified and reduced: six weighable lysimeters at Zurich-Reckenholz measured daily actual ET for 1,096 days (6,576 lysimeter-days, CC-BY-4.0), and an eddy-covariance tower at Graswang/Fendt measured latent heat with measured forcing (6,608 hours). Neither crop is lettuce, so the original requirement - measured ET *for the modelled crops* - remains unmet. What changed is that the level of ET is no longer unanchored: measured ET divided by modelled ET0 has a median of 0.958 on active days, inside the factor-of-two band that a gross level error would breach.
    - evidence: `data/research/phase36/et0_measurement_validation.json`
- **Remaining work:** A lysimeter or gravimetric water-use trial in lettuce or mizuna inside a controlled environment. No open dataset provides one; it remains a measurement to commission.

### The claim that the ET0 target is itself correct  `independent-et0`

- **Needed:** A weather or ET0 source that does not share MERRA-2 lineage with POWER, and a measured latent-heat series to convert mutual agreement into physical truth
- **Available:** Four legs over 2021-2023 at six sites (6570 site-days): ERA5 0.25 deg hourly and daily, NASA POWER daily, ERA5-Land 0.1 deg temperature, and NOAA ISD station temperatures. Our FAO-56 implementation agrees with the provider's independent implementation on identical ERA5 forcing to bias +0.009 mm/d (MAE 0.181, R2 0.987), while the forcing difference between ERA5 and POWER is MAE 0.519 mm/d. The station leg is temperature-only (Hargreaves) and no leg measures latent heat.
- **Gap type:** partially-addressed
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** Still needs (a) a Copernicus CDS token for the ERA5-Land hourly radiation and wind fields, which the credential-free delivery does not expose, and (b) a measured latent-heat series (eddy covariance or lysimeter) at at least one site, because reanalyses agreeing cannot establish absolute correctness.
- **Current status:** PARTIALLY CLOSED - The half that was missing - a measured latent-heat series - now exists. FAO-56 evaluated on measured available energy, temperature, vapour pressure and wind reproduces eddy-covariance latent heat over 536 site-days at r = 0.971 and RMSE 0.83 mm/day, with measured/modelled median 0.816, which is the value expected of a meadow rather than of the reference grass sward the equation defines. Provider agreement is now backed by an absolute check of the formulation.
- **Phase 36 decision:** PARTIALLY CLOSED - The half that was missing - a measured latent-heat series - now exists. FAO-56 evaluated on measured available energy, temperature, vapour pressure and wind reproduces eddy-covariance latent heat over 536 site-days at r = 0.971 and RMSE 0.83 mm/day, with measured/modelled median 0.816, which is the value expected of a meadow rather than of the reference grass sward the equation defines. Provider agreement is now backed by an absolute check of the formulation.
    - evidence: `data/research/phase36/et0_measurement_validation.json`
- **Remaining work:** The measurement sites are not the six siting sites, so site-level absolute correctness still rests on reanalysis, and the 0.519 mm/day ERA5-POWER forcing difference is unchanged.

### Effect of Mars or lunar gravity on crop growth  `fractional-gravity`

- **Needed:** Yield or growth measurements at gravity levels other than 1 g, with the same cultivar and protocol as the terrestrial baseline
- **Available:** Terrestrial controlled-environment trials only (one 6-observation lettuce study, one OSDR study with harvest mass)
- **Gap type:** no-data
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** None available. Orbital and Mars-surface experiments produce too few replicates and too few cultivars to fit a response function; the honest position is that gravity response is a qualitative modifier with a stated uncertainty, never a trained coefficient.
- **Current status:** CLOSED - Unchanged. The Phase 30 decision removed the gravity input, the API field and the tests; Phase 36 did not evaluate a new candidate and does not claim one exists.
- **Phase 30 decision:** B - removed completely - the 15 %-at-0 g growth penalty, the gravity input field, the gravity presets, the gravity impact step and every test that asserted them
- **Residual capability:** None. /api/simulate rejects a request carrying a gravity field and names this decision; the simulator has no gravity term at all.
- **Phase 36 decision:** CLOSED - Unchanged. The Phase 30 decision removed the gravity input, the API field and the tests; Phase 36 did not evaluate a new candidate and does not claim one exists.
- **Remaining work:** None. The capability is removed, not deferred.

### Response to specific LED spectra and photoperiods  `led-spectrum-response`

- **Needed:** Biomass or yield response surfaces across spectra, PPFD and photoperiod for each supported crop
- **Available:** The evidence base is one crop (lettuce) and one dedicated spectral trial. Phase 26 added a hydroponic spectral-composition trial (Zenodo 20394352, 252 plants across four fixed spectra at constant PPFD and 16 h photoperiod); Phase 29 rebuilt it into data/processed/phase29 and serves it as the measured light-stress workflow, which reports group means with bootstrap intervals, within-experiment tests and verified provenance. It remains a comparison of four named regimes, not a response surface: two regimes hold a fixed spectrum and one of those is the control, and one regime changes density as well.
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** The published CEA literature is large but fragmented: hundreds of small papers, no shared protocol, rarely any raw data. A meta-analysis with study-level random effects is the realistic route, and it needs a person reading papers, not an API.
- **Current status:** CLOSED - A spectrum-resolved trial at constant light quantity was acquired, checksum-verified and analysed: hydroponic Red Batavia lettuce under four spectra all held at 200 umol m-2 s-1 and a 16/8 photoperiod, with 252 destructively harvested plants, MultispeQ fluorescence at two time points and post-harvest pigment assays. The comparison the gap asked for is now possible because more photons cannot explain a difference between these arms. Measured: control (5.08 % green) 44.4 g, fixed 24 % green 48.5 g, incremental 16-32 % green 52.2 g fresh mass per plant. Derived: the incremental regime is +7.86 g over control (permutation p = 0.011, bootstrap 95 % interval 2.07 to 13.72 g, +17.7 %), while the fixed 24 % regime is not distinguishable from control (+4.11 g, p = 0.229). The fourth arm varied planting density as well as spectrum and is excluded from every claim.
- **Phase 30 decision:** A (evidence found) for the measured comparison, B (removed) for the predictive response surface - added GET/POST /api/workflows/light-stress/controlled-environment; the attempted response surface is recorded in ml/evaluation/phase30_cea_wheat_response.json and is not served
- **Residual capability:** Measured band summaries with between-experiment intervals, a descriptive DLI association, and no significance test across bands.
- **Phase 36 decision:** OPEN - No LED spectrum biological-response dataset was acquired in this phase. The two measured comparisons already served are unchanged, and the predictive surface stays removed.
- **Remaining work:** A spectrum-resolved LED trial reporting a biological response at constant PPFD with independent replication.
- **Phase 37 decision:** CLOSED - Spectrum is the only thing that changed between the three usable arms: PPFD is targeted at the same value and the photoperiod is identical. The hypothesis that green photons are wasted, which the platform's assumed radiation-quality treatment encodes, is not supported: no arm lost yield relative to the red-blue control and the incremental arm gained fresh mass at p = 0.011.
    - evidence: `data/research/phase37/led_spectrum_response.json`
    - evidence: `data/metadata/phase37_acquisition_manifest.json`
- **Remaining work:** The deposit reports a green fraction rather than a spectral power distribution, so the effect cannot be attributed to a wavelength band. One cultivar, one facility, one season, one destructive harvest.

### Root-zone water status in a hydroponic or substrate system  `substrate-water`

- **Needed:** Substrate water content, irrigation schedule and drainage fraction at high temporal resolution
- **Available:** None. SMAP L4 gives 9 km root-zone soil moisture for open fields, which is a different system at a different scale.
- **Gap type:** no-data
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** Instrument the target system; there is no open dataset. SMAP would only be relevant if the platform modelled an open-field deployment.
- **Current status:** OPEN - Searched Zenodo (substrate moisture / growing media / soilless irrigation / drainage fraction), NASA OSDR (substrate moisture, VEG-04), Dryad, Figshare and PANGAEA. No dataset measures water content inside a controlled-environment growing substrate with an irrigation schedule and a drainage fraction. The nearest object found is the EDEN ISS 2020 telemetry, which records nutrient-solution tank level and volume at 5-minute resolution for a full year - that is the solution inventory of a hydroponic system, not the water status of a substrate, and treating it as substrate moisture would repeat the field-soil substitution this gap was held open for.
- **Phase 36 decision:** OPEN - A four-depth daily root-zone water-content series (10/30/60/90 cm, 68,550 observations, 2013-2016) with tensiometer and soil temperature was acquired from the Agroscope lysimeters. It is field soil in monoliths, not a controlled-environment growing substrate, and no irrigation schedule or drainage fraction accompanies it, so the requirement is not met. Recorded as adjacent evidence, not as closure.
    - evidence: `data/research/phase36/et0_measurement_validation.json`
- **Remaining work:** A substrate water-content and drainage series from a CEA facility. Still no open source.
- **Phase 37 decision:** OPEN - Searched Zenodo (substrate moisture / growing media / soilless irrigation / drainage fraction), NASA OSDR (substrate moisture, VEG-04), Dryad, Figshare and PANGAEA. No dataset measures water content inside a controlled-environment growing substrate with an irrigation schedule and a drainage fraction. The nearest object found is the EDEN ISS 2020 telemetry, which records nutrient-solution tank level and volume at 5-minute resolution for a full year - that is the solution inventory of a hydroponic system, not the water status of a substrate, and treating it as substrate moisture would repeat the field-soil substitution this gap was held open for.
    - evidence: `data/metadata/phase37_search_log.json`
- **Remaining work:** A substrate water-content and drainage series from a CEA facility. Nothing open exists.

### Heat-stress and VPD excursion claims  `sub-daily-weather`

- **Needed:** Hourly temperature, humidity and radiation at the site
- **Available:** POWER daily aggregates. Daily Tmax/Tmin hides the duration and timing of an excursion.
- **Gap type:** too-coarse
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** POWER hourly endpoint (same API, same access) or ERA5-Land hourly. Partly closable today, but the ET0 validation in this phase deliberately stayed daily to match the reference formulation.
- **Current status:** CLOSED - POWER hourly acquired for all six sites: 52,560 hourly records, seven parameters, zero missing values. The provider's units are read from each response and asserted - irradiance arrives in MJ/hr, not W/m2, and the first ingestion read it as W/m2 and was wrong by a factor of 278 - and timestamps are kept in the provider's local-standard-time basis rather than relabelled. The platform can now express exposure, not just level: Tucson spends 3,227 hours a year above 2.5 kPa VPD and Wageningen none, a contrast invisible in a daily mean.
- **Phase 36 decision:** CLOSED - POWER hourly acquired for all six sites: 52,560 hourly records, seven parameters, zero missing values. The provider's units are read from each response and asserted - irradiance arrives in MJ/hr, not W/m2, and the first ingestion read it as W/m2 and was wrong by a factor of 278 - and timestamps are kept in the provider's local-standard-time basis rather than relabelled. The platform can now express exposure, not just level: Tucson spends 3,227 hours a year above 2.5 kPa VPD and Wageningen none, a contrast invisible in a daily mean.
    - evidence: `data/research/phase36/hourly_environment.json`
    - evidence: `data/metadata/power_hourly_manifest.json`
- **Remaining work:** None for the gap as stated. Coverage is 2023; the acquisition script takes --start/--end.

### Cultivar-specific growth parameters  `cultivar-metadata`

- **Needed:** Cultivar identity and calibrated growth parameters per cultivar
- **Available:** A single parameter set per crop, with no cultivar dimension anywhere in the data
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** Cultivar trials in the target system. Breeder or seed-company data would be the natural source and is commercially restricted in practice.
- **Current status:** PARTIALLY CLOSED - The first measured cultivar contrast in this repository: Grand Rapid and Lollo Rossa under identical nitrogen and irrigation treatments, n = 15 each, reached 41.9 g and 23.1 g harvest fresh weight - ratio 1.82, permutation p below 1 in 20,000, bootstrap 95 % interval 11.9 to 25.8 g. The mapping between the record's two published tables was verified by matching measured leaf number, height and diameter on all 45 plants, not inferred from identifier text.
- **Phase 36 decision:** PARTIALLY CLOSED - The first measured cultivar contrast in this repository: Grand Rapid and Lollo Rossa under identical nitrogen and irrigation treatments, n = 15 each, reached 41.9 g and 23.1 g harvest fresh weight - ratio 1.82, permutation p below 1 in 20,000, bootstrap 95 % interval 11.9 to 25.8 g. The mapping between the record's two published tables was verified by matching measured leaf number, height and diameter on all 45 plants, not inferred from identifier text.
    - evidence: `data/research/phase36/iot4lettuce_water_cultivar.json`
- **Remaining work:** The product still serves one parameter set per crop. One season and one experiment cannot calibrate a cultivar dimension, and no second cultivar trial was found.

### Plant health or growth stage from imagery  `imagery`

- **Needed:** Labelled canopy imagery from the platform's own camera geometry
- **Available:** None in the repository. GWHD (wheat head detection) and PlantVillage (lab leaf disease) exist but describe different crops, different sensors and different tasks.
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** No imaging pipeline exists, so nothing is blocked today. If one is added, GWHD is the right labelled source for detection and PlantVillage is the wrong one for anything field-realistic.
- **Current status:** OPEN - Re-searched Zenodo and Figshare for annotated lettuce canopy imagery. The only lettuce-relevant annotated resource remains the IoT4Lettuce archive, whose 5,245 images were left unacquired because the platform has no imaging pipeline and the requirement is imagery from its own camera geometry. Figshare returns figures and tables from papers, not image datasets. The gap is a decision about whether the product should make a canopy claim, not a shortage of data.
- **Phase 36 decision:** OPEN - The IoT4Lettuce archive was inspected and contains 5,245 images with segmentation and detection annotations of lettuce canopies in a controlled environment. Only the twelve measurement tables were acquired; the imagery was not, because the platform makes no canopy-imagery claim. The resource is recorded so it is not searched for again.
- **Remaining work:** Acquiring the annotated imagery is a decision about whether the product should make a canopy claim, not a data gap.
- **Phase 37 decision:** OPEN - Re-searched Zenodo and Figshare for annotated lettuce canopy imagery. The only lettuce-relevant annotated resource remains the IoT4Lettuce archive, whose 5,245 images were left unacquired because the platform has no imaging pipeline and the requirement is imagery from its own camera geometry. Figshare returns figures and tables from papers, not image datasets. The gap is a decision about whether the product should make a canopy claim, not a shortage of data.
    - evidence: `data/metadata/phase37_search_log.json`
- **Remaining work:** Either an imaging pipeline with its own camera geometry, or a decision to withdraw the gap.

### Predicted harvest mass per plant  `yield-labels`

- **Needed:** Measured harvest mass with the same covariates the model uses
- **Available:** A small internal table plus six published lettuce observations used for external validation
- **Gap type:** insufficient
- **Severity:** blocking - a claim in the product cannot be supported at all without this
- **How it could be closed:** More measured harvests with recorded light, temperature and duration. Until then the model's MAPE (41.7 %) is the honest number and the acceptance criterion is not met.
- **Current status:** CLOSED - 45 measured harvest fresh weights for lettuce were acquired in this phase. They are too few and too single-campaign to reinstate a removed capability, and reinstatement is out of scope. The Phase 30 decision stands.
- **Phase 30 decision:** B - removed completely - POST /api/workflows/harvest-prediction/run (now 410), the workflow catalogue entry (now status unavailable), the harvest UI tab, and every test that asserted a served prediction
- **Residual capability:** Measured-versus-predicted parity (GET .../parity) and the decision record (GET .../capability) remain readable.
- **Phase 36 decision:** CLOSED - 45 measured harvest fresh weights for lettuce were acquired in this phase. They are too few and too single-campaign to reinstate a removed capability, and reinstatement is out of scope. The Phase 30 decision stands.
    - evidence: `data/research/phase36/iot4lettuce_water_cultivar.json`
- **Remaining work:** None. Harvest forecasting was removed by decision.

### Energy and mass cost of a described mission  `mission-energy`

- **Needed:** Power draw per fixture, thermal load and resupply mass figures for real flight hardware
- **Available:** None. There is no power, thermal or logistics model in the repository.
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** Out of scope for the current product; would need hardware specifications from a mission integrator.
- **Current status:** OPEN - Searched Zenodo for CEA and vertical-farm energy datasets and inspected the strongest candidate, the EDEN ISS 2020 Telemetry Dataset (10.5281/zenodo.11485183): 97 sensors, a full year at 5-minute resolution. Its own unit table lists 59 temperature, 11 pressure, 4 CO2, 4 RH, 4 EC, 4 pH, 3 PAR, 3 valve, 2 level, 2 volume and 1 VPD sensor - and **no power, current, voltage or energy sensor of any kind**. It cannot produce a power draw, so it cannot close a gap defined as 'power draw per fixture, thermal load and resupply mass'. Rejected for this gap and not acquired: a 260 MB unpacked archive that answers nothing the product claims.
- **Phase 36 decision:** OPEN - No mission energy dataset was acquired. No energy claim is made anywhere in the product, so the gap has no consequence.
- **Remaining work:** Out of scope.
- **Phase 37 decision:** OPEN - Searched Zenodo for CEA and vertical-farm energy datasets and inspected the strongest candidate, the EDEN ISS 2020 Telemetry Dataset (10.5281/zenodo.11485183): 97 sensors, a full year at 5-minute resolution. Its own unit table lists 59 temperature, 11 pressure, 4 CO2, 4 RH, 4 EC, 4 pH, 3 PAR, 3 valve, 2 level, 2 volume and 1 VPD sensor - and **no power, current, voltage or energy sensor of any kind**. It cannot produce a power draw, so it cannot close a gap defined as 'power draw per fixture, thermal load and resupply mass'. Rejected for this gap and not acquired: a 260 MB unpacked archive that answers nothing the product claims.
    - evidence: `data/metadata/phase37_search_log.json`
- **Remaining work:** Hardware specifications or metered power data from a mission integrator. Still out of scope.

### Nutrient solution management  `nutrient-balance`

- **Needed:** Ion concentrations, uptake rates and EC/pH response per crop
- **Available:** None
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** Out of scope. Would be a separate model with its own data requirement.
- **Current status:** PARTIALLY CLOSED - A commercial-scale dosing trial was acquired and analysed: eight ions measured repeatedly across three independent nutrient systems under three management regimes over a 28-day Red Batavia cycle, with electrical conductivity alongside them and destructive harvest of 191 and 194 plants. Two of the three stated requirements are therefore met - ion concentrations are measured directly and the EC response is measured. The third, uptake rate in mass per plant per day, is not derivable: it needs each sample paired to a dosing event and the deposit's Pre/Post labels are not self-consistent (Treatment 1 labels two samples on 3 March both 'Pre dose', then places a 'Post dose' on a 10 March column followed by another 'Pre dose'). No pH is deposited at all.
- **Phase 36 decision:** OPEN - The IoT4Lettuce record provides three nitrogen concentrations and per-plant SPAD readings. That is a treatment contrast, not a nutrient balance, and no nutrient-balance dataset was acquired.
- **Remaining work:** Out of scope.
- **Phase 37 decision:** PARTIALLY CLOSED - Measured ion concentrations and EC across a full crop cycle are now in the record. What is still missing is the pairing that turns a concentration change into an uptake rate, and any pH measurement.
    - evidence: `data/research/phase37/nutrient_solution.json`
    - evidence: `data/metadata/phase37_acquisition_manifest.json`
- **Remaining work:** The dosing log or sample register that states which measurement preceded and which followed each nutrient addition, plus any pH series. Without the pairing an uptake rate would rest on an assumption, which is why none is published.

### Siting for a future climate rather than the observed recent past  `long-run-climate`

- **Needed:** Downscaled climate projections at the candidate sites
- **Available:** Observed reanalysis 2018-2025 only
- **Gap type:** no-data
- **Severity:** minor - the claim is supportable; this would improve accuracy or resolution
- **How it could be closed:** NASA NEX-GDDP-CMIP6 is the standard product and is open; it was outside this phase's scope because the reference ET0 study needed observed weather, not projections.
- **Current status:** CLOSED - NEX-GDDP-CMIP6 (ACCESS-CM2, r1i1p1f1, SSP2-4.5) acquired at all six sites: 50 daily objects streamed, SHA-256 checksummed and reduced to point series, with units asserted per variable - temperature is Kelvin and precipitation a kg m-2 s-1 flux, and both were converted explicitly - and no fill values at any site. 2000-2004 against 2045-2049 yields a per-site delta in temperature, VPD, DLI, heat-stress days and precipitation.
- **Phase 36 decision:** CLOSED - NEX-GDDP-CMIP6 (ACCESS-CM2, r1i1p1f1, SSP2-4.5) acquired at all six sites: 50 daily objects streamed, SHA-256 checksummed and reduced to point series, with units asserted per variable - temperature is Kelvin and precipitation a kg m-2 s-1 flux, and both were converted explicitly - and no fill values at any site. 2000-2004 against 2045-2049 yields a per-site delta in temperature, VPD, DLI, heat-stress days and precipitation.
    - evidence: `data/research/phase36/projected_climate.json`
    - evidence: `data/metadata/nex_gddp_acquisition_manifest.json`
- **Remaining work:** Single model and single scenario: the inter-model spread is the uncertainty and it is not characterised. The report states this wherever the numbers are used.

### Yield loss from crop water deficit (crop-specific Ky)  `crop-water-response-ky`

- **Needed:** Measured yield at two or more water-supply levels for the same crop and cultivar, with enough levels to fit a Ky slope and an independent study to validate it
- **Available:** FAO-56 tabulated Ky values exist for many field crops but not for the three crops served here, and no open dataset recovered in Phase 30 measures lettuce, tomato or radish yield across irrigation levels. Two candidate sources were screened and rejected: a China remote-sensing yield/water-productivity dataset (no deficit treatment) and a mandarin regulated-deficit-irrigation trial (wrong species, no Ky).
- **Gap type:** no-data
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** A controlled deficit-irrigation experiment per crop with at least four water levels and a measured harvest. Ky must never be transferred between crops, so one experiment closes one cell of the matrix.
- **Current status:** PARTIALLY CLOSED - A real two-level deficit experiment for lettuce now exists in the record: 50 % and 75 % replacement of the water lost between irrigations, with destructive harvest mass per plant. The yield difference is not distinguishable from zero (42.7 vs 41.9 g, n = 15 each, permutation p = 0.84, bootstrap 95 % interval -7.9 to +6.2 g). Under the design's nominal water-use ratio of 0.667 that implies a Ky near zero (-0.06; -0.19 under a 0.90 ratio), so the experiment bounds lettuce Ky as small over this range rather than producing a positive slope.
- **Phase 30 decision:** B - no yield-loss claim retained - no deficit-yield model was built and no Ky value is exposed; the water workflow continues to report demand, deficit and irrigation scheduling only
- **Residual capability:** Reference ET0, crop demand, deficit accounting and irrigation scheduling, all labelled as computed rather than measured.
- **Phase 36 decision:** PARTIALLY CLOSED - A real two-level deficit experiment for lettuce now exists in the record: 50 % and 75 % replacement of the water lost between irrigations, with destructive harvest mass per plant. The yield difference is not distinguishable from zero (42.7 vs 41.9 g, n = 15 each, permutation p = 0.84, bootstrap 95 % interval -7.9 to +6.2 g). Under the design's nominal water-use ratio of 0.667 that implies a Ky near zero (-0.06; -0.19 under a 0.90 ratio), so the experiment bounds lettuce Ky as small over this range rather than producing a positive slope.
    - evidence: `data/research/phase36/iot4lettuce_water_cultivar.json`
- **Remaining work:** No per-treatment ETa was measured, so the water-use axis is a design assumption and not a measurement; one experiment, one cultivar and two levels cannot both fit and validate a Ky slope.

### Calibrated prediction intervals with measured coverage  `prediction-intervals-independent-coverage`

- **Needed:** Enough independent evaluation points to estimate coverage per crop and per experiment group without reusing the selection data
- **Available:** The two Phase 30 evaluations produce intervals, but with 6 and 8 independent holdout points: a coverage estimate from eight points has a binomial half-width of roughly +/-0.3, so it cannot support a coverage guarantee.
- **Gap type:** insufficient
- **Severity:** major - the claim is supportable only with a stated limitation that a user would notice
- **How it could be closed:** More independent experiments, or an external evaluation set with documented protocol. Neither exists for the crops served here.
- **Current status:** OPEN - Both datasets acquired this phase were tested against the lettuce model domains and both are outside them: the green-light trial measures mass only at a single destructive harvest 35 days after sowing against a declared 2-29 day domain, and the dosing trial reports no air temperature, no root temperature and no PPFD. Neither can measure interval coverage without breaking the model's own domain contract.
- **Phase 30 decision:** documented, not closed - train/selection/holdout separation was enforced and recorded in both Phase 30 artifacts; the harvest workflow was removed rather than given a wider interval
- **Residual capability:** Descriptive intervals on measured group means.
- **Phase 34 decision:** measured, not closed - The coverage question was answered by measurement rather than by more data: each served 90 % interval was held against a campaign no fit saw, and the mizuna conformal radius was calibrated on one flight campaign and evaluated on the other in both directions. Evidence: ml/evaluation/phase34_cross_campaign_coverage.json.
    - `lettuce-earth-growth-v1`: 0 of 6 independent PeerJ 2024 treatment means covered, ratio median 3.655 (1.905-5.493)
    - `lettuce-earth-growth-v2`: 0 of 6 covered, ratio median 3.212 (1.674-5.375)
    - `lettuce-earth-growth-v3`: 6 of 6 covered, ratio median 1.163 (0.606-1.863) - coverage, not accuracy; its Touliatos holdout still fails the 30 % criterion
    - `mizuna-microbial-load-v1`: 107 of 123 samples covered across both directions, pooled 0.8699 (nominal 0.90)
    - `mizuna-microbial-relative-load-v2`: 110 of 123 covered, pooled 0.8943 (nominal 0.90)
- **Why this is still open:** Coverage of six correlated greenhouse means is not a coverage guarantee, two flight campaigns do not estimate a campaign-offset distribution, and two of the five models fail the check outright. The interval stays descriptive; the cards now state the measurement instead of leaving the scope unstated.
- **Phase 36 decision:** OPEN - Unchanged. The new independent campaign cannot measure interval coverage: its only measured mass is at 42 days after transplant, outside the models' declared 2-29 day domain, at chamber temperatures of 13.1-41.8 C against a declared 20-32 C domain, and root temperature was not measured. Scoring it would have required violating the models' own domain contract.
    - evidence: `ml/evaluation/phase36_model_reevaluation.json`
- **Remaining work:** More independent experiments inside the declared domain.
- **Phase 37 decision:** OPEN - Both datasets acquired this phase were tested against the lettuce model domains and both are outside them: the green-light trial measures mass only at a single destructive harvest 35 days after sowing against a declared 2-29 day domain, and the dosing trial reports no air temperature, no root temperature and no PPFD. Neither can measure interval coverage without breaking the model's own domain contract.
    - evidence: `ml/evaluation/phase37_model_evidence.json`
- **Remaining work:** Independent experiments inside the declared domain, with repeated mass measurements over time and a measured root temperature.

## The two that matter most

**`measured-eta`** and **`independent-et0`** decide how much the ET0 work is worth. The first says the platform computes a reference flux and cannot measure a crop's actual water use. The second says the target it validates against is one provider's reanalysis. Fixing the second is cheap and mechanical (an ERA5-Land token). Fixing the first requires an experiment.
