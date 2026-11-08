# Phase 11 — uncertainty and out-of-distribution

Phase 10 measured the intervals and refused to call them guarantees. Phase 11 asks the
harder question about the other half of the uncertainty story: **does the novelty score
mean anything at all?**

Until now the honest answer was "unvalidated". This document turns that into a tested
negative, which is a different and stronger position.

Evidence: `ml/evaluation/phase11_ood_uncertainty.json`.

```
python ml/training/phase11_ood_uncertainty.py    # ~30 s
```

---

## 1. Two controls made the test possible

The Phase 11 duplicate audit handed this question a gift. The corpus now contains:

| Control | What it is | What a sane score must do |
| --- | --- | --- |
| **OSD-320** | bit-for-bit the same arrays as OSD-46 (r = 1.000000, max|diff| = 0.0) | call it ordinary data |
| **OSD-782** | bulk RNA-seq, same organism, different platform | flag it |
| held-out group | an ordinary biological group from OSD-46 | call it ordinary |

The first control is the one that catches broken detectors. A score that calls a re-deposited
copy "novel" is measuring accession metadata, not data.

Expectations were fixed before the run: duplicate ≤ reference distribution, platform shift
≥ 0.9 AUC against the reference, held-out groups within ±0.15 of 0.5.

---

## 2. Two scores, three controls

Per-gene z-scoring within each study (required to compare platforms at all), then either a
Mahalanobis distance in 10 PCA components fitted on OSD-46, or the mean 1 − Pearson
correlation to the 5 nearest OSD-46 arrays. Every reference sample is scored by a model that
never saw it.

| Score | reference | duplicate | platform shift | C1 duplicate | C2 shift | C3 held-out | passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mahalanobis (10 PCs) | 2.595 | 3.043 | 1.286 | 0.702 ✗ | 0.016 ✗ | 0.471 ✓ | 1/3 |
| kNN correlation | 1.000 | 0.395 | 0.837 | 0.033 ✓ | 0.310 ✗ | 0.505 ✓ | 2/3 |

**Neither score passes. `ood-score-not-validated-by-any-available-control`.**

The direction of the failures is the interesting part:

- **The platform-shifted study scores *lower* than the training data itself** (0.016 and
  0.310 against a reference median). A score that calls a different measurement platform
  *more familiar* than the training set is not measuring novelty in any usable sense.
- **The duplicate scores higher than the reference under Mahalanobis** (0.702). The same
  arrays, scored by a model fitted on all 44 instead of 43, drift upward by enough to look
  novel.

---

## 3. Why it fails — three structural reasons, none fixable by tuning

**Standardisation destroys the signal under test.** To compare an array study with an
RNA-seq study at all, every gene must be put on a common scale, and per-gene z-scoring
deletes each gene's mean level — which is much of what a platform shift *is*. The feature
engineering needed to make the comparison possible is the same step that removes the
difference being looked for.

**In-sample distances are biased upward.** Mahalanobis distances computed with the same
points used to estimate the covariance carry a factor of about √((n−1)/(n−p)); at 44 arrays
and 10 components that is 1.13×, larger than the gap between an ordinary sample and an
unusual one. The first version of this script compared a new study against in-sample
distances and reported AUC 0.001 for a genuinely different platform — the *opposite* of the
truth. Scoring every reference sample leave-one-out is what fixed it, and it is the reason
the current Mahalanobis row is interpretable at all.

**A different platform is confounded with everything else.** OSD-782 differs in assay,
preparation protocol and organism part simultaneously with platform. Even a score that
flagged it correctly could not say which of those moved. "Outside anything this model has
seen" is the strongest defensible statement, and it is a description, not a classification.

---

## 4. What the product may say

| Claim | Status |
| --- | --- |
| "This sample is a long way from the training data" | **Permitted** — a distance is a description |
| "This sample is out of distribution" (as a validated flag) | **Rejected** — no score passed its controls |
| "OOD threshold validated" | **Rejected** — unchanged from Phase 10, now with a tested basis |
| "The model can detect platform shift" | **Rejected by data** — cross-platform validation does not exist here |

No threshold is emitted. The artifact records descriptive quantiles of leave-one-out
training-study scores **and** says in the same object that they are not thresholds, because
publishing quantiles next to a warning is how quantiles become thresholds.

---

## 5. Uncertainties that do hold up

The conformal intervals from Phase 10 are untouched and remain the defensible mechanism,
with empirical and nominal coverage always reported separately:

| Model | Nominal | Measured held-out coverage | Mean width |
| --- | --- | --- | --- |
| `mizuna-microbial-relative-load-v2` | 0.90 | **0.9919** (group level) | 3.4015 |
| `mizuna-microbial-load-v1` | 0.90 | **0.9919** (group level) | 3.5555 radius |
| `lettuce-earth-growth-v2` | 0.90 | **0.9606** | 91.20 |
| `lettuce-earth-growth-v1` | 0.90 | **0.9393** | 112.94 |

These are measured coverages on held-out groups, not guarantees: multiple tissues from one
pillow, and two campaigns, are not a sample of future campaigns. The distinction between
"90 % interval" as a claim and "interval that achieved 0.9919 on held-out groups" as a
measurement is preserved everywhere in the product.

---

## 6. Status

| Item | Classification |
| --- | --- |
| Novelty score tested against a duplicate control | **Completed** (new) |
| Novelty score tested against a platform-shift control | **Completed** (new) |
| False-positive control on held-out groups | **Completed** — both scores pass, 0.471 and 0.505 |
| A validated OOD score | **Rejected by scientific evaluation** — 1/3 and 2/3 controls passed |
| A validated OOD threshold | **Rejected** — no threshold emitted, `thresholdValidated: false` |
| Conformal intervals | **Completed** (Phase 10), unchanged, empirical ≠ nominal |
| Registry change | **None** |

The value here is negative but durable: the platform can now say the OOD flag was *tested*
and did not survive, rather than that it was never examined. A future dataset with two
measured platforms of the same samples would be the thing that unblocks it — that is a
data requirement, not a modelling one.
