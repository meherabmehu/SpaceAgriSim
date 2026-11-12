# Phase 12 — simulator and model validation position

Phase 12 adds an input-validation and interpretation layer. It adds **no new physics, no new
accuracy claim, and no new training data**. This document records what validates what, so
the platform cannot drift into implying more than Phase 9–11 established.

---

## 1. Two different things are being served, and they are not interchangeable

| Layer | What it is | What validates it |
| --- | --- | --- |
| **Habitat simulator** (`/simulate`, `/compare`, `/optimize`) | Deterministic scenario model with explicit assumptions and factor multipliers | Phase 7 calibration against documented literature coefficients; every response carries the assumption list and the coverage table |
| **ML models** (8 registry models) | Trained artifacts served through `/predict/*` and `/workflow/run` | Phase 9–11 out-of-fold evaluation, permutation tests, and biological-group splits |

The simulator does **not** consume any ML model output, and no ML model calibrates the
simulator's crop coefficients. A simulator number is a scenario; a model output is an
estimate inside a documented domain. Both say so in their own responses.

---

## 2. What Phase 12 validates (the workflow layer)

| Check | Kind of evidence | Result |
| --- | --- | --- |
| Feature schema exactness | Structural | Missing and unexpected features both rejected; nothing imputed |
| Finiteness | Structural | `NaN`/`inf` rejected |
| Physical plausibility | Domain-independent limits | `airTemperature` 900 °C → 422, `ppfd` −50 → 422 |
| Training-domain position | The model's own recorded range | Reported as `insideTrainingDomain`; outside it the run proceeds **labelled** as extrapolation |
| Category gate | Scientific classification | Category 6 → 410, never a number |
| Input family | Registry-derived feature map | Environmental inputs cannot drive a molecular classifier, in either direction |
| Reproducibility | Pinned artifact SHA-256 | Same input + same artifact → same output, asserted in tests |
| Export fidelity | Byte-level | The exported `prediction` parses to exactly the float the API returned |

These are **transparency and safety** checks. None of them is an accuracy claim.

---

## 3. What Phase 12 deliberately does not claim

### 3.1 No validated out-of-distribution threshold

Phase 11 tested two novelty scores against three controls:

| Score | Controls passed |
| --- | --- |
| `mahalanobis_pca` | 1 of 3 |
| `nearest_neighbour_correlation` | 2 of 3 |

`thresholdValidated` is `false` in `ml/evaluation/phase11_ood_uncertainty`, and the
verdict is `ood-score-not-validated-by-any-available-control`. Phase 12 therefore ships
**schema-based domain checks** and a transparent training-domain report. `/workflow/run`
never returns a novelty score, never calls a distance an out-of-distribution probability, and
the docs never say "OOD detection".

### 3.2 No calibrated probabilities

All eight models report `calibrated: false`. Class probabilities are the evaluator's softmax
output and the workflow says so in the response. Interval coverage is reported as
**measured on held-out biological groups**, distinct from the nominal 0.90:

| Model | Nominal | Measured | Width |
| --- | --- | --- | --- |
| `lettuce-earth-growth-v1` | 0.90 | 0.9393 | 313.71 |
| `lettuce-earth-growth-v2` | 0.90 | 0.9606 | — |
| `mizuna-microbial-load-v1` | 0.90 | 0.9919 | — |
| `mizuna-microbial-relative-load-v2` | 0.90 | 0.9919 | — |

The pre-specified Phase 10 decision rule still governs: if no method reaches nominal, the
achieved coverage is reported explicitly and the interval must not be described as a 90 %
interval.

### 3.3 No gravity, radiation or dose generalization beyond what was measured

* OSD-346 partial gravity did **not** replicate (nested batch/run confound; signal does not
  survive removing the flight run).
* OSD-782 dose labels are valid but the batch confound blocks dose prediction: within-timepoint
  ρ 0.224, p 0.158, sign flips at 3 h. Not served.
* Radiation models are nested-selection re-measured in Phase 11 with no promotion
  (0.8611 / 0.9097 with selection inside the folds; delta versus shipped is not positive).
* The microbial pooled flight effect is +2.820 (95 % CI +2.327 to +3.314) with a prediction
  interval of −0.377 to +6.018 for a **new** campaign. The interval includes zero on purpose.

### 3.4 No crop-yield, lunar or Mars prediction

No model predicts yield, biomass, survival or productivity on the Moon or Mars. The only
served environmental model is Earth-only Batavia lettuce (4 features, WUR data,
`sourceType: external scientific data (not NASA)`), and its limitations say it is not
calibrated for partial gravity or radiation. Molecular classifiers identify the applied
experimental condition; they are not gravity or radiation effect sizes.

---

## 4. How the position is enforced, not just documented

| Statement | Enforced by |
| --- | --- |
| Retired models cannot answer | `validate_input` raises `retired-model`; the route maps it to 410; two tests assert it |
| Molecular models need their gene schema | Family inference in `workflow._infer_family`; tests in both directions |
| Impossible values are rejected | `PHYSICAL_LIMITS`; tests for 900 °C and negative PPFD |
| Nothing is presented as calibrated | `calibrated: false` asserted for all 8 catalogue rows in tests |
| No OOD threshold is presented | No endpoint returns a novelty score; the only domain statement is `insideTrainingDomain` from the recorded range |
| Exports cannot disagree with the API | CSV/JSON/MD export reads the stored payload; tests compare against the API float |

The gate is `backend/tests/test_phase12_workflow.py` (32 tests),
`test_phase12_assistant.py` (38), `test_phase12_explorer.py` (17) plus the whole Phase 9–11
suite, which is unchanged and still passing.
