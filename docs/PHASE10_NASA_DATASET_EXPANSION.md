# Phase 10 — NASA dataset evaluation

Phase 10 did **not** acquire new NASA datasets, and this document explains that
decision with the evidence rather than leaving it as an omission.

## What already exists

Phase 9 swept every OSDR identifier from OSD-1 to OSD-900:

| Verdict | Studies |
| --- | --- |
| usable processed matrix | **231** |
| rejected — no expression data | 209 |
| rejected — raw sequencing only | 115 |
| rejected — raw amplicon only | 32 |
| **found in range** | **587** |

Of those 231, six publish a processed taxonomic table, and the plant-relevant ones
were evaluated. The catalogue now lists **17 datasets** (18 through the API, which
also surfaces the external Earth lettuce source), including the four Phase 9 added:
OSD-46, OSD-782, OSD-411 and OSD-780.

## Why Phase 10 added none

The Phase 10 mission is model improvement, and every weak model here is limited by
**evidence**, not by an unfilled data slot. Re-examining the 231 usable studies
against the specific gaps the audit found gives no candidate:

| Gap found in the audit | What would close it | Available in OSDR? |
| --- | --- | --- |
| Mizuna harvest: 14 endpoints, 1 experiment | more harvests with paired conditions **in the same design** | no — merging separate experiments would confound experiment with treatment, which is the defect the audit already rejected |
| Lettuce growth: 4 experiments | a 5th and 6th independent greenhouse experiment | no NASA source; the data is external (WUR/4TU) and Earth-only |
| Radiation dose: confounded with processing order | a dose study with randomised processing order | not in the 231; OSD-782 is the only plant dose series with a processed matrix |
| Gravity: 90° reorientation ≠ gravity level | a real partial-gravity plant study with processed expression | no — OSD-480 is 6.2 TB of raw FASTQ with no processed matrix |
| Cross-study transfer target | a second radiation study whose **own** contrast is learnable | OSD-782 fails its own within-study test (0.438, CI 0.300–0.591) |
| Microbial absolute load across campaigns | a third campaign with baseline samples | only VEG-04A and VEG-04B exist |

## What Phase 10 did with the data it has

Rather than acquire data that would not change a conclusion, Phase 10 used the
existing studies more rigorously:

1. **Reuse of the deployed pipeline.** The explanation, stability and cross-study
   scripts import the *training* loader and selection function instead of copying
   them. Phase 9 had a bug caused by a duplicated group key, so the duplication is
   removed rather than repeated.
2. **A within-study reference for the transfer study**, which turned a negative into
   a correctly scoped negative. That required no new data, only a measurement nobody
   had made.
3. **Group-level conformal calibration** on the 35 pillows and 4 experiments already
   present, which fixed an interval defect without a single new observation.

## The OSD-480 question, explicitly

OSD-480 is the obvious gravity candidate and is **not** pursued. It is 3,208 objects
and 6.2 TB of raw FASTQ with no processed matrix. Running an alignment and
quantification pipeline would (a) be unreproducible from this repository, (b) take
days of compute, and (c) produce numbers no reviewer could check. The brief asks for a
justified resource plan before that work; the justification does not exist while the
scientific question (partial gravity) still cannot be answered by a ground
reorientation study of any size.

## Conclusion

The honest Phase 10 dataset statement is that **the corpus was already exhausted for
these questions in Phase 9**, and the marginal value of another study is zero until a
study arrives that fills a specific gap listed above. Fabricating progress by adding
an unrelated dataset would inflate the catalogue without improving a single model.
