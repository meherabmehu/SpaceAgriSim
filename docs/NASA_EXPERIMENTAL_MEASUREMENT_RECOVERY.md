# Phase 7 — NASA Experimental Measurement Recovery

**Status of the Phase 6 conclusion this document replaces.** Phase 6 searched the
NASA Open Science Data Repository, which is a *genomics and multi-omics archive*,
for 1980s–1990s CELSS crop-physiology evidence, found none, and concluded that
biomass time series, transpiration, water use, CO₂ assimilation, PPFD and
photoperiod response were **not measured anywhere in NASA's public data**. That
conclusion was wrong as stated. The measurements exist; they are published in
**NASA Technical Memoranda**, which OSDR does not index and which carry no
machine-readable tables.

Phase 7 therefore re-ran the search against the NASA Technical Reports Server.

| Search | Queries | Unique documents | With downloadable PDF |
|---|---|---|---|
| NTRS | 39 | 256 | 110 |

Zero-hit queries were recorded rather than discarded, so a negative finding can
be distinguished from a search that was never actually run. The record is in
`data/metadata/phase7_ntrs_search.json`.

---

## 1. What was recovered

Six documents were downloaded, hashed and stored under `data/raw/ntrs/`
(gitignored: they are large and publicly re-downloadable). Every byte count and
SHA-256 is in `data/metadata/phase7_ntrs_checksums.json`.

| NTRS ID | Report | Pages | Bytes | Role in Phase 7 |
|---|---|---|---|---|
| 19900009537 | TM-102784 — *Continuous Hydroponic Wheat Production Using a Recirculating System* | 60 | 1.95 MB | **Primary harvest and growth tables** |
| 19900016137 | TM-102788 — *Carbon Dioxide and Water Exchange Rates by a Wheat Crop in NASA's Biomass Production Chamber* | 32 | 0.90 MB | **Primary gas-exchange and transpiration values** |
| 19900016140 | TM-103494 — *System Development and Early Biological Tests in NASA's Biomass Production Chamber* | 32 | 1.10 MB | **Water balance; second irradiance/photoperiod point** |
| 19910010713 | N91-20026 — soybean biomass production centre | 27 | 1.07 MB | Surveyed; no usable harvested table recovered |
| 19900001255 | Carbon-flow mass balance | 40 | 1.12 MB | Surveyed; mass-balance context only |
| 19940009239 | TM-109192 — BWT931 volatile organic compounds | 68 | 1.45 MB | **Excluded**: air-quality chemistry, not a plant-physiology target |

The acquirer enforces four rules, all of which are code rather than intent: an
`ntrs.nasa.gov` host allowlist, a `%PDF` magic-byte check, a 60 MB per-document
budget, and refusal to accept a download whose hash silently changed.

## 2. What was extracted, and how it was defended

Three independent safeguards run on every build of
`scripts/extract_ntrs_tables.py`. A build that fails any one of them exits
non-zero and writes nothing.

1. **Provenance.** Every extracted value is tied to a page number *and* to an
   evidence string that must literally appear on that page. This catches silent
   column-shift errors in typewritten, OCR-degraded tables, which is the dominant
   failure mode here.
2. **Arithmetic.** Derived columns are recomputed from primary measurements
   (`seeds/plant`, `mass/plant`, edible biomass index, per-m² and per-m³
   conversions).
3. **Aggregates.** All eight published 16-tray mean/standard-deviation pairs are
   recomputed from the extracted tray values.

Current state: **46 provenance checks pass, 8 aggregate pairs reproduce, 6
independently published derived quantities recompute.**

| Extracted output | Rows | Source |
|---|---|---|
| `data/processed/ntrs_wheat_harvest_trays.csv` | 16 trays | TM-102784 Tables 6–7 (p.40–41) |
| `data/processed/ntrs_wheat_growth_series.csv` | 7 ages | TM-102784 Tables 9–10 (p.43) |
| `data/processed/ntrs_wheat_gas_exchange.csv` | 15 variables | TM-102788 (per-variable page) |
| `data/processed/ntrs_bpc_water_balance.csv` | 24 variables | TM-103494 (per-variable page) |

## 3. Defects found in the sources, and what was done about them

The point of the safeguards is that these are *recorded*, not silently smoothed.
Each is written into `data/metadata/ntrs_extraction_report.json`.

| Defect | Evidence | Handling |
|---|---|---|
| TM-102784 Table 6, tray 7, total biomass reads `451` in the text layer | `231` is the only value that yields the published mean (371.0 g), the published tray-7 EBI (16 %) and the printed STD (96 g). With 451 the mean becomes 384.75 g. | OCR artefact corrected to `231`, with the derivation written into the report |
| TM-102784 tray 9 plant count contradicts its own derived columns | Printed 216 plants is consistent with the published 271 plant mean, but the printed seeds/plant (14.2) and mass/plant (0.34) require 326 plants | Primary measurements retained; the two derived columns excluded from validation and flagged |
| TM-102784 tray 11 EBI | Published 37 % vs 38.6 % recomputed from 146.65/380 | Total biomass retained (it is what reproduces the 371 g mean); EBI flagged as mis-rounded in the source |
| TM-102784 day-24 % root | Published 22.0 vs 22.95 recomputed from 4.82/21 | Dry mass retained (it reproduces the published 0.07 g/plant); % root flagged |
| TM-102784 per-m² → per-m³ height assumption | Table 7 implies a 0.526 m canopy height; Table 10 implies 0.385 m. Both are internally consistent within their own table | Both factors validated as printed and recorded as a documented inconsistency, not reconciled |
| TM-102784 tray area | Authors state 0.24 m². The 1546 g/m² total-dry-matter average reproduces exactly at 0.24 m². The seed-mass-per-m² column requires 0.2328 m² (printed average) or 0.238 m² (recomputed average) | All three figures recorded; no correction applied |

**No value in this recovery is graph-digitised.** Everything is either a printed
table cell or a printed statement. Nothing is rounded toward an expected answer.

## 4. What this changes, and what it does not

**Changed.** Five targets that Phase 6 declared non-existent are now backed by
measured, page-cited values: harvest yield, dry-matter growth series,
transpiration, water use, CO₂ assimilation and water recovery. The simulator's
water and gas assumptions can now at least be checked against reality.

**Not changed — and it matters.** Measurement is not trainability. These are
**ground-chamber, single-crop (wheat), single-institution** studies with
stand-level or per-tray replication at one or two operating points. That
supports *bounds checking* and *plausibility validation*. It does not support
cross-validated predictive models, gravity or radiation response, or any
transfer to lettuce/tomato/radish. Three targets remain genuinely absent:
**O₂ evolution, gravity-dependent growth, and radiation dose-response**.

Part B (`PHASE7_ML_TRAINING.md`) turns this into an explicit per-task
eligibility matrix, and Part C (`PHASE7_SCIENTIFIC_CALIBRATION.md`) applies the
usable parts to the simulator without changing its output definitions.
