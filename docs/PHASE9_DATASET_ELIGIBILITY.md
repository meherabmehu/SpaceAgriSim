# Phase 9 dataset eligibility

Ranked table of every candidate, with the exact reason each rejection was made.
The ranking criterion is **fitness for a defensible supervised model**, not
convenience: an independent biological unit, a label that is actually measured, and
a design in which the label is not confounded with processing.

## Ranked eligibility

| Rank | Study | Priority | Biological unit | n (units) | Label source | Verdict | Why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **OSD-46** | A radiation | biological group (genotype × condition × age × timepoint) | 44 samples / **22 groups** | applied treatment (0 / 100 Gy γ / 30 Gy Fe-56) | **eligible** | three measured conditions, and γ vs HZE are batch-balanced |
| 2 | **OSD-46** (binary) | A radiation | same | 44 / 22 | irradiated vs not | **eligible with a stated confound** | controls are not batch-balanced; a batch-controlled subset is reported |
| 3 | OSD-782 | A radiation dose | biological group | 36 / 12 | nominal absorbed dose 0 / 10 / 100 Gy | **rejected** | dose confounded with processing order; best balanced accuracy 0.361, p = 0.353 |
| 4 | OSD-411 | B gravity | biological group | 63 / 16 | 90° reorientation vs vertical | **rejected** | balanced accuracy 0.500 at chance, p = 0.517; failed every genotype and tissue transfer direction |
| 5 | OSD-267 (VEG-01A) | C crop microbiome | individual plant | 11 samples, leaf **2 flight / 5 ground** | ISS flight vs ground control | **rejected for modelling, analysed descriptively** | two flight plants cannot form a training class |
| 6 | OSD-269 (VEG-03A) | C crop microbiome | individual plant | 15 samples, leaf 6 flight / 5 ground | ISS flight vs ground control | **rejected for modelling, analysed descriptively** | n too small, and leaf/root are repeated measures on the same plant |
| 7 | OSD-480 | B gravity | — | 0 usable | none published | **rejected** | 3208 objects / 6.2 TB of raw FASTQ; no processed count matrix |
| 8 | OSD-772 | C crop microbiome | — | 0 usable | none published | **rejected** | 442 objects raw amplicon FASTQ; no taxonomy or OTU table |
| 9 | OSD-412 / 413 / 414 | C crop microbiome | — | 0 usable | none published | **rejected** | 87 / 25 / 21 objects raw amplicon FASTQ; no processed abundance table |
| 10 | OSD-72 | C (found by sweep) | — | — | — | **rejected** | murine colon microbiota, not a crop |
| 11 | OSD-170 | C (found by sweep) | — | — | — | **rejected** | aircraft bioaerosol samples, not a crop, no plant factor |
| 12 | OSD-276 | C (found by sweep) | — | — | — | **rejected** | ISS surface swabs, not a crop |
| 13 | OSD-487 | C (found by sweep) | — | — | — | **rejected** | human diabetic foot ulcer microbiome |
| 14 | OSD-780 | C (already used) | plate count campaign | existing models | measured plate counts | **already modelled** | Phase 6/7 models; unchanged here |

## Why each rejection is a scientific decision, not a data-availability decision

**OSD-782 (dose).** The study does publish 0 / 10 / 100 Gy conditions, so a naive
reading says "regression target available". It is not usable as a predictor because
the dose groups are confounded with sample processing order. Four grouping schemes
were tested before rejecting it — cell hold-out (0.083), timepoint hold-out (0.500),
dose hold-out (0.000), and dose plus collection time as a covariate (0.083) — and
the best learner reached balanced accuracy 0.361 against a 0.333 chance rate with
p = 0.353. Retuning was explicitly declined: the failure is structural, not
hyperparametric.

**OSD-411 (gravity).** 63 samples over 16 groups looks usable until the labels are
examined: the factor is *reorientation on the ground*, not gravity level. The model
failed in every direction tested — WT→pgm-1 transfer 0.531, pgm-1→WT 0.419, four
tissue hold-outs between 0.375 and 0.562, and full leave-one-group-out 0.048/0.047.
A 90° reorientation is **not** partial gravity, so no Moon or Mars claim can be
made from it in any case.

**OSD-267 / OSD-269 (crop microbiome).** These carry the label the priority asks
for (ISS flight versus ground control) and a processed taxonomy table. They are
rejected purely on design:

- VEG-01A leaf has **2 flight plants**; a classifier cannot be trained on that.
- Each plant contributes both a leaf and a root sample, so tissues are repeated
  measures, not independent observations. Treating them as independent would
  double-count plants.
- Pooling VEG-01A and VEG-03A would confound mission with condition, which is the
  same defect as an unbalanced batch.

A descriptive compositional comparison is still legitimate and is reported in
`PHASE9_ML_EVALUATION.md`: CLR centroid distance between flight and ground leaf
communities gives p = 0.904 (VEG-01A) and p = 0.794 (VEG-03A) over 5000
permutations — **no detectable separation**. No model was registered.

**OSD-480 (gravity, large).** Rejected on volume and content: 6.2 TB of raw
FASTQ with no processed matrix. Acquiring it would mean running an alignment and
quantification pipeline that does not exist in this project, and the resulting
numbers would not be reproducible from the repository.

## Labels that are explicitly not modelled

| Tempting target | Why it is refused |
| --- | --- |
| Crop yield from expression | no paired yield measurement exists in any acquired study |
| Absorbed dose in grays | only nominal dose labels exist, and OSD-782's are confounded |
| Partial / lunar / martian gravity | all available labels are binary flight or a ground reorientation |
| Absolute microbial load | 16S gives relative composition only; CFU cannot be recovered |
| Stress severity | no severity scale is published with these studies |

## Final count

- **2 models** built and registered (both NASA OSD-46, different questions).
- **2 candidates** built, evaluated and **excluded** with retained evidence.
- **0 models** built for crop microbiome, with the discovery correction recorded.
- **No** lettuce v2 change: no new evaluation showed a genuine gain over
  `lettuce-earth-growth-v2`, so the existing model was left alone rather than
  re-tuned to look better.
