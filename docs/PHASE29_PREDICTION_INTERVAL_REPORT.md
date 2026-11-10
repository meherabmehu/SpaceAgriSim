# Phase 29 — Prediction Interval Report

**Question.** The harvest workflow serves a 90 % interval beside every prediction and prints
"0.8993 out-of-fold coverage". This report asks whether that number means what a reader would take it
to mean, and it separates two things the platform had been discussing in one breath: **point accuracy**
and **interval coverage**.

Short answer: no. The served coverage figure is a *descriptive* statistic about held-out rows drawn
from experiments the calibration already contained. It is not a guarantee of coverage on a new site,
and this phase found direct evidence that the guarantee would fail.

Artefacts: `ml/training/phase29_interval_audit.py`, `ml/evaluation/phase29_interval_audit.json`.
Nothing in the served model was changed by this audit.

---

## 1. What is actually served

| Property | Value |
|---|---|
| Method | conformal residual quantiles on the log target (5 % / 95 %) |
| Residual quantiles | −0.8205 / +0.8335 (log scale) |
| Multiplicative width | ×5.23 |
| Reported out-of-fold coverage | 0.8993 |
| Reproduced out-of-fold coverage | 0.8993 (recomputed from the 1648 committed residuals) |

The reproduction is exact. Whatever else is wrong, the artifact is not misquoting its own
computation.

What ×5.23 means in practice, at 24 °C and 400 µmol/m²/s:

| Stage | Point estimate (g/plant) | 90 % interval (g/plant) |
|---|---|---|
| 8 DAT | 17.7 | 7.8 – 40.8 |
| 18 DAT | 135.9 | 59.8 – 312.9 |
| 28 DAT | 491.4 | 216.3 – 1131.3 |

An interval that spans a factor of 5.2 is a truthful statement of how little the model knows, and it
is not a useful planning number at the individual-plant level. Both halves of that sentence matter.

---

## 2. Calibration method and its assumption

The method is **cross-conformal**: residuals come from the four leave-one-experiment-out folds and
are pooled into single 5 % and 95 % quantiles.

Conformal prediction rests on **exchangeability** — the calibration points and the query point must be
draws from the same distribution. The platform's own error decomposition already shows why that is
doubtful here: per-experiment bias runs from −635 to +505 g/m² and measured means span 1.6 to 4.5
kg/m². The exchangeability unit used in calibration is *the individual plant row, pooled across
experiments*, which is one level too fine if experiments differ systematically.

---

## 3. The test that was run: split-conformal on halves

If residuals are exchangeable, calibrating on half the data and measuring coverage on the other half
should reproduce a similar width and similar coverage. If they are not, the halves disagree.

| Quantity | Served (cross-conformal) | Split-conformal |
|---|---|---|
| Residual quantiles (log) | −0.8205 / +0.8335 | −0.4257 / +0.3836 |
| Multiplicative width | ×5.23 | **×2.25** |
| Width ratio vs served | 1.00 | **0.429** |
| Coverage on the other half | — | 0.8431 and 0.9560 |

The split-conformal interval is **less than half as wide** as the served one, and its coverage on the
held-out half is a plateau at 0.84–0.96 rather than a steady 0.90. A width ratio of 0.429 does not
mean the narrower interval is better; it means **the residual distribution depends on which
experiments happen to land in the calibration half**, which is precisely a failure of exchangeability.
The reported 0.8993 therefore carries much less information than its precision suggests.

---

## 4. Coverage by group — where the pooled number hides failures

### By experiment

| Experiment | rows | coverage | mean measured (g/plant) | mean interval width (g/plant) |
|---|---|---|---|---|
| EXP1 | 432 | 0.8866 | 158.2 | 247.2 |
| EXP2 | 432 | 0.9884 | 181.9 | 299.7 |
| **EXP3** | 352 | **0.6960** | 65.6 | 159.9 |
| EXP4 | 432 | 0.9884 | 102.1 | 175.0 |

EXP3 — the experiment with the smallest plants — is covered 69.6 % of the time at a nominal 90 %. The
pooled 0.8993 is an average of 0.70 and 0.99, and the average is the least useful of the four numbers.
**This is the single most important finding in this report**: coverage is a per-population property,
and the platform was reporting it as if it were a property of the model.

### By growth stage

| Stage (DAT) | rows | coverage | mean measured (g/plant) | mean width (g/plant) |
|---|---|---|---|---|
| **1–5** | 192 | **0.6667** | 1.9 | 2.9 |
| 5–10 | 336 | 0.9226 | 11.5 | 20.7 |
| 10–15 | 240 | 0.8125 | 40.7 | 79.5 |
| 15–20 | 384 | 0.9740 | 111.4 | 209.0 |
| 20–25 | 384 | 0.9297 | 182.9 | 338.3 |
| 25–30 | 352 | 0.9460 | 341.4 | 574.0 |

Seedling stage coverage is 66.7 %. Two of six stages are above 0.94 while two are below 0.82 — the
interval is simultaneously too wide late and too narrow early, and a single multiplicative width
cannot represent that. Any user asking about seedlings is being misled by a number describing mature
plants.

---

## 5. Holdout behaviour, correctly stated

The holdout observation (138 ± 6 g/plant measured, interval 84.0 – 442.3 g/plant) **is covered**.

That fact is recorded and **cannot be used to claim the interval is reliable**. It is one
observation. One observation covering a 90 % interval is consistent with true coverage anywhere
between 10 % and 100 %, and `holdoutCheck.reading` in the artefact says exactly this:

> One observation covering the interval is not evidence of 90 % coverage. It is recorded because it
> happened, and it cannot be used to claim the interval is reliable on new environments.

The audit's conclusion block is equally explicit:

- `outOfFoldCoverageIsDescriptive: true`
- `canClaimIndependentCoverage: **false**`
- **Why:** the calibration residuals come from the same four experiments the coverage was measured
  on, and the intervals are pooled across experiments whose yields differ by nearly a factor of
  three.
- **What would be needed:** independent experiments with all four model inputs, used only for
  calibration scoring. None exists in this repository.

---

## 6. What changed in the product as a result

No number was changed and no interval was refitted — which is the point: the audit found the served
number is weaker than it looked, and weakening a *claim* is the honest response, not narrowing a
*number*.

Three things were made visible where a user meets them:

1. The holdout interval check is labelled as one observation, in the artefact that stores it.
2. The coverage claim is not repeated as a guarantee anywhere in the product; the harvest panel shows
   the interval with the domain warnings and the failed-holdout banner above it.
3. This report and the audit JSON are the reference for anyone who wants to quote coverage. Quoting
   `0.8993` without the EXP3 (0.696) and 1–5 DAT (0.667) numbers is now a documented misreading, not
   an oversight.

---

## 7. Consequences for the promotion decision

The interval audit does not change the Outcome B verdict, because the verdict is on point accuracy
against a pre-registered criterion. It changes something adjacent and just as important: **even if a
future candidate met the 30 % MAPE criterion, this interval would not be ready to ship as a planning
uncertainty**, because its calibration population is a single protocol family. The next candidate's
review should require independent calibration data, not merely a passing point estimate.

The 30 % criterion remains 30 %.
