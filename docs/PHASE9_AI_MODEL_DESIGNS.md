# Phase 9 AI model designs

Each candidate is specified before training, including the failure condition. A
design that only says what success looks like cannot be falsified.

## Design principles applied to all candidates

1. **The biological unit is the group, never the sample.** In OSD-46 an array is a
   technical replicate of one biological group, so splits are made over groups.
2. **All feature selection happens inside the training fold.** Nothing about the
   held-out group may influence which genes are chosen.
3. **The shipped artifact must be evaluable without a Python stack.** The runtime
   is dependency-free, so tree ensembles are evaluated but not shipped —
   `extract_linear_evaluator()` converts the best linear learner into a JSON
   evaluator.
4. **The failure condition is stated up front.** If the pre-specified scheme does
   not beat its baseline, the model is excluded rather than retuned.
5. **Permutation p-values are finite-sample corrected** as `(1 + #{null ≥
   observed}) / (1 + B)`, so the reported p-value can never be zero.

---

## A1 — `radiation-quality-osd46-v1` (shipped)

**Question.** Does Arabidopsis transcriptional state retain a signature of *which*
radiation quality it received?

| Item | Value |
| --- | --- |
| Study | OSD-46, Affymetrix ATH1 microarray |
| Platform | 22,560 gene models after collapsing probesets |
| Samples | 44 arrays |
| Biological groups | **22** (WT/atm-1 × control/γ/HZE × age × collection time) |
| Classes | `control` 8, `gamma` 18, `hze` 18 |
| Target | applied treatment, measured in the design |
| Split | leave-one-biological-group-out |
| Features | in-fold detection filter → top 1000 by variance → top 150 by ANOVA F |
| Learners | majority baseline, logistic-L2, logistic-L1, random forest, HistGBM |

**Why it is the strongest result in the phase.** γ (100 Gy, Cs-137) and Fe-56
(30 Gy) are balanced across array batches — 8 each on `0806A-10`, 10 each on
`1006A-03`. A classifier that separates them therefore cannot be reading array
batch.

**Stated limitation.** 100 Gy γ and 30 Gy Fe-56 differ in **both** quality and
absorbed dose, so the model separates the two *conditions*. It cannot attribute the
difference to radiation quality alone. That sentence ships with every prediction.

**Failure condition.** Balanced accuracy at or below the majority baseline, or
permutation p > 0.05 → exclude.

---

## A2 — `radiation-exposure-osd46-v1` (shipped)

**Question.** Is a sample irradiated at all? Same study, same features, binary
label.

| Item | Value |
| --- | --- |
| Samples / groups | 44 / 22 |
| Classes | `control` 8, `irradiated` 36 |
| Split | leave-one-biological-group-out |
| Extra evaluation | batch-controlled: `0806A-10` alone, 20 arrays, 4 control / 16 irradiated |

**The confound, stated numerically.** Cramér's V between array batch and condition
is **0.715**. The 8 controls appear only on `0706A-10` (4) and `0806A-10` (4) and
never on `1006A-03`, which holds 20 of the 44 arrays. A batch-blind classifier
could be reading sample handling.

**Mitigation.** `0806A-10` is the only batch containing all three conditions, so
evaluating there removes the confound by construction. Both numbers are reported;
the batch-controlled one is the defensible figure.

---

## B — `radiation-dose-osd782-v1` (designed, evaluated, **excluded**)

**Question.** Can nominal absorbed dose (0 / 10 / 100 Gy) be predicted from
expression?

| Item | Value |
| --- | --- |
| Study | OSD-782, bulk RNA-seq, GeneLab VST |
| Samples / groups | 36 / 12 |
| Pre-registered schemes | cell hold-out, timepoint hold-out, dose hold-out, dose + collection time as covariate |

**Outcome.** Best learner logistic-L1 at balanced accuracy **0.361** against a
0.333 chance rate, p = 0.2475. Dose is confounded with sample processing order.
Excluded, evidence retained in `ml/evaluation/excluded/`.

**Why not retuned.** The brief forbids models built to look good; the failure
appears under every one of the four grouping schemes, so it is structural.

---

## C — crop microbiome (designed, **not built**)

Two designs were considered and both were refused on the same principle — do not
build a model whose validation cannot mean anything.

**C1, ISS lettuce flight vs ground (OSD-267 / OSD-269).** Design: genus-level
relative abundance, CLR-transformed, plant as the group. Refused because VEG-01A
has **2 flight leaf plants**, tissues are repeated measures per plant, and pooling
missions confounds mission with condition. Replaced by the descriptive test in
`PHASE9_ML_EVALUATION.md`.

**C2, extension of the existing OSD-780 plate-count models.** Not attempted: the
existing `mizuna-microbial-load-v1` and `mizuna-microbial-relative-load-v2` already
model the measured plate counts with the published design. Adding a second model on
the same data would raise the model count without adding evidence, and model count
is explicitly not a success metric.

---

## D — D and E, why they produced nothing

**D, stress response.** No acquired study publishes a stress-severity measurement
paired with expression. Inventing a severity scale from timepoint order would be an
invented label, which the brief forbids.

**E, cross-study harmonised molecular.** Designed and run as a genuine experiment
(`ml/training/train_cross_study_transfer.py`): 17,997 shared TAIR genes between
OSD-46 (Wild Type + atm-1, microarray) and OSD-782 (Col-0, RNA-seq), per-gene z-scoring
within each study, in-fold ANOVA selection, 4 × 4 grid over C and k.

**Outcome: a verified negative.** All 16 settings landed on identical
accuracy 0.667 / balanced 0.500 with control recall 0.00 — the classifier labels
everything "irradiated". The within-study positive control on the same pipeline
scores 0.977 / 0.986, so the pipeline works and the transfer genuinely fails.

---

## F — lettuce v2 improvement

**Not attempted.** The brief permits it only if a new evaluation shows *genuine*
gain. No new lettuce data was acquired in Phase 9, and re-tuning on the same rows
would be a search over the test set rather than new evidence. `lettuce-earth-growth-v2`
is unchanged.
