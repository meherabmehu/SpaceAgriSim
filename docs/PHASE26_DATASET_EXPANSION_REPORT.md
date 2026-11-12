# Phase 26 — Dataset Expansion Report

Status: **delivered on branch `phase26-dataset-expansion`.** Every dataset described here was
downloaded in this phase, checked against the publisher's own declared size and checksum, and — for
three of the five — parsed into a tidy table with a quality file. Nothing in this report is a
description of an intention.

Catalogue before this phase: 23 datasets. After: **28**. Acquired: 5. Processed: 3.

---

## 1. What was added, and what each one is actually for

| Dataset | Class | Rows that matter | Role |
| --- | --- | --- | --- |
| Schröder et al. 2021 greenhouse lettuce pots (Zenodo 5550230, CC BY 4.0) | A | 604 pot-days, 35 published pots | the measured side of the water-use comparison |
| Green-light spectral lettuce trial (Zenodo 20394352, CC BY 4.0) | B | 252 harvested plants | spectrum as a factor; no model consumes it yet |
| Halbert-Howard 2020 hydroponic tomato (Zenodo 5084389, CC BY 4.0) | B | row-level uptake | nutrient-uptake prior, not yet parsed |
| LED photoperiod open-field tomato (Zenodo 23759737, CC BY 4.0) | C | 20 plants, weekly | external check on the shape of a tomato growth curve |
| *Corymbia calophylla* gas exchange (Zenodo 5130624, CC BY 4.0) | D | 2 454 records | reference only; never a label or a feature |

Only one of the five reached class A. Two are class C and D precisely because the data cannot
support the product — the tomato trial is open-field with twenty plants, and the gas-exchange series
is a mature tree rather than a crop. **No dataset was added to raise a count**, and the count is a
by-product of the acquisitions rather than the goal.

Non-NASA sourcing is real: all five are Zenodo deposits from independent research groups. Thirteen
further agency and repository endpoints (FAOSTAT, WaPOR, CDS ERA5-Land, NEON, ICOS, USDA NAL,
WorldClim, ESA Copernicus, OpenET, Dryad, CGIAR, Figshare) are catalogued as *not acquired* with the
specific blocking reason for each — credential, licence decision, wrong spatial support, or no
compatible product at all.

## 2. The acquisition failure this phase had, and what it changed

The first run of `scripts/datasets/acquire.py` reported **five successful downloads of 600–900
bytes each**. Those bytes were Zenodo's JSON metadata: the API link it followed redirects to a
metadata document rather than to the file. The manifest said five datasets acquired. It was wrong,
and it was wrong in the most dangerous way — the numbers looked plausible until the files were
opened.

The downloader now requires three independent checks before a file counts as acquired:

1. the size matches the publisher's own declared size;
2. the MD5 matches the publisher's own published checksum;
3. the magic bytes match the declared format (`PK\x03\x04` for xlsx; a JSON payload rejected as CSV).

A payload failing any check is **deleted and recorded as a failed verification**, not kept with a
warning. Verified files now range 94 KB – 1.5 MB. The regression is pinned by
`test_no_verified_file_is_a_metadata_stub`.

## 3. Two parsing errors found by reading the raw workbook

Both were caught because the numbers were checked against the publication, not because a test failed.

**Evapotranspiration rates were read the wrong way round.** The workbook's three-column date blocks
are headed `ET total`, `ET/d`, `ET/h`, but the columns actually hold mL **per hour** and mL **per
day** respectively. An earlier parser treated `ET/d` as a daily rate and produced rates ~24× too
small. Both are now stored, the daily rate is recomputed from the interval total and elapsed days,
and the agreement between the source daily column and the recomputed one is recorded: **median
relative difference 4.2 % across 549 rows**, which is what confirms the mapping. A regression test
asserts the source daily column sits within 10 % of the recomputed rate.

**The biomass "organ" column held a root description.** The comment column reads `Shoot` or
`lettuce root mix 1-5`, and an earlier version produced eleven pseudo-organs instead of two. Now
mapped to `shoot`/`root`, and a test asserts the organ set is exactly those two.

## 4. Data-quality findings that are recorded rather than corrected

| Finding | Handling |
| --- | --- |
| 6 pot-days exceed the study's own published 350 mL/pot/day irrigation ceiling (worst 1 214) | flagged in a column, **kept**, excluded by name from robust statistics |
| 4 autoclaved treatments are marked "not used in publication" | retained and tagged `inPublication = false`; deleting them would hide that they exist |
| the 2.2 L pot's surface area is unpublished | `potAreaAssumptionM2 = 0.0112` recorded as an **assumption** with its ±10 % consequence |
| green-light `leafAreaMm2` is numerically consistent with cm², not mm² | recorded as an inference in the quality file, source not altered |
| tomato weekly table has 20 plants and 6 weeks | recorded; per-plant, open field, never pooled with controlled-environment data |

## 5. What the catalogue now claims, and what it still cannot

`data/research/dataset_catalog` and `docs/DATASET_CATALOG.md` are generated from the builder's
dataset list, and `--check` fails on drift. A test pins the totals exactly:

```
28 datasets   A:2  B:7  C:9  D:4  E:5  F:1        licence evidence: 14 verified, 10 documented-secondary, 4 unverified
```

The verified-licence count rose from 9 to 14 because all five new entries had their licence page
read. The four unverified entries are carry-overs from earlier phases and are unchanged.

`docs/DATASET_GAP_MATRIX.md` — regenerated, still **12 gaps, none closed**:

- `measured-eta` moved from `no-data` to `partially-addressed`, **severity unchanged at blocking**,
  with the specific clause it closed named (the "no measured crop water use of any kind exists"
  clause) and the four blockers that survive named alongside it;
- `led-spectrum-response` and `yield-labels` gained evidence records without any change of severity.

## 6. Reproducibility

```
python3 scripts/datasets/acquire.py           # download + verify, writes data/metadata/phase26_acquisition_manifest
python3 scripts/datasets/preprocess.py        # writes data/processed/phase26/*.csv + *_quality.py
python3 ml/research/validate_measured_et.py   # writes ml/evaluation/phase26_measured_et_validation
python3 ml/research/build_catalog.py          # catalogue JSON + markdown
python3 ml/research/build_gap_matrix.py       # gap matrix JSON + markdown
python3 ml/research/build_feature_readiness.py # readiness JSON + coverage matrix
```

The manifest ties every processed table back to a SHA-256 of the exact bytes it was parsed from,
and a test re-hashes every acquired file on each run and fails if the bytes have moved.

## 7. Honest limits of this expansion

- Five datasets is a small number. It is what survives verification, not what a search returned.
- Three of the five cannot support a product claim, and the catalogue says so in their class.
- No new training-grade dataset arrived. Section 3 of the model improvement report explains why that
  means no model was retrained.
- The one dataset that changed a capability — Schröder et al. — changed it to "identifiable in shape,
  not in level", which is a smaller movement than it first appears.
