# Phase 32 — dataset acquisition: what was searched, what was acquired, what was refused

The brief for this phase is that a DOI or a catalogue entry is not an acquisition, that no synthetic
data may stand in as evidence, and that a feature whose data cannot be obtained is removed rather
than left as a promise. This file records the outcome of that search for every feature the Phase 26
readiness audit listed as data-blocked or experimental.

## Acquired and verified in this phase

| Dataset | Study | Licence | Verification |
| --- | --- | --- | --- |
| OSD-46 Arabidopsis radiation microarray (GeneLab GLDS-46) | "Gamma radiation and HZE treatment of seedlings in Arabidopsis" (UC Davis / Brookhaven) | Public OSDR access; retain attribution, comply with OSDR terms | Re-downloaded during Phase 32 from `nasa-osdr.s3.us-west-2.amazonaws.com/OSD-46/version-6/array/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv`: **23 794 742 bytes**, sha256 `f15c4179dbbebdfd39c53ffb906f6251ed1fc3fa3c926efc3c71c4736eefda27`, matching the checksum pinned in `data/metadata/dataset_manifest.json` |

That checksum match is what makes the calibration in `ml/evaluation/phase32_radiation_calibration.json`
reproducible: the 44 arrays scored there are the same bytes the shipped classifiers were trained on.

Already acquired in earlier phases and used unchanged in this one: the WUR lettuce experiment
tables (4TU.ResearchData, CC BY 4.0), the OSD-780 mizuna plate counts and the OSD-655 VEG harvest
records (public OSDR access), Schröder et al. 2021 pot evapotranspiration (Zenodo, CC BY 4.0), the
Kilowatts lettuce LUE compilation (Zenodo, CC BY 4.0) and the CEA wheat experiments (Zenodo,
CC BY 4.0).

## Searched and refused, by feature

| Feature | Searched | Finding | Outcome |
| --- | --- | --- | --- |
| Cultivar-specific growth parameters | NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley Data, Dataverse, USDA Ag Data Commons, OpenAIRE, journal supplements | No experiment in the catalogue carries a cultivar label usable as a model input; each study reports one cultivar, so a cultivar effect is not identifiable from the pooled data | **Removed** |
| Nutrient solution management | the same repositories, plus hydroponic-nutrient keywords | The acquired hydroponic archive reports solution composition per treatment, not a per-plant response the platform could predict | **Removed** |
| Mission energy and mass budget | NASA NTRS, OSDR, Zenodo | No mission-level energy or mass budget dataset exists in the repository or in the search results | **Removed** |
| Root-zone water status | OSDR, Zenodo, Dryad, PANGAEA, Mendeley | No root-zone water-potential time series. The simulator's single well-mixed store is an assumption inside the water calculation, not a measurement of root-zone status | **Removed** |
| Plant health from imagery | Zenodo, Figshare, Kaggle-mirrored PlantVillage, PlantCLEF | Paired imagery and harvest labels exist, but the catalogue's imagery sources are licence classes E/F (research-only, no-redistribution, or conflicting records), which cannot back a served model | **Removed** |
| Siting for a future climate | NASA NEX-GDDP-CMIP6, Copernicus, ESGF | The downscaled product is catalogued at licence class D and could not be acquired within this phase | **Removed** |
| Response to LED spectra | Zenodo (GreenLight 2024 lettuce), Zenodo (CEA wheat cv. Apogee) | Two measured datasets obtained in Phases 29-30 | **Served as a measured group comparison only**; the fitted response surface failed its sealed holdout at 297.46 % MAPE and was deleted rather than served behind a caveat |
| Radiation-quality and exposure classification | OSD-46 | Acquired and checksum-verified | **Served with a measured calibration** (Phase 32) |

## Acquisition attempts that failed, and why they are recorded rather than retried

The following were attempted in Phase 30 and Phase 31 and failed for environmental reasons, not
because the data does not exist. They are recorded here with the failure, and the dependent claims
were scoped down instead of being propped up:

* **USDA Ag Data Commons** — DNS unresolvable from this environment.
* **figshare search API** — rejects scripted queries from this environment.
* **Dryad** — HTTP 401 on the API without institutional credentials.

The consequence is stated in the product: `GET /api/reference-et0/model` and every ET0 response say
that the implementation is validated against the FAO-56 worked examples and that **no measured-ET0
station benchmark is bundled**. That is a documented limitation, not an open task — making it an
open task would be honest only if a route to the data existed.

## Ethics of the count

No dataset was downloaded to raise a count. Every dataset above is used by code that ships, and a
dataset that no longer backs a shipped claim was removed from the catalogue's served surface rather
than left in a table. The eight features removed in this phase did not fail for lack of searching;
they failed because the data that would support them either does not exist in obtainable form or
arrives under a licence that forbids redistribution.
