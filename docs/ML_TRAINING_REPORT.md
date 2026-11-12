# ML Training Report — Phase 6

All numbers below were produced in this Phase 6 run and are reproducible.

**Verified training environment:** Python 3.13.16 · numpy 2.3.5 · pandas 2.2.3 · scikit-learn 1.6.1

---

## 1. Model inventory after Phase 6

| Model | Source | Task | n | Groups | Evidence status |
|---|---|---|---|---|---|
| `mizuna-harvest-v1` | NASA OSD-655 | fresh harvest mass regression | 14 | 10 | **baseline-only** |
| `tomato-flight-response-v1` | NASA OSD-767 | flight/ground molecular context | 36 | 21 | **experimental** |
| `lettuce-earth-growth-v1` | WUR/4TU (**not NASA**) | Earth lettuce shoot mass | 1,648 | 4 | **experimental** |
| **`mizuna-microbial-load-v1`** | **NASA OSD-780** | **edible-leaf microbial load** | **123** | **35** | **experimental** |

Exactly one new model was trained. It is the only one the data could support.

## 2. Reproducibility finding: library-version sensitivity

The pre-existing artifacts were committed under a different environment
(Python 3.12.10 · numpy 2.5.4 · pandas 3.1.1 · scikit-learn 1.9.1). Retraining the
**same code on the same data** in the Phase 6 environment gives materially
different metrics:

| Model | Recorded (py3.12/sklearn1.9) | Phase 6 (py3.13/sklearn1.6) | Δ |
|---|---|---|---|
| `mizuna-harvest-v1` | MAE 14.76, R² **−0.153** | MAE 15.50, R² **−0.333** | MAE +5.0 % |
| `tomato-flight-response-v1` | macro-F1 0.805, AUC 0.941 | macro-F1 0.916, AUC 0.975 | F1 +11.1 pts |
| `lettuce-earth-growth-v1` | R² 0.81196, MAE 38.947 | R² 0.81198, MAE 38.939 | negligible |

**Within one environment, training is bit-for-bit deterministic** — verified by
running the pipeline twice and comparing artifacts (`metrics` identical, `linear`
arrays identical).

Interpretation, stated carefully:

* The **conclusions are robust**: the mizuna model does not beat its baseline
  under *either* environment (R² negative in both), and the tomato classifier is
  strong under both. Only the point estimates move.
* Random-forest and group-split numerics are the sensitive parts. The lettuce
  model (random forest) barely moved; the mizuna ridge model moved more, because
  with 14 points the fold-mean baseline and the ridge shrinkage interact with
  small numerical differences.
* **Recommendation:** pin `scikit-learn` exactly for future artifact
  regeneration, and treat any reported metric as ±environment. This is now
  recorded in the progress ledger as an open engineering action.

## 3. `mizuna-harvest-v1` — re-evaluated, retained as baseline-only

Reproduce: `python ml/analysis/reevaluate_harvest.py` →
`docs/phase6/mizuna_reevaluation`

| | MAE (g) | RMSE (g) | R² |
|---|---|---|---|
| Nested 4-fold grouped ridge | 14.771 | 17.610 | −0.163 |
| Group-mean baseline | **14.410** | **17.420** | **−0.138** |

**The model does not beat the mean baseline.** It is retained as `baseline-only`.

Three independent reasons this cannot be promoted:

1. **The target is two different measurements.** Verified arithmetically: flight
   `Total (g)` = `mean(4 MMD replicate weighings) + crew consumption` (8/8 rows
   exact); ground `Total (g)` = `harvested leaf mass + broken leaves` (6/6 rows
   exact). The flight figure embeds *what the crew ate*. Pooling them makes the
   `flight` feature partly a protocol dummy. See `docs/DATA_HARMONIZATION.md` H1.
2. **Only one arm has leaf counts.** 0/12 flight rows vs 6/12 ground rows record
   `# Leaves, Total`. The richest biological covariate exists in one arm only.
3. **n = 14 in 10 groups.** Arms: flight n=8 (mean 45.30 g), ground n=6
   (mean 43.73 g). Means are nearly equal, and the ground arm alone (n=6,
   6 pillows) cannot support a grouped 4-fold fit at all.

Recommendation recorded in the artifact: keep `baseline-only`; present the
**measured** 14 values rather than a model prediction.

## 4. `mizuna-microbial-load-v1` — the new model

Reproduce: `python ml/training/train_microbial.py`

**Source:** NASA OSD-780 (LSDS-128 VEG-04A/B plate counts) — newly acquired in
Phase 6, absent from the prior inventory.

**Target:** `log10(1 + CFU per gram fresh leaf weight)` — a **measured** culturable
aerobic plate count. **Not** biomass, not yield, not shelf life.

**Inputs (all measured):** flight/ground arm, red/blue spectrum, VEG-04A/04B
campaign, sanitised/unsanitised sampling state, assay subsample fresh weight,
harvest index.

**Design:** 123 leaf samples across **35 biological units** (experiment × arm ×
pillow). 4-fold `GroupKFold` on the pillow; nested 3-fold grouped alpha search;
gene/sample leakage structurally impossible.

### 4.1 Results

| Model | MAE (log₁₀ CFU/g) | RMSE | R² |
|---|---|---|---|
| **Ridge (selected)** | **1.087** | **1.404** | **0.549** |
| Random forest challenger | 1.136 | 1.461 | 0.512 |
| Group-mean baseline | 1.718 | 2.098 | −0.007 |

Within pooled data the ridge model **beats the baseline decisively**
(R² 0.549 vs −0.007), and the flexible learner does no better — evidence the
signal is captured by a simple regularised model, not fitted noise.

### 4.2 The decisive limitation: it does not transfer between campaigns

Leave-one-**experiment**-out (train on one VEG-04 campaign, test on the other):

| Held out | n | MAE | R² |
|---|---|---|---|
| VEG-04A | 20 | 1.777 | **−0.555** |
| VEG-04B | 103 | 2.365 | **−0.580** |

Both holdouts are negative. The model learns **campaign-specific** structure, not
a transferable rule. It is therefore reported as **`experimental`**, with the
artifact's `recommendedUse` explicitly restricting it to descriptive
in-campaign stratification.

### 4.3 Measured biological contrast (the real finding)

Rather than a fabricated predictive claim, the model documents a reproducible
**measured** effect:

| Campaign | Arm | n | mean log₁₀ CFU/g | difference |
|---|---|---|---|---|
| VEG-04A | flight | 5 | 5.617 | **+3.063** (≈1,155×) |
| VEG-04A | ground | 15 | 2.554 | — |
| VEG-04B | flight | 31 | 3.615 | **+2.639** (≈436×) |
| VEG-04B | ground | 72 | 0.975 | — |

And crucially the effect is **tissue-specific**: root-zone samples show no
flight/ground gap (root 7.30 vs 7.42; soil 7.08 vs 6.92; wick 8.16 vs 7.60
log₁₀ CFU/g). A leaf-surface effect with no root-zone effect is consistent with
an aerial/cabin or handling exposure route — but OSD-780 cannot separate cabin
environment from payload handling from sampling protocol, so **causality is not
established and is not claimed.**

## 5. Models correctly *not* trained

The Phase 6 brief lists eight candidate tasks. Only one was supportable.

| Task | Status | Reason |
|---|---|---|
| A. Crop biomass regression | **Blocked (data)** | No biomass table beyond OSD-655's 14 endpoints exists in 25 verified studies |
| B. Harvest yield regression | **Blocked (data)** | Same; OSD-655 target mixes two formulas |
| C. Water-demand prediction | **Blocked (data)** | No transpiration/uptake measurement. Irrigation *supplied* is a management input |
| D. Photosynthesis / gas exchange | **Blocked (data)** | No CO₂-assimilation or O₂-evolution table anywhere in the corpus |
| E. Light-response modelling | **Blocked (data)** | Light is recorded as red/blue category, never measured PPFD × photoperiod |
| F. Gravity-response modelling | **Blocked (data)** | Flight/ground is a classification label; converting it to a continuous lunar/Martian response would be fabrication |
| G. Radiation-response modelling | **Blocked (data)** | No plant-specific dose–response dataset; ISS dosimetry is not plant-paired |
| H. Plant stress classification | **Blocked (data)** | No genuine labelled stress/disease outcomes exist |
| **I. Microbial food-safety load** | **✅ Trained** | OSD-780 provides 123 measured leaf samples with real CFU/g labels |

A mechanistic estimator was preferred to an unreliable model in every blocked
case, per the brief's own instruction.

## 6. Artifact integrity

Artifacts are portable JSON (never pickle), each registered with a SHA-256 in
`ml/artifacts/registry` and verified at load time by
`backend/app/research.py::load_model`. A checksum mismatch raises rather than
silently serving a different model.
