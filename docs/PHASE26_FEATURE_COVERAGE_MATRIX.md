# Phase 26 — Feature Readiness and Coverage Matrix

Generated from `data/research/phase26/feature_readiness.json` on 2026-11-10 by `ml/research/build_feature_readiness.py`. Edit the JSON, not this file.

Twelve named capabilities, audited against the evidence that exists in this repository. A tier describes what a feature may **claim**, not how much code it has, and the builder refuses to write an audit whose tiers outrun their evidence.

## Tiers

| Tier | Meaning |
| --- | --- |
| `production-ready` | independent evaluation exists and the stated limits match what it found |
| `research-ready` | measured data and a committed evaluation exist; the claimed level is not identifiable from them |
| `experimental` | implemented and internally evaluated; no independent validation exists |
| `data-blocked` | no obtainable dataset can move this feature; the block is the data's absence |
| `unsupported` | the product must not make the claim at all |

**12 features: production-ready: 0, research-ready: 4, experimental: 4, data-blocked: 4, unsupported: 0. 2 of 12 moved in Phase 26.**

## Readiness

| # | Feature | Tier | Previous | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Predicted crop water use in litres per plant per day | `research-ready` **(moved)** | `data-blocked` | 3 artefacts, 1 datasets |
| 2 | The claim that the ET0 target is itself correct | `research-ready` | `research-ready` | 2 artefacts, 4 datasets |
| 3 | Predicted harvest mass per plant | `research-ready` | `research-ready` | 4 artefacts, 3 datasets |
| 4 | Response to specific LED spectra and photoperiods | `experimental` | `experimental` | 3 artefacts, 1 datasets |
| 5 | Effect of Mars or lunar gravity on crop growth | `data-blocked` | `data-blocked` | 2 artefacts, 0 datasets |
| 6 | Root-zone water status in a hydroponic or substrate system | `data-blocked` | `data-blocked` | 1 artefacts, 0 datasets |
| 7 | Heat-stress and VPD excursion claims | `research-ready` | `research-ready` | 2 artefacts, 2 datasets |
| 8 | Cultivar-specific growth parameters | `experimental` | `experimental` | 2 artefacts, 0 datasets |
| 9 | Plant health or growth stage from imagery | `data-blocked` | `data-blocked` | 1 artefacts, 0 datasets |
| 10 | Energy and mass cost of a described mission | `experimental` | `experimental` | 2 artefacts, 0 datasets |
| 11 | Nutrient solution management | `experimental` **(moved)** | `data-blocked` | 2 artefacts, 1 datasets |
| 12 | Siting for a future climate rather than the observed recent past | `data-blocked` | `data-blocked` | 1 artefacts, 0 datasets |

## Coverage: which dataset backs which feature

| Feature | Datasets | Measured on |
| --- | --- | --- |
| Predicted crop water use in litres per plant per day | `zenodo-schroder-2021-lettuce-pot` | 380 pot-days from 35 published pots, 7 treatments, 11 weighings |
| The claim that the ET0 target is itself correct | `nasa-power-daily`, `era5-land`, `era5-hourly-0p25`, `noaa-isd-lite` | four independent reanalysis and station sources over matched days |
| Predicted harvest mass per plant | `zenodo-greenlight-2024-lettuce`, `zenodo-schroder-2021-lettuce-pot`, `zenodo-ledphotoperiod-2025-tomato` | 252 hydroponic lettuce plants, 35 greenhouse lettuce pots, 20 open-field tomato plants |
| Response to specific LED spectra and photoperiods | `zenodo-greenlight-2024-lettuce` | 252 plants across four fixed spectra at constant 200 umol/m2/s and 16 h |
| Effect of Mars or lunar gravity on crop growth | — | nothing: no fractional-gravity plant growth dataset exists in this repository |
| Root-zone water status in a hydroponic or substrate system | — | nothing: no root-zone water-potential series exists in-repo. The Schroeder trial's water-holding-capacity sheet is a static substrate property, not a root-zone time series. |
| Heat-stress and VPD excursion claims | `era5-hourly-0p25`, `noaa-isd-lite` | hourly reanalysis and station records at grid and station resolution |
| Cultivar-specific growth parameters | — | three crop profiles (lettuce, tomato, radish) with no cultivar field |
| Plant health or growth stage from imagery | — | nothing: the tomato trial ships an RGB leaf-area series, which is a measurement derived from imagery rather than the imagery itself |
| Energy and mass cost of a described mission | — | nothing: energy per LED-hour and per litre is a deterministic calculation over stated assumptions, not a measurement |
| Nutrient solution management | `zenodo-halbert-2020-tomato-hydroponic` | row-level shoot and fruit nutrient uptake with solution concentrations and a recycled-solution fraction; not yet preprocessed |
| Siting for a future climate rather than the observed recent past | — | nothing acquired: the CMIP6 downscaled product is catalogued at class D and was not downloaded |

### 1. Predicted crop water use in litres per plant per day

**Tier: `research-ready`** (was `data-blocked` before Phase 26)

Measured on: 380 pot-days from 35 published pots, 7 treatments, 11 weighings

Supports:
- the seasonal shape of lettuce water demand (Spearman 0.7909 across 11 days)
- a per-plant, per-day water-use benchmark that any future change must be compared with

Does not support:
- a level correction: pot-surface and canopy-area denominators reverse the sign of the discrepancy, and neither is published
- a crop coefficient: no per-day trial weather exists
- transpiration alone: the measurement includes substrate evaporation

What would move it: per-day weather and pot geometry for a gravimetric or lysimeter trial, so that measured ET can be divided by a reference ET0 for the same days

Blocking evidence: none obtainable under an open licence in this phase

Evidence artefacts: `ml/evaluation/phase26_measured_et_validation.json`, `data/processed/phase26/schroder2021_lettuce_et.csv`, `backend/app/simulation/water.py`

### 2. The claim that the ET0 target is itself correct

**Tier: `research-ready`** (unchanged in Phase 26)

Measured on: four independent reanalysis and station sources over matched days

Supports:
- that the FAO-56 computation is implemented correctly and is stable across inputs
- that the emulator reproduces the computation, not that the computation is truth

Does not support:
- a claim that reanalysis ET0 equals on-site measurement
- spatial validity below the reanalysis grid cell

What would move it: a flux-tower or lysimeter site inside a controlled environment, which is the same object measured-eta needs

Blocking evidence: no controlled-environment ET0 measurement exists openly

Evidence artefacts: `ml/evaluation/et0_dataset_quality.json`, `docs/ERA5_LAND_INDEPENDENT_VALIDATION.md`

### 3. Predicted harvest mass per plant

**Tier: `research-ready`** (unchanged in Phase 26)

Measured on: 252 hydroponic lettuce plants, 35 greenhouse lettuce pots, 20 open-field tomato plants

Supports:
- leave-one-experiment-out lettuce harvest prediction (v2 R2 0.8699 / MAE 34.9 g)
- per-plant harvest mass for two independent lettuce experiments

Does not support:
- any controlled-environment tomato or mizuna harvest prediction
- a spaceflight yield claim: no spaceflight harvest label exists in-repo

What would move it: a controlled-environment tomato or mizuna harvest trial with per-plant labels and documented conditions

Blocking evidence: no such open dataset was found in this phase's search

Evidence artefacts: `ml/evaluation/lettuce_splits.json`, `ml/evaluation/lettuce_out_of_fold.csv`, `data/processed/phase26/greenlight2024_lettuce_harvest.csv`, `data/processed/phase26/schroder2021_lettuce_biomass.csv`

### 4. Response to specific LED spectra and photoperiods

**Tier: `experimental`** (unchanged in Phase 26)

Measured on: 252 plants across four fixed spectra at constant 200 umol/m2/s and 16 h

Supports:
- that spectral composition can be held as a categorical factor with 48-80 plants per arm

Does not support:
- an intensity response: PPFD was constant by design
- a photoperiod response: photoperiod was constant by design
- any quantitative yield model: no model consumes this table yet

What would move it: a trial varying PPFD and photoperiod independently, or a model that consumes the existing table with leave-one-spectrum-out evaluation

Blocking evidence: the photoperiod half of the claim has no dataset at all

Evidence artefacts: `data/processed/phase26/greenlight2024_lettuce_harvest.csv`, `data/processed/phase26/greenlight2024_lettuce_fluorescence.csv`, `backend/app/science_classification.py`

### 5. Effect of Mars or lunar gravity on crop growth

**Tier: `data-blocked`** (unchanged in Phase 26)

Measured on: nothing: no fractional-gravity plant growth dataset exists in this repository

Supports:
- a bounded response curve whose sensitivity coefficient is a modelling assumption

Does not support:
- any quantitative Mars- or lunar-gravity yield prediction
- the conflation of clinostat, ground analog and spaceflight data, none of which is present

What would move it: a fractional-gravity growth experiment; none exists openly at the replication needed

Blocking evidence: no open dataset; a measurement to commission, not to download

Evidence artefacts: `backend/app/simulation/factors.py`, `docs/MODEL_LIMITATIONS.md`

### 6. Root-zone water status in a hydroponic or substrate system

**Tier: `data-blocked`** (unchanged in Phase 26)

Measured on: nothing: no root-zone water-potential series exists in-repo. The Schroeder trial's water-holding-capacity sheet is a static substrate property, not a root-zone time series.

Supports:
- a single well-mixed root-zone water store with a recovery efficiency assumption

Does not support:
- substrate matric potential, oxygen status, or root-zone gradients

What would move it: a substrate water-potential series logged alongside a growth trial

Blocking evidence: the acquisition that came closest (water holding capacity) measures capacity, not status

Evidence artefacts: `backend/app/simulation/water.py`

### 7. Heat-stress and VPD excursion claims

**Tier: `research-ready`** (unchanged in Phase 26)

Measured on: hourly reanalysis and station records at grid and station resolution

Supports:
- hourly VPD and temperature trajectories for siting and for ET0 input

Does not support:
- canopy-level excursions inside a controlled environment
- any statement about a facility's internal climate

What would move it: in-facility climate logging at sub-hourly resolution

Blocking evidence: no open controlled-environment climate series with the required resolution was found

Evidence artefacts: `ml/evaluation/phase11_dataset_discovery.json`, `docs/DATASET_GAP_MATRIX.md`

### 8. Cultivar-specific growth parameters

**Tier: `experimental`** (unchanged in Phase 26)

Measured on: three crop profiles (lettuce, tomato, radish) with no cultivar field

Supports:
- a species-level parameter set explicitly documented as not cultivar-resolved

Does not support:
- any cultivar-specific prediction, and no dataset in-repo carries a cultivar label usable as a model input

What would move it: two or more cultivars of one species grown under identical conditions

Blocking evidence: the lettuce experiments in-repo each use a single unnamed cultivar

Evidence artefacts: `backend/app/simulation/crops.py`, `docs/MODEL_LIMITATIONS.md`

### 9. Plant health or growth stage from imagery

**Tier: `data-blocked`** (unchanged in Phase 26)

Measured on: nothing: the tomato trial ships an RGB leaf-area series, which is a measurement derived from imagery rather than the imagery itself

Supports:
- nothing: the product does not claim an imagery model

Does not support:
- any computer-vision claim, health classification, or growth-stage detection

What would move it: paired imagery and destructive harvest from the same plants

Blocking evidence: the class E/F imagery datasets in the catalogue cannot be used under their licences or do not match the task

Evidence artefacts: `docs/DATASET_GAP_MATRIX.md`

### 10. Energy and mass cost of a described mission

**Tier: `experimental`** (unchanged in Phase 26)

Measured on: nothing: energy per LED-hour and per litre is a deterministic calculation over stated assumptions, not a measurement

Supports:
- a reproducible accounting of lighting and pumping energy under stated assumptions

Does not support:
- a validated mission energy budget, and any comparison against a real facility

What would move it: metered energy data from an operating controlled-environment facility

Blocking evidence: no metered facility energy dataset is openly available

Evidence artefacts: `backend/app/simulation/engine.py`, `backend/app/science_classification.py`

### 11. Nutrient solution management

**Tier: `experimental`** (was `data-blocked` before Phase 26)

Measured on: row-level shoot and fruit nutrient uptake with solution concentrations and a recycled-solution fraction; not yet preprocessed

Supports:
- that a nutrient-uptake prior is constructible from a licensed, acquired source

Does not support:
- any per-plant nutrient claim: replication is at row level
- a closed nutrient balance: the sheet reports uptake, not depletion and replenishment

What would move it: preprocessing the acquired workbook into a tidy table and evaluating a nutrient prior against it with row-level folds

Blocking evidence: row-level replication caps the inference, and the product makes no nutrient claim today

Evidence artefacts: `data/raw/phase26/zenodo-halbert-2020-tomato-hydroponic/Data_Tomato_hydroponic_experiment_Halbert-Howard_et_al_2020.xlsx`, `scripts/datasets/registry.py`

### 12. Siting for a future climate rather than the observed recent past

**Tier: `data-blocked`** (unchanged in Phase 26)

Measured on: nothing acquired: the CMIP6 downscaled product is catalogued at class D and was not downloaded

Supports:
- nothing: no siting-for-future-climate claim is made

Does not support:
- any projection-based recommendation

What would move it: acquiring the downscaled projections and defining a projection-based ET0 target with an explicit scenario

Blocking evidence: the product's ET0 target is the observed recent past by construction

Evidence artefacts: `docs/DATASET_GAP_MATRIX.md`

## What this table is not

No feature reached `production-ready` in this phase and none was promoted on the strength of a new download. The two tiers that moved each gained a specific, cited artefact: `measured-eta` gained the first measured crop water use in the repository, and `nutrient-balance` gained a licensed nutrient-uptake workbook. Both movements are modest by design - in both cases the acquisition made the feature *legitimately discussable*, not *solved*.

4 features remain `data-blocked`. That count fell by one in this phase, and only because a licensed nutrient-uptake workbook was actually downloaded and verified. The remaining blocks do not shrink, because the datasets that would clear them do not exist under an open licence and a catalogue entry cannot be invented.
