# Phase 9 ML training

What was trained, how the pipeline prevents leakage, and the three real bugs that
were found and fixed during this phase.

## Harness

`ml/training/phase9_harness.py` provides the shared machinery:

| Function | Role |
| --- | --- |
| `classification_learners()` | majority baseline, logistic-L2, logistic-L1, random forest (400 trees), HistGBM |
| `select_features()` | in-fold detection filter → variance stage → ANOVA F stage |
| `grouped_cv_score()` | leave-one-group-out CV with in-fold selection and a leakage assertion |
| `permutation_test()` | labels permuted **between groups**, finite-sample corrected |
| `bootstrap_ci()` | stratified percentile bootstrap over held-out samples |
| `extract_linear_evaluator()` | fitted linear model → dependency-free JSON evaluator |
| `warn_on_fold_imbalance()` | reports held-out folds containing only one class |

### Why leave-one-group-out instead of stratified k-fold

With these designs each group belongs to exactly one class, so `StratifiedGroupKFold`
cannot balance class membership across folds when the group determines the label.
Measured on OSD-411 it produced a fold whose entire test set was a single class,
which drove a pooled accuracy of 0.000 — a number that reads as model failure but
is an artefact of the partition. LOGO is deterministic, gives every group the same
treatment, and guarantees all classes appear in each training fold whenever the
study has at least two groups per class. The cost is more fits, which is
affordable at these sizes.

`grouped_cv_score()` asserts on every fold that
`set(groups[train]) & set(groups[test]) == ∅` and that every sample is held out
exactly once. A leak therefore fails loudly rather than quietly inflating a score.

### Seeds and determinism

`SEED = 20261107` drives the splitter, all learners, the bootstrap and the
permutation generator. Two consecutive runs of `train_radiation_osd46.py` produce
byte-identical metrics; the artifacts differ only in their `trainedAt` timestamp.

## QC performed before training

| Check | OSD-46 | OSD-782 | OSD-411 |
| --- | --- | --- | --- |
| Missing values | none; imputation refused | none after VST | none in usable rows |
| Probeset collapse | 22,810 probesets → 22,560 gene models by mean | n/a | n/a |
| Complete-data filter | 22,560 → **21,267** genes finite across all 44 arrays (the figure the artifact reports as `genesAvailable`) | n/a | n/a |
| Library size floor | n/a | 5,000,000 reads (`MIN_LIBRARY_READS`) | same |
| Transformation | published log2 normalised | GeneLab VST | published counts, VST |
| Batch metadata | recovered from S3 CEL headers → `osd46_array_batch.csv` | confounded, documented | none published |

The OSD-46 batch table required work: ISA metadata does not carry the array batch,
so it was recovered from the raw CEL file headers and written to
`data/processed/osd46_array_batch.csv`. Without it the central claim of A1 — that
γ and HZE are batch-balanced — could not have been checked at all.

## Group-key construction

The biological unit for OSD-46 is
`genotype | radiation | ageDays | hoursAfterIrradiation`. Two bugs were found here
and both changed the results:

1. **`ageDays` was omitted**, which merged plants of different ages into one group.
2. **`hoursAfterIrradiation` was NaN** for the eight non-irradiated controls, and
   NaN does not group. Filling it with the literal `no-timepoint` restored 22
   groups instead of a smaller, silently collapsed number.

Neither bug announced itself. Both were found by comparing the group count against
the study description.

## Three bugs found and fixed

### 1. Variance preselection on z-scored data (the expensive one)

Per-gene z-scoring forces every gene's variance to exactly **1.0** (verified: range
1.0 ± 7e-16). "Keep the most variable genes" therefore becomes an arbitrary
tie-break, and the cross-study experiment initially produced a convincing negative
that was entirely a pipeline artefact.

Fix: `select_features(..., variance_preselection=False)` for standardised input,
plus a hard guard that raises `ValueError` when the spread of variances is
degenerate. The tell that something was wrong was a **within-study positive control
scoring at chance** (0.818 / 0.500); a reference that cannot reproduce a known
positive means the pipeline, not the biology, is broken.

### 2. Binary logistic coefficients stored under both class labels

A binary `LogisticRegression` stores a single `coef_` row. Storing it under both
class labels made both classes score identically, so the model could never disagree
with itself. Validation surfaced it only as an opaque "non-finite" artifact error.

Fix: `extract_linear_evaluator()` writes class-0 as a zero row and puts the
decision function on class 1. Verified against sklearn: softmax matches
`predict_proba` to **1.1e-16** (binary) and **1.7e-16** (multiclass).

### 3. Scaler silently dropped

The evaluator looked up the pipeline step by the literal name `"scale"`.
`named_steps` returns `None` on a miss instead of raising, so standardisation was
silently skipped: a manual score of −0.502 against sklearn's −0.377.

Fix: scalers are detected by fitted attributes (`mean_`, `scale_`) and the function
raises on ambiguity or absence.

## Training runs and cost

| Script | Runtime | Output |
| --- | --- | --- |
| `train_radiation_osd46.py` | 2 m 48 s | A1 + A2 artifacts, `phase9_osd46_radiation.json` |
| `train_rnaseq_models.py` | 3 m 55 s | B + C evaluations, excluded artifacts |
| `train_cross_study_transfer.py` | 1.6 s | `phase9_cross_study_transfer.json` |
| `phase9_sensitivity.py` | 15 s | `phase9_osd46_sensitivity.json` |
| `analyze_veg_microbiome.py` | 0.7 s | `phase9_veg_microbiome_feasibility.json` |

Deep learning was not used anywhere. The largest task has 44 samples over 22
groups; a network would have more parameters than independent observations and
could not be identified.

## Artifact protocol

Each artifact records: source study and URL, platform, organism, task, class
labels, sample and group counts, gene counts, validation scheme, metrics, baseline
metrics, every learner's result, permutation test, batch confound, seeds,
environment, the JSON evaluator, the domain ranges, per-class reference profiles,
limitations and recommended use.

`ml/artifacts/registry.json` pins a SHA-256 per artifact, and the test suite
re-verifies every one. Excluded candidates keep their evaluation under
`ml/evaluation/excluded/` and are **absent** from the registry.
