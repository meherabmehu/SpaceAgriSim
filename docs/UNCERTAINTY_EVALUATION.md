# Prediction uncertainty evaluation

## Current interface semantics

| API/UI signal | Meaning |
| --- | --- |
| `interval.kind` contains `uncalibrated descriptive range` | Residual summary only; it is not a confidence or coverage guarantee. |
| `outOfDistribution: true` | One or more inputs fall outside the recorded domain or an explicitly unsupported combination was detected. |
| `predictionStatus: baseline-only` | Artifact must not be used as an operational predictor. |
| `predictionStatus: experimental` | Artifact has limited research validation and stated scope; it is not mission validated. |

## Group-aware calibration feasibility

- Mizuna has 10 groups but only 14 outcomes and does not beat its mean baseline. A nominal conformal interval would imply precision the predictor has not earned.
- Tomato has 21 plant groups, but target is recorded experimental context rather than a continuous operational crop outcome. Probability remains uncalibrated.
- Lettuce has four experiment groups. Leave-one-experiment-out evaluation is appropriate for error estimation, but reserving enough independent groups for tuning, training and calibration cannot support a stable 95% interval claim.

## Decision

No calibrated prediction interval was implemented. The frontend/API already communicates the descriptive-range label and out-of-domain warnings; Phase 3 retains that distinction rather than relabeling residual quantiles as calibrated uncertainty.
