#!/usr/bin/env python3
"""Maintain the global dataset catalogue: 21 datasets, each with licence evidence and a class.

The catalogue answers one question for every dataset the project has considered: *could this
support a claim the product makes, under the licence it is actually distributed with?* The class is
that answer, and it is deliberately harsh:

    A  acquired and used here
    B  usable after preprocessing (open licence, right variables, right scale)
    C  external validation only (wrong task, wrong sensor, or too few rows to train on)
    D  scientific reference only (correct and open, but cannot validate this product)
    E  needs an agreement or a licence decision before it may be used at all
    F  not suitable (the licence prohibits the use)

Licence evidence is graded, never assumed:

    verified            the terms page or licence file was read for this catalogue entry
    documented-secondary  a credible secondary record (registry entry, dataset card) states it
    unverified          believed open, not checked in this pass; must be checked before use

`--check` re-renders the markdown and fails if it differs from the committed document.

    python3 ml/research/build_catalog.py [--check]
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_JSON = ROOT / "data" / "research" / "dataset_catalog.json"
TARGET_MD = ROOT / "data" / "research" / "DATASET_CATALOG.md"

CHECKS = "2026-11-09"

CLASSES = {
    "A": "acquired and used in this repository",
    "B": "usable after preprocessing - open licence, relevant variables, usable scale",
    "C": "external validation only - wrong task, sensor or size for training",
    "D": "scientific reference only - open and correct, but cannot validate this product",
    "E": "needs an agreement or a licence decision before use",
    "F": "not suitable - the licence prohibits the intended use",
}

DATASETS = [
    {
        "id": "nasa-power-daily",
        "name": "NASA POWER daily agroclimatology (community AG)",
        "publisher": "NASA Langley Research Center, POWER Project",
        "url": "https://power.larc.nasa.gov/data-access-viewer/",
        "format": "JSON / CSV / NetCDF via REST point and regional APIs",
        "coverage": "global, 0.5 x 0.625 deg (MERRA-2 grid), daily, 1981-present",
        "variables": ["ALLSKY_SFC_SW_DWN", "T2M", "T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M",
                      "WS2M", "PS", "PRECTOTCORR"],
        "units": "MJ m^-2 d^-1; degC; %; m s^-1; kPa; mm day^-1",
        "license": "NASA open data: no restrictions on use, access or download; citation requested",
        "licenseUrl": "https://registry.opendata.aws/nasa-power/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted",
        "usabilityClass": "A",
        "classReason": ("Acquired and used: the ET0 target and the emulator features are derived "
                        "from it. The licence permits redistribution and commercial use."),
        "imported": True,
        "importNote": "data/raw/nasa_power/*.json via ml/research/acquire_power_climate.py",
        "caveat": ("Reanalysis on a coarse grid: a site label is a grid-cell value, not an "
                   "instrument reading, and its MERRA-2 lineage means it cannot validate itself."),
    },
    {
        "id": "smap-l4-ssm",
        "name": "SMAP L4 Global 3-hourly 9 km surface and root-zone soil moisture (SPL4SMGP v8)",
        "publisher": "NASA NSIDC DAAC",
        "url": "https://nsidc.org/data/spl4smgp/versions/8",
        "format": "HDF5, EASE-Grid 2.0",
        "coverage": "global, 9 km, 3-hourly, from 2015-03-31",
        "variables": ["surface soil moisture", "root-zone soil moisture", "soil temperature"],
        "units": "m^3 m^-3; K",
        "license": "NASA open data policy; free Earthdata login required",
        "licenseUrl": "https://www.earthdata.nasa.gov/engage/open-data-services-and-software/data-and-information-policy",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted",
        "usabilityClass": "B",
        "classReason": ("Open, correct variables, but 9 km is open-field soil moisture - it would "
                        "support an open-field deployment, not the controlled-environment system "
                        "the product models. Not imported."),
        "imported": False,
        "importNote": "no substrate or root-zone state model exists to consume it",
        "caveat": "A different system at a different scale from a hydroponic root zone.",
    },
    {
        "id": "mod13q1-v061",
        "name": "MODIS/Terra Vegetation Indices 16-Day L3 Global 250 m (MOD13Q1 v061)",
        "publisher": "NASA LP DAAC",
        "url": "https://lpdaac.usgs.gov/products/mod13q1v061/",
        "format": "HDF4 / GeoTIFF",
        "coverage": "global, 250 m, 16-day composites, 2000-present",
        "variables": ["NDVI", "EVI", "VI quality", "pixel reliability"],
        "units": "index (scaled integer with fill 0.0001 scaling)",
        "license": "CC BY 4.0 (AWS Open Data registry entry for MODIS)",
        "licenseUrl": "https://registry.opendata.aws/modis/",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "B",
        "classReason": ("Open and preprocessed, but 250 m / 16-day is far coarser than a single "
                        "growth module. Usable for a field-scale context layer, not for the "
                        "per-module model."),
        "imported": False,
        "importNote": "no field-scale context layer in the product yet",
        "caveat": "A 16-day composite cannot resolve a growth stage that turns over in days.",
    },
    {
        "id": "gpm-imerg-3imerghh-07",
        "name": "GPM IMERG Final Precipitation L3 Half Hourly 0.1 deg (3B-HH v07)",
        "publisher": "NASA GES DISC",
        "url": "https://www.earthdata.nasa.gov/data/catalog/ges-disc-gpm-3imerghh-07",
        "format": "HDF5 / NetCDF4 / GeoTIFF",
        "coverage": "60 N-60 S, 0.1 deg, 30-minute, from 2000-06 (Final run)",
        "variables": ["precipitation", "precipitation quality index", "random error"],
        "units": "mm h^-1",
        "license": "openly shared without restriction per EOSDIS policy; Earthdata login required",
        "licenseUrl": "https://www.earthdata.nasa.gov/data/catalog/ges-disc-gpm-3imerghh-07",
        "licenseEvidence": "verified",
        "commercialUse": "permitted",
        "usabilityClass": "B",
        "classReason": ("High-quality open precipitation at 0.1 deg. It does not enter ET0 - "
                        "FAO-56 needs no precipitation term for a daily reference - and no "
                        "irrigation or drainage model consumes it yet."),
        "imported": False,
        "importNote": "candidate input for a future water-balance closure",
        "caveat": "Citation requested: Huffman, Stocker, Bolvin, Nelkin & Tan (2023), DOI 10.5067/GPM/IMERG/3B-HH/07.",
    },
    {
        "id": "era5-land",
        "name": "ERA5-Land hourly reanalysis",
        "publisher": "Copernicus Climate Change Service (C3S) via the Climate Data Store",
        "url": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land",
        "format": "NetCDF / GRIB via CDS API",
        "coverage": "global land, 0.1 deg, hourly, 1950-present",
        "variables": ["2 m temperature", "dew point", "surface solar radiation", "10 m wind",
                      "surface pressure", "precipitation"],
        "units": "K; m; J m^-2; m s^-1; Pa; m",
        "license": "Copernicus licence: free, attribution and no endorsement required",
        "licenseUrl": "https://cds.climate.copernicus.eu/licences/",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "B",
        "classReason": ("The independent weather source this project needs, and the cheapest way "
                        "to close the `independent-et0` gap. Not imported: the CDS API needs a "
                        "free personal token, which the owner has not issued."),
        "imported": False,
        "importNote": "blocked on a free CDS API token",
        "caveat": "Same family of physics as every reanalysis; it is independent of MERRA-2, not of reanalysis.",
    },
    {
        "id": "soilgrids-2-0",
        "name": "SoilGrids 2.0 predicted soil properties",
        "publisher": "ISRIC - World Soil Information",
        "url": "https://soilgrids.org/",
        "format": "GeoTIFF / VRT via WebDAV and REST",
        "coverage": "global, 250 m, 7 standard depths to 200 cm",
        "variables": ["clay", "sand", "silt", "bulk density", "organic carbon", "pH", "CEC"],
        "units": "g kg^-1; kg dm^-3; dS m^-1; pH",
        "license": "CC BY 4.0",
        "licenseUrl": "https://www.isric.org/about/data-policy",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "B",
        "classReason": ("Open and useful, but it describes soil, and the platform models a "
                        "hydroponic or substrate system. Relevant only if an open-field mode is "
                        "added."),
        "imported": False,
        "importNote": "no soil model in the product",
        "caveat": "Predictions, with their own uncertainty; not measurements at any site.",
    },
    {
        "id": "chirps-v2-0",
        "name": "CHIRPS v2.0 quasi-global precipitation",
        "publisher": "UCSB Climate Hazards Center",
        "url": "https://www.chc.ucsb.edu/data/chirps",
        "format": "GeoTIFF / NetCDF",
        "coverage": "50 N-50 S, 0.05 deg, daily, 1981-present",
        "variables": ["precipitation"],
        "units": "mm day^-1",
        "license": "public domain per the CHC data page; citation requested",
        "licenseUrl": "https://www.chc.ucsb.edu/data/chirps",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "B",
        "classReason": ("Open, finer than IMERG for accumulation, but precipitation is not an "
                        "input to daily reference ET0 and no water-balance model consumes it."),
        "imported": False,
        "importNote": "candidate precipitation input alongside IMERG; one of the two is enough",
        "caveat": "Station-blended, so its independence from POWER depends on the station network.",
    },
    {
        "id": "gwhd2021",
        "name": "Global Wheat Head Detection 2021",
        "publisher": "GWHD consortium, hosted on Zenodo",
        "url": "https://zenodo.org/records/5092309",
        "format": "JPEG images with Pascal-VOC-style bounding boxes",
        "coverage": "6,515 images, 275,187 wheat heads, 11 countries, 44 sessions",
        "variables": ["RGB imagery", "head bounding boxes"],
        "units": "pixels; boxes in image coordinates",
        "license": "CC BY 4.0",
        "licenseUrl": "https://zenodo.org/records/5092309",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "C",
        "classReason": ("Excellent labelled data for a task the product does not perform: wheat "
                        "head detection in field imagery. No imaging pipeline exists, so this is "
                        "external validation material only, never a training set for a capability "
                        "we do not ship."),
        "imported": False,
        "importNote": "no imaging capability to validate",
        "caveat": "A model trained here would detect wheat, not the crops this platform simulates.",
    },
    {
        "id": "osdr-plant-experiments",
        "name": "NASA OSDR / GeneLab plant experiment corpus",
        "publisher": "NASA Open Science Data Repository (OSDR)",
        "url": "https://osdr.nasa.gov/bio/",
        "format": "per-study ISA-Tab, tables, images, omics",
        "coverage": "per study; small, heterogeneous, mostly Arabidopsis",
        "variables": ["per-study assay metadata", "some harvest mass and phenotype tables"],
        "units": "per study",
        "license": "NASA open data policy: no restrictions on use; per-study citation",
        "licenseUrl": "https://osdr.nasa.gov/bio/about/policies.html",
        "licenseEvidence": "verified",
        "commercialUse": "permitted",
        "usabilityClass": "C",
        "classReason": ("Used for provenance and as a qualitative prior only. The studies are too "
                        "few, too heterogeneous and mostly the wrong species to train or validate "
                        "a yield model."),
        "imported": True,
        "importNote": "data/metadata/dataset_manifest.json - provenance only, never a feature",
        "caveat": "Microgravity studies exist here, but none with the replication a response function needs.",
    },
    {
        "id": "peerj17085-lettuce",
        "name": "Published lettuce light-intensity and temperature trial (PeerJ 17085)",
        "publisher": "PeerJ (open access article with tables)",
        "url": "https://peerj.com/articles/17085/",
        "format": "HTML/Markdown tables in an open-access article",
        "coverage": "6 observations, one cultivar, light intensity x temperature",
        "variables": ["fresh mass", "light intensity", "temperature"],
        "units": "g per plant; umol m^-2 s^-1; degC",
        "license": "article CC BY 4.0; the extracted table is a derived dataset",
        "licenseUrl": "https://peerj.com/articles/17085/",
        "licenseEvidence": "unverified",
        "commercialUse": "permitted with attribution (article licence)",
        "usabilityClass": "C",
        "classReason": ("Six observations. Enough to sit beside a prediction as an external "
                        "check, nowhere near enough to fit or tune anything, and it is never used "
                        "as training data."),
        "imported": True,
        "importNote": "data/literature/external_lettuce_peerj17085.json - validation only",
        "caveat": "One cultivar, one facility: agreement here is a sanity check, not validation.",
    },
    {
        "id": "deepweeds",
        "name": "DeepWeeds: weed image classification in northern Australia",
        "publisher": "Commonwealth Scientific and Industrial Research Organisation (CSIRO) via Zenodo",
        "url": "https://zenodo.org/records/5542236",
        "format": "JPEG images with species labels",
        "coverage": "17,509 images, 8 weed species plus negative class, field imagery",
        "variables": ["RGB imagery", "species label", "GPS location"],
        "units": "pixels",
        "license": "CC BY 4.0 per the Zenodo record",
        "licenseUrl": "https://zenodo.org/records/5542236",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "C",
        "classReason": ("Open field-weed imagery for a classification task the product does not "
                        "perform. Recorded because it is the standard counter-example to using "
                        "PlantVillage for anything field-realistic."),
        "imported": False,
        "importNote": "no weed or imagery capability exists",
        "caveat": "Not checked against the platform's crop set; validation value only.",
    },
    {
        "id": "fluxnet2015",
        "name": "FLUXNET2015 eddy-covariance flux tower dataset",
        "publisher": "FLUXNET community, distributed via the FLUXNET data portal",
        "url": "https://fluxnet.org/data/fluxnet2015-dataset/",
        "format": "CSV per site, half-hourly and aggregated",
        "coverage": "212 sites worldwide, 1991-2014, half-hourly to annual",
        "variables": ["latent heat flux (LE)", "sensible heat", "net radiation", "air temperature",
                      "vapour pressure deficit", "wind speed", "soil moisture"],
        "units": "W m^-2; degC; hPa; m s^-1; %",
        "license": "CC BY 4.0 per site, subject to accepting the FLUXNET data policy",
        "licenseUrl": "https://fluxnet.org/data/data-policy/",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted with attribution, after accepting the data policy",
        "usabilityClass": "C",
        "classReason": ("The strongest validation material this project has identified: measured "
                        "latent heat flux at grassland towers is an independent check on a "
                        "reference-ET calculation, which is exactly what the `independent-et0` "
                        "gap asks for. It cannot train the emulator - the towers are not the six "
                        "reference sites and the footprint is a field, not a module - so it is "
                        "validation only, and it is not imported yet."),
        "imported": False,
        "importNote": "requires accepting the data policy; tower footprints differ from the sites",
        "caveat": "Eddy-covariance energy-balance closure is typically 10-20 % off, so a mismatch "
                  "of that size would not settle the question either way.",
    },
    {
        "id": "plantvillage",
        "name": "PlantVillage leaf-disease image dataset",
        "publisher": "Penn State / PlantVillage (multiple mirrors)",
        "url": "https://huggingface.co/datasets/mahmood/plantvillage",
        "format": "JPEG images with disease labels",
        "coverage": "54,306 images, 38 classes, lab-collected leaves on uniform backgrounds",
        "variables": ["RGB leaf imagery", "crop and disease label"],
        "units": "pixels",
        "license": "conflicting records: CC BY-SA 3.0 (HF card) vs GPL-2 (Kaggle mirror) vs none (GitHub)",
        "licenseUrl": "https://huggingface.co/datasets/mahmood/plantvillage",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "undecided - the ShareAlike term and the conflicting records disagree",
        "usabilityClass": "E",
        "classReason": ("A commercial product cannot proceed on a dataset whose own distribution "
                        "points state three different licences, one of which is a copyleft that "
                        "would reach the model weights. Needs a licence decision, and its lab "
                        "photographs would transfer poorly to field imagery in any case."),
        "imported": False,
        "importNote": "licence decision required before any use",
        "caveat": "Widely used as if open; the licence conflict is the reason it is not used here.",
    },
    {
        "id": "wapor",
        "name": "FAO WaPOR - water productivity through open access of remotely sensed derived data",
        "publisher": "FAO",
        "url": "https://www.fao.org/in-action/remote-sensing-for-water-productivity/en/",
        "format": "GeoTIFF via FAO portal and API",
        "coverage": "Africa and Near East, 100 m / 250 m, decadal, 2009-present",
        "variables": ["actual evapotranspiration", "biomass production", "water productivity",
                      "soil moisture"],
        "units": "mm per dekad; kg ha^-1",
        "license": "CC BY-NC-SA 4.0 - non-commercial",
        "licenseUrl": "https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-portal/en/",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "not permitted (non-commercial)",
        "usabilityClass": "E",
        "classReason": ("The only open product that measures actual (not reference) "
                        "evapotranspiration, and it is non-commercial. A commercial deployment "
                        "would need an agreement with FAO; it cannot be used as delivered."),
        "imported": False,
        "importNote": "non-commercial licence is disqualifying under this project's rules",
        "caveat": "Would be the strongest validation of a crop water model if the licence allowed it.",
    },
    {
        "id": "planet-scope",
        "name": "PlanetScope daily 3 m imagery",
        "publisher": "Planet Labs PBC",
        "url": "https://www.planet.com/products/planet-imagery/",
        "format": "GeoTIFF, orthorectified scenes",
        "coverage": "global, 3-5 m, daily revisit, commercial subscription",
        "variables": ["multispectral imagery (8 bands)", "analytic and visual products"],
        "units": "reflectance",
        "license": "commercial subscription; no redistribution of derived products without agreement",
        "licenseUrl": "https://www.planet.com/terms-of-use/",
        "licenseEvidence": "unverified",
        "commercialUse": "requires a paid agreement",
        "usabilityClass": "E",
        "classReason": ("The only daily 3 m imagery that would make per-module imaging feasible, "
                        "and it is a paid subscription. Out of scope by the project's no-paid-"
                        "services rule."),
        "imported": False,
        "importNote": "paid service; forbidden by the project constraints",
        "caveat": "Recorded so the imaging gap has a named, priced answer rather than a vague one.",
    },
    {
        "id": "openet",
        "name": "OpenET ensemble evapotranspiration",
        "publisher": "OpenET consortium",
        "url": "https://openetdata.org/",
        "format": "API / GeoTIFF, monthly and daily",
        "coverage": "continental United States, 30 m and field-scale, 2016-present",
        "variables": ["actual evapotranspiration", "ensemble and per-model estimates"],
        "units": "mm day^-1",
        "license": "free for research with registration; commercial terms require an agreement",
        "licenseUrl": "https://openetdata.org/about/",
        "licenseEvidence": "unverified",
        "commercialUse": "requires an agreement",
        "usabilityClass": "E",
        "classReason": ("Actual ET is exactly the missing measurement class, but the coverage is "
                        "US-only and the commercial terms are not open. Needs a licence decision "
                        "and would still not cover the six reference sites outside the US."),
        "imported": False,
        "importNote": "licence decision plus a coverage limit",
        "caveat": "An ensemble of models, so its disagreement is itself the uncertainty estimate.",
    },
    {
        "id": "plantclef2021",
        "name": "PlantCLEF 2021 plant identification challenge data",
        "publisher": "CLEF / LifeCLEF",
        "url": "https://www.imageclef.org/PlantCLEF2021",
        "format": "JPEG images with species labels, registration required",
        "coverage": "millions of plant images, species-level labels, herbarium and field",
        "variables": ["RGB imagery", "species label"],
        "units": "pixels",
        "license": "research-use terms; redistribution restricted; per-image provenance varies",
        "licenseUrl": "https://www.imageclef.org/PlantCLEF2021",
        "licenseEvidence": "unverified",
        "commercialUse": "not permitted without agreement",
        "usabilityClass": "E",
        "classReason": ("Species identification is not a capability the product claims, and the "
                        "agreement forbids redistribution. Kept in the catalogue only so a future "
                        "contributor does not mistake it for an open dataset."),
        "imported": False,
        "importNote": "agreement required; task not in scope",
        "caveat": "Aggregated from many sources with heterogeneous underlying licences.",
    },
    {
        "id": "faostat",
        "name": "FAOSTAT crop production and yield statistics",
        "publisher": "FAO",
        "url": "https://www.fao.org/faostat/en/",
        "format": "CSV / API",
        "coverage": "country-year, global, 1961-present",
        "variables": ["production", "area harvested", "yield", "producer prices"],
        "units": "t; ha; kg ha^-1; USD",
        "license": "CC BY 4.0",
        "licenseUrl": "https://www.fao.org/contact-us/terms/en/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "D",
        "classReason": ("Free and authoritative, and structurally unable to validate this "
                        "product: a country-year yield aggregate cannot be compared with a "
                        "per-square-metre controlled-environment model. Reference context only."),
        "imported": False,
        "importNote": "level of aggregation incompatible with the model's support",
        "caveat": "National aggregates mix field, greenhouse and subsistence production.",
    },
    {
        "id": "koppen-geiger-beck",
        "name": "Present-day and future Koppen-Geiger climate classification (Beck et al. 2018)",
        "publisher": "University of Idaho / ETH Zurich, hosted on figshare",
        "url": "https://figshare.com/articles/dataset/Present_and_future_K_ppen-Geiger_climate_classification_maps_at_1-km_resolution/6396959",
        "format": "GeoTIFF, 1 km",
        "coverage": "global, 1 km, 1980-2016 and projections to 2071-2100",
        "variables": ["Koppen-Geiger class"],
        "units": "class code",
        "license": "CC BY 4.0",
        "licenseUrl": "https://figshare.com/articles/dataset/Present_and_future_K_ppen-Geiger_climate_classification_maps_at_1-km_resolution/6396959",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "usabilityClass": "D",
        "classReason": ("Used only to justify why the six reference sites were chosen to span "
                        "climates. A categorical map cannot validate a continuous flux."),
        "imported": False,
        "importNote": "context for site selection, not an input",
        "caveat": "Classification, not weather; two sites in one class can differ entirely.",
    },
    {
        "id": "nasa-nex-gddp-cmip6",
        "name": "NASA NEX-GDDP-CMIP6 statistically downscaled climate projections",
        "publisher": "NASA Earth Exchange (NEX)",
        "url": "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6",
        "format": "NetCDF, 0.25 deg",
        "coverage": "global, 0.25 deg, daily, 1950-2100 across CMIP6 models",
        "variables": ["tasmax", "tasmin", "pr", "hurs", "rsds", "sfcWind"],
        "units": "K; mm day^-1; %; W m^-2; m s^-1",
        "license": "open (NASA NEX); model-specific citation requested",
        "licenseUrl": "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "permitted",
        "usabilityClass": "D",
        "classReason": ("The right product for a future-climate siting claim, which the platform "
                        "does not make. Validating an observed-weather ET0 study against "
                        "projections would be a category error."),
        "imported": False,
        "importNote": "out of scope for an observed-weather study",
        "caveat": "Downscaled model output: uncertainty is the spread across models, not one file.",
    },
    {
        "id": "plantwild",
        "name": "PlantWild in-the-wild plant image dataset",
        "publisher": "PlantWild authors, hosted on Hugging Face",
        "url": "https://aiinagriculture.org/datasets/",
        "format": "JPEG images with labels",
        "coverage": "field-collected plant imagery, multiple species",
        "variables": ["RGB imagery", "labels"],
        "units": "pixels",
        "license": "CC BY-NC-ND 4.0 - non-commercial, no derivatives",
        "licenseUrl": "https://aiinagriculture.org/datasets/",
        "licenseEvidence": "documented-secondary",
        "commercialUse": "not permitted (non-commercial, no derivatives)",
        "usabilityClass": "F",
        "classReason": ("Not suitable at any effort: the no-derivatives term prohibits training "
                        "on it, and training a model is a derivative use. Recorded as the "
                        "clearest example in this list of a licence that forbids the intended "
                        "use outright."),
        "imported": False,
        "importNote": "licence prohibits the intended use",
        "caveat": "Kept in the catalogue so the exclusion is a documented decision, not an omission.",
    },
]


def summary(datasets: list[dict]) -> dict:
    by_class: dict[str, list[str]] = {}
    by_evidence: dict[str, int] = {}
    for dataset in datasets:
        by_class.setdefault(dataset["usabilityClass"], []).append(dataset["id"])
        by_evidence[dataset["licenseEvidence"]] = by_evidence.get(dataset["licenseEvidence"], 0) + 1
    return {"byClass": by_class, "byLicenseEvidence": by_evidence}


def render(payload: dict) -> str:
    datasets = payload["datasets"]
    counts = summary(datasets)
    lines = [
        "# SpaceAgriSim Dataset Catalogue",
        "",
        f"Generated from `data/research/dataset_catalog.json` on {payload['generatedOn']} by "
        "`ml/research/build_catalog.py`. Edit the JSON, not this file.",
        "",
        "Every dataset the project has evaluated, with the licence evidence behind its class. The "
        "class answers one question: could this support a claim the product makes, under the "
        "licence it is actually distributed with?",
        "",
        f"**{len(datasets)} datasets evaluated.** "
        + ", ".join(f"{letter}: {len(counts['byClass'].get(letter, []))}"
                    for letter in sorted(CLASSES)) + ".",
        "",
        "## Classes",
        "",
        "| Class | Meaning | Datasets |",
        "|---|---|---|",
    ]
    for letter, meaning in CLASSES.items():
        ids = counts["byClass"].get(letter, [])
        lines.append(f"| **{letter}** | {meaning} | {len(ids)} |")

    lines += [
        "",
        "## Licence evidence",
        "",
        "| Grade | Meaning | Datasets |",
        "|---|---|---|",
        f"| verified | the terms were read for this entry | "
        f"{counts['byLicenseEvidence'].get('verified', 0)} |",
        f"| documented-secondary | a credible registry or dataset card states it | "
        f"{counts['byLicenseEvidence'].get('documented-secondary', 0)} |",
        f"| unverified | believed open, not checked; must be checked before use | "
        f"{counts['byLicenseEvidence'].get('unverified', 0)} |",
        "",
        "## Summary",
        "",
        "| Dataset | Class | Licence | Commercial use | Imported |",
        "|---|---|---|---|---|",
    ]
    for dataset in datasets:
        lines.append(f"| [{dataset['name']}](#{dataset['id']}) | **{dataset['usabilityClass']}** | "
                     f"{dataset['license']} | {dataset['commercialUse']} | "
                     f"{'yes' if dataset['imported'] else 'no'} |")

    lines += ["", "## Detail", ""]
    for dataset in datasets:
        lines += [
            f"### {dataset['name']}  `{dataset['id']}`",
            "",
            f"- **Class:** {dataset['usabilityClass']} - {CLASSES[dataset['usabilityClass']]}",
            f"- **Why this class:** {dataset['classReason']}",
            f"- **Publisher:** {dataset['publisher']}",
            f"- **URL:** {dataset['url']}",
            f"- **Format:** {dataset['format']}",
            f"- **Coverage:** {dataset['coverage']}",
            f"- **Variables:** {', '.join(dataset['variables'])}",
            f"- **Units:** {dataset['units']}",
            f"- **Licence:** {dataset['license']}",
            f"- **Licence evidence:** {dataset['licenseEvidence']} ({dataset['licenseUrl']})",
            f"- **Commercial use:** {dataset['commercialUse']}",
            f"- **Imported:** {'yes - ' if dataset['imported'] else 'no - '}{dataset['importNote']}",
            f"- **Caveat:** {dataset['caveat']}",
            "",
        ]
    lines += [
        "## What the catalogue does not do",
        "",
        "- It does not rate scientific quality. A class B dataset can be scientifically weaker "
        "than a class D one; the classes are about fitness for this product's claims.",
        "- It does not resolve licences. Where the records conflict the entry says so and the "
        "dataset stays class E until someone decides.",
        "- It is not a download list. Only class A here is actually in `data/`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    ids = [dataset["id"] for dataset in DATASETS]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate dataset ids")
    for dataset in DATASETS:
        if dataset["usabilityClass"] not in CLASSES:
            raise SystemExit(f"{dataset['id']}: unknown class {dataset['usabilityClass']}")

    payload = {
        "catalogue": "SpaceAgriSim evaluated datasets",
        "generatedBy": "ml/research/build_catalog.py",
        "generatedOn": CHECKS if not TARGET_JSON.is_file() else
        json.loads(TARGET_JSON.read_text(encoding="utf-8")).get("generatedOn", CHECKS),
        "classDefinitions": CLASSES,
        "counts": summary(DATASETS),
        "datasets": DATASETS,
    }
    rendered = render(payload)

    if args.check:
        if not TARGET_JSON.is_file() or not TARGET_MD.is_file():
            print("MISSING catalogue files; run without --check")
            return 1
        committed = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
        if committed["datasets"] != DATASETS:
            print("STALE JSON: the script's dataset list differs from data/research/dataset_catalog.json")
            return 1
        if TARGET_MD.read_text(encoding="utf-8") != render(committed):
            print("STALE markdown: re-render from the JSON")
            return 1
        print(f"catalogue up to date ({len(DATASETS)} datasets)")
        return 0

    TARGET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TARGET_JSON.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    TARGET_MD.write_text(rendered, encoding="utf-8")
    counts = summary(DATASETS)
    print(f"wrote {TARGET_MD.relative_to(ROOT)}: {len(DATASETS)} datasets "
          + ", ".join(f"{letter}:{len(counts['byClass'].get(letter, []))}"
                      for letter in sorted(CLASSES)))
    print("licence evidence:", counts["byLicenseEvidence"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
