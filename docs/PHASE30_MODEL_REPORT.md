# Phase 30 — Model evaluation report

Two models were fitted in Phase 30 and **neither is served**. Both missed the unchanged 30 %
independent-error criterion, both were evaluated with a sealed holdout chosen before scoring, and
both are retained as evidence rather than deleted.

Artifacts:

- `ml/evaluation/phase30_harvest_crossstudy.json` — cross-study lettuce harvest model
- `ml/evaluation/phase30_cea_wheat_response.json` — controlled-environment wheat response surface

Scripts:

- `ml/training/phase30_harvest_crossstudy.py`
- `ml/training/phase30_cea_wheat_response.py`

---

## 1. Harvest model across independent studies (lettuce)

### Why a new evaluation

The Phase 28 workflow served `lettuce-earth-growth-v3` with a holdout MAPE of 41.59 %, already above
the 30 % criterion, and the Phase 29 diagnosis showed the declared DLI domain was hardcoded and did
not match the observed data. The remaining question was not "can the model be tuned" but "does any
model in this class generalise across published studies". The Phase 30 compilation of 53 treatment
means from 40 studies makes that question answerable.

### Protocol (fixed before scoring)

| Element | Value |
|---|---|
| Unit of independence | study (one publication) |
| Rows | 53 raw → 47 usable (5 missing a core feature, 1 zero dry mass) |
| Development pool | 32 studies, 39 treatments |
| Validation | leave-one-study-out over the development pool |
| Holdout | 8 studies sealed by SHA-256 of the study key, one scoring pass |
| Random split | not used — sibling treatments of one study would leak across the split |
| Target | log10(shoot dry mass g per plant) |
| Features | CO₂, photoperiod, PPFD, DLI, planting density, plant age |
| Candidates | mean baseline, light-limited structure, ridge-log, GBM-log |
| Selection rule | lowest out-of-fold MAE; within 2 % prefer the structurally simpler candidate |
| Criterion | **30 % MAPE, unchanged** |

### Out-of-fold results (39 records, 32 studies)

| Candidate | MAE (g/plant) | MAPE | R² |
|---|---|---|---|
| **baseline-mean (selected)** | **1.9834** | 211.42 % | −0.2395 |
| light-limited structure | 1.9723 | 223.58 % | −0.2452 |
| ridge-log | 2.2763 | 98.74 % | −2.0171 |
| GBM-log | 2.2088 | 123.87 % | −0.1793 |

The decisive result is that **no fitted candidate beat the mean baseline on out-of-fold MAE**. The
2 % simplicity rule selected the baseline. This is a statement about the covariates, not about the
selection procedure: at 32 studies, the measured environment does not explain between-study harvest
mass well enough to beat predicting the mean.

### Sealed holdout (8 treatments, 8 studies) — single pass

| Metric | Value |
|---|---|
| n | 8 |
| MAE | 5.2309 g/plant |
| RMSE | 6.8966 g/plant |
| **MAPE** | **310.17 %** |
| Median APE | 84.49 % |
| Mean bias | −3.9362 g/plant |
| R² | −0.4831 |
| Criterion | 30 % — **FAILED** |
| Interval span | ×29.1 |
| `promoted` | false |

### Diagnosed causes of the failure

1. **Scale heterogeneity between studies.** Measured dry mass spans two orders of magnitude across
   studies at similar DLI, because "dry mass per plant" is not a comparable quantity across
   protocols (harvest age, density, cultivar, fresh/dry basis).
2. **The unit is a published mean, not a plant.** Within-study variance is unavailable, so no
   candidate can learn the noise structure it is being scored against.
3. **Missing covariates.** Cultivar, root-zone temperature and daily light distribution are not in
   the compilation, and the wheat series shows photoperiod and PPFD act together.
4. **Not a leakage artefact.** The random-split alternative was explicitly not used; the failure
   persists with grouped validation, which means it is a data limitation rather than a split error.

### Consequence

Operational harvest forecasting was removed (see `PHASE30_REMOVED_CAPABILITIES.md`). The measured-
versus-modelled parity record remains at `GET /api/workflows/harvest-prediction/parity`.

**Holdout disclosure:** the eight holdout studies were scored once. They have not been used for
selection and will not be re-split; selecting a different candidate set after seeing these numbers
would be tuning on the evaluation data.

---

## 2. Controlled-environment wheat response surface

### Protocol

| Element | Value |
|---|---|
| Unit of independence | experiment (sub-plots of one chamber stay together) |
| Rows | 36 experiments with yield and environment |
| Development | 30 experiments, leave-one-experiment-out |
| Holdout | 6 experiments sealed by SHA-256, one scoring pass |
| Target | log10(grain yield kg m⁻²) |
| Features | PPFD, photoperiod, DLI, CO₂, air temperature, relative humidity, cycle length |
| Candidates | mean baseline, structured DLI-CO₂, ridge-log, GBM-log |
| Criterion | **30 % MAPE, unchanged** |

### Results

| | Out of fold (30 experiments) | Sealed holdout (6 experiments) |
|---|---|---|
| Selected candidate | `structured-dli-co2` | `structured-dli-co2` |
| MAE (kg m⁻²) | 0.3173 | 0.4049 |
| MAPE | 57.42 % | **297.46 %** |
| Median APE | 38.98 % | 256.54 % |
| R² | 0.2720 | −0.3673 |
| Verdict | development only | **FAILED** |

The out-of-fold conformal interval (90 %, split conformal on log residuals) has a multiplicative
width of 3.58× and a descriptive out-of-fold coverage of 0.867, falling to 0.826 within the ambient-
CO₂ band. With 30 residuals and 6 holdout experiments, that coverage figure is descriptive, not a
coverage guarantee.

Imputation disclosure: `co2Ppm` 0 rows, `photoperiodHours` 1 row — counted at fill time, not at
read time.

### Why it failed

The environmental axes are correlated by design: the high-PPFD experiments are also the long-
photoperiod ones, CO₂ has nine distinct levels across 36 runs, and temperature spans 6.9 °C. Six
sealed experiments cannot be predicted from 30 correlated ones by any of the candidate classes, and
the out-of-fold R² of 0.27 already said the surface was weak before the holdout was opened.

### Consequence

No predictive surface is served. What ships is the measured comparison
(`GET/POST /api/workflows/light-stress/controlled-environment`): band summaries with a between-
experiment 95 % interval, the experiment identifiers behind each band, and an explicit statement that
no significance test is reported because the bands differ in several factors at once.

---

## 3. Prediction intervals — the honest position

Phase 30 did not build a new interval method, and the reason is arithmetic rather than preference:

- The evaluation points available for coverage are 8 (harvest) and 6 (wheat) independent groups.
- A coverage estimate from 8 points has a binomial half-width near ±0.3 at 90 % confidence, so no
  coverage guarantee can be estimated, let alone advertised.
- The harvest interval spanned a factor of 29.1. That is a correct description of the model's
  uncertainty and a decisive statement that the model is not a forecast.

Both artifacts therefore report intervals as **descriptive**, carry `holdoutSpent` /
`selectionRuleWrittenBeforeScoring` / `priorHoldoutInspection` fields, and neither is served.

---

## 4. Summary table

| Model | Independent evaluation | Result | Criterion | Served |
|---|---|---|---|---|
| Lettuce harvest, cross-study | 8 sealed studies | 310.17 % MAPE | 30 % | **no** |
| Wheat CEA response surface | 6 sealed experiments | 297.46 % MAPE | 30 % | **no** |
