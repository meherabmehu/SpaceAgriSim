# Phase 29 — Harvest Model Generalisation Report

**Question.** The Phase 28 audit found the served lettuce model (`lettuce-earth-growth-v3`,
`trained-exploratory`) at 41.594 % MAPE on its independent holdout against an unchanged 30 %
acceptance criterion, and 41.68 % MAPE internally. This phase asks the only question that finding
leaves open: **is the failure specific to that model configuration, or is it the data?**

The answer, stated first: a better-fitting candidate was found, it was taken to the holdout once,
and it failed. The holdout MAPE is 39.28 %, 2.31 points better than v3 and 9.28 points worse than
the criterion. **Outcome B.** v3 stays in service as `trained-exploratory`, no v4 artefact exists, and
the registry is unchanged.

Everything in this report is reproducible from four committed artefacts:

| artefact | what it holds |
|---|---|
| `ml/training/phase29_harvest_diagnosis.py` → `ml/evaluation/phase29_harvest_diagnosis.json` | pipeline audit, error decomposition, design and domain findings |
| `ml/training/phase29_harvest_experiments.py` → `ml/evaluation/phase29_harvest_experiments.json` | six candidates, identical grouped folds, selection rule |
| `ml/training/phase29_harvest_final.py` → `ml/evaluation/phase29_harvest_final.json` | the single holdout scoring of the selected candidate |
| `ml/training/phase29_interval_audit.py` → `ml/evaluation/phase29_interval_audit.json` | the interval audit, reported separately in `PHASE29_PREDICTION_INTERVAL_REPORT.md` |

---

## 1. What was audited, and what the audit found

The brief named eleven suspects. Each was checked against the data rather than argued about.

| Suspect | Finding |
|---|---|
| Coverage of the light factor | PPFD takes three values (200 / 400 / 750 µmol/m²/s) and is the only factor with a clean within-experiment gradient. Daily light integral therefore takes 11.52 / 23.04 / 43.20 mol/m²/day. |
| PPFD × photoperiod → DLI | Correctly converted; photoperiod is constant at 16 h across all four experiments, so **DLI is a re-expression of PPFD in this dataset** and the model cannot learn a photoperiod effect from it. |
| Log target and inverse transform | The target is `log(fresh yield per m²)`; the inverse is unbiased at the median but the model is scored on the mean, and the log transform's upward skew on back-transformation is part of the residual bias. Not corrected by a smearing factor, because doing so would tune on the evaluation set. |
| Density handling | Per-plant mass × 25 plants/m². **The training data has one density**, so the model does not learn a density response; it divides by it. Density differences between studies are therefore a pure transfer error. |
| Outliers and missing values | `data/processed/lettuce_earth.csv` is clean: 1648 rows, 4 experiments, no missing covariates, no rows dropped in this phase. |
| Train/validation distribution | Air and root temperature are a 2×2 quadrant design **per experiment** (2 levels each within EXP1–EXP4), so temperature is largely a design label, not a continuous input the model can interpolate over. |
| Crop / cultivar / domain differences | One crop (lettuce), multiple cultivars pooled, all four experiments from one research group's protocol family. |
| Group/time split integrity | Leave-one-experiment-out, GroupKFold(4): each fold holds out one whole experiment (1216 train / 432 test, or 1296 / 352 for EXP3). Verified by re-running the fold construction; groups never cross. |
| Leakage | No holdout observation enters any fitting step; the PeerJ development rows are declared development-only (`countsAsValidation: false`) because they informed v3's feature choice. |
| Bias and residuals | See the per-experiment table below. |
| OOF-vs-holdout gap | 41.68 % internal MAPE vs 41.594 % holdout MAPE: the gap is **zero**, which is itself the finding. The model does not fail because it overfits; it fails because the population it learned does not transfer. |

### Per-experiment bias (out-of-fold, g fresh mass per m²)

| Experiment | rows | measured mean | predicted mean | mean bias | MAE |
|---|---|---|---|---|---|
| EXP1 | 432 | 3954.3 | 3319.1 | −635.2 | 1061.2 |
| EXP2 | 432 | 4548.5 | 4023.8 | −524.7 | 803.6 |
| EXP3 | 352 | 1640.9 | 2146.1 | +505.2 | 850.5 |
| EXP4 | 432 | 2551.8 | 2349.0 | −202.8 | 629.5 |

The bias switches sign across experiments and reaches ±0.5 kg/m² on means that span a factor of
2.8. Removing each experiment's own mean bias *increases* error to 956.2 g/m². That inversion is the
diagnosis: **the model knows roughly how a lettuce grows within an experiment and does not know how
to place a new experiment.** A negative `betweenExperimentShareOfMAE` (−0.1445) is the arithmetic
statement of that, and it is quoted here rather than the more flattering "error is mostly between
experiments" framing it superficially resembles.

### A domain declaration that is wrong

`ml/artifacts/lettuce-earth-growth-v3.json` declares `dailyLightIntegral.max = 34.5`. The observed
maximum in the training data is **43.2** (750 µmol/m²/s × 16 h). The other three features'
declarations match observation exactly. So the artifact issues domain warnings on inputs it was in
fact trained on — 43.2 is inside its data and outside its declared range.

This was **not** repaired. Changing a served artifact's metadata to widen its own domain is a
scientific decision with a promotion review attached, and it would not change any prediction. It is
recorded as a defect: `phase29_harvest_diagnosis.json → declaredDomainAudit.dailyLightIntegral`.

---

## 2. Six candidates, one protocol

The selection rule was written down before any candidate was scored, and every candidate saw
**identical folds, identical rows (1648), identical target and identical seed (42)**.

Selection rule: lowest leave-one-experiment-out MAE in g/m²; within 1 % of the best, prefer the
structurally safer extrapolation, in the order structured-saturating → monotone-gbm →
structured-ridge → gbm-log → huber-gbm → rate-gbm.

| Candidate | What it is | OOF MAE (g/m²) | OOF MAPE | OOF coverage | Interval width | PeerJ MAPE |
|---|---|---|---|---|---|---|
| **monotone-gbm** (selected) | `HistGradientBoostingRegressor` with monotone constraints on DLI and stage | **797.2** | 41.12 % | 0.8993 | ×5.27 | 74.48 % |
| huber-gbm | gradient boosting with a robust (Huber) loss | 817.7 | 41.4 % | 0.899 | ×5.31 | 70.8 % |
| rate-gbm | boosting on a growth-rate target | 822.7 | 40.1 % | 0.899 | ×4.54 | 74.4 % |
| gbm-log | the v3 configuration, re-fitted as the control | 835.5 | 41.7 % | 0.899 | ×5.23 | 71.6 % |
| structured-saturating | mechanistic saturating-light × cardinal-temperature model, 8 fitted parameters | 1226.3 | 46.1 % | — | ×5.08 | — |
| structured-ridge | regularised linear structure | 1778.0 | 83.7 % | — | ×6.49 | — |

Three things follow, and they are the useful result of the phase:

1. **The ceiling is close.** Best-to-control is a 4.6 % MAE improvement and 0.56 points of MAPE. No
   amount of further tuning closes a 9-point gap.
2. **The mechanistic candidates are worse, not better.** A saturating light response with cardinal
   temperatures and a genuine growth curve — the "scientifically right" model — fits this data far
   worse than boosting does. The data are noisier than the structure.
3. **MAPE and MAE disagree.** `rate-gbm` has the best MAPE (40.1 %) and a mid-table MAE. The
   selection rule used MAE because the acceptance criterion is on MAPE at the holdout and choosing a
   candidate by the metric that will judge it is exactly the selection-on-evaluation error this
   project forbids. This disagreement is recorded rather than resolved.

**Everything above was computed without the holdout.** `holdoutReadHere: false`.

---

## 3. The holdout, scored once

The holdout is the Touliatos et al. (2016) horizontal-hydroponic lettuce observation at 50
plants/m². It is one observation. It was scored once, by `phase29_harvest_final.py`.

| Quantity | Value |
|---|---|
| Measured | 138 ± 6 g/plant (n = 40) |
| Predicted | 192.2 g/plant |
| 90 % interval | 84.0 – 442.3 g/plant |
| Ratio | 1.393 |
| MAPE | **39.28 %** |
| Criterion (unchanged) | 30 % |
| Passed | **false** |
| v3 on the same observation | 41.594 % |
| Change vs v3 | **−2.31 points** |
| Interval covered the observation | yes |

Domain status of the holdout inputs: three of four lie outside the declared domain — DAT 35
(declared ≤ 29), air temperature 17.5 (declared 20–32), root temperature 17.5 (declared 20–32). This
is an **extrapolation test**, and its failure is evidence about transfer beyond the domain. It is not
by itself evidence that the model interpolates badly inside the domain — the internal per-experiment
results are.

Two honest notes on the comparison:

- The 2.31-point improvement is real but it is measured on a **single observation**. A one-point
  holdout cannot distinguish 39.28 from 41.59 with any confidence, and no interval on the difference
  is claimed.
- The interval covers the observation. `PHASE29_PREDICTION_INTERVAL_REPORT.md` explains at length why
  that is not evidence of 90 % coverage.

---

## 4. Strict holdout protection — what was and was not honoured

| Requirement | Status |
|---|---|
| No holdout data in training, HPO, feature or threshold selection | Honoured. `holdoutReadHere: false` in the experiments file; the PeerJ rows are flagged development-only and are not used for scoring. |
| No repeated inspection of the holdout | Honoured **in this phase**: one script, one scoring, one file. |
| Do not alter the 30 % criterion or redefine the metric | Honoured. `acceptanceCriterionPct: 30.0`, `notChanged: ["the 30 % acceptance criterion", "the holdout observations", "the evaluation metric"]`. |
| Preserve the Phase 28 result as historical baseline | Honoured. v3's 41.594 % is quoted from the artifact, not recomputed and overwritten. |
| Score only the final selected candidate | Honoured. Six candidates scored on folds; one scored on the holdout. |
| Never call a previously inspected holdout untouched | See below. |

**The limitation, stated plainly.** This holdout *has* been inspected in earlier phases: it was used
in Phase 19/28 as v3's independent check, and its value (138 g/plant) appears in committed artefacts
from those phases. The model in service was already selected partly in that light. In this phase the
numbers were not read before candidate scoring — the experiment script cannot see them — but the
broader project history means the holdout is **not an untouched final test set**, and
`holdoutProvenance.pristineClaim` says so in those words.

The consequence is asymmetric and worth naming: a *pass* on this holdout would have been weaker
evidence than a pass on a fresh one. A *failure* is not weakened by prior inspection at all, because
no amount of previous knowledge makes a model meet a criterion it misses.

---

## 5. Why no further improvement was attempted

The brief invited target transforms, density-aware or crop/stage-specific models, robust losses and
domain-shift correction. Five of those six candidates are exactly that list, and they were tried.

What was **not** done, deliberately:

- **A density-aware model.** Training density is a single constant (25 plants/m²). A "density-aware"
  model would have to learn a slope from a variable with zero variance, which means encoding an
  assumption as if it were a fitted effect.
- **Crop- or stage-specific models.** One crop, and stage is already a feature with a clean signal;
  splitting 1648 rows further would produce models with fewer rows than parameters in the structured
  cases.
- **Domain-shift correction (recalibration on the holdout).** That is fitting to the evaluation set.
- **Heavier HPO.** The selection rule's 1 % band and the monotone tie-break were written first;
  searching further against fold MAE would have been searching for a number, not a model.

The honest summary is that **the data are the binding constraint**: four experiments from one
protocol family, two of four features nearly constant within experiment, a single density and a
single photoperiod. Nothing in the modelling space fixes that.

---

## 6. Consequences carried forward

1. **No v4 artifact was registered.** `ml/artifacts/registry.json` still lists v1–v3 and
   `lettuce-earth-growth-v4.json` does not exist. A test asserts both.
2. **v3 remains `trained-exploratory`.** The harvest workflow continues to report
   `modelValidatedForForecasting: false` and shows "holdout failed · not a forecast" above the
   prediction.
3. **The criterion is 30 % and stays 30 %.** It is quoted from the same constant in every artefact.
4. **The next improvement is data, not code.** Named, in priority order: a second cultivar at the
   same density; a density series at fixed DLI; a photoperiod series at fixed DLI. Any one of those
   would give the model a variable it currently cannot learn, and none of them is obtainable from an
   API.

The result of this phase is therefore a negative one, and it is filed as one. A model that fails its
stated criterion and says so, with the failure reproducible from committed scripts, is worth more
than a model that passes a criterion chosen after the fact.
