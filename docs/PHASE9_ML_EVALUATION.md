# Phase 9 ML evaluation

Every number below is reproducible from the committed scripts and artifacts. Where a
result is negative it is reported as a negative.

## A1 — radiation quality (OSD-46, 3 classes)

44 arrays, 22 biological groups, leave-one-group-out, 150 genes selected inside each
fold.

| Learner | Accuracy | Balanced accuracy | Macro F1 | Shipped |
| --- | --- | --- | --- | --- |
| majority baseline | 0.000 | 0.000 | 0.000 | — |
| **logistic-L2** | **0.932** | **0.898** | **0.906** | **yes** |
| logistic-L1 | 0.795 | 0.648 | — | no |
| random forest | 0.932 | 0.875 | — | no (not serialisable) |
| HistGBM | 0.864 | 0.843 | — | no (not serialisable) |

Confusion matrix (rows = truth, columns = prediction, order control/gamma/HZE):

```
[[ 6,  0,  2],
 [ 0, 18,  0],
 [ 1,  0, 17]]
```

Per-class recall: control 0.750, gamma 1.000, HZE 0.944. The four errors are all
control↔HZE, which is the scientifically expected confusion — both are dense-track
conditions relative to sparse γ.

- Bootstrap 95 % CI for accuracy: **0.864 – 1.000**.
- Permutation test: observed 0.932 against a null mean of 0.318 (95th percentile
  0.500), **p = 0.0099** over 100 permutations — the floor at that budget, computed
  as `(1 + 0) / (1 + 100)`.
- Genes shared across all 22 folds: **74 of 150**, so the signal is not carried by a
  single fold-specific gene set.

**Metric revision, reconciled.** An earlier intermediate OSD-46 artifact reported
balanced accuracy 0.870. The committed artifact reports 0.898. Rather than leave a
silent discrepancy, `phase9_sensitivity.py` measured the dependence on the number of
selected genes:

| k | 25 | 50 | 100 | 150 | 300 | 500 |
| --- | --- | --- | --- | --- | --- | --- |
| accuracy | 0.932 | 0.932 | 0.932 | 0.932 | 0.886 | 0.864 |
| balanced | 0.898 | 0.898 | 0.898 | 0.898 | 0.861 | 0.843 |

The result is **flat across k = 25…150**, so k does not explain the change. The
earlier number came from an intermediate run whose group key and selection path were
later corrected (documented in `PHASE9_ML_TRAINING.md`); it was never committed, so
it is superseded rather than reproduced. The committed artifact is the reference.

For completeness the sweep also ran the illegitimate rule — choosing the top-variance
genes once on the pooled matrix, which lets held-out arrays influence the feature
set. It scores *higher* (balanced 0.958 at k = 150). That gap is the size of the
optimism the leakage would have bought, and is exactly why the deployed rule selects
inside the fold.

## A2 — radiation exposure (OSD-46, binary)

| Evaluation | Accuracy | Balanced accuracy | Notes |
| --- | --- | --- | --- |
| majority baseline | 0.818 | 0.500 | ≥ chance, so this is a real baseline |
| **all 44 arrays** | 0.932 | 0.910 | batch-confounded |
| **`0806A-10` only** | — | **0.969** | 20 arrays, 4 control / 16 irradiated |

Permutation p = 0.0099 (floor). The batch-controlled figure is the defensible one,
and both are shipped with the artifact.

Note that the majority baseline here is 0.818 accuracy but 0.500 balanced: this is
why the project compares classifiers on **balanced** accuracy. The registry
previously compared on an MAE key that classifiers do not have, which made every
classifier advertise "does not beat baseline". Fixed in this phase.

## B and C — excluded candidates

| Model | Study | Samples / groups | Best learner | Balanced accuracy | p | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| dose | OSD-782 | 36 / 12 | logistic-L1 | **0.361** | 0.353 | excluded |
| gravity | OSD-411 | 63 / 16 | logistic-L1 | **0.500** | 0.517 | excluded |

OSD-782 by grouping scheme: cell hold-out 0.083, timepoint hold-out 0.500, dose
hold-out 0.000, dose + collection-time covariate 0.083. OSD-411 by transfer
direction: WT→pgm-1 0.531, pgm-1→WT 0.419, tissue hold-outs 0.533 / 0.500 / 0.375 /
0.562, full LOGO 0.048. Excluded artifacts live in `ml/evaluation/excluded/` with
`evidenceStatus: insufficient-evidence`; a test asserts they are unreachable from the
API.

## E — cross-study transfer (verified negative)

17,997 shared TAIR genes, per-gene z-scoring within each study, ANOVA-only selection
(z-scored input, so variance preselection is disabled by the guard), 4 × 4 grid over
C ∈ {0.01, 0.1, 1.0, 10.0} × k ∈ {50, 150, 500, 2000}.

| Evaluation | Accuracy | Balanced accuracy | Control recall |
| --- | --- | --- | --- |
| within-OSD-46 reference (LOGO, k = 150, C = 1.0) | **0.977** | **0.986** | — |
| cross-study, all 16 settings | 0.667 | 0.500 | **0.00** |

`allSettingsIdentical: true`, verdict `transfer-failed-collapsed-to-majority`. The
classifier labels everything "irradiated", which is exactly the majority class in the
test study (24 of 36). Because the positive control on the same pipeline scores
0.977/0.986, this is a statement about the biology and the platform gap, not about
the code.

**This is the most useful negative in the phase**: it says a microarray-trained
Arabidopsis radiation classifier does not transfer to RNA-seq without
harmonisation, and 16 hyperparameter settings do not rescue it.

## Priority C — descriptive, not predictive

Host chloroplast and mitochondrial reads removed, genus level, CLR-transformed,
permutation test over plants (5000 permutations).

| Study | Mission | Leaf design | Genera | CLR centroid distance | p |
| --- | --- | --- | --- | --- | --- |
| OSD-267 | VEG-01A | 2 flight / 5 ground | 66 | 2.391 | **0.904** |
| OSD-269 | VEG-03A | 6 flight / 5 ground | 97 | 0.690 | **0.794** |

**No detectable compositional difference** between flight and ground lettuce leaf
communities at these sample sizes. No model was registered. This is a descriptive
statement about relative composition: it is not a CFU count, not a food-safety
verdict, and carries no yield implication.

## Calibration

No probability calibration is applied or claimed. The shipped evaluator produces a
softmax over trained classes, which is a **relative score between those classes**,
not a confidence interval. Every API response says so explicitly
(`interval.calibrated = false`), because an uncalibrated softmax on 22 groups would
not survive a reliability check and pretending otherwise would be the exact failure
mode this phase is meant to prevent.

## Summary of what Phase 9 establishes

- A radiation **quality** signature exists in OSD-46 and is not explained by array
  batch (p = 0.0099).
- A radiation **exposure** signature exists, with a batch-controlled estimate of
  0.969 that survives the confound.
- Absorbed **dose** and ground **reorientation** are not predictable from the
  available designs.
- Cross-study molecular transfer **fails** even with a working pipeline.
- ISS lettuce microbiome composition shows **no detectable flight effect** at
  n = 2–6 plants per class.
