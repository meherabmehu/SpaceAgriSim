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
the within-study reference shows why. It has to be measured **under two protocols**,
because the two answer different questions and the answer differs:

| Within-OSD-782 reference | Balanced accuracy | 95 % interval / p |
| --- | --- | --- |
| hold out (dose, timepoint) cells | 0.438 | [0.300, 0.591] |
| hold out whole timepoints | **0.812** | permutation p = 0.001 |

So the target study **does** carry a learnable irradiated-versus-control signal. It
does not survive generalization to an unseen (dose, timepoint) cell, because each of
those 12 cells is a single contiguous sequencing batch, so a cell-held-out fold also
asks the model to generalise across a batch.

A cross-study transfer faces the harder condition — everything about the target is
unseen — so the **cell-held-out figure is the transfer-analogous one**, and the
transfer negative stands. What does not stand is the stronger phrasing used earlier in
this phase, that OSD-782's contrast "is not learnable by this pipeline". That sentence
was written from one protocol and is false under the other. The corrected statement is
narrower and more useful.

## Corrected conclusion

Phase 9's conclusion was that a microarray-trained classifier does not transfer to
RNA-seq, and implied that harmonisation was the obstacle. Phase 10 first concluded the
target had no signal at all. Both were single-protocol readings. The evidence supports
neither in full:

> Cross-study transfer from OSD-46 to OSD-782 fails under four label-free
> harmonisations. The target is not signal-free: its irradiated-versus-control
> contrast reaches balanced accuracy 0.812 (p = 0.001) when whole timepoints are held
> out, and 0.438 (95 % CI 0.300–0.591) when whole (dose, timepoint) cells are. A
> transfer must generalise across the harder of the two conditions, so the negative
> stands and harmonisation remains implicated — but it is not proven to be the cause,
> because the design cannot separate it from the cell-level batch structure of the
> target.

That is the honest limit of what 36 libraries can establish. The measurement that
would settle it is a target study whose cells are not single batches.

## What was not done, and why

- **No target-label use.** No transform sees OSD-782 labels. Transductive methods
  (using unlabelled test features) were used; that is standard and is disclosed.
- **No tuning toward a positive result.** The four harmonisations were chosen as
  distinct scientific hypotheses, not searched over a grid.
- **No promotion.** The registry is unchanged; Phase 9's negative is preserved in
  `ml/evaluation/phase9_cross_study_transfer.json`.
