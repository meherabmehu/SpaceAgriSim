# Phase 8 — Machine-Learning Improvements

Two things were changed: one model was improved on measured evidence, and one
prediction was withdrawn. Everything else was left alone because the evidence did
not support changing it, which is also a result.

---

## The improvement: lettuce Earth growth, random forest → gradient boosting

### What was wrong

Phase 7 ran a benchmark of Dummy, ridge, RandomForest and HistGradientBoosting on
every task with measured data, under identical leave-one-experiment-out folds. On
the lettuce task it found:

| Learner | R² | MAE (g) |
|---|---|---|
| baseline (mean) | −0.054 | 125.83 |
| ridge | 0.576 | 78.93 |
| RandomForest | 0.797 | 39.92 |
| HistGradientBoosting | **0.880** | **32.59** |

The registered artifact was the random forest. Its own nested protocol scores
R² 0.812, which is consistent with the benchmark's 0.797 for the same family. So
the platform had already measured that boosting was better on this task and was
serving the random forest anyway. That is not a bug in any single function; it is
a gap between measuring a result and acting on it.

### What was done

A second model, `lettuce-earth-growth-v2`, trained with `GradientBoostingRegressor`
on the same WUR dataset. v1 was **not** overwritten: it is byte-identical, still
registered, still checksum-verified and still served, because the Phase 7 result
must stay reproducible.

Measured on the same folds:

| Learner | R² | MAE (g) | Beats v1 MAE on |
|---|---|---|---|
| RandomForest (v1 class) | 0.8131 | 39.14 | — |
| **GradientBoosting (shipped)** | **0.8699** | **34.92** | **4 / 4 held-out experiments** |
| HistGradientBoosting | 0.8796 | 32.59 | — |

The improvement is not a pooled average hiding a fold that got worse: it wins on
MAE in every one of the four held-out experiments. The training script asserts
this and refuses to write the artifact otherwise.

### Why classic boosting and not the better-scoring HistGradientBoosting

HistGradientBoosting scores 0.0099 higher. Shipping it would mean re-implementing
sklearn's feature binning and structured-array predictor layout inside the
dependency-free JSON evaluator — a large correctness surface for a one-percent
gain, in an evaluator whose whole selling point is that it is auditable by hand.

Classic `GradientBoostingRegressor` stores ordinary decision trees in exactly the
same `children_left` / `feature` / `threshold` / `value` arrays the existing
forests already use, so it serialises losslessly and evaluates as one line of
arithmetic:

```
prediction = init + learning_rate × Σ tree(x)
```

The serialised ensemble was verified against sklearn before the artifact was
written: **max absolute difference 0.0**. A test re-checks it against the stored
trees.

### Engineering details

- New artifact block `boostedTrees: {init, learningRate, trees[]}`.
- `_validate_trees` is factored out so bagged and boosted ensembles cannot diverge
  on branch bounds, cycle detection or feature width. A test corrupts the learning
  rate and a branch index *with valid checksums* and asserts both are rejected —
  otherwise the checksum would mask the semantic check.
- Predictions are clamped at zero. Boosted trees will cross zero just below the
  measured range, and fresh mass cannot be negative; the response sets
  `outputClamped: true` when it happens rather than silently returning a physical
  impossibility.
- The response reports the full model-selection comparison, including the model it
  replaced, so a caller can see the basis for the swap.
- `Evidence.jsx` renders registry cards generically, so v2 appears as an
  additional card with **no frontend source change** (verified: `git diff` against
  the baseline is empty for `frontend/`).

## The withdrawal: absolute microbial load

Documented in `PHASE8_SCIENTIFIC_INTEGRITY.md`. In ML terms: a model with
leave-one-campaign-out R² of −0.55 and −0.58 on both held-out campaigns is not a
weak model, it is a model whose estimand is not identifiable from the available
features. Standardising within campaign — which removes the campaign offset from
the target — is what made transfer possible at all (+0.444 / +0.373).

That is the generalisable lesson and it is why the v2 model was not tuned further:
more capacity on the absolute estimand would have produced a better-looking
training fit and the same failure out of sample.

## What was deliberately not done

- **No deep learning.** The largest measured target is 1648 samples over 4
  experiments; the largest NASA target is 123 samples over 35 groups. A neural
  model here would be unidentifiable, and the Phase 7 report states this reason
  explicitly rather than treating it as a style preference.
- **No hyperparameter search on v2 beyond the fixed configuration.** Tuning on the
  same four folds that produce the reported metric would inflate it. The
  configuration was chosen because it is the one the Phase 7 benchmark already
  used, so the comparison is like-for-like.
- **No promotion.** v2 is `experimental`, not `validated`. Four experiments from one
  cultivar on Earth is not validation, and the interval is still labelled
  uncalibrated.
- **Mizuna harvest was not retuned.** 14 endpoints, inconsistent target definition
  between arms. It stays `baseline-only` with no promotion path.
- **Tomato was not retuned.** Its label is recorded environment, not measured plant
  performance; better classification accuracy would not make it a stress predictor.

## Reproduce

```bash
python ml/training/train_lettuce_v2.py     # writes artifact, registry entry, benchmark
python scripts/package_runtime_data.py     # bundles verified assets for the API
cd backend && python -m pytest -q
```

The training script prints the full comparison, the per-fold win count, and the
serialisation check before writing anything.
