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

### Radiation dose (OSD-782) — exclusion retained, reasoning corrected

Phase 9 excluded the dose model at balanced accuracy 0.361 (p = 0.2475) because the
dose label was described as confounded with processing order. The label is in fact
**valid** — 0 / 10 / 100 Gy, full factorial against four timepoints — and the
confound is narrower: each (dose, timepoint) cell is one sequencing batch.

Re-measured under three protocols on the same 36 libraries:

| Protocol | Balanced accuracy | p |
| --- | --- | --- |
| hold out one (dose, timepoint) cell | 0.111 | — |
| hold out one whole timepoint | 0.611 | 0.0005 |
| hold out one whole timepoint, ordinal (Spearman) | ρ = 0.197, monotone | 0.0155 |

The dose gradient **is** recoverable when the split matches the design, and the
cell-level protocol returns below chance — which is what a split measuring batch
membership looks like. Nothing is promoted: 36 libraries in one genotype and one
laboratory cannot support a dose predictor, and the Phase 9 exclusion stands on that
ground rather than on the label.

### Gravity (OSD-411) — exclusion retained, and a real study found

The OSD-411 exclusion is correct: 90° reorientation at 1 g is not a gravity level, and
every sample is at 1 g. What was wrong was the wider claim that no partial-gravity plant
study with processed expression exists. A metadata scan of all 231 usable studies found
**OSD-314**, which centrifuges Arabidopsis to 0.34 g in orbit.

The within-flight 0 g versus 0.34 g contrast reaches balanced accuracy **1.000**
(p = 0.0055) on held-out light treatments, corroborated by the study's own 8,478–13,504
differentially expressed genes. It is still **not served**: 17 libraries, one genotype,
one mission, two folds, no sequencing-run identifier in the deposit, and 0.34 g is
neither Moon nor Mars gravity. Detail: `PHASE10_DOSE_GRAVITY_RECOVERY.md`.

### Cross-study harmonisation — four attempts, none adopted

z-score, rank, quantile-map and pathway modules all collapse to one class. See
`PHASE10_CROSS_STUDY_VALIDATION.md` for why the correct conclusion is
*inconclusive about harmonisation* rather than *harmonisation failed*.

## What did not change

- **Registry: 8 models.** No additions, no removals, no status changes. The two
  radiation entries gained a `phase10.explanationAvailable` field describing a
  capability that already existed; no metric, interval radius or status moved.
- **Catalogue: 18 datasets.** OSD-314 was added with its limitations attached.
- **No artifact was overwritten.** Intervals and explanations were added as fields;
  the fitted parameters, checksums of the model itself, and every metric are
  untouched apart from the interval block.
- **No deep learning.** Every task here has 14–1,648 rows over 1–35 groups. A neural
  network is not justified by any of them, and none was attempted.

## Reproducing

```bash
python scripts/acquire_phase10_osd314.py          # verified OSD-314 acquisition
python ml/training/phase10_conformal_study.py     # measures coverage
python ml/training/phase10_patch_uncertainty.py   # fits the adopted radii
python ml/training/phase10_explain_radiation.py   # explanations + stability
python ml/training/phase10_weak_model_audit.py    # the audit table
python ml/training/phase10_cross_study.py         # harmonisation comparison
python ml/training/phase10_dose_recovery.py       # dose, three protocols
python ml/training/phase10_partial_gravity_osd314.py  # graded-gravity analysis
python ml/training/phase10_gravity_recovery.py    # metadata scan over 231 studies
python ml/training/phase10_registry_api_audit.py  # registry vs artifacts
```

Each is deterministic. The conformal study pins `n_jobs=1` because it was not, and a
test now re-runs a slice to prove stability.
