# Scientific validation plan

Written before the measurements it describes, so that the criteria cannot be chosen after seeing the
results. Where a criterion was in fact fixed earlier, that is noted.

## 1. What counts as validation

| Term | Definition used here |
| --- | --- |
| Internal evaluation | Held-out folds within the training data, grouped at the biological or experimental unit. Useful for model selection; **not** validation. |
| Development set | Data used to choose model form, features or hyperparameters. Reported, labelled `countsAsValidation: false`, and **never** called validation. |
| Independent validation | Data untouched during fitting **and** selection, scored once against a criterion fixed in advance. |
| External validation | Independent validation on a study from a different group, system or country. |
| Reproducibility | The same artifact produces the same prediction from the trainer and from the served API. Necessary for validation to mean anything; not sufficient. |

A model may only be labelled `externally-validated` if it passes §3. No model currently qualifies.

## 2. Splitting rules

1. **Groups, never rows.** Every split keeps all samples from one experimental unit together:
   plant, pillow, biological group, array batch, or whole experiment. Row-level splitting of
   repeated measures inflates accuracy by memorising the individual.
2. **Selection inside the training fold.** Gene filtering, ANOVA feature selection, scaling and
   hyperparameter search are fitted within each training fold. The inner search is nested so the
   outer fold never informs it.
3. **One holdout per question.** A study is either training/development or holdout, never both. If a
   holdout number influences a design decision, the study is reclassified as development and a new
   holdout is required before any validation claim is made. This is what happened to PeerJ 17085 in
   this audit.
4. **Baselines are mandatory.** Every regression reports a dummy/mean baseline on the same folds;
   every classifier reports a majority-class or permuted-label null. A model that does not beat its
   baseline is reported as such (`mizuna-harvest-v1`, R² −0.333).
5. **Refusal over extrapolation.** Where an input falls outside the fitted domain, the model either
   flags the response `outOfDistribution` with the violated bounds, or refuses to score. Silent
   extrapolation is not permitted.

## 3. Pre-declared acceptance criteria

| Model | Quantity | Criterion | Basis |
| --- | --- | --- | --- |
| `lettuce-earth-growth-v3` | MAPE on an independent study, per-observation | **≤ 30 %** | Declared before the holdout was scored. For a harvest forecast used to size a farm, a third of the crop is the point at which the number stops being useful, and the criterion was set from that requirement rather than from what the model could reach. |
| `lettuce-earth-growth-v3` | Mean bias error | **≤ 15 %** of the mean measured value | A model that is right on average with large errors is still unusable per plant; bias is checked separately from spread. |
| `lettuce-earth-growth-v3` | Domain | **No scoring outside the declared domain** | Refuse, do not extrapolate. |
| Regression models (mizuna) | R² | **> 0** on held-out folds | A negative R² means the mean predictor wins; such a model may be served only as exploratory and must say so. |
| Classifiers | Balanced accuracy | **> 0.5** and above the permuted-label null | Guards against a class-imbalance artefact. |
| Classifiers | Attribution | **No causal claim** | A classifier that separates conditions differing in two factors at once (100 Gy gamma vs 30 Gy Fe-56, differing in quality *and* dose) may not attribute the difference to either. |
| Simulation | Conservation | **Exact identity** every simulated day | Mass in = standing + harvested; water in = transpired + recovered + retained. |
| Simulation | Domain | **Finite, non-negative, bounded factors** | Asserted per crop and per duration. |
| All | Uncertainty | **A stated interval with measured coverage**, labelled calibrated or not | No point estimate without an interval, and no coverage claim without an out-of-fold measurement. |

Criteria are not relaxed after measurement. If a model fails, it is reported as failed and stays
`trained-exploratory`.

## 4. Uncertainty reporting

* Regression: 90 % intervals from conformal residual quantiles on grouped out-of-fold predictions.
  For log-target models the interval is a ratio, which is what makes it usable across two orders of
  magnitude of yield.
* Coverage is measured out-of-fold and labelled **descriptive, not independent evidence** — the
  quantiles and the coverage come from the same predictions.
* Classifiers: stratified percentile bootstrap over held-out predictions (95 %).
* The simulation is deterministic given its inputs, so its "uncertainty" is parameter uncertainty,
  reported as sensitivity rather than as a distribution.

## 5. Bias and residual analysis

Every regression is examined for structure in the residuals, not only for their size:

* residuals against each input (light, temperature, duration);
* residuals against the group, to expose a study that is systematically off;
* ratio (not difference) for positive quantities spanning orders of magnitude, because a 50 g error
  means something different at 90 g than at 700 g;
* sign of the mean bias, since an overprediction and an underprediction of the same magnitude have
  different consequences for sizing.

Where a model's bias is small only because two opposing errors cancel, that is stated.

## 6. Independent validation procedure (per model)

1. Identify candidate sources not used in training. Record DOI, licence, retrieval date, SHA-256 of
   the retrieved file, and the metadata needed to judge comparability.
2. Confirm that every model input is reported **per observation**. Study averages are never
   substituted for per-observation inputs; a source that only reports an average cannot be used for
   a row-level metric.
3. Check the domain. Record and report every violation rather than widening the domain to fit.
4. Score once, with the criterion from §3, and publish: MAPE, MAE, RMSE, MBE, R², per-observation
   ratios, interval coverage, and the domain violations.
5. Write the verdict into the artifact (`validation.independent`), the registry
   (`independentValidation`) and the response (`validationStatus`). `scripts/verify_model_registry.py`
   fails if any of the three disagree, or if a failed evaluation is labelled validated.
6. Do not re-tune after seeing the result. A failure is a finding, not a task.

## 7. Reproduction

* Training: `python ml/training/train_<model>.py` writes the artifact and appends the registry entry,
  including the SHA-256 of the training table.
* Verification: `python scripts/verify_model_registry.py` (checksums, API loadability, status
  consistency, independent-validation consistency).
* Dataset inventory: `python scripts/generate_dataset_registry.py` regenerates
  `docs/DATASET_REGISTRY.md` from the files themselves.
* Tests: `cd backend && python -m pytest` — includes scientific invariants for the simulation and
  `tests/test_lettuce_v3_scientific.py` for the yield model.
