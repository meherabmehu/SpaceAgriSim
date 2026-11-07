# Phase 2 model reassessment

## Reproducibility and leakage review

The stored training code was reviewed against its data tables and evaluation artifacts. No artifact was replaced in this phase: the evidence does not justify claiming a more capable model.

| Model | Observed training design | Reassessment | Decision |
| --- | --- | --- | --- |
| `mizuna-harvest-v1` | 14 OSD-655 harvested endpoints; nested GroupKFold; Ridge alpha selected in inner folds | OOF MAE 14.76 g is worse than mean baseline MAE 14.19 g; R2 -0.153. Irrigation is a retrospective feature. | Downgrade registry-facing prediction status to **baseline-only**; retain solely as a reproducible, limited research demonstration. |
| `tomato-flight-response-v1` | 36 specimens / 21 plants; nested stratified group CV; within-fold variance selection, feature selection and scaling | The procedure prevents plant identity leakage. It still contains one experiment and flight/ground batch confounding is possible. | Keep **experimental** molecular-context status. No health, stress or yield interpretation. |
| `lettuce-earth-growth-v1` | 1,648 WUR observations / 4 experiments; nested leave-one-experiment-out validation | Whole-experiment outer folds prevent row-level leakage. Four groups cannot establish independent-study generalization. | Keep **experimental**, Earth-only status. Do not replace its random forest without a new held-out source. |

## Uncertainty conclusion

All three artifacts currently expose residual-derived descriptive ranges, not calibrated confidence intervals. Group-aware conformal calibration needs enough independent groups to reserve a valid calibration partition. Four lettuce experiments and ten mizuna groups do not support a stable, general 95% interval claim; the API therefore continues to label the range uncalibrated.

## Registry changes

The API model registry now exposes input domains, registered artifact SHA-256, baseline-comparison outcome and one of: `baseline-only`, `experimental`, or `insufficient-evidence`. It deliberately does not expose executable tree/coefficient arrays.
