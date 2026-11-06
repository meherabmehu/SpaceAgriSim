# External scientific data inventory

Reviewed 2026-11-06. External sources are retained separately from NASA OSDR sources and are never described as spaceflight evidence.

| Source | Data and access evidence | Intended status | Decision |
| --- | --- | --- | --- |
| [WUR/4TU lettuce growth dataset](https://doi.org/10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1) | CC-BY-4.0 source already preserved locally: 1,648 Earth chamber observations across four experiments; air/root temperature, PPFD, days after transplant and fresh shoot mass | Earth-only lettuce growth | Active external model source, with experiment-level splitting |
| [Zenodo green-light hydroponic lettuce](https://zenodo.org/records/20394352) | 94.2 kB workbook reported to contain treatment metadata, 28/35-day measurements and harvest biomass | Spectrum-response candidate | Review before download/use: license field was not verified as a reusable scientific-data license in this audit |
| [Zenodo aeroponic airflow lettuce](https://zenodo.org/records/21300353) | 35.1 kB workbook reported to include fresh biomass, gas exchange, fluorescence and microclimate under five airflow configurations | Gas-exchange / airflow candidate | Not ingested: published license is displayed as copyright; needs explicit reuse confirmation |
| [Zenodo hydroponic multi-sensor lettuce](https://zenodo.org/records/20759414) | 39.1 GB, repeated 42-day phenotyping for 45 plants under fertigation treatments | Time-series phenotyping candidate | Not downloaded: large object store, data-access/processing plan and license review required |
| [Dryad leaf gas-exchange calibration data](https://doi.org/10.5061/dryad.5x69p8djr) | leaf-level photosynthesis, transpiration, conductance, PPFD and environmental variables for cowpea, redbud and walnut | Mechanistic gas-exchange reference | Not a lettuce/space crop source; do not train a crop-specific SpaceAgriSim model on it |
| [Dryad global photosynthesis/water meta-analysis](https://doi.org/10.5061/dryad.p5hqbzkz0) | 737 paired observations across 102 publications, many species/protocols | Contextual literature evidence | Not pooled into a crop model due to species/protocol heterogeneity |

## Current external-data policy

1. Only the licensed WUR/4TU lettuce data are used for application inference.
2. Dataset discovery is not dataset ingestion. Candidate records remain outside the model registry until the downloadable files, license, columns, units, independent replicates and missingness are checked.
3. Image, point-cloud and multi-sensor datasets are not converted into biomass labels unless an explicit measured-label linkage is verified.
4. Gas-exchange data from other species can inform documented mechanistic bounds, but cannot be relabelled as lettuce or spaceflight observations.

