# SpaceAgriSim Dataset Catalogue

Generated from `data/research/dataset_catalog.json` on 2026-11-09 by `ml/research/build_catalog.py`. Edit the JSON, not this file.

Every dataset the project has evaluated, with the licence evidence behind its class. The class answers one question: could this support a claim the product makes, under the licence it is actually distributed with?

**21 datasets evaluated.** A: 1, B: 6, C: 5, D: 3, E: 5, F: 1.

## Classes

| Class | Meaning | Datasets |
|---|---|---|
| **A** | acquired and used in this repository | 1 |
| **B** | usable after preprocessing - open licence, relevant variables, usable scale | 6 |
| **C** | external validation only - wrong task, sensor or size for training | 5 |
| **D** | scientific reference only - open and correct, but cannot validate this product | 3 |
| **E** | needs an agreement or a licence decision before use | 5 |
| **F** | not suitable - the licence prohibits the intended use | 1 |

## Licence evidence

| Grade | Meaning | Datasets |
|---|---|---|
| verified | the terms were read for this entry | 7 |
| documented-secondary | a credible registry or dataset card states it | 10 |
| unverified | believed open, not checked; must be checked before use | 4 |

## Summary

| Dataset | Class | Licence | Commercial use | Imported |
|---|---|---|---|---|
| [NASA POWER daily agroclimatology (community AG)](#nasa-power-daily) | **A** | NASA open data: no restrictions on use, access or download; citation requested | permitted | yes |
| [SMAP L4 Global 3-hourly 9 km surface and root-zone soil moisture (SPL4SMGP v8)](#smap-l4-ssm) | **B** | NASA open data policy; free Earthdata login required | permitted | no |
| [MODIS/Terra Vegetation Indices 16-Day L3 Global 250 m (MOD13Q1 v061)](#mod13q1-v061) | **B** | CC BY 4.0 (AWS Open Data registry entry for MODIS) | permitted with attribution | no |
| [GPM IMERG Final Precipitation L3 Half Hourly 0.1 deg (3B-HH v07)](#gpm-imerg-3imerghh-07) | **B** | openly shared without restriction per EOSDIS policy; Earthdata login required | permitted | no |
| [ERA5-Land hourly reanalysis](#era5-land) | **B** | Copernicus licence: free, attribution and no endorsement required | permitted with attribution | no |
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
| [NASA NEX-GDDP-CMIP6 statistically downscaled climate projections](#nasa-nex-gddp-cmip6) | **D** | open (NASA NEX); model-specific citation requested | permitted | no |
| [PlantWild in-the-wild plant image dataset](#plantwild) | **F** | CC BY-NC-ND 4.0 - non-commercial, no derivatives | not permitted (non-commercial, no derivatives) | no |

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

- **Class:** B - usable after preprocessing - open licence, relevant variables, usable scale
- **Why this class:** The independent weather source this project needs, and the cheapest way to close the `independent-et0` gap. Not imported: the CDS API needs a free personal token, which the owner has not issued.
- **Publisher:** Copernicus Climate Change Service (C3S) via the Climate Data Store
- **URL:** https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land
- **Format:** NetCDF / GRIB via CDS API
- **Coverage:** global land, 0.1 deg, hourly, 1950-present
- **Variables:** 2 m temperature, dew point, surface solar radiation, 10 m wind, surface pressure, precipitation
- **Units:** K; m; J m^-2; m s^-1; Pa; m
- **Licence:** Copernicus licence: free, attribution and no endorsement required
- **Licence evidence:** documented-secondary (https://cds.climate.copernicus.eu/licences/)
- **Commercial use:** permitted with attribution
- **Imported:** no - blocked on a free CDS API token
- **Caveat:** Same family of physics as every reanalysis; it is independent of MERRA-2, not of reanalysis.

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

- **Class:** D - scientific reference only - open and correct, but cannot validate this product
- **Why this class:** The right product for a future-climate siting claim, which the platform does not make. Validating an observed-weather ET0 study against projections would be a category error.
- **Publisher:** NASA Earth Exchange (NEX)
- **URL:** https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6
- **Format:** NetCDF, 0.25 deg
- **Coverage:** global, 0.25 deg, daily, 1950-2100 across CMIP6 models
- **Variables:** tasmax, tasmin, pr, hurs, rsds, sfcWind
- **Units:** K; mm day^-1; %; W m^-2; m s^-1
- **Licence:** open (NASA NEX); model-specific citation requested
- **Licence evidence:** documented-secondary (https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6)
- **Commercial use:** permitted
- **Imported:** no - out of scope for an observed-weather study
- **Caveat:** Downscaled model output: uncertainty is the spread across models, not one file.

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

## What the catalogue does not do

- It does not rate scientific quality. A class B dataset can be scientifically weaker than a class D one; the classes are about fitness for this product's claims.
- It does not resolve licences. Where the records conflict the entry says so and the dataset stays class E until someone decides.
- It is not a download list. Only class A here is actually in `data/`.
