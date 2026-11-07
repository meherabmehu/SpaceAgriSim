# Phase 10 — cross-study generalization

Phase 9 measured that a radiation classifier trained on OSD-46 (Affymetrix ATH1
microarray) does not transfer to OSD-782 (Illumina RNA-seq): 0.667 accuracy, 0.500
balanced accuracy, control recall 0.00, identical collapse across 16 settings.

Phase 10 asks the next question: **is that a representation problem that a better
harmonisation could fix?** Evidence: `ml/evaluation/phase10_cross_study.json`.

## Four harmonisations, one shared scoring protocol

Train OSD-46 → test OSD-782, irradiated versus control, 17,997 shared gene models.
Every transform is fit without test labels. Feature selection uses training rows only.

| Harmonisation | What it shares between platforms | Accuracy | Balanced | Control recall | Irradiated recall |
| --- | --- | --- | --- | --- | --- |
| per-gene z-score (Phase 9) | standardised scale | 0.667 | 0.500 | **0.00** | 1.00 |
| rank → quantile | ordering only | 0.667 | 0.500 | **0.00** | 1.00 |
| quantile map | test distribution mapped onto train | 0.667 | 0.500 | **0.00** | 1.00 |
| pathway modules (training-only co-expression) | neither scale nor gene identity | 0.667 | 0.500 | **0.00** | 1.00 |

All four collapse to predicting "irradiated" for every sample. Decision rule, fixed
before running: a harmonisation counts only if balanced accuracy exceeds 0.5 **with
non-zero recall for both classes**. Nothing is adopted. Beating 0.667 accuracy by
predicting the majority class is not a result.

## The reference that changes the interpretation

The obvious reading is "harmonisation does not work". That reading is too strong, and
the within-study reference shows why:

| Evaluation | Balanced accuracy | 95 % bootstrap interval |
| --- | --- | --- |
| **leave-one-group-out inside OSD-782** | **0.438** | **[0.300, 0.591]** |

The irradiated-versus-control contrast is **not learnable inside the target study
itself** by this pipeline. The interval spans chance (control recall 0.167, irradiated
recall 0.708), so OSD-782's own labels do not reproduce under group-held-out
validation.

That means a cross-study negative **against this target cannot distinguish**:

- a harmonisation failure — the representation really does not transfer, from
- an absent signal — there was nothing transferable to begin with.

## Corrected conclusion

Phase 9's conclusion, as written, was that a microarray-trained classifier "does not
transfer to RNA-seq without harmonisation, and 16 hyperparameter settings do not
rescue it". The first clause is true. The implication that harmonisation is the
obstacle is **not supported** by this evidence, because the target study does not
support the task even in-distribution.

The accurate statement is:

> Cross-study transfer from OSD-46 to OSD-782 fails under four label-free
> harmonisations. However OSD-782's own within-study balanced accuracy is 0.438
> (95 % CI 0.300–0.591), indistinguishable from chance, so this experiment is
> **inconclusive about harmonisation** and only establishes that this particular
> target pair cannot demonstrate transfer.

Recording this is more valuable than a rescued hyperparameter. It also identifies what
would settle the question: a target study whose own contrast is learnable, so that a
transfer failure can be attributed to the transfer.

## What was not done, and why

- **No target-label use.** No transform sees OSD-782 labels. Transductive methods
  (using unlabelled test features) were used; that is standard and is disclosed.
- **No tuning toward a positive result.** The four harmonisations were chosen as
  distinct scientific hypotheses, not searched over a grid.
- **No promotion.** The registry is unchanged; Phase 9's negative is preserved in
  `ml/evaluation/phase9_cross_study_transfer.json`.
