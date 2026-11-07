# Phase 10 — uncertainty and interval calibration

Phase 9 shipped intervals that said `empiricallyCalibrated: false` and reported their
own shortfall: 0.811 and 0.849 coverage against a nominal 0.90. That honesty was
correct and the defect was real. A stated 90 % interval covering 85 % of held-out
points is a bug wearing a caveat, and this phase treats it as a bug.

Evidence: `ml/evaluation/phase10_conformal.json`, decision:
`ml/evaluation/phase10_uncertainty_decision.json`.

## What was measured

Four methods, one shared leave-group-out protocol, so every method sees identical
held-out data. Nominal coverage 0.90 throughout.

| Model | split (Phase 9) | cv_plus | mondrian | group_level |
| --- | --- | --- | --- | --- |
| `mizuna-microbial-relative-load-v2` | 0.870 | 0.870 | 0.870 | **0.992** |
| `mizuna-microbial-load-v1` | 0.886 | 0.886 | 0.886 | **0.992** |
| `lettuce-earth-growth-v1` | 0.908 | **0.939** | — | 1.000 |
| `lettuce-earth-growth-v2` | 0.907 | **0.961** | — | 1.000 |

Method definitions:

- **split** — Phase 9's: fit on part of the training groups, calibrate on the rest.
- **cv_plus** — grouped cross-conformal: out-of-fold residuals from every training
  group, so no group is spent on calibration alone.
- **mondrian** — as cv_plus with the quantile taken within each campaign.
- **group_level** — cross-conformal whose exchangeability unit is the biological
  group, using each group's worst residual.

## The finding that mattered

For the two microbial models, **every row-level method lands between 0.862 and
0.886**, and adding methods does not move it. That is the signature of a broken
assumption rather than a bad quantile: rows there are tissues inside a pillow, so
row-level exchangeability does not hold, and a row-level interval was answering
"will this tissue be covered?" when the user's question is "will this pillow be
covered?"

Switching the unit to the group reaches 0.992. It costs width — 3.40 against 2.44
for the relative model, 7.26 against 4.91 for the absolute one — and that cost is
published rather than hidden, next to the row-level radius it replaced.

For lettuce the answer is different and simpler: **CV+ wins on both criteria at
once** (0.939/0.961 coverage, and narrower: 314 g against 446 g, 329 g against
475 g). Group-level is not used there because four well-separated experiments
inflate a group-maximal interval to 1023 g, which is useless as a per-plant figure.

## Promotion rule, fixed before the results

1. Adopt a method only if measured coverage is at least nominal − 0.02.
2. Among those, the narrowest interval wins.
3. If no method reaches nominal, report the achieved coverage and stop calling it a
   90 % interval.
4. For repeated measures, prefer group-level.
5. Never tune a radius on the groups used to score it.

Rule 5 is why the intervals were not simply inflated until they hit 0.90. Inflating
a radius to reach nominal on the evaluation groups is tuning on the test set;
group-level conformal reaches it for a principled reason.

## What the API now reports

Each served interval carries: the method, the radius, the nominal coverage, the
**measured** coverage, the calibration group count, the exchangeability unit, and a
caveat. The row-level radius is kept alongside for audit. Example:

```
kind: "90% group-level cross-conformal interval, measured held-out coverage 0.992"
nominalCoverage: 0.9
empiricalCoverage: 0.9919
empiricallyCalibrated: true
calibrationGroups: 35
exchangeabilityUnit: "biological group (worst residual within group)"
```

## A reproducibility bug found on the way

The first version of the study was **not deterministic**. Identical inputs returned
coverage 0.878 on one run and 0.886 on the next. The cause was
`RandomForestRegressor(n_jobs=-1)`: parallel tree building sums split gains in a
different order, a near-tie flips, and one prediction crosses the interval boundary.

A calibration figure that changes between identical runs is not a measurement, so the
study pins `n_jobs=1`, and `test_phase10_uncertainty.py` re-runs a slice of it to
prove the numbers are stable.

## Honest limits

Conformal coverage is marginal under exchangeability. Multiple tissues from one
pillow are not exchangeable with a new pillow, and **two campaigns are not a sample
of campaigns**. A third campaign's offset would still have to come from that
campaign's own baseline samples. The 0.992 figures are measured coverages over 35
pillows in two observed campaigns; they are not guarantees, and no document in this
repository describes them as such.

## No promotion

Recalibrating an interval is not a validation. Every model status is unchanged from
Phase 9 and both rejected candidates remain excluded; `test_phase10_uncertainty.py`
asserts exactly that.
