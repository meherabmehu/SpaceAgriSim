# Phase 10 — NASA dataset expansion

Phase 10 added **one** dataset, and the way it found it is the point: Phase 9 had
concluded that no plant study with processed expression and a real partial-gravity
manipulation existed, on the evidence of a single study (OSD-480, raw FASTQ only).

That conclusion was drawn from one deposit rather than from a search. Phase 10 ran the
search.

## The scan

Every study the Phase 9 sweep classified as having a usable processed matrix — **231**
of 587 — had its ISA metadata fetched from the OSDR API and scanned for any vocabulary
that could name a non-1 g acceleration: partial or fractional gravity, centrifuge,
clinostat, random positioning, explicit g values, lunar/Mars.

| Step | Result |
| --- | --- |
| studies with usable processed matrix | 231 |
| metadata retrieved | **231 / 231** |
| keyword candidates | 22 |
| graded-gravity **plant** studies with processed RNA-seq | **2** |

Patterns were deliberately loose. Missing a study was the expensive error; listing
extra candidates only costs review time. All 22 candidates, their titles, matched
patterns and factor tables are recorded in
`ml/evaluation/phase10_gravity_recovery`.

## What was added

**OSD-314** — *Adaptive response of Arabidopsis seedlings in microgravity and Mars
reduced gravity environment is enhanced by red light photostimulation.*

Arabidopsis thaliana Col-0 on the ISS, with a subset **centrifuged to 0.34 g in
orbit**, alongside microgravity samples and a 1 g ground control, every gravity level
crossed against red-light and dark treatments. 17 libraries.

It is the first dataset in this catalogue whose gravity label is a **gravity level**
rather than a reorientation direction. Acquisition is pinned by byte length and
SHA-256 in `scripts/acquire_phase10_osd314.py`, and the catalogue entry carries its
own limitations, including that 1 g samples are ground controls while 0 g and 0.34 g
samples are in orbit.

What it did and did not support is in `PHASE10_DOSE_GRAVITY_RECOVERY.md`: a
within-flight 0 g versus 0.34 g contrast reaching balanced accuracy 1.000 (p = 0.0055),
corroborated by the deposit's own 8,478–13,504 differentially expressed genes, and
**no model**, because 17 libraries in one mission cannot support one.

Catalogue: **17 → 19** NASA datasets.

## The second candidate, now analysed

**OSD-346** — Arabidopsis phyA/phyB under blue light, six commanded gravity levels from
0 to 1 g, 36 libraries, per-sample RSEM quantifications rather than a matrix. It was
built and analysed as the independent test of the OSD-314 result, and it **does not
reproduce it**: a graded gravity signal is present (ρ = 0.571, p = 0.0015) but emerges
only from 0.6 g upward, and the microgravity-versus-0.34 g distinction is absent in
every framing tried.

The per-sample files are the reason the acquisition took a script rather than a
download: 36 files are pinned by SHA-256 in `data/metadata/osd346_checksums` and
combined into `data/processed/osd346_partial_gravity.csv`. The 73 MB of raw files are
not committed; the digests are, so the matrix rebuilds byte-identically.

## Why nothing else was added

Every remaining weak model is limited by evidence that no available study supplies:

| Gap | What would close it | Available? |
| --- | --- | --- |
| Mizuna harvest: 14 endpoints, 1 experiment | more harvests **inside the same design** | no — merging experiments confounds experiment with treatment |
| Lettuce growth: 4 experiments | a 5th and 6th independent greenhouse experiment | no NASA source; the data is external and Earth-only |
| Radiation dose at fine resolution | randomised processing order, not just more doses | no — each (dose, timepoint) cell is one sequencing batch |
| Microbial absolute load across campaigns | a third campaign with baseline samples | only VEG-04A and VEG-04B exist |
| Cross-study transfer target | a second radiation study whose own contrast survives an unseen (dose, timepoint) cell | OSD-782 does not; no other processed radiation RNA-seq study exists in the 231 |
| Partial gravity above 1 g, or Moon/Mars levels | a study at 0.17 g or 0.38 g | no — the whole catalogue spans 0 to 1.05 g, so lunar and Mars gravity remain unobserved here |

## The lesson recorded here

An inventory is not a search. Phase 9's dataset conclusion was stated as a fact about
NASA's holdings and was based on one study's file listing; the correct version took an
API request per study and 15 minutes. The scan is now a script
(`ml/training/phase10_gravity_recovery.py`), so the next such claim can be re-checked
rather than re-asserted.
