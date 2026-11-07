# Phase 10 — dose and gravity: recovering what Phase 9 excluded

Phase 9 excluded two models: absorbed dose (OSD-782) and gravity (OSD-411). Both
exclusions were right. Both were also accompanied by explanations that turned out to be
**partly wrong**, and this document corrects them with measurements.

Evidence: `ml/evaluation/phase10_dose_recovery.json`,
`ml/evaluation/phase10_partial_gravity.json`,
`ml/evaluation/phase10_gravity_recovery.json`.

---

## 1. Dose: the label was valid, the protocol was not

Phase 9 said the dose labels were unusable because dose was "confounded with
processing order", and reported a 3-class balanced accuracy of 0.361 with permutation
p = 0.2475.

The `absorbedDoseGy` column in the sample sheet is a **valid, explicit dose label**:
0 Gy / 10 Gy / 100 Gy, full factorial against four collection times with three
replicates each. Dose is not confounded with time — every timepoint contains all three
doses. What *is* true is narrower: each (dose, timepoint) cell is a single contiguous
sequencing block (GSM7623649–7623657 are the 1 h samples in dose order), so a batch
effect cannot be separated from a cell effect. That limits what a cell-level split can
mean. It does not make the label unusable.

So Phase 10 re-ran the question three ways on the same 36 libraries:

| Protocol | Balanced accuracy | Design-preserving permutation p |
| --- | --- | --- |
| A. hold out one (dose, timepoint) cell — the Phase 9 protocol | **0.111** | — |
| B. hold out one whole timepoint | **0.611** | **0.0005** |
| C. hold out one whole timepoint, ordinal fit on Gy (Spearman ρ) | **0.197** (monotone) | **0.0155** |

Protocol A is *worse than chance*: 0.111 against 0.333. Three doses each get assigned
to a different dose, which is the signature of a split that is measuring batch
membership rather than biology — holding out a cell removes an entire timepoint from
training, so the fold never asks the dose question at all.

Holding out whole timepoints asks it properly, and the answer changes: **the dose
gradient is recoverable**, with a weak ordinal signal (ρ = 0.197) and a moderate
3-class signal (0.611). The permutation null is design-preserving — labels are shuffled
*within* timepoint, so the null cannot be beaten by detecting the timepoint.

Both readings are in the artifact. Neither is served, because 36 libraries, one
genotype and one laboratory cannot support a dose predictor.

### The binary contrast under both protocols

| Protocol | Balanced accuracy | Interval / p |
| --- | --- | --- |
| hold out (dose, timepoint) cell | 0.563 | pair bootstrap [0.405, 0.722], group bootstrap [0.386, 0.729] |
| hold out whole timepoint | **0.813** | p = 0.0005 |

This is the measurement the cross-study study was missing, and it forced a correction
there: the target is not signal-free. Its contrast is learnable across timepoints and
does not survive an unseen (dose, timepoint) cell — which is the condition a
cross-study transfer actually faces. See `PHASE10_CROSS_STUDY_VALIDATION.md`.

The pair bootstrap resamples libraries and ignores that three of them share a cell; the
group bootstrap resamples the 12 cells. Both are reported because the Phase 9 reference
used the pair version, and the difference shows how much of that interval's confidence
came from treating correlated replicates as independent.

### One bug worth recording

The first run of this analysis selected **one gene** and produced a model that could
not fit its own training data. Cause: `scipy.stats.f_oneway` was passed 4,000 gene
vectors, which it broadcast into a single scalar rather than returning 4,000 statistics.
The selection is now hand-vectorised, and every fold must reach in-sample accuracy
≥ 0.9 or the script raises. A pipeline that cannot fit its own training rows is a bug,
never a finding — that check is the cheapest possible guard against the entire class of
error.

---

## 2. Gravity: the study existed, and Phase 9 had not looked

Phase 9 concluded that no plant study with processed expression and a real partial
gravity manipulation exists, on the evidence of OSD-480 (raw FASTQ only, 6.2 TB).

Phase 10 scanned the ISA metadata of **all 231** studies the sweep classified as having
a usable processed matrix, looking for any vocabulary that could name a non-1 g
acceleration (partial/fractional gravity, centrifuge, clinostat, explicit g values,
lunar/Mars). 231 of 231 were retrieved, 22 matched, and two are graded-gravity plant
experiments with processed RNA-seq:

| Study | What it is | Gravity levels |
| --- | --- | --- |
| **OSD-314** | Arabidopsis on ISS, subset centrifuged in orbit, red light × dark | **0 g, 0.34 g, 1 g** |
| OSD-346 | Arabidopsis phyA/phyB, fractional gravity under blue light | 0 to 0.64 g, eight levels |

The Phase 9 statement was therefore wrong, and the correction matters more than the
excuse for it: OSD-480 was one study, not a search.

### OSD-314 analysis

17 libraries, six conditions: 3 gravity levels × 2 light treatments. Two structural
facts decide what may be claimed:

- **Across all three levels, gravity is confounded with flight.** The 1 g samples are
  ground controls; the 0 g and 0.34 g samples are in orbit.
- **Within flight, gravity is clean.** The 0 g and 0.34 g samples came from the same
  mission and the same processing run, and both have red-light and dark replicates.

So the primary contrast holds flight constant and asks only about 0.34 g of
centrifugation:

| Analysis | Result |
| --- | --- |
| **Primary:** 0 g vs 0.34 g, held-out light treatment | balanced accuracy **1.000**, p = 0.0055, per-class recall 1.00 / 1.00 |
| Secondary: 3 levels, ordinal Spearman (flight-confounded) | ρ = 0.929, p = 0.0005 — **not promoted** |

A perfect split on 11 libraries is the kind of number that usually means a leak, so it
was checked against the study's own differential expression: the deposit reports
**8,478–13,504 genes at adjusted p < 0.05** for the within-flight uG-versus-0.34 g
contrasts. A transcriptome difference of that size between those conditions is the
data providers' finding, not an artefact of this split.

### What is still not claimed

- **No servable model.** 17 libraries, one genotype, one mission, two folds.
- **No Moon or Mars prediction.** 0.34 g is a centrifugation level; it is neither
  0.17 g nor 0.38 g, and interpolating past the data is how the OSD-411 exclusion
  happened in the first place.
- **No batch exclusion.** The deposited runsheet carries no sequencing-run or
  library-batch identifier, so a prep batch effect cannot be excluded from the record
  alone. That is a limit of the deposit, not something more analysis of the same files
  can fix.
- **The three-level analysis is never quoted alone.** It is flight-confounded by
  construction and is labelled so in the artifact and in the catalogue entry.

### OSD-346 is the replication, and is deliberately unstarted

OSD-346 has eight gravity levels and per-sample RSEM gene results, so it is the right
replication. Its expression is deposited as 26 per-sample files rather than one matrix,
and merging those without parsing its own factor table would risk exactly the label
error this section is about. It is named as the next action rather than attempted
half-way.

---

## Outcome

| Question | Phase 9 | Phase 10 |
| --- | --- | --- |
| Is the OSD-782 dose label usable? | no, "confounded with processing order" | **yes**; the confound is cell-level batch, not dose |
| Is dose learnable? | no (0.361, p 0.2475) | **yes, across timepoints** (0.611, p 0.0005; ρ 0.197) — not across unseen cells (0.111) |
| Does a partial-gravity plant study exist? | no | **yes: OSD-314**, and it is now catalogued |
| Is partial gravity detectable? | untestable | **yes** within flight (1.000, p 0.0055), corroborated by the deposit's own DE table |
| Is a gravity or dose model served? | no | **no**, and both exclusions stand |

Registry: unchanged at 8 models. Catalogue: 17 → 18 NASA datasets. Tests:
`backend/tests/test_phase10_dose_gravity.py`, which pins each number to its protocol
and asserts that none of it is promoted.
