# ML Evaluation — Phase 6

> **Phase 31 status note (2026-11-09).** This document records the evidence as of the phase
> that produced it and is kept as a historical record. Three models described in it are no longer
> served: `mizuna-harvest-v1`, `mizuna-microbial-load-v1` and `et0-emulator-v1`. Their artifacts and
> evaluations are retained, and the reasons for withdrawal are in
> [`PHASE31_REMOVED_MODELS.md`](PHASE31_REMOVED_MODELS.md). Read the model catalogue at
> `/api/models` (or `python3 scripts/audit_models.py`) for what the application serves now.

Detailed evaluation evidence. Summary metrics live in `docs/ML_TRAINING_REPORT.md`.

---

## 1. `mizuna-harvest-v1` (NASA OSD-655)

**Verdict: `baseline-only` — retained, not promoted.**

| Evaluation | MAE (g) | R² | Outcome |
|---|---|---|---|
| Nested 4-fold `GroupKFold` ridge | 14.771 | −0.163 | worse than baseline |
| Group-mean baseline | 14.410 | −0.138 | reference |
| Whole-cohort holdout (flight↔ground) | see artifact `cohortHoldoutMetrics` | — | diagnostic only |

Why it fails:

* **Target heterogeneity** (H1). The two arms compute `Total (g)` from different
  measurements — flight includes crew consumption, ground includes broken leaves.
  Verified 8/8 and 6/6 exact reconstructions.
* **Covariate asymmetry.** Leaf counts exist in 6/12 ground rows and 0/12 flight
  rows.
* **Sample size.** 14 outcomes, 10 groups. Arms are statistically
  indistinguishable (45.30 g vs 43.73 g).

## 2. `tomato-flight-response-v1` (NASA OSD-767)

**Verdict: `experimental` — materially strengthened by Phase 6 validation.**

Reproduce: `python ml/analysis/validate_tomato.py` →
`docs/phase6/tomato_validation`

### Q1 — Batch confounding: **not present**

* All **36** libraries share a single lane suffix (`_L008`). Flight status is
  therefore **not** aliased to a sequencing lane.
* Spectrum is near-balanced: flight 8 blue / 10 red; ground 9 / 9.
* *Caveat recorded:* because there is only one lane, a lane-level batch effect
  could not be estimated even if one existed. The design is confounded **with
  respect to lane by construction** — it cannot be ruled out, only shown not to
  be separable by lane.
* Tissue is unbalanced (ground 12 leaf / 6 root; flight 9 / 9), which is why Q4
  matters.

### Q2 — Leakage-controlled reproduction

Gene selection (`SelectKBest`, k=64) and scaling are fitted **inside** each
training fold. Re-running with explicit per-fold assertions that no plant spans
train/test reproduces the score:

| Metric | Value |
|---|---|
| Macro-F1 | **0.916** |
| Accuracy | 0.917 |
| ROC-AUC | 0.985 |
| Confusion matrix | `[[18, 0], [3, 15]]` (ground, flight) |
| Macro-F1 baseline (prior) | 0.444 |

Fold-to-fold gene-set stability: mean **29.7 of 64** genes shared between fold
pairs (max 37). Moderate instability — the *decision* is stable, the specific gene
list is not, so the gene list must not be interpreted as a biomarker panel.

### Q3 — Label-permutation test: **signal is real**

200 permutations with labels shuffled at the **plant** level (preserving the
biological replicate structure):

| | Macro-F1 |
|---|---|
| Observed | **0.916** |
| Null mean | 0.466 |
| Null 95th percentile | 0.650 |
| Null max (of 200) | 0.750 |
| **Empirical p** | **0.005** |

The observed score exceeds every one of 200 permutations. This is strong
evidence the classifier detects genuine flight-associated molecular structure
rather than memorising noise.

### Q4 — Scope: not a tissue shortcut

| Tissue | n | Macro-F1 | ROC-AUC |
|---|---|---|---|
| Leaf only | 21 | 0.856 | 0.981 |
| Root only | 15 | 0.796 | 0.944 |

Both tissues classify independently, and tissue alone does not predict the label
(both arms contain both tissues). The signal is not a leaf/root artefact.

### Preserved scope restriction

The label is the **recorded experimental context**. It is **not** disease, health,
stress severity, biomass or yield, and is never described as such.

## 3. `lettuce-earth-growth-v1` (WUR/4TU — external, **not NASA**)

**Verdict: `experimental` — reproducible and the strongest-validated model.**

| Metric | Phase 6 | Recorded | Match |
|---|---|---|---|
| R² | 0.81198 | 0.81196 | ✅ |
| MAE (g) | 38.939 | 38.947 | ✅ |
| RMSE (g) | 71.732 | 71.737 | ✅ |
| Baseline R² | −0.054 | −0.054 | ✅ |

1,648 observations in **4 experiment groups**, validated by **nested
leave-one-experiment-out** CV — i.e. the model is tested on *entire experiments
it has never seen*. R² 0.81 under that regime is a genuinely strong result, and
materially stronger evidence than the mizuna model has.

**Domain restriction preserved:** Earth-only, four WUR experiments, lettuce.
It is **not** a lunar or Martian growth model, and it is **not NASA data**. It is
the only model here whose cross-experiment generalisation has been demonstrated.

## 4. `mizuna-microbial-load-v1` (NASA OSD-780)

Full details in `docs/ML_TRAINING_REPORT.md` §4. Key evaluation facts:

| Diagnostic | Result |
|---|---|
| Pooled grouped CV R² | 0.549 (baseline −0.007) |
| Random-forest challenger R² | 0.512 (no advantage) |
| Leave-one-experiment-out R² | **−0.555** (VEG-04A), **−0.580** (VEG-04B) |
| Conformal 90 % empirical coverage | **0.811** (under-nominal) |
| Evidence status | `experimental` |

Verdict rule encoded in the artifact: a model must beat the baseline, achieve
positive R² on **every** leave-one-experiment-out holdout, *and* have conformal
coverage within 5 points of nominal to reach `validated-exploratory`. This model
fails two of three, so it is `experimental`.

## 5. Cross-model summary

| Model | Beats baseline? | Cross-experiment? | Calibrated intervals? | Status |
|---|---|---|---|---|
| `mizuna-harvest-v1` | ❌ | ❌ | ❌ | baseline-only |
| `tomato-flight-response-v1` | ✅ (0.916 vs 0.444) | not testable (1 study) | ❌ | experimental |
| `lettuce-earth-growth-v1` | ✅ | ✅ (leave-one-experiment-out) | ❌ | experimental |
| `mizuna-microbial-load-v1` | ✅ | ❌ | ❌ | experimental |

**No model in this repository is `validated` for operational use.** None is
mission-ready, and none should be presented as a NASA-validated prediction.
