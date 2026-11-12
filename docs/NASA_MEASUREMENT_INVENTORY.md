# NASA Measurement Inventory — Phase 6

Every row below is a *number that NASA actually measured and published*, with
its provenance recorded. Nothing here is simulated, interpolated or inferred.

Reproduce acquisition: `python scripts/acquire_phase6.py`
Provenance file: `data/metadata/phase6_checksums`
(records study, original URL, timestamp, SHA-256, byte count, published size)

---

## 1. Newly acquired in Phase 6

| Study | File | Bytes | SHA-256 (first 16) | What it measures |
|---|---|---|---|---|
| OSD-780 | `LSDS-128_Plate Count_Aerobic_Plate_Count_TRANSFORMED.csv` | 11,708 | `229a0d93fff86625` | Culturable aerobic plate count, CFU/g fresh weight |
| OSD-780 | `LSDS-128_Plate Count_Yeast_Mold_Plate_Count_Transformed.csv` | 9,106 | `0170d2fbc1daaaea` | Culturable yeast/mould plate count, CFU/g |
| OSD-780 | `OSD-780_dictionary_DataDictionary_OSD-780.csv` | 1,012 | `4ea878d266ad1f13` | Unit and column definitions |
| OSD-670 | `OSD-670_sup_Regolith-Analysis.csv` | 292 | `274d7924a6cb099a` | Asteroid-regolith substrate chemistry (P, K, NO₃, NH₄, Ca, Mg, Na, Fe, Al, pH, CEC) — **not** a plant phenotype |
| OSD-120 | `OSD-120_sup_images_correlated-08-June-2023.xlsx` | 107,991 | `72435de5e386fc78` | Image↔sample index — **no** numeric plant phenotype |

Exact digests are in `data/metadata/phase6_checksums`; all five files
matched the OSDR-published byte size exactly on acquisition.

## 2. The usable new measurement: OSD-780

Processed by `python scripts/preprocess_osd780.py`
→ `data/processed/mizuna_microbial_load.csv`
→ `data/metadata/osd780_quality_report`

### 2.1 What is measured

Per the official NASA data dictionary (LSDS-128):

| Column | Unit | Meaning |
|---|---|---|
| `fresh_weight_gram` | g | Mass of the tissue/subsample weighed for the assay |
| `colony_count_1`, `colony_count_2` | count | Raw colony counts from duplicate plates |
| `average_colony_count_per_milliliter` | per mL | Mean colony count per mL |
| `colony_forming_unit_per_gram_fresh_weight_per_swab` | CFU/g | **Primary target** |
| `colony_forming_units_per_swab` | CFU/swab | Different unit — not interchangeable |

> **Critical unit discipline:** `fresh_weight_gram` is the mass of the tissue
> taken *for the assay*. It is **not** harvest biomass, standing biomass, edible
> yield or growth rate. Using it as a biomass label would be a category error and
> is explicitly forbidden by `docs/DATA_HARMONIZATION.md` rule H7.

### 2.2 Experimental design recovered from sample names

The sample-name grammar is **not documented upstream**. It was recovered by
inspection and is validated by the fact that every one of the 204 + 169 rows
parses:

```
<experiment>_<environment>_<tissue>[_pillow<N>|_Sample<N>]_<spectrum>
    [_<treatment>][_harvest<N>]

experiment  : VEG04A | VEG04B
environment : F  -> flight   |  GC -> ground control
tissue      : leaf | root | soil | wick | Swab
spectrum    : red | blue
treatment   : clean (sanitised) | unclean (unsanitised)
harvest     : VEG-04B harvest index (1..3)
```

| Factor | Levels |
|---|---|
| Assay | aerobic, yeast/mould |
| Experiment | VEG-04A, VEG-04B |
| Environment | flight, ground |
| Tissue | leaf, root, soil, wick, swab |
| Spectrum | red, blue |
| Treatment | clean, unclean, unspecified |

### 2.3 Row accounting

| Sheet | Rows | Parsed | Notes |
|---|---|---|---|
| Aerobic plate count | 203 (+1 artefactual NaN row dropped) | 203/203 | 203 unique sample names |
| Yeast/mould plate count | 169 | 169/169 | — |

Model-eligible subset (aerobic, leaf tissue, CFU/g present): **123 samples in 35
biological units** (pillows).

### 2.4 Measured target summary — log₁₀(1 + CFU/g)

Aerobic, leaf tissue:

| Experiment | Environment | n | mean | sd | min | max |
|---|---|---|---|---|---|---|
| VEG-04A | flight | 5 | 5.617 | 0.815 | 4.923 | 6.856 |
| VEG-04A | ground | 15 | 2.554 | 1.157 | 1.063 | 5.020 |
| VEG-04B | flight | 31 | 3.615 | 2.081 | 0.000 | 7.231 |
| VEG-04B | ground | 72 | 0.975 | 1.501 | 0.000 | 5.096 |

Aerobic, root-zone tissues (for contrast):

| Experiment | Environment | Tissue | n | mean log₁₀ CFU/g |
|---|---|---|---|---|
| VEG-04A | flight | root | 2 | 7.297 |
| VEG-04A | ground | root | 4 | 7.420 |
| VEG-04A | flight | soil | 16 | 7.077 |
| VEG-04A | ground | soil | 12 | 6.923 |
| VEG-04A | flight | wick | 2 | 8.157 |
| VEG-04A | ground | wick | 4 | 7.604 |

**Interpretation, stated conservatively:** the flight-associated elevation
appears on **edible leaf tissue** (≈2.6–3.1 log₁₀ higher in flight) but is
**absent in the root zone**, where both arms sit at ≈7–8 log₁₀ CFU/g. A leaf
surface effect with no root-zone effect is consistent with an aerial/cabin or
handling exposure route rather than a substrate effect — but OSD-780 cannot
distinguish cabin environment from payload handling from sampling protocol, so
**causality is not established** and must not be claimed.

### 2.5 Zero counts are retained

A zero colony count is a genuine measured "no growth" result, not missing data.
It is retained as `log10(1 + 0) = 0`. 64 rows have a missing CFU/g (these are
the swab samples, whose target is CFU/swab, a different unit) and are excluded
from the CFU/g model rather than imputed.

## 3. Pre-existing measurements re-verified

| Study | File | Target | Unit | Usable rows |
|---|---|---|---|---|
| OSD-655 | `VEG-04-Flight-Mass.csv` | Total harvest mass | g/pillow | 8 |
| OSD-655 | `VEG-04-GroundControl-Mass.csv` | Total harvest mass | g/pillow | 6 |
| OSD-655 | `Veg-04-FlightWater.csv`, `VEG-04-GroundControlWater.csv` | Irrigation supplied | mL/event | 14 pillows |
| OSD-655 | `Veg-04A_B_Master Chem_csv format.csv` | Elemental composition | — | assays |
| OSD-745 | `LSDS-109_*` (16 files) | Elemental, phenolic, anthocyanin, ORAC | — | assays |
| OSD-767 | `GLDS-709_rna_seq_STAR_Unnormalized_Counts` | Gene counts | counts | 36 samples |
| OSD-895 | `eden_iss_2018_biomass_summary.csv` | EDEN ISS crop summaries | kg/m², g/m² | 11 crop rows — **manual transcription from PDF paper, not a NASA table** |

## 4. Confidential missing measurements

The following Phase 6 target types were searched for and **do not exist** in
machine-readable public form anywhere in the 25 verified studies:

| Target type | Status |
|---|---|
| Harvest dry mass | **Not available** (only fresh mass in OSD-655; EDEN ISS dry biomass is PDF-only ranges g/m²) |
| Repeated growth observations (time series) | **Not available** (no per-day growth table in any study) |
| Plant water uptake / transpiration | **Not available** (OSD-655 logs irrigation *supplied*) |
| Water recovery | **Not available** |
| CO₂ assimilation / net photosynthesis | **Not available** (no gas-exchange table in any study) |
| O₂ evolution | **Not available** |
| PPFD / photoperiod as measured per-sample covariates | **Not available** (light is recorded as red/blue category, not PPFD) |
| Radiation dose paired with plant response | **Not available** (no matched plant-specific dose table; ISS dosimetry is not plant-paired) |
| Continuous gravity-treatment response | **Not available** (OSD-436 is flight-vs-parabolic-flight molecular only) |
| Genuine plant-health / disease severity labels | **Not available** |

These absences are the direct cause of the "no new biomass model" outcome
recorded in `docs/ML_TRAINING_REPORT.md`. They are evidence gaps, not oversights.
