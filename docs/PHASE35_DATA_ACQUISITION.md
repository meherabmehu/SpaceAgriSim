# Phase 35 — Data acquisition

The question this phase asked of each search: *is there a measured, downloadable, licensed dataset
that would let one of the open gaps be closed by measurement rather than by documentation?*

Answer for this phase: **no new dataset was acquired.** Every candidate below was checked, and each
was rejected for a reason specific to it. Nothing was counted, added to the catalogue or used to
raise a feature count, and no gap was closed.

## Method

For each result: read the record (not the abstract alone), identify whether data files exist, check
licence and size, and read enough of the design to say whether the system matches this project's
controlled-environment model. A paper, registration, poster, figure, data sheet or model output is
recorded as such — never as an acquired dataset.

## Searched and rejected

| Candidate | Publisher / DOI | What it actually is | Why rejected |
|---|---|---|---|
| Annual evapotranspiration data | Zenodo, `10.5281/zenodo.18150992`, CC-BY-4.0 | GLEAM / MERRA-2 / MOD16A / TerraClimate yearly netCDF, 173.5 MB | Model and remote-sensing products over land, not measured crop water use in a controlled environment. Validating a CEA water balance against global ET grids would compare different quantities. |
| evapotranspiration2 | Zenodo, `10.5281/zenodo.12773955`, CC-BY-4.0 | 37.6 GB of normalised CSVs, 1992–2024 | Size makes verification impossible here, and the record is a normalised product without the site metadata needed to identify a controlled environment. |
| Dataset agreement of global ET datasets | Zenodo, `10.5281/zenodo.18151961`, CC-BY-4.0 | Intercomparison mapping of global ET products | Compares models with models. No measured reference. |
| Soil Moisture, Irrigation Actuator and Weather Dataset | Mendeley Data, `10.17632/c837v6p8ph.2`, CC-BY-4.0 | Full 2025 season, 5 sectors, 486,894 probe readings + 3,055,944 valve records, 10-min grid, reconstructed applied water, ERA5 weather | **Closest candidate this phase.** Rejected because the system is open-field and potted mineral-soil drip fertigation (tomato, zucchini, blueberry) with no controlled radiation, temperature or photoperiod, and no measured harvest. A substrate water balance in a CEA cannot be validated against it without pooling incompatible systems, which the project's own rules forbid. Recorded so a future phase can revisit if a CEA equivalent appears. |
| Soil moisture / EC time series, Upper Gunnison Basin | ESS-DIVE, `10.15485/17427453` | Forest soil VWC at 14 sites | Forest hydrology; no crop, no controlled environment. |
| RISMA soil-moisture network | Government of Canada / ISMN | Field VWC and meteorology, 36 stations | Field agriculture; no crop production outcome. |
| CDI AquaIA | Zenodo, `10.5281/zenodo.15969966`, CC-BY-4.0 | 1.2 kB feature-model file (UVL) for a deficit-irrigation concept | A configuration model, not measurements. |
| LED spectrum × lettuce quality | Figshare, `10.14796432` supplement, CC-BY-4.0 | A .docx data sheet attached to a paper | A document, not a machine-readable dataset with per-plant outcomes. |
| Red-blue spectrum on lettuce growth | Plant, Soil and Environment 70(5):305, DOI `10.17221/480/2023-PSE`, CC-BY-NC-4.0 | Journal article with treatment means in tables | Treatment means without replication structure; NC licence also blocks the reuse this project would need. |
| LED spectra, red and green lettuce | Plants 12(3):463, CC-BY-4.0 | Journal article; figures and tables | Article, not a dataset. A future phase could transcribe treatment means but that is a derived table, not an acquired experiment. |
| OSD-480 Plant Gravity Perception (PGP) flight study | NASA OSDR, GLDS-480, DOI `10.26030/rjmp-6p90` | 1.41 TB of root gravitropism imaging/transcriptomics; fractional-g stimuli 0.1–1.0 g on the EMCS centrifuge | Transcriptomic and morphological response, not edible biomass; 1.41 TB cannot be verified in this environment. Documented as the nearest existing fractional-gravity experiment. |
| OSD-411 PGP pilot | NASA OSDR, GLDS-411, DOI `10.26030/9sfd-3h07` | Transcriptomic pilot, already evaluated in Phase 9 as a failing candidate | No growth outcome; already rejected on evidence grounds. |
| GLDS-251 Seedling Growth fractional-g RNA-seq | NASA GeneLab, via Herranz et al. 2019 (`10.3389/fpls.2019.01529`) | Root transcriptomes at 0.05–1 g | Gene expression only, 5-day seedlings, no harvest mass. |

## What the six priority categories now look like

| Category | Status after this phase | Exact missing evidence |
|---|---|---|
| A. Measured reference ET / crop water use in CEA | **blocked** | A lysimeter or gravimetric water-use series for a CEA crop with concurrent radiation, temperature, humidity and wind, in an open repository. |
| B. Substrate moisture and irrigation time series | **blocked** | Substrate volumetric water content plus applied-volume events for a hydroponic or substrate CEA crop, per bed, with the same climate series. The Mendeley set is the wrong system. |
| C. CEA growth with T, PPFD, DLI, photoperiod, humidity, cultivar, density and measured harvest | **partly available, already used** | The WUR (v1–v3) and PeerJ (development) data carry these variables; no additional campaign with the full variable set was found this phase. |
| D. LED spectral response with measured crop outcomes | **blocked** | A per-plant table with spectral composition (R:B ratio, far-red), PPFD, DLI and measured fresh/dry mass. Papers exist; machine-readable data does not, in what was searched. |
| E. Independent campaigns for external validation | **unchanged** | One additional campaign beyond the training data would let the lettuce intervals be tested rather than bounded. Phase 34 found and used OSD-780's second campaign for mizuna; nothing new for lettuce. |
| F. Fractional gravity with measured biological outcomes | **blocked** | Measured edible biomass (not transcript abundance, not root bending angle) as a function of g-level between 0 and 1, in a controlled environment. No such dataset exists in OSDR, GeneLab, Zenodo, Dryad or Figshare in what was searched. |

## Provenance of the datasets actually in use (unchanged)

| Dataset | Licence | Identifier | Role |
|---|---|---|---|
| WUR lettuce experiments (1 648 plants, 4 experiments) | CC-BY-4.0 | `10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1` | training v1–v3 |
| Touliatos, Dodd & McAinsh 2016 | CC-BY (publisher) | `10.1002/fes3.83` | independent holdout |
| Wicharuck et al. 2024, PeerJ 12:e17085 | CC-BY-4.0 | `10.7717/peerj.17085` | development comparison |
| NASA OSD-780 (VEG-04A + VEG-04B) | CC0-1.0 | `10.26030/s3hn-cj93` | mizuna campaigns |
| NASA OSD-46 (seedling radiation series) | CC0-1.0 | `10.26030/...` (recorded in the catalogue) | radiation classifiers |
| NASA OSD-767 | CC0 per repository record | recorded in the catalogue | tomato classifier |

No licence was assumed: each is the licence as stated by the record at the time it was read, and
each is stored with its URL in the dataset catalogue and provenance manifest.
