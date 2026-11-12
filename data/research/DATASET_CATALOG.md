# SpaceAgriSim Dataset Catalogue

Generated from `data/research/dataset_catalog.json` on 2026-11-09 by `ml/research/build_catalog.py`. Edit the JSON, not this file.

Every dataset the project has evaluated, with the licence evidence behind its class. The class answers one question: could this support a claim the product makes, under the licence it is actually distributed with?

**36 datasets evaluated.** A: 12, B: 6, C: 9, D: 3, E: 5, F: 1.

## Classes

| Class | Meaning | Datasets |
|---|---|---|
| **A** | acquired and used in this repository | 12 |
| **B** | usable after preprocessing - open licence, relevant variables, usable scale | 6 |
| **C** | external validation only - wrong task, sensor or size for training | 9 |
| **D** | scientific reference only - open and correct, but cannot validate this product | 3 |
| **E** | needs an agreement or a licence decision before use | 5 |
| **F** | not suitable - the licence prohibits the intended use | 1 |

## Licence evidence

| Grade | Meaning | Datasets |
|---|---|---|
| verified | the terms were read for this entry | 22 |
| documented-secondary | a credible registry or dataset card states it | 10 |
| unverified | believed open, not checked; must be checked before use | 4 |

## Summary

| Dataset | Class | Licence | Commercial use | Imported |
|---|---|---|---|---|
| [NASA POWER daily agroclimatology (community AG)](#nasa-power-daily) | **A** | NASA open data: no restrictions on use, access or download; citation requested | permitted | yes |
| [SMAP L4 Global 3-hourly 9 km surface and root-zone soil moisture (SPL4SMGP v8)](#smap-l4-ssm) | **B** | NASA open data policy; free Earthdata login required | permitted | no |
| [MODIS/Terra Vegetation Indices 16-Day L3 Global 250 m (MOD13Q1 v061)](#mod13q1-v061) | **B** | CC BY 4.0 (AWS Open Data registry entry for MODIS) | permitted with attribution | no |
| [GPM IMERG Final Precipitation L3 Half Hourly 0.1 deg (3B-HH v07)](#gpm-imerg-3imerghh-07) | **B** | openly shared without restriction per EOSDIS policy; Earthdata login required | permitted | no |
| [ERA5-Land hourly reanalysis](#era5-land) | **C** | Copernicus licence: free, attribution and no endorsement required | permitted with attribution | yes |
| [ERA5 hourly reanalysis (0.25 deg) via Open-Meteo archive](#era5-hourly-0p25) | **C** | Open-Meteo CC BY 4.0; values under the Copernicus licence | permitted with attribution | yes |
| [NOAA ISD-Lite hourly surface observations](#noaa-isd-lite) | **C** | U.S. Government work, public domain | permitted | yes |
| [SoilGrids 2.0 predicted soil properties](#soilgrids-2-0) | **B** | CC BY 4.0 | permitted with attribution | no |
| [CHIRPS v2.0 quasi-global precipitation](#chirps-v2-0) | **B** | public domain per the CHC data page; citation requested | permitted with attribution | no |
| [Global Wheat Head Detection 2021](#gwhd2021) | **C** | CC BY 4.0 | permitted with attribution | no |
| [NASA OSDR / GeneLab plant experiment corpus](#osdr-plant-experiments) | **C** | NASA open data policy: no restrictions on use; per-study citation | permitted | yes |
| [Published lettuce light-intensity and temperature trial (PeerJ 17085)](#peerj17085-lettuce) | **C** | article CC BY 4.0; the extracted table is a derived dataset | permitted with attribution (article licence) | yes |
| [DeepWeeds: weed image classification in northern Australia](#deepweeds) | **C** | CC BY 4.0 per the Zenodo record | permitted with attribution | no |
| [FLUXNET2015 eddy-covariance flux tower dataset](#fluxnet2015) | **C** | CC BY 4.0 per site, subject to accepting the FLUXNET data policy | permitted with attribution, after accepting the data policy | no |
| [PlantVillage leaf-disease image dataset](#plantvillage) | **E** | conflicting records: CC BY-SA 3.0 (HF card) vs GPL-2 (Kaggle mirror) vs none (GitHub) | undecided - the ShareAlike term and the conflicting records disagree | no |
| [FAO WaPOR - water productivity through open access of remotely sensed derived data](#wapor) | **E** | CC BY-NC-SA 4.0 - non-commercial | not permitted (non-commercial) | no |
| [PlanetScope daily 3 m imagery](#planet-scope) | **E** | commercial subscription; no redistribution of derived products without agreement | requires a paid agreement | no |
| [OpenET ensemble evapotranspiration](#openet) | **E** | free for research with registration; commercial terms require an agreement | requires an agreement | no |
| [PlantCLEF 2021 plant identification challenge data](#plantclef2021) | **E** | research-use terms; redistribution restricted; per-image provenance varies | not permitted without agreement | no |
| [FAOSTAT crop production and yield statistics](#faostat) | **D** | CC BY 4.0 | permitted with attribution | no |
| [Present-day and future Koppen-Geiger climate classification (Beck et al. 2018)](#koppen-geiger-beck) | **D** | CC BY 4.0 | permitted with attribution | no |
| [NASA NEX-GDDP-CMIP6 statistically downscaled climate projections](#nasa-nex-gddp-cmip6) | **A** | open (NASA NEX); model-specific citation requested | permitted | yes |
| [Green-light inclusion in hydroponic lettuce at constant PPFD (Red Batavia)](#zenodo-green-light-lettuce) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [Temporal variation of nutrient ratios in hydroponic solution (Red Batavia)](#zenodo-nutrient-dosing) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [NASA POWER hourly agroclimatology (community AG)](#nasa-power-hourly) | **A** | NASA open data: no restrictions on use, access or download; citation requested | permitted | yes |
| [Agroscope weighable-lysimeter water balance, Zurich-Reckenholz](#zenodo-agroscope-lysimeter-2026) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [TERENO Graswang/Fendt eddy-covariance and lysimeter fluxes](#zenodo-tereno-graswang-fendt) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [IoT4Lettuce - multimodal phenotyping of hydroponic lettuce under variable fertigation](#zenodo-iot4lettuce) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [PlantWild in-the-wild plant image dataset](#plantwild) | **F** | CC BY-NC-ND 4.0 - non-commercial, no derivatives | not permitted (non-commercial, no derivatives) | no |
| [Greenhouse lettuce pot experiment with gravimetric evapotranspiration (Schroeder et al. 2021)](#zenodo-schroder-2021-lettuce-pot) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [Green-light spectral composition trial in hydroponic lettuce](#zenodo-greenlight-2024-lettuce) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [Indoor wheat (cv. Apogee) under fully controlled environmental conditions](#zenodo-cea-wheat-apogee) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [Kilowatts to kilograms: lettuce light-use-efficiency compilation](#zenodo-kilowatts-lettuce-lue) | **A** | CC BY 4.0 | permitted with attribution | yes |
| [Portable-platform LED photoperiod extension trial in open-field tomato](#zenodo-ledphotoperiod-2025-tomato) | **C** | CC BY 4.0 | permitted with attribution | yes |
| [Tomato hydroponic nutrient-uptake and yield trial (Halbert-Howard et al. 2020)](#zenodo-halbert-2020-tomato-hydroponic) | **B** | CC BY 4.0 | permitted with attribution | no |
| [Leaf gas-exchange series for Corymbia calophylla (marri)](#zenodo-marri-2021-gasexchange) | **D** | CC BY 4.0 | permitted with attribution | no |

## Detail

### NASA POWER daily agroclimatology (community AG)  `nasa-power-daily`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired and used: the ET0 target and the emulator features are derived from it. The licence permits redistribution and commercial use.
- **Publisher:** NASA Langley Research Center, POWER Project
- **URL:** https://power.larc.nasa.gov/data-access-viewer/
- **Format:** JSON / CSV / NetCDF via REST point and regional APIs
- **Coverage:** global, 0.5 x 0.625 deg (MERRA-2 grid), daily, 1981-present
- **Variables:** ALLSKY_SFC_SW_DWN, T2M, T2M_MAX, T2M_MIN, T2MDEW, RH2M, WS2M, PS, PRECTOTCORR
- **Units:** MJ m^-2 d^-1; degC; %; m s^-1; kPa; mm day^-1
- **Licence:** NASA open data: no restrictions on use, access or download; citation requested
- **Licence evidence:** verified (https://registry.opendata.aws/nasa-power/)
- **Commercial use:** permitted
- **Imported:** yes - data/raw/nasa_power/*.json via ml/research/acquire_power_climate.py
- **Caveat:** Reanalysis on a coarse grid: a site label is a grid-cell value, not an instrument reading, and its MERRA-2 lineage means it cannot validate itself.

### SMAP L4 Global 3-hourly 9 km surface and root-zone soil moisture (SPL4SMGP v8)  `smap-l4-ssm`

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** Open, correct variables, but 9 km is open-field soil moisture - it would support an open-field deployment, not the controlled-environment system the product models. Not imported.
- **Publisher:** NASA NSIDC DAAC
- **URL:** https://nsidc.org/data/spl4smgp/versions/8
- **Format:** HDF5, EASE-Grid 2.0
- **Coverage:** global, 9 km, 3-hourly, from 2015-03-31
- **Variables:** surface soil moisture, root-zone soil moisture, soil temperature
- **Units:** m^3 m^-3; K
- **Licence:** NASA open data policy; free Earthdata login required
- **Licence evidence:** documented-secondary (https://www.earthdata.nasa.gov/engage/open-data-services-and-software/data-and-information-policy)
- **Commercial use:** permitted
- **Imported:** no - no substrate or root-zone state model exists to consume it
- **Caveat:** A different system at a different scale from a hydroponic root zone.

### MODIS/Terra Vegetation Indices 16-Day L3 Global 250 m (MOD13Q1 v061)  `mod13q1-v061`

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** Open and preprocessed, but 250 m / 16-day is far coarser than a single growth module. Usable for a field-scale context layer, not for the per-module model.
- **Publisher:** NASA LP DAAC
- **URL:** https://lpdaac.usgs.gov/products/mod13q1v061/
- **Format:** HDF4 / GeoTIFF
- **Coverage:** global, 250 m, 16-day composites, 2000-present
- **Variables:** NDVI, EVI, VI quality, pixel reliability
- **Units:** index (scaled integer with fill 0.0001 scaling)
- **Licence:** CC BY 4.0 (AWS Open Data registry entry for MODIS)
- **Licence evidence:** documented-secondary (https://registry.opendata.aws/modis/)
- **Commercial use:** permitted with attribution
- **Imported:** no - no field-scale context layer in the product yet
- **Caveat:** A 16-day composite cannot resolve a growth stage that turns over in days.

### GPM IMERG Final Precipitation L3 Half Hourly 0.1 deg (3B-HH v07)  `gpm-imerg-3imerghh-07`

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** High-quality open precipitation at 0.1 deg. It does not enter ET0 - FAO-56 needs no precipitation term for a daily reference - and no irrigation or drainage model consumes it yet.
- **Publisher:** NASA GES DISC
- **URL:** https://www.earthdata.nasa.gov/data/catalog/ges-disc-gpm-3imerghh-07
- **Format:** HDF5 / NetCDF4 / GeoTIFF
- **Coverage:** 60 N-60 S, 0.1 deg, 30-minute, from 2000-06 (Final run)
- **Variables:** precipitation, precipitation quality index, random error
- **Units:** mm h^-1
- **Licence:** openly shared without restriction per EOSDIS policy; Earthdata login required
- **Licence evidence:** verified (https://www.earthdata.nasa.gov/data/catalog/ges-disc-gpm-3imerghh-07)
- **Commercial use:** permitted
- **Imported:** no - candidate input for a future water-balance closure
- **Caveat:** Citation requested: Huffman, Stocker, Bolvin, Nelkin & Tan (2023), DOI 10.5067/GPM/IMERG/3B-HH/07.

### ERA5-Land hourly reanalysis  `era5-land`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** External validation input, not training data. Used through a credential-free delivery for its 0.1 deg temperature field only: that route returns null for radiation and wind, so it cannot drive a full FAO-56 computation. The hourly radiation and wind fields still require a CDS token and were not retrieved.
- **Publisher:** Copernicus Climate Change Service (C3S) via the Climate Data Store
- **URL:** https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land
- **Format:** NetCDF / GRIB via CDS API
- **Coverage:** global land, 0.1 deg, hourly, 1950-present
- **Variables:** 2 m temperature, dew point, surface solar radiation, 10 m wind, surface pressure, precipitation
- **Units:** K; m; J m^-2; m s^-1; Pa; m
- **Licence:** Copernicus licence: free, attribution and no endorsement required
- **Licence evidence:** documented-secondary (https://cds.climate.copernicus.eu/licences/)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/validation/et0/ - temperature-only Hargreaves leg, no training use
- **Caveat:** Temperature-only in every result reported here, and its 0.1 deg Tmax was further from the station than ERA5 0.25 deg at all six validation sites: a finer grid is not automatically closer to a point observation.

### ERA5 hourly reanalysis (0.25 deg) via Open-Meteo archive  `era5-hourly-0p25`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** The primary forcing of the independent ET0 validation and the source of the provider's own FAO-56 series used as the implementation control. External validation only; it never enters training.
- **Publisher:** ECMWF/C3S, delivered by the Open-Meteo archive API
- **URL:** https://open-meteo.com/en/docs/historical-weather-api
- **Format:** JSON over HTTPS
- **Coverage:** global, 0.25 deg, hourly, 1940-present
- **Variables:** 2 m temperature, 2 m dew point, shortwave radiation, 10 m wind speed, surface pressure, provider FAO-56 ET0
- **Units:** degC; degC; W m^-2; m s^-1; hPa; mm d^-1
- **Licence:** Open-Meteo CC BY 4.0; values under the Copernicus licence
- **Licence evidence:** verified (https://open-meteo.com/en/license)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/validation/et0/harmonised_daily.csv - validation forcing
- **Caveat:** A reanalysis: agreement with it bounds implementation and forcing error, not physical truth, and it shares much of its observing system with MERRA-2.

### NOAA ISD-Lite hourly surface observations  `noaa-isd-lite`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** The only leg in the ET0 validation with no reanalysis lineage: a point station measurement. It carries no radiation field, so it can only support a temperature-based method. External validation only.
- **Publisher:** NOAA National Centers for Environmental Information
- **URL:** https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/
- **Format:** gzipped fixed-width text, one file per station-year
- **Coverage:** per station, hourly, global
- **Variables:** air temperature, dew point, sea-level pressure, wind speed, sky cover code, precipitation
- **Units:** degC (stored as tenths); hPa; m s^-1; coded
- **Licence:** U.S. Government work, public domain
- **Licence evidence:** verified (https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00516)
- **Commercial use:** permitted
- **Imported:** yes - data/validation/et0/ - Hargreaves observational leg
- **Caveat:** A point observation at an airport, not a grid cell: representativeness, not accuracy, is the limiting factor, and it cannot confirm the radiation term.

### SoilGrids 2.0 predicted soil properties  `soilgrids-2-0`

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** Open and useful, but it describes soil, and the platform models a hydroponic or substrate system. Relevant only if an open-field mode is added.
- **Publisher:** ISRIC - World Soil Information
- **URL:** https://soilgrids.org/
- **Format:** GeoTIFF / VRT via WebDAV and REST
- **Coverage:** global, 250 m, 7 standard depths to 200 cm
- **Variables:** clay, sand, silt, bulk density, organic carbon, pH, CEC
- **Units:** g kg^-1; kg dm^-3; dS m^-1; pH
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://www.isric.org/about/data-policy)
- **Commercial use:** permitted with attribution
- **Imported:** no - no soil model in the product
- **Caveat:** Predictions, with their own uncertainty; not measurements at any site.

### CHIRPS v2.0 quasi-global precipitation  `chirps-v2-0`

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** Open, finer than IMERG for accumulation, but precipitation is not an input to daily reference ET0 and no water-balance model consumes it.
- **Publisher:** UCSB Climate Hazards Center
- **URL:** https://www.chc.ucsb.edu/data/chirps
- **Format:** GeoTIFF / NetCDF
- **Coverage:** 50 N-50 S, 0.05 deg, daily, 1981-present
- **Variables:** precipitation
- **Units:** mm day^-1
- **Licence:** public domain per the CHC data page; citation requested
- **Licence evidence:** documented-secondary (https://www.chc.ucsb.edu/data/chirps)
- **Commercial use:** permitted with attribution
- **Imported:** no - candidate precipitation input alongside IMERG; one of the two is enough
- **Caveat:** Station-blended, so its independence from POWER depends on the station network.

### Global Wheat Head Detection 2021  `gwhd2021`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** Excellent labelled data for a task the product does not perform: wheat head detection in field imagery. No imaging pipeline exists, so this is external validation material only, never a training set for a capability we do not ship.
- **Publisher:** GWHD consortium, hosted on Zenodo
- **URL:** https://zenodo.org/records/5092309
- **Format:** JPEG images with Pascal-VOC-style bounding boxes
- **Coverage:** 6,515 images, 275,187 wheat heads, 11 countries, 44 sessions
- **Variables:** RGB imagery, head bounding boxes
- **Units:** pixels; boxes in image coordinates
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/5092309)
- **Commercial use:** permitted with attribution
- **Imported:** no - no imaging capability to validate
- **Caveat:** A model trained here would detect wheat, not the crops this platform simulates.

### NASA OSDR / GeneLab plant experiment corpus  `osdr-plant-experiments`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** Used for provenance and as a qualitative prior only. The studies are too few, too heterogeneous and mostly the wrong species to train or validate a yield model.
- **Publisher:** NASA Open Science Data Repository (OSDR)
- **URL:** https://osdr.nasa.gov/bio/
- **Format:** per-study ISA-Tab, tables, images, omics
- **Coverage:** per study; small, heterogeneous, mostly Arabidopsis
- **Variables:** per-study assay metadata, some harvest mass and phenotype tables
- **Units:** per study
- **Licence:** NASA open data policy: no restrictions on use; per-study citation
- **Licence evidence:** verified (https://osdr.nasa.gov/bio/about/policies.html)
- **Commercial use:** permitted
- **Imported:** yes - data/metadata/dataset_manifest.json - provenance only, never a feature
- **Caveat:** Microgravity studies exist here, but none with the replication a response function needs.

### Published lettuce light-intensity and temperature trial (PeerJ 17085)  `peerj17085-lettuce`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** Six observations. Enough to sit beside a prediction as an external check, nowhere near enough to fit or tune anything, and it is never used as training data.
- **Publisher:** PeerJ (open access article with tables)
- **URL:** https://peerj.com/articles/17085/
- **Format:** HTML/Markdown tables in an open-access article
- **Coverage:** 6 observations, one cultivar, light intensity x temperature
- **Variables:** fresh mass, light intensity, temperature
- **Units:** g per plant; umol m^-2 s^-1; degC
- **Licence:** article CC BY 4.0; the extracted table is a derived dataset
- **Licence evidence:** unverified (https://peerj.com/articles/17085/)
- **Commercial use:** permitted with attribution (article licence)
- **Imported:** yes - data/literature/external_lettuce_peerj17085.json - validation only
- **Caveat:** One cultivar, one facility: agreement here is a sanity check, not validation.

### DeepWeeds: weed image classification in northern Australia  `deepweeds`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** Open field-weed imagery for a classification task the product does not perform. Recorded because it is the standard counter-example to using PlantVillage for anything field-realistic.
- **Publisher:** Commonwealth Scientific and Industrial Research Organisation (CSIRO) via Zenodo
- **URL:** https://zenodo.org/records/5542236
- **Format:** JPEG images with species labels
- **Coverage:** 17,509 images, 8 weed species plus negative class, field imagery
- **Variables:** RGB imagery, species label, GPS location
- **Units:** pixels
- **Licence:** CC BY 4.0 per the Zenodo record
- **Licence evidence:** documented-secondary (https://zenodo.org/records/5542236)
- **Commercial use:** permitted with attribution
- **Imported:** no - no weed or imagery capability exists
- **Caveat:** Not checked against the platform's crop set; validation value only.

### FLUXNET2015 eddy-covariance flux tower dataset  `fluxnet2015`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** The strongest validation material this project has identified: measured latent heat flux at grassland towers is an independent check on a reference-ET calculation, which is exactly what the `independent-et0` gap asks for. It cannot train the emulator - the towers are not the six reference sites and the footprint is a field, not a module - so it is validation only, and it is not imported yet.
- **Publisher:** FLUXNET community, distributed via the FLUXNET data portal
- **URL:** https://fluxnet.org/data/fluxnet2015-dataset/
- **Format:** CSV per site, half-hourly and aggregated
- **Coverage:** 212 sites worldwide, 1991-2014, half-hourly to annual
- **Variables:** latent heat flux (LE), sensible heat, net radiation, air temperature, vapour pressure deficit, wind speed, soil moisture
- **Units:** W m^-2; degC; hPa; m s^-1; %
- **Licence:** CC BY 4.0 per site, subject to accepting the FLUXNET data policy
- **Licence evidence:** documented-secondary (https://fluxnet.org/data/data-policy/)
- **Commercial use:** permitted with attribution, after accepting the data policy
- **Imported:** no - requires accepting the data policy; tower footprints differ from the sites
- **Caveat:** Eddy-covariance energy-balance closure is typically 10-20 % off, so a mismatch of that size would not settle the question either way.

### PlantVillage leaf-disease image dataset  `plantvillage`

- **Class:** E - needs an agreement or a licence decision before use
- **Why this class:** A commercial product cannot proceed on a dataset whose own distribution points state three different licences, one of which is a copyleft that would reach the model weights. Needs a licence decision, and its lab photographs would transfer poorly to field imagery in any case.
- **Publisher:** Penn State / PlantVillage (multiple mirrors)
- **URL:** https://huggingface.co/datasets/mahmood/plantvillage
- **Format:** JPEG images with disease labels
- **Coverage:** 54,306 images, 38 classes, lab-collected leaves on uniform backgrounds
- **Variables:** RGB leaf imagery, crop and disease label
- **Units:** pixels
- **Licence:** conflicting records: CC BY-SA 3.0 (HF card) vs GPL-2 (Kaggle mirror) vs none (GitHub)
- **Licence evidence:** documented-secondary (https://huggingface.co/datasets/mahmood/plantvillage)
- **Commercial use:** undecided - the ShareAlike term and the conflicting records disagree
- **Imported:** no - licence decision required before any use
- **Caveat:** Widely used as if open; the licence conflict is the reason it is not used here.

### FAO WaPOR - water productivity through open access of remotely sensed derived data  `wapor`

- **Class:** E - needs an agreement or a licence decision before use
- **Why this class:** The only open product that measures actual (not reference) evapotranspiration, and it is non-commercial. A commercial deployment would need an agreement with FAO; it cannot be used as delivered.
- **Publisher:** FAO
- **URL:** https://www.fao.org/in-action/remote-sensing-for-water-productivity/en/
- **Format:** GeoTIFF via FAO portal and API
- **Coverage:** Africa and Near East, 100 m / 250 m, decadal, 2009-present
- **Variables:** actual evapotranspiration, biomass production, water productivity, soil moisture
- **Units:** mm per dekad; kg ha^-1
- **Licence:** CC BY-NC-SA 4.0 - non-commercial
- **Licence evidence:** documented-secondary (https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-portal/en/)
- **Commercial use:** not permitted (non-commercial)
- **Imported:** no - non-commercial licence is disqualifying under this project's rules
- **Caveat:** Would be the strongest validation of a crop water model if the licence allowed it.

### PlanetScope daily 3 m imagery  `planet-scope`

- **Class:** E - needs an agreement or a licence decision before use
- **Why this class:** The only daily 3 m imagery that would make per-module imaging feasible, and it is a paid subscription. Out of scope by the project's no-paid-services rule.
- **Publisher:** Planet Labs PBC
- **URL:** https://www.planet.com/products/planet-imagery/
- **Format:** GeoTIFF, orthorectified scenes
- **Coverage:** global, 3-5 m, daily revisit, commercial subscription
- **Variables:** multispectral imagery (8 bands), analytic and visual products
- **Units:** reflectance
- **Licence:** commercial subscription; no redistribution of derived products without agreement
- **Licence evidence:** unverified (https://www.planet.com/terms-of-use/)
- **Commercial use:** requires a paid agreement
- **Imported:** no - paid service; forbidden by the project constraints
- **Caveat:** Recorded so the imaging gap has a named, priced answer rather than a vague one.

### OpenET ensemble evapotranspiration  `openet`

- **Class:** E - needs an agreement or a licence decision before use
- **Why this class:** Actual ET is exactly the missing measurement class, but the coverage is US-only and the commercial terms are not open. Needs a licence decision and would still not cover the six reference sites outside the US.
- **Publisher:** OpenET consortium
- **URL:** https://openetdata.org/
- **Format:** API / GeoTIFF, monthly and daily
- **Coverage:** continental United States, 30 m and field-scale, 2016-present
- **Variables:** actual evapotranspiration, ensemble and per-model estimates
- **Units:** mm day^-1
- **Licence:** free for research with registration; commercial terms require an agreement
- **Licence evidence:** unverified (https://openetdata.org/about/)
- **Commercial use:** requires an agreement
- **Imported:** no - licence decision plus a coverage limit
- **Caveat:** An ensemble of models, so its disagreement is itself the uncertainty estimate.

### PlantCLEF 2021 plant identification challenge data  `plantclef2021`

- **Class:** E - needs an agreement or a licence decision before use
- **Why this class:** Species identification is not a capability the product claims, and the agreement forbids redistribution. Kept in the catalogue only so a future contributor does not mistake it for an open dataset.
- **Publisher:** CLEF / LifeCLEF
- **URL:** https://www.imageclef.org/PlantCLEF2021
- **Format:** JPEG images with species labels, registration required
- **Coverage:** millions of plant images, species-level labels, herbarium and field
- **Variables:** RGB imagery, species label
- **Units:** pixels
- **Licence:** research-use terms; redistribution restricted; per-image provenance varies
- **Licence evidence:** unverified (https://www.imageclef.org/PlantCLEF2021)
- **Commercial use:** not permitted without agreement
- **Imported:** no - agreement required; task not in scope
- **Caveat:** Aggregated from many sources with heterogeneous underlying licences.

### FAOSTAT crop production and yield statistics  `faostat`

- **Class:** D - scientific reference only - open and correct, but cannot validate this product
- **Why this class:** Free and authoritative, and structurally unable to validate this product: a country-year yield aggregate cannot be compared with a per-square-metre controlled-environment model. Reference context only.
- **Publisher:** FAO
- **URL:** https://www.fao.org/faostat/en/
- **Format:** CSV / API
- **Coverage:** country-year, global, 1961-present
- **Variables:** production, area harvested, yield, producer prices
- **Units:** t; ha; kg ha^-1; USD
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://www.fao.org/contact-us/terms/en/)
- **Commercial use:** permitted with attribution
- **Imported:** no - level of aggregation incompatible with the model's support
- **Caveat:** National aggregates mix field, greenhouse and subsistence production.

### Present-day and future Koppen-Geiger climate classification (Beck et al. 2018)  `koppen-geiger-beck`

- **Class:** D - scientific reference only - open and correct, but cannot validate this product
- **Why this class:** Used only to justify why the six reference sites were chosen to span climates. A categorical map cannot validate a continuous flux.
- **Publisher:** University of Idaho / ETH Zurich, hosted on figshare
- **URL:** https://figshare.com/articles/dataset/Present_and_future_K_ppen-Geiger_climate_classification_maps_at_1-km_resolution/6396959
- **Format:** GeoTIFF, 1 km
- **Coverage:** global, 1 km, 1980-2016 and projections to 2071-2100
- **Variables:** Koppen-Geiger class
- **Units:** class code
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://figshare.com/articles/dataset/Present_and_future_K_ppen-Geiger_climate_classification_maps_at_1-km_resolution/6396959)
- **Commercial use:** permitted with attribution
- **Imported:** no - context for site selection, not an input
- **Caveat:** Classification, not weather; two sites in one class can differ entirely.

### NASA NEX-GDDP-CMIP6 statistically downscaled climate projections  `nasa-nex-gddp-cmip6`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired in Phase 36 for the six sites (ACCESS-CM2, SSP2-4.5, 2000-2004 against 2045-2049) and used for the projected-environment analysis. It remains the wrong product for validating an observed-weather ET0 study, which is why the two uses are kept apart.
- **Publisher:** NASA Earth Exchange (NEX)
- **URL:** https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6
- **Format:** NetCDF, 0.25 deg
- **Coverage:** global, 0.25 deg, daily, 1950-2100 across CMIP6 models
- **Variables:** tasmax, tasmin, pr, hurs, rsds, sfcWind
- **Units:** K; mm day^-1; %; W m^-2; m s^-1
- **Licence:** open (NASA NEX); model-specific citation requested
- **Licence evidence:** documented-secondary (https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6)
- **Commercial use:** permitted
- **Imported:** yes - point series in data/processed/nex_gddp via ml/research/acquire_nex_gddp.py
- **Caveat:** Downscaled model output: uncertainty is the spread across models, not one file.

### Green-light inclusion in hydroponic lettuce at constant PPFD (Red Batavia)  `zenodo-green-light-lettuce`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired, MD5-verified and analysed. It is the first dataset in this repository that varies spectrum while holding light quantity fixed, which is the only design that separates a colour effect from a photon effect; 252 destructively harvested plants, and the density-confounded fourth arm is excluded from every spectrum claim.
- **Publisher:** Zenodo, accompanying the green-light spectral-composition study
- **URL:** https://doi.org/10.5281/zenodo.20394352
- **Format:** XLSX workbook, one file
- **Coverage:** four spectra at a constant 200 umol m-2 s-1 and 16/8 photoperiod over a 35-day Red Batavia cycle: red-blue control (5.08 % green), fixed 24 % green, incremental 16-24-32 % green, and the incremental regime at 1.25x density
- **Variables:** destructive harvest fresh and dry mass, leaf number and area, rosette morphology, MultispeQ chlorophyll fluorescence, chlorophyll, carotenoid, flavonoid and polyphenol assays
- **Units:** g; mm; mm2; count; dimensionless fluorescence ratios; mg g-1 FW
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://creativecommons.org/licenses/by/4.0/)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/raw/zenodo_20394352 via ml/research/acquire_spectrum_light.py
- **Caveat:** One cultivar, one facility, one season, and a single destructive harvest at 35 days. The authors report a green percentage, not a spectral power distribution, so the effect cannot be resolved by wavelength band.

### Temporal variation of nutrient ratios in hydroponic solution (Red Batavia)  `zenodo-nutrient-dosing`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired, MD5-verified and analysed. Supplies the ion-concentration and EC half of the nutrient-solution requirement for a real crop cycle. No pH is deposited, and the pre/post-dose labels are not self-consistent, so no mass-balance uptake rate is claimed from it.
- **Publisher:** Zenodo, accompanying the nutrient-ratio study
- **URL:** https://doi.org/10.5281/zenodo.17794636
- **Format:** XLSX workbook, one file
- **Coverage:** three independent nutrient systems under three management regimes, a 28-day Red Batavia cycle, eight ions sampled repeatedly plus electrical conductivity
- **Variables:** nitrate, phosphate, potassium, calcium, magnesium, sulphate, iron, manganese, electrical conductivity, destructive harvest fresh and dry mass
- **Units:** mg L-1; dS m-1; g
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://creativecommons.org/licenses/by/4.0/)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/raw/zenodo_17794636 via ml/research/acquire_spectrum_light.py
- **Caveat:** The same study is also deposited as 10.5281/zenodo.18804397; all five shared sheets are cell-for-cell identical, so it is one experiment, not two. It is recorded as a duplicate and not counted as independent evidence.

### NASA POWER hourly agroclimatology (community AG)  `nasa-power-hourly`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired for all six sites and used: the diurnal-cycle analysis, the VPD exposure counts and the DLI come from it. The provider's published units are asserted in the ingestion, because the hourly irradiance arrives in MJ/hr and not W/m2.
- **Publisher:** NASA Langley Research Center, POWER Project
- **URL:** https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
- **Format:** JSON via REST point API
- **Coverage:** six reference sites, 2023, hourly (8,760 values per parameter per site)
- **Variables:** T2M, RH2M, T2MDEW, WS2M, PS, ALLSKY_SFC_SW_DWN, PRECTOTCORR
- **Units:** degC; %; m s^-1; kPa; MJ hr^-1 (converted to W m^-2); mm hr^-1
- **Licence:** NASA open data: no restrictions on use, access or download; citation requested
- **Licence evidence:** verified (https://registry.opendata.aws/nasa-power/)
- **Commercial use:** permitted
- **Imported:** yes - data/raw/nasa_power_hourly/*.json via ml/research/acquire_power_hourly.py
- **Caveat:** Local standard time, as the provider states; not relabelled as UTC. MERRA-2 lineage, so it cannot validate a MERRA-2-derived ET0.

### Agroscope weighable-lysimeter water balance, Zurich-Reckenholz  `zenodo-agroscope-lysimeter-2026`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired, checksum-verified against the publisher and used as the measured ET level test. A weighable lysimeter is a direct mass-balance measurement, so nothing in the series comes from MERRA-2.
- **Publisher:** Agroscope (Holzkamper, Spiess, Prasuhn), Zenodo
- **URL:** https://doi.org/10.5281/zenodo.20825203
- **Format:** CSV and ZIP, semicolon-delimited with units rows
- **Coverage:** six weighable lysimeters, 2013-08-01 to 2016-07-31, daily
- **Variables:** actual ET (mm/day), FDR volumetric water content at 10/30/60/90 cm, soil water tension, soil temperature, seepage nitrate load
- **Units:** mm d^-1; vol %; hPa; degC; kg N ha^-1
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://creativecommons.org/licenses/by/4.0/)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/raw/zenodo_20825203 via ml/research/acquire_zenodo_lysimeter.py
- **Caveat:** Field soil in monoliths under a tillage trial, not a controlled-environment substrate; the crop rotation is not lettuce.

### TERENO Graswang/Fendt eddy-covariance and lysimeter fluxes  `zenodo-tereno-graswang-fendt`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired and used as the absolute test of the ET0 formulation: with measured available energy and measured vapour pressure the equation can be compared against measured latent heat without any reanalysis in the path.
- **Publisher:** Mauder et al., TERENO, Zenodo
- **URL:** https://doi.org/10.5281/zenodo.3957208
- **Format:** XLSX workbooks inside a TAR
- **Coverage:** two pre-alpine grassland sites, 2013 and 2014, daytime observations
- **Variables:** latent heat flux, sensible heat flux, available energy (Rn-G), air temperature, vapour pressure, wind speed, aerodynamic resistance
- **Units:** W m^-2; degC; hPa; m s^-1; s m^-1
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://creativecommons.org/licenses/by/4.0/)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/raw/zenodo_3957208 via ml/research/acquire_zenodo_lysimeter.py
- **Caveat:** Grassland, not a crop; one workbook (2013 Graswang) is unusable because it has no wind column.

### IoT4Lettuce - multimodal phenotyping of hydroponic lettuce under variable fertigation  `zenodo-iot4lettuce`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired and used for the cultivar contrast and the deficit-irrigation yield response. Only 12 of 20,679 members were transferred (297 kB of measurement tables from a 39.1 GB archive), by range request.
- **Publisher:** Rodrigues et al., Zenodo
- **URL:** https://doi.org/10.5281/zenodo.20759414
- **Format:** 39.1 GB ZIP; measurement tables acquired by HTTP range request
- **Coverage:** 45 plants, 2 cultivars, 3 nitrogen levels, 2 irrigation rates, 42-day cycle, 2024
- **Variables:** destructive harvest fresh weight, leaf number, diameter, height, SPAD, greenhouse temperature and humidity, PAR
- **Units:** g; cm; dimensionless; degC; %; umol m^-2 s^-1
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://creativecommons.org/licenses/by/4.0/)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/raw/zenodo_20759414 via ml/research/acquire_iot4lettuce.py
- **Caveat:** The archive's published MD5 covers the whole 39 GB object and is therefore unverified; member-level SHA-256 are recorded instead. The design is unbalanced - the 50 % irrigation rate was applied to one cultivar only.

### PlantWild in-the-wild plant image dataset  `plantwild`

- **Class:** F - not suitable - the licence prohibits the intended use
- **Why this class:** Not suitable at any effort: the no-derivatives term prohibits training on it, and training a model is a derivative use. Recorded as the clearest example in this list of a licence that forbids the intended use outright.
- **Publisher:** PlantWild authors, hosted on Hugging Face
- **URL:** https://aiinagriculture.org/datasets/
- **Format:** JPEG images with labels
- **Coverage:** field-collected plant imagery, multiple species
- **Variables:** RGB imagery, labels
- **Units:** pixels
- **Licence:** CC BY-NC-ND 4.0 - non-commercial, no derivatives
- **Licence evidence:** documented-secondary (https://aiinagriculture.org/datasets/)
- **Commercial use:** not permitted (non-commercial, no derivatives)
- **Imported:** no - licence prohibits the intended use
- **Caveat:** Kept in the catalogue so the exclusion is a documented decision, not an omission.

### Greenhouse lettuce pot experiment with gravimetric evapotranspiration (Schroeder et al. 2021)  `zenodo-schroder-2021-lettuce-pot`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired, hash-verified and used: it is the measured side of ml/evaluation/phase26_measured_et_validation.json, the first measured crop water-use comparison in the repository.
- **Publisher:** Zenodo (Agronomy 11:1175 supplementary data)
- **URL:** https://doi.org/10.5281/zenodo.5550230
- **Format:** XLSX, 9 sheets
- **Coverage:** 35 published pots across 7 treatments, 13 weighing dates over 35 days, greenhouse, 2019
- **Variables:** per-pot evapotranspiration, shoot and root fresh/dry mass, water holding capacity, nutrient contents, fertilisation
- **Units:** mL per pot per day; g per pot; % by mass
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/5550230)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/raw/phase26/ via scripts/datasets/acquire.py; data/processed/phase26/schroder2021_*
- **Caveat:** Evapotranspiration, not transpiration: substrate evaporation is included. Pot diameter, pot spacing and per-day weather are unpublished, so no crop coefficient can be derived and any mm-per-day figure carries an area assumption. One cultivar, one greenhouse, Earth gravity.

### Green-light spectral composition trial in hydroponic lettuce  `zenodo-greenlight-2024-lettuce`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired, preprocessed and served: Phase 29 rebuilt it into data/processed/phase29 and the light-stress workflow reports its measured groups with intervals and provenance. It manipulates spectral composition only, so it cannot support a light-intensity claim and still trains nothing.
- **Publisher:** Zenodo
- **URL:** https://doi.org/10.5281/zenodo.20394352
- **Format:** XLSX, 4 sheets
- **Coverage:** 252 harvested plants across 4 spectral treatments, 35 days after sowing, constant 200 umol m^-2 s^-1 and 16 h photoperiod
- **Variables:** leaf length and width, rosette width, fresh and dry mass, leaf number, leaf area, chlorophyll fluorescence indices, postharvest assays
- **Units:** mm; g; count; mm^2 as published (see caveat); dimensionless indices
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/20394352)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/processed/phase29/light_stress_harvest.csv, _photosynthesis.csv, _pigments.csv and light_spectrum_treatments.csv (supersedes the phase26 extracts)
- **Caveat:** The leafAreaMm2 column is numerically consistent with cm^2 rather than mm^2 (a 48 g lettuce with 20 leaves of 158 x 123 mm implies ~1350 cm^2). Recorded as an inference in the table's quality file, not corrected in the source.

### Indoor wheat (cv. Apogee) under fully controlled environmental conditions  `zenodo-cea-wheat-apogee`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired and served as a measured comparison: Phase 30 built data/processed/phase30/cea_wheat_experiments.csv and _subplots.csv, and the light-stress workflow's controlled-environment panel reports measured yields by environmental band. A response surface fitted to it failed its sealed holdout and is not served.
- **Publisher:** Zenodo
- **URL:** https://doi.org/10.5281/zenodo.17764612
- **Format:** XLSX (yield table, 719 sub-plot rows) plus ZIP of per-run environmental logs (not acquired)
- **Coverage:** 39 chamber experiments / runs, 719 destructive grain-harvest sub-plots, PPFD 235-1084 umol m^-2 s^-1, photoperiod 6.1-22.6 h, CO2 400-1478 ppm, air temperature 21.1-28.0 degC, 39-91 day cycles
- **Variables:** grain yield per sub-plot, mean PPFD, photoperiod, CO2 setpoint, air temperature, relative humidity, cycle length, sowing and harvest dates, cultivar, system
- **Units:** kg m^-2 (grain, as harvested); umol m^-2 s^-1; h day^-1; ppm; degC; % RH; days
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/17764612)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/processed/phase30/cea_wheat_experiments.csv, cea_wheat_subplots.csv, and the shared quality record data/processed/phase30/quality.json
- **Caveat:** One cultivar (Apogee) in one facility family. The environmental logs are per-run summaries here, and PPFD varied within a run in most experiments, so a band is a group of whole experiments rather than a controlled level. Grain yield is not edible biomass and the harvest index is not modelled.

### Kilowatts to kilograms: lettuce light-use-efficiency compilation  `zenodo-kilowatts-lettuce-lue`

- **Class:** A - acquired and used in this repository
- **Why this class:** Acquired and used as an independent evaluation set, not as training data: Phase 30 scored the harvest model leave-one-study-out on these 40 studies. The model failed (310 % holdout MAPE) and forecasting was withdrawn, so the table now serves as the record of that failure.
- **Publisher:** Zenodo
- **URL:** https://doi.org/10.5281/zenodo.14640245
- **Format:** XLSX, 1 sheet, 53 published treatment means
- **Coverage:** 53 treatment means from 40 published studies; PPFD 43-428 umol m^-2 s^-1, photoperiod 12-24 h, CO2 280-2800 ppm, plant density 16-1372 plants m^-2, dry mass up to 16.5 g per plant
- **Variables:** dry mass per plant, PPFD, photoperiod, daily light integral, CO2, plant density, source study
- **Units:** g (dry mass); umol m^-2 s^-1; h day^-1; mol m^-2 d^-1; ppm; plants m^-2
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/14640245)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/processed/phase30/lettuce_multistudy.csv
- **Caveat:** Treatment means copied from publications rather than raw replicates, so within-study variance is unavailable and the unit of independence is the study, not the plant. Dry mass, not fresh mass, and no cultivar metadata.

### Portable-platform LED photoperiod extension trial in open-field tomato  `zenodo-ledphotoperiod-2025-tomato`

- **Class:** C - external validation only - wrong task, sensor or size for training
- **Why this class:** Twenty plants in ambient field conditions: an external check on the shape of a tomato growth curve, not a controlled-environment observation and far too few plants to train on.
- **Publisher:** Zenodo
- **URL:** https://doi.org/10.5281/zenodo.23759737
- **Format:** XLSX, 8 sheets
- **Coverage:** 20 tagged plants, weekly non-destructive measurements, open agricultural field
- **Variables:** plant height, leaf number, stem number, stem diameter, weekly RGB leaf area, final shoot and root mass, field environment
- **Units:** cm; mm; count; g
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/23759737)
- **Commercial use:** permitted with attribution
- **Imported:** yes - data/processed/phase26/ledphotoperiod2025_tomato_growth.csv and _harvest.csv
- **Caveat:** Open field, not a controlled environment. Ambient weather was not held constant and is not used as a model input.

### Tomato hydroponic nutrient-uptake and yield trial (Halbert-Howard et al. 2020)  `zenodo-halbert-2020-tomato-hydroponic`

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** Acquired and licensed for reuse, but replicated at row level only and not yet preprocessed into a table, so nothing consumes it.
- **Publisher:** Zenodo
- **URL:** https://doi.org/10.5281/zenodo.5084389
- **Format:** XLSX, 11 sheets
- **Coverage:** per-row shoot and fruit biomass with nutrient uptake, concentration series and recycled-solution fractions
- **Variables:** shoot fresh and dry mass, fruit number and mass, dry-matter ratio, shoot and fruit nutrient uptake, solution concentrations, recycled fraction
- **Units:** g per row; mg per row; mmol L^-1; %
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/5084389)
- **Commercial use:** permitted with attribution
- **Imported:** no - acquired only; no processed table yet
- **Caveat:** Row-level replication means the effective sample size is the number of rows, not the number of plants. Not a per-plant dataset.

### Leaf gas-exchange series for Corymbia calophylla (marri)  `zenodo-marri-2021-gasexchange`

- **Class:** D - scientific reference only - open and correct, but cannot validate this product
- **Why this class:** A mature field tree, not a crop: the physiology is real and open, and it cannot validate a crop growth or water model. Reference only.
- **Publisher:** Zenodo
- **URL:** https://doi.org/10.5281/zenodo.5130624
- **Format:** CSV, 2454 rows
- **Coverage:** field tree, per-measurement records with PAR, conductance, transpiration and leaf temperature
- **Variables:** assimilation, stomatal conductance, intercellular CO2, transpiration, PAR, leaf temperature, leaf-to-air VPD
- **Units:** umol m^-2 s^-1; mol m^-2 s^-1; mmol m^-2 s^-1; umol m^-2 s^-1; degC; kPa
- **Licence:** CC BY 4.0
- **Licence evidence:** verified (https://zenodo.org/records/5130624)
- **Commercial use:** permitted with attribution
- **Imported:** no - acquired for reference; never used as a label or a feature
- **Caveat:** Species mismatch. Any use as a crop prior would be an unstated extrapolation.

## What the catalogue does not do

- It does not rate scientific quality. A class B dataset can be scientifically weaker than a class D one; the classes are about fitness for this product's claims.
- It does not resolve licences. Where the records conflict the entry says so and the dataset stays class E until someone decides.
- It is not a download list. Only class A here is actually in `data/`.
