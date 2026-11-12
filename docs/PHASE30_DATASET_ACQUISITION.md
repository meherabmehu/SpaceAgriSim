# Phase 30 — Dataset acquisition report

Phase 30 was authorised to search for and acquire data, not to plan. This is the record: every
source searched, every source acquired with its hash, licence and access date, and every source
rejected with the reason it was rejected.

Machine-readable copies:

- `data/metadata/phase30_acquisition_manifest` — datasets, rejections, transformations
- `data/processed/phase30/quality` — per-dataset unit map, environment ranges, missingness
- `data/research/dataset_catalog` — both acquisitions entered as class A

Raw files are committed under `data/raw/phase30/` with the hashes below. They are immutable: the
builder reads them, never writes to them.

---

## 1. Acquired

### 1.1 Indoor wheat (cv. Apogee) under fully controlled environmental conditions

| Field | Value |
|---|---|
| DOI | `10.5281/zenodo.17764612` |
| Publisher | Zenodo |
| Licence | CC BY 4.0 (verified on the record page) |
| Accessed | 2026-11-10 |
| File | `data/raw/phase30/wheat_yields.xlsx` (138 723 B) |
| SHA-256 | `385d4680067832026296ec6bec1ce8757fa4bc42bd42d6f37b62899b52dc33c5` |
| Crop / cultivar | wheat, Apogee |
| Independence unit | experiment (one chamber run) |
| Shape | 39 experiment rows, 719 sub-plot rows, 34 rows with both yield and full environment |

**Not acquired:** `20260801_Data_S1_EnvironmentalConditions.zip` (33 327 241 B) — the raw
climate-computer logs. Data S2 already carries the per-experiment environment means computed by the
data authors, and a model fitted at experiment level gains nothing from sub-daily logs. Recorded in
the manifest rather than silently skipped.

**Measurement basis.** Destructive harvest of grain per sub-plot; chamber environment logged by the
climate computer during the run.

**Environment coverage (experiment level):**

| Variable | n | Min | Max | Distinct |
|---|---|---|---|---|
| Mean PPFD (µmol m⁻² s⁻¹) | 38 | 235.0 | 1084.2 | 38 |
| Photoperiod (h/day) | 38 | 6.08 | 22.56 | 38 |
| CO₂ (ppm) | 38 | 400 | 1478 | 9 |
| Air temperature (°C) | 38 | 21.1 | 28.0 | 23 |
| Relative humidity (%) | 38 | 55 | 72 | 14 |
| Cycle length (days) | 37 | 39 | 91 | 22 |
| Grain yield (kg m⁻²) | 37 | 0.0625 | 1.8076 | 37 |

**Missingness and structure that a model must respect:**

- PPFD varies *within* a run in 33 of 36 experiments; photoperiod in 16. The experiment table carries
  the mean plus the sub-plot values, minimum, maximum and a `VariesWithinExperiment` flag for every
  environment column. Nothing averages away a within-run change.
- One row is a summary artefact with no real experiment id and is excluded, not repaired.
- CO₂ has nine distinct values across 39 runs, i.e. it is closer to a categorical factor than a
  continuous axis. This is stated in the gap matrix and in the evaluation limitations.

### 1.2 Kilowatts to kilograms — lettuce light-use-efficiency compilation

| Field | Value |
|---|---|
| DOI | `10.5281/zenodo.14640245` |
| Publisher | Zenodo |
| Licence | CC BY 4.0 (verified) |
| Accessed | 2026-11-10 |
| File | `data/raw/phase30/lue_dataset.xlsx` (34 049 B) |
| SHA-256 | `feb96c6c79c3997fde182dedbd252a76aa41ddd6d980db34c8ce2beaf434cedd` |
| Crop | lettuce |
| Independence unit | study (publication), not plant |
| Shape | 53 published treatment means from **40** published studies |

**Important caveat.** The record's own citation column lists 41 studies; the builder's study key
collapses two entries that share a study, so the committed table has **40** study keys and the
evaluation reports 40. The discrepancy is recorded rather than smoothed: 53 treatment means, 40
independent studies is what the table can actually support.

**Coverage:** PPFD 43–428 µmol m⁻² s⁻¹, photoperiod 12–24 h, CO₂ 280–2800 ppm, plant density
16–1372 plants m⁻², shoot dry mass up to 16.5 g per plant.

**Measurement basis.** Treatment means copied from publications. Within-study variance is therefore
unavailable, and no cultivar metadata was published. This is why the evaluation treats the study, not
the plant, as the unit of independence.

---

## 2. Rejected (12)

Every rejection is recorded in the manifest with the DOI and the reason, so the search is not
repeated blindly.

| DOI | Source | Record | Reason |
|---|---|---|---|
| `10.5281/zenodo.8410252` | Zenodo | Piikkio2023 lettuce point cloud | licence field is null — not redistributable |
| `10.5281/zenodo.20759414` | Zenodo | 39 GB dataset | size, and the varied factor is fertigation, not light/temperature |
| `10.5281/zenodo.22004997` | Zenodo | light-environment measurements | no crop response variable |
| `10.5281/zenodo.20394352` | Zenodo | Greenlight reanalysis | duplicates a study already used; would double-count one experiment |
| `10.5281/zenodo.17712088` | Zenodo | simulation output | model output, not measurement |
| `10.5281/zenodo.16271245` | Zenodo | pak choi trial | wrong species |
| `10.5281/zenodo.14529253` | Zenodo | wheat SPAD series | response variable is a chlorophyll index |
| `10.5281/zenodo.22280237` | Zenodo | spinach far-red timing | 22 KB, single series, no yield |
| `10.5281/zenodo.5797817` | Zenodo | China RS yield & water productivity | no deficit treatment, no water-application gradient, therefore no crop-specific Ky |
| `10.5281/zenodo.7895889` | Zenodo | Diverfarming RDI mandarin | wrong species and system; no yield-response factor |
| `10.5061/dryad.73n5tb3d4` | Dryad | UAV imagery (8 GB) | imagery only; download also returned 401 |
| `10.5061/dryad.gqnk98skd` | Dryad | faba bean water × herbivory × pollination | water effect confounded with biotic treatments |

Sources that were searched but produced no committable candidate, and the reason a search cannot
proceed from this environment, are recorded in the gap matrix `phase30Decision.searched` entries:
NASA Open Data, GeneLab/OSDR, NASA LSDA, NTRS, ESA, Zenodo, Dryad, Figshare, Harvard Dataverse,
OpenAIRE, PANGAEA, Mendeley Data, Research Data Australia, USDA Ag Data Commons, Europe PMC,
Crossref, Semantic Scholar, OpenAlex and journal supplements.

Two environment-level obstacles are recorded rather than hidden: **USDA Ag Data Commons** did not
resolve DNS from this environment, and the **OSDR biodata API** exposed no working JSON endpoint, so
OSDR records were used from their committed extracts rather than re-queried.

---

## 3. Transformations applied

Recorded verbatim in the manifest because a silent transformation is how unit mixing starts:

1. Column names mapped to unit-carrying names; the map is in the builder, and every mapping is
   written into `quality` as `unitMap[field] = {unit, modelled}`.
2. **No imputation.** Blanks stay blank; coverage is reported per field.
3. **No unit conversion.** Published units are carried in the column name.
4. Experiment-level aggregation computes the mean of sub-plot yields and **refuses to average an
   environment that changed within an experiment** — it reports the range instead, plus the
   per-sub-plot values and a `VariesWithinExperiment` flag.
5. Literature rows are labelled `observationKind = published-treatment-mean`: they are means reported
   by other authors, not plants weighed in this repository.

The builder is deterministic and has a `--check` mode that rebuilds from the raw workbook in memory
and compares against the committed CSVs; `backend/tests/test_phase30_datasets.py` runs it.

---

## 4. What the acquisitions did and did not change

| Question | Answer |
|---|---|
| Did the wheat series close the environmental-stress gap? | Half. It supplies a measured comparison across PPFD, photoperiod, CO₂ and temperature bands. The fitted response surface failed its sealed holdout and is not served. |
| Did the lettuce compilation enable a harvest forecast? | No. It enabled the evaluation that showed no forecast is justified (310.17 % holdout MAPE, mean baseline selected). |
| Did anything close the water-deficit yield gap? | No. No crop-specific Ky was found for lettuce, tomato or radish. |
| Was any dataset added to raise a count? | No. Two were added; twelve were rejected in writing. |
