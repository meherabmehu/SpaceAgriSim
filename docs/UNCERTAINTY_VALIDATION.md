# Prediction Uncertainty Validation — Phase 6

The rule applied throughout: **an interval is only called a confidence interval
if its empirical coverage has been measured and matches nominal.** Otherwise it
is labelled an *uncalibrated descriptive range*.

---

## 1. Methods considered

| Method | Applicable here? | Why |
|---|---|---|
| Group-aware split conformal | Yes — implemented | Distribution-free, needs only exchangeable residuals, and honours the biological replicate structure |
| Bootstrap intervals | Limited | With n=14 in 10 groups, bootstrap resampling of groups is unstable and would overstate precision |
| Quantile regression | No | Needs far more samples per group than exist (max 123 pooled, 35 groups) |
| Ensemble uncertainty | Diagnostic only | Used as a model-comparison challenger (random forest vs ridge), not as an interval |
| Experiment-level error analysis | **Yes — primary** | The only honest uncertainty statement available at these sample sizes |

## 2. Results by model

### 2.1 `mizuna-harvest-v1`

| Property | Value |
|---|---|
| Method | Group-aware split conformal, 90 % nominal |
| Radius | 28.24 g |
| Groups evaluated | 10 |
| **Empirical group coverage** | **0.800** |
| Calibrated? | **No** |

With 14 points in 10 groups, coverage cannot be estimated reliably and falls
below nominal. Reported as an **uncalibrated descriptive range**, and the model is
`baseline-only` regardless.

### 2.2 `tomato-flight-response-v1`

| Property | Value |
|---|---|
| Reported probability | Probability of the recorded flight class |
| Calibrated? | **No** — no probability calibration was performed or claimed |
| Interval type | None. The artifact states the probability is *uncalibrated*, not a confidence |

The permutation test (`p = 0.005`, §Q3 of `docs/ML_EVALUATION.md`) is the
evidence supporting the *decision*, which is a different and valid claim from an
interval on a probability.

### 2.3 `lettuce-earth-growth-v1`

| Property | Value |
|---|---|
| Interval method | None published |
| Why | Leave-one-experiment-out already reports the honest generalisation error directly (R² 0.812, MAE 38.94 g) |

No interval is invented for it; the leave-one-experiment-out error is itself the
uncertainty statement.

### 2.4 `mizuna-microbial-load-v1`

| Property | Value |
|---|---|
| Method | Group-aware split conformal, 90 % nominal |
| Calibration groups | 17 (pillow sets disjoint from evaluation) |
| Evaluation groups | 18 |
| Radius | 2.346 log₁₀ CFU/g |
| **Empirical coverage** | **0.811** |
| Nominal | 0.900 |
| Calibrated? | **No** |

The artifact's `interval.kind` literally reads
`"UNCALIBRATED descriptive residual range ... (empirical coverage below nominal;
not a confidence interval)"`, and `empiricallyCalibrated: false` is set by code,
not by hand.

## 3. What was measured vs what was assumed

| Statement | Basis |
|---|---|
| "Conformal 90 % intervals cover 81 % of held-out groups (mizuna, microbial)" | **Measured** |
| "Tomato classifier macro-F1 0.916 exceeds all of 200 plant-level permutations" | **Measured** |
| "Lettuce model achieves R² 0.812 on unseen experiments" | **Measured** |
| "Microbial model does not transfer across campaigns (R² < 0)" | **Measured** |
| Confidence intervals on any model | **Not produced** — no model supports a calibrated interval |
| Prediction intervals for lunar/Martian scenarios | **Not produced** — no validation data of any kind exists for those environments |

## 4. Out-of-domain handling

Preserved from earlier phases and re-verified:

* Every model artifact carries a `domain` block with observed min/max per feature.
* `backend/app/research.py::predict_values` appends an explicit
  `"<feature> outside observed training range [min, max]"` warning for any input
  beyond that domain, returned as `outOfDistribution: true`.
* `backend/tests/test_research.py` asserts the flag fires (e.g. `waterSuppliedL`
  set to 8 L against a 1.245–2.01 L training domain).
* The new microbial model publishes its own domain (including `freshWeightG`
  5.0–? g) so its 5–9 g assay-subsample range is enforced rather than assumed.

## 5. Disclosure rules encoded in artifacts

Each model artifact carries an `evidenceStatus`, an `evidenceBasis` block listing
which tests passed, and a `recommendedUse` string. These are generated from the
measured metrics by code, so a future retrain that *does* achieve transfer would
promote itself, and one that regresses cannot silently keep a confident label.

The status vocabulary is:

| Status | Meaning |
|---|---|
| `validated` | beats baseline, positive cross-experiment R², calibrated intervals. **Nothing in this repository qualifies.** |
| `validated-exploratory` | all three conditions met at exploratory scope. **Nothing qualifies.** |
| `experimental` | beats baseline inside pooled data; transfer and/or calibration unproven |
| `baseline-only` | fails to beat a trivial baseline; present the measurements instead |
| `insufficient-evidence` | not trained, or trained and rejected |
