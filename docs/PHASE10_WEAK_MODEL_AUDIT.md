# Phase 10 — weak model audit

Every registered model was examined for *why* it is weak before anything was
retrained. The distinction that matters throughout: a model limited by its method
can be improved, and a model limited by its evidence cannot. Retuning the second
kind is how a project talks itself into believing a 14-row dataset supports a
predictor.

Measurements are in `ml/evaluation/phase10_weak_model_audit`.

## Summary

| Model | Held-out result | Limiting factor | Addressable? | Outcome |
| --- | --- | --- | --- | --- |
| `mizuna-harvest-v1` | R² −0.333 | 14 endpoints, 1 experiment | **no**, sample size | baseline-only status kept |
| `lettuce-earth-growth-v2` | R² 0.870 | 4 held-out experiments | **no**, group count | no v3; rule not met |
| `tomato-flight-response-v1` | acc 0.917 | 36 samples, 21 plants | **no**, sample size and label meaning | no new version |
| `mizuna-microbial-load-v1` | R² 0.549 pooled | cross-campaign offset | **no** | interval fixed instead (see below) |
| `mizuna-microbial-relative-load-v2` | R² 0.509 | interval coverage | **partly**, it was a real defect | recalibrated |
| `radiation-quality-osd46-v1` | bal 0.898 | 22 groups | not revisited — already validated | unchanged |
| `radiation-exposure-osd46-v1` | bal 0.910 | batch confound, published | not revisited | unchanged |

## Mizuna harvest — why a 14-row regression cannot be improved

Four learners on identical group-held-out folds:

| Learner | R² | MAE |
| --- | --- | --- |
| mean baseline | −0.138 | 14.41 |
| ridge | −0.376 | 16.29 |
| random forest | **−0.106** | 13.93 |
| gradient boosting | −0.995 | 18.00 |

The random forest is the best candidate and reaches R² −0.106. It is tempting to
call that an improvement over the −0.138 baseline, and that is exactly the trap: a
negative R² means the model is worse than predicting the mean, so "best of a bad
set" is not a result. The promotion bar was set to **R² > 0 and above the mean
baseline**, and no candidate clears it.

The dataset has 14 harvested endpoints from a single experiment, with the
irrigation feature recorded retrospectively. Synthetic augmentation is refused
outright: generating training rows from 14 real harvests would manufacture the
evidence the model is supposed to rest on.

**Decision: keep `baseline-only`.** That status is already on the model card, and
this audit confirms it rather than changing it.

## Lettuce — a v3 was tested and rejected

Two re-tuning attempts plus one feature-engineering attempt, all on the same
leave-one-experiment-out folds as the shipped model:

| Candidate | R² | MAE |
| --- | --- | --- |
| mean baseline | −0.054 | 125.83 |
| **v2, shipped** | **0.870** | **34.92** |
| v3, deeper trees (15 leaves, 300 estimators) | 0.868 | 35.33 |
| v3, shallower and slower (5 leaves, 0.03) | 0.800 | 45.60 |
| v3, engineered features (log days, air−root ΔT, PPFD×days) | 0.860 | 36.05 |

Pre-specified rule: beat the shipped model on **both** pooled R² and MAE, and win at
least three of the four held-out experiments. Nothing clears it. The best attempt is
0.0014 R² *worse*, and the engineered features lose too.

That is the honest outcome. With four experiments, a 0.01 R² difference is roughly
one experiment's worth of noise, which is why the rule was written in terms of
per-experiment wins rather than a pooled gain.

**Decision: no v3; `lettuce-earth-growth-v2` stays.** Its interval, which was
uncalibrated, was fixed separately (see `PHASE10_UNCERTAINTY.md`).

## Tomato — no search, on purpose

36 samples over 21 plants, accuracy 0.917, macro F1 0.916. No hyperparameter search
was run. With 21 groups, a search that improves the number without a held-out plant
set to confirm it is a search over noise. The model already separates recorded flight
context, which is the only thing its labels support; that limitation is not a tuning
problem.

## The microbial pair — the one weakness that was actually fixable

These two are the only models whose weakness was a **defect rather than a data
limit**: their stated 90 % intervals covered 81 % and 85 % of held-out groups.
Phase 9 disclosed this honestly; Phase 10 measured it and fixed it. Details in
`PHASE10_UNCERTAINTY.md`, but the summary belongs here because it is the model-audit
answer:

| Model | Split conformal (Phase 9) | Group-level conformal (adopted) |
| --- | --- | --- |
| `mizuna-microbial-relative-load-v2` | 0.870 coverage | **0.992** |
| `mizuna-microbial-load-v1` | 0.886 coverage | **0.992** |

The cross-campaign limitation of the absolute model is unchanged and remains stated:
it still does not transfer to an unseen campaign's absolute level.

## What was deliberately not done

- **No model was promoted.** Every status is byte-identical to Phase 9, and a test
  asserts it.
- **No synthetic data.** Nine of the weaknesses here are sample-size problems, and
  augmentation is the wrong answer to all nine.
- **No repeated tuning on the final held-out groups.** Each attempt is a single
  pre-specified configuration, scored once on folds that were fixed before the run.
