# Phase 2 NASA crop and life-support data-gap audit

Audited 2026-11-06 against the official NASA OSDR study/file APIs, NASA Science pages and NTRS. This is a suitability review, not a claim that every referenced study has been downloaded or is fit for prediction.

## Method

For each candidate, the review records the official URL, accessible-file evidence, measurement type, independent-experiment evidence and a conservative status. OSDR file records were queried directly at `https://osdr.nasa.gov/osdr/data/osd/meta/{id}` and `.../files/{id}`. A dataset is not called trainable merely because it contains crop names or environmental metadata.

## Existing registry recheck

The existing 13-study registry is present and its selected raw-file checksum report covers 28 files. OSD-655 remains the only included study with a small harvested-mass table used by an artifact. OSD-745 provides nutritional/elemental tables, OSD-767 provides tomato molecular data, and the remaining entries are molecular, microbiological, technical or metadata-context evidence for the current prediction targets.

## Newly reviewed NASA candidates

| Candidate | Official source and accessible evidence | Measurements found | Independence / controls | Classification |
| --- | --- | --- | --- | --- |
| OSD-895, EDEN ISS greenhouse, Antarctica | [OSDR study](https://osdr.nasa.gov/bio/repo/data/studies/OSD-895); official API returns 19 samples, one plant-biomass assay, a 72,795-byte metadata ZIP and a 4,311,817-byte supplement | edible fresh biomass, above/below-ground dry biomass, harvest age, environmental setpoints; 2018 Earth analogue greenhouse | 19 sample records cover crop/cycle summaries; crop protocols and harvest methods differ | Directly useful for scientific calibration/benchmarking; not sufficient by itself for a general ML model until the assay table is extracted and cycle-level independence is confirmed |
| OSD-723, ionic silver lettuce hydroponics | [OSDR study](https://osdr.nasa.gov/bio/repo/data/studies/OSD-723); API returns 309 samples and 621 files, including metadata archive and sequencing files | published study description reports lettuce growth response and nutrient uptake; registered assay is whole-genome shotgun sequencing | treatment, growth medium, time and organism part factors exist; downloaded record listing does not itself establish a clean numeric biomass table | Molecular/biological context and possible preprocessing candidate; not added as a yield model source without an accessible, unit-resolved growth table |
| OSD-412, VEG-03D multi-species leafy greens | [OSDR study](https://osdr.nasa.gov/bio/repo/data/studies/OSD-412); API returns 43 samples and 89 files | amplicon microbiome measurements | flight/ground-associated plant/pillow samples; assay is microbiome sequencing | Molecular/microbiome context only, not crop-yield training |
| Plant Habitat-02 radish | [NASA Science investigation](https://science.nasa.gov/biological-physical/investigations/plant-habitat-02-wvqpm/) | NASA describes metabolic, physiological, mineral and generation-time objectives for APH-grown radishes | space investigation; no downloadable numeric table was verified in this audit | Investigation context; await an official downloadable measurement record before modelling |
| CELSS/BPC wheat BWT931 | [NASA NTRS record](https://ntrs.nasa.gov/citations/19940009506) | record describes 17 validated life-support parameters including water purification, CO2 removal, O2 production and biomass | report says validated database access was subject to approval/limitations; public PDF is downloadable | Scientifically valuable calibration reference; not an openly downloadable numerical training table |

## Prediction-target evidence matrix

| Target | Usable NASA numerical evidence now | Status | Rationale |
| --- | --- | --- | --- |
| Crop biomass / harvest | OSD-655 small mizuna table; OSD-895 biomass assay metadata and supplement | Limited | OSD-655 has 14 outcomes; OSD-895 needs table extraction and cycle-independence review |
| Biomass over time | OSD-895 has harvest-age/cycle context, but no verified repeated time-series table yet | Gap | No time-resolved, harmonized NASA crop series verified |
| Water consumption / transpiration | OSD-655 irrigation supplied; BPC report describes database but data not openly retrieved | Gap | Supplied irrigation is not physiological transpiration |
| Water recovery | BPC report context only | Unsupported | No accessible numerical recovery series verified |
| CO2 uptake / O2 production | BPC report context only | Unsupported | No openly downloadable time series verified |
| Light / spectrum response | OSD-655 and existing Veggie metadata report treatments; OSD-767 molecular experiment has spectral context | Context only | Not a sufficiently independent numerical response dataset for general production prediction |
| Temperature / humidity response | EDEN/OSD-895 setpoints, not a validated response grid | Calibration context | Setpoint is not an independently varied response variable |
| Nutrient conditions | OSD-723 treatment context; OSD-655 nutrient assays | Context / outcome-specific | Neither currently supplies a harmonized general crop-growth training target |
| Radiation response | Existing OSDR studies report mission/radiation context | Unsupported for dose-response prediction | No matched controlled dose-response crop table verified |
| Partial gravity | Existing Arabidopsis work, no compatible food-crop response table verified | Unsupported | No evidence for Moon/Mars crop extrapolation |

## Findings and decisions

1. OSD-895 is the highest-value newly identified NASA candidate because its official metadata records plant-biomass fields and an accessible small metadata archive. It will be added only after preserving the official metadata, inspecting actual columns/units and documenting cycle-level limitations.
2. The BPC/CELSS record is an important physical-validation reference, but the NTRS page explicitly says the validated numerical database had access limitations. The public report must not be represented as an open telemetry dataset.
3. OSD-723 and OSD-412 should not be merged with biomass datasets: their registered assays are sequencing/microbiome evidence, not a verified common yield target.
4. There remains no verified NASA numerical basis for live ISS telemetry, water recovery, CO2 assimilation, oxygen evolution, radiation-dose prediction or lunar/Martian crop prediction.

## Data handling requirements for follow-up

- Keep NASA and external sources separate in storage, UI and model cards.
- Preserve native units and source protocol; do not pool species, cultivar or harvest conventions without an explicit harmonization specification.
- Record file size, checksum, access date, license/terms and download URL for each acquired file.
- Use experiment/cycle grouping for validation; do not inflate sample counts using repeated or derived rows.
- Retain unsupported targets as simulator assumptions rather than converting them to ML claims.
