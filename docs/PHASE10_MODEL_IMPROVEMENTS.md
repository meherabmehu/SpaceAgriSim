# Phase 10 — model improvements

What was attempted, what was adopted, and what was rejected. Nothing here is
promoted on a pooled metric alone.

## Adopted

### Interval calibration for four models

The only change that reached production, and it is a change to what the models
*claim*, not to what they predict. Full detail in `PHASE10_UNCERTAINTY.md`.

| Model | Phase 9 stated | Phase 9 delivered | Phase 10 states | Phase 10 measured |
| --- | --- | --- | --- | --- |
| `mizuna-microbial-relative-load-v2` | 90 % | 0.849 | 90 % group-level | **0.992** |
| `mizuna-microbial-load-v1` | 90 % | 0.811 | 90 % group-level | **0.992** |
| `lettuce-earth-growth-v1` | none claimed | untested | 90 % CV+ | **0.939** |
| `lettuce-earth-growth-v2` | none claimed | untested | 90 % CV+ | **0.961** |

The microbial radii are wider (3.40 vs 2.44 SD; 7.26 vs 4.91 log₁₀ CFU/g). That cost
is deliberate and published beside the row-level radius it replaced.

### Explanations for the two radiation classifiers

New capability, not an improvement to accuracy. `PHASE10_EXPLAINABLE_AI.md`.

## Rejected, with the numbers

### Mizuna harvest — no model is possible

| | R² | MAE |
| --- | --- | --- |
| mean baseline | −0.138 | 14.41 |
| random forest (best) | **−0.106** | 13.93 |
| ridge | −0.376 | 16.29 |
| gradient boosting | −0.995 | 18.00 |

The promotion bar is R² > 0. Nothing clears it. Beating a negative baseline with a
less-negative number is not an improvement, and `baseline-only` status is kept.

### Lettuce v3 — tested and rejected

| | R² | MAE | Held-out experiments won vs v2 |
| --- | --- | --- | --- |
| **v2 (shipped)** | **0.870** | **34.92** | — |
| deeper trees, 300 estimators | 0.868 | 35.33 | 1 of 4 |
| shallower and slower | 0.800 | 45.60 | 0 of 4 |
| engineered features | 0.860 | 36.05 | 2 of 4 |

Rule: win on pooled R², on MAE, **and** on ≥3 of 4 held-out experiments. None passes.
With four experiments a 0.01 R² difference is one experiment's worth of noise.

### Tomato — no search run

36 samples, 21 plants. A search that improves the number without a held-out plant set
to confirm it searches noise. The model's limitation is label meaning (flight context,
not stress or yield), which tuning cannot address.

### Radiation dose (OSD-782) and gravity (OSD-411) — exclusions retained

Both were re-examined in Phase 9 and re-measured in Phase 10 through the cross-study
work. Neither reaches a defensible baseline:

| Candidate | Balanced accuracy | Permutation p | Status |
| --- | --- | --- | --- |
| dose, 3-class (chance 0.333) | 0.361 | 0.2475 | excluded, artifact retained |
| gravity reorientation | 0.500 | 0.6931 | excluded, artifact retained |

A new finding strengthens the dose exclusion rather than overturning it: OSD-782's own
**binary** irradiated-vs-control contrast is also at chance (0.438, 95 % CI
0.300–0.591). A study whose simplest contrast does not reproduce cannot support a
finer three-level dose model, so the structural explanation and the measured one now
agree.

### Cross-study harmonisation — four attempts, none adopted

z-score, rank, quantile-map and pathway modules all collapse to one class. See
`PHASE10_CROSS_STUDY_VALIDATION.md` for why the correct conclusion is
*inconclusive about harmonisation* rather than *harmonisation failed*.

## What did not change

- **Registry: 8 models.** No additions, no removals, no status changes.
- **No artifact was overwritten.** Intervals and explanations were added as fields;
  the fitted parameters, checksums of the model itself, and every metric are
  untouched apart from the interval block.
- **No deep learning.** Every task here has 14–1,648 rows over 1–35 groups. A neural
  network is not justified by any of them, and none was attempted.

## Reproducing

```bash
python ml/training/phase10_conformal_study.py     # measures coverage
python ml/training/phase10_patch_uncertainty.py   # fits the adopted radii
python ml/training/phase10_explain_radiation.py   # explanations + stability
python ml/training/phase10_weak_model_audit.py    # the audit table
python ml/training/phase10_cross_study.py         # harmonisation comparison
```

Each is deterministic. The conformal study pins `n_jobs=1` because it was not, and a
test now re-runs a slice to prove stability.
