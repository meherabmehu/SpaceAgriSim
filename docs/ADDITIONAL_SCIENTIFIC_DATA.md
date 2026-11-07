# Additional scientific data review

## Reviewed sources

| Source | Measured evidence | Decision |
| --- | --- | --- |
| [NASA OSDR VEG-05 / OSD-766](https://osdr.nasa.gov/bio/repo/data/studies/OSD-766) | Tomato flight/ground experimental conditions and microbiome assays; reported fruit outcome context | Not added to yield training because registered public assay is microbiome sequencing, not a compatible numerical fruit-yield table. |
| [NASA OSDR OSD-59](https://osdr.nasa.gov/bio/repo/data/studies/OSD-59) | Mizuna spaceflight RNA-seq and ground controls | Molecular context only; no harvest-mass target for independent Mizuna regression validation. |
| [NASA NTRS controlled-environment agriculture report](https://ntrs.nasa.gov/api/citations/20140017323/downloads/20140017323.pdf?attachment=true) | Aggregate biomass and water-use summaries for multiple crops | Calibration/literature context only; aggregate table is not a row-level ML dataset. |
| [NASA NTRS plant performance table](https://ntrs.nasa.gov/api/citations/19950005542/downloads/19950005542.pdf) | Literature model-input values for transpiration, biomass, CO2 and O2 | Not ingested as measured training observations; model-input tables are not independent experimental replicates. |
| [Zenodo Piikkio lettuce data](https://zenodo.org/records/8410252) | 402 point clouds paired with fresh weight | Not downloaded: image/point-cloud model target and predictors are incompatible with the current environmental lettuce model. |

## Result

No additional source met the full requirements for safe ingestion into a current model: verified reusable access, compatible target/unit, independent experimental structure and defensible predictor harmonization. No fabricated or weakly joined dataset was created.

