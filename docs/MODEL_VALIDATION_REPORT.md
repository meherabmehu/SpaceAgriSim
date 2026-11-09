# Model validation report

Every number here is produced by the code in this repository and is reproducible from it. Nothing is
rounded up, nothing is a training-set score presented as a validation score, and no failed result has
been removed.

Reproduce: `python ml/training/train_lettuce_v3.py`, `python scripts/verify_model_registry.py`,
`cd backend && python -m pytest`, `GET /api/external-validation`.

---

## 1. Lettuce fresh yield — v3 (the audit's central model)

**Artifact** `ml/artifacts/lettuce-earth-growth-v3.json`, SHA-256
`885bc54c5e61…` (full value in `ml/artifacts/registry.json`), status **`trained-exploratory`**.

### 1.1 Specification

| Item | Value |
| --- | --- |
| Task | Fresh shoot mass per plant, served as per-area yield ÷ caller's density |
| Target | `log(fresh yield per m²)`, reconstructed as `freshShootMassG × 25` (source density 25 plants/m²) |
| Features | `daysAfterTransplant`, `airTemperature`, `rootTemperature`, `dailyLightIntegral` |
| Derived input | `DLI = PPFD × photoperiodHours × 3600 / 10⁶` [mol m⁻² d⁻¹] |
| Caller inputs | the four above plus `photoperiodHours` (default 16) and `plantDensityPerM2` (default 25) |
| Serving identity | `massPerPlant = freshYieldPerM2 / plantDensityPerM2` |
| Learner | Gradient boosting on decision trees, serialised as `init + learningRate × Σ tree` |
| Training data | 1 648 rows, 4 experiments (EXP1–4), WUR Carotti et al. 2021, CC-BY-4.0, 16 h, cv. Batavia Othilie |
| Rows SHA-256 | recorded in the artifact (`trainingDataSha256`) |
| Split | Leave-one-experiment-out, 4 folds |

### 1.2 Learner selection on identical folds (internal, g fresh mass per m²)

| Learner | MAE | RMSE | MAPE | MBE |
| --- | --- | --- | --- | --- |
| **gradient boosting (shipped)** | **835.5** | **1 539.8** | **41.7 %** | **−249.3** |
| random forest | 928.4 | 1 698.3 | 46.4 % | +57.0 |
| ridge | 1 751.7 | 3 391.2 | 73.4 % | +533.4 |
| dummy (mean) | 2 797.7 | 4 668.3 | 459.2 % | −2 132.1 |

R² 0.861, n = 1 648. The dummy baseline is included because a model that cannot beat the mean has no
business being served; boosting beats it by a factor of 3.3 on MAE.

### 1.3 Feature-variant comparison (disclosed selection)

Internal MAE is flat across light drivers (835–872 g/m²), so the internal metric could not choose
between them. The development set could, and that is exactly why it cannot then be called validation.

| Light driver | Internal MAE | Development MAPE | Development MBE |
| --- | --- | --- | --- |
| PPFD only | 836 | 71.6 % | +47.1 g |
| **DLI only (shipped)** | **836** | **42.7 %** | **+2.6 g** |
| PPFD + DLI | 836 | 52.5 % | +22.3 g |
| DLI + cumulative DLI | 872 | 50.6 % | +8.5 g |
| DLI + cumulative DLI + ΔT | 869 | 50.7 % | +9.5 g |

DLI was chosen on agronomic grounds (it is the standard light metric in controlled-environment
horticulture, and light dose rather than instantaneous flux is the causal quantity). The fact that it
also scored best is recorded, not used as the justification.

### 1.4 Development set — PeerJ 17085 (Wicharuck et al. 2024, doi:10.7717/peerj.17085)

Greenhouse vertical farm, 48 plants/m², 12 h photoperiod, 27.5 °C, 28 DAT. **Six observations, used
for model-form selection: this is not validation.**

| Observation | Cultivar | PPFD | Measured (g) | v3 predicted (g) | Ratio | v2 predicted (g) | v2 ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| upper | Baby Cos | 697 | 84.5 | 157.4 | 1.86 | 454.2 | 5.4 |
| middle | Baby Cos | 391 | 123.8 | 123.4 | 1.00 | 341.0 | 2.8 |
| lower | Baby Cos | 322 | 92.9 | 123.4 | 1.33 | 341.0 | 3.7 |
| upper | Green Oak | 697 | 97.3 | 157.4 | 1.62 | 454.2 | 4.7 |
| middle | Green Oak | 391 | 190.7 | 123.4 | 0.65 | 341.0 | 1.8 |
| lower | Green Oak | 322 | 203.7 | 123.4 | 0.61 | 341.0 | 1.7 |

**MAPE 42.7 %** (v2: 232.2 %), **MBE +2.6 g** (v2: **+246.6 g**). MAE 51.9 (v2: 246.6), RMSE 58.9.
The v2 rows above are recomputed on the same six observations by `GET /api/external-validation`, so
the comparison is checkable in the running service rather than only in this table.

Residual structure, which the aggregate hides:

* v3 returns the same prediction at 391 and 322 µmol m⁻² s⁻¹ (a tree ensemble plateaus between split
  points) while the measurements differ by 67 % within Baby Cos and 7 % within Green Oak;
* Green Oak is underpredicted at low light and Baby Cos overpredicted at high light — the errors have
  opposite signs, so the near-zero MBE is two errors cancelling, not accuracy;
* the model has no cultivar input, and the cultivar effect (63.5 g mean difference across the three light levels) is larger than
  the within-cultivar light effect.

### 1.5 Independent holdout — Touliatos, Dodd & McAinsh 2016 (doi:10.1002/fes3.83)

Untouched during fitting **and** during every selection decision above. Scored once.

| Observation | System | Density (plants/m²) | Measured (g) | Predicted (g) | Ratio |
| --- | --- | --- | --- | --- | --- |
| `hhs-50` | horizontal hydroponic | 50 | 138.0 | 195.4 | **1.42** |
| `vfs-1000` | stacked vertical farm | 1000 | 95.0 | — | **refused** |

`hhs-50`: MAPE **41.6 %**, MAE 57.4 g, MBE +57.4 g. **Criterion 30 % → failed** (`passed: false`).
Domain violations reported with the result: DAT 35 outside [2, 29]; air temperature 17 °C below the
20 °C floor.

`vfs-1000`: density 1000 plants/m² lies outside the supported [10, 200] band and the reported yield is
per occupied floor area (stacking), so the per-area identity that converts yield to per-plant mass
does not hold. The model **refuses to score it** rather than producing a number that would look like a
0.10× underprediction and mean nothing.

### 1.6 Uncertainty

Conformal residual quantiles on the log target: 5 % = −0.821, 95 % = +0.834, out-of-fold coverage
0.90 against nominal 0.90. The artifact states that this coverage comes from the same out-of-fold
predictions the quantiles come from, so it is descriptive, not independent evidence. Responses mark
`calibrated: false`.

### 1.7 Verdict

`trained-exploratory`. The improvement over v2 is real and large (232 % → 42.7 % on identical rows,
bias essentially removed), and the model still **fails** the criterion that decides whether it may be
used for harvest forecasting. It has no cultivar, no CO₂ and no nutrient input; it represents density
through an identity rather than a learned response and refuses above ~200 plants/m²; its light
response is monotonic where the data are not.

---

## 2. Lettuce fresh mass — v2 and v1 (kept for reproducibility)

| Model | MAE (g/plant) | RMSE | R² | External MAPE | Status |
| --- | --- | --- | --- | --- | --- |
| `lettuce-earth-growth-v2` | 34.9 | 59.7 | 0.870 | **232.2 %**, median 3.21× overprediction, `passed: false` | `trained-exploratory` |
| `lettuce-earth-growth-v1` | 38.9 | — | 0.812 | not separately re-screened | `trained-exploratory` |

v2 remains callable and byte-identical. Deleting it once v3 existed would erase the evidence that the
correction was needed; `GET /api/external-validation` still returns its failure beside v3's.

---

## 3. Mizuna models (NASA VEG-04A)

| Model | Target | Rows / groups | MAE | RMSE | R² | Baseline |
| --- | --- | --- | --- | --- | --- | --- |
| `mizuna-harvest-v1` | harvest fresh mass (g/pillow) | 14 / 10 | 15.5 | 18.9 | **−0.333** | mean predictor wins |
| `mizuna-microbial-load-v1` | log10(1+CFU/g) | 123 / 35 | 1.087 | 1.404 | 0.549 | — |
| `mizuna-microbial-relative-load-v2` | within-campaign z of log10 CFU/g | 123 / 35 | 0.539 | 0.695 | 0.509 | ridge / boosting compared |

`mizuna-harvest-v1` is **worse than predicting the mean on held-out data**. It is retained as an
exploratory artifact, labelled as such, and no surface presents it as a harvest forecast. Fourteen
outcomes from one experiment cannot support a cross-study claim.

Both microbial models carry group-level cross-conformal intervals: nominal 0.90, achieved 0.992 on 35
calibration groups, exchangeability unit = biological group (worst residual within group). The
achieved coverage exceeds nominal because the interval is built on the worst residual per group — a
conservative choice, stated in the artifact.

`mizuna-microbial-relative-load-v2` was a **re-scope, not a rescue**: v1's absolute load estimand did
not transfer between campaigns, so v2 predicts within-campaign relative load and says so. The
re-scoping is recorded in the registry rather than folded silently into a "v2 improvement".

---

## 4. Molecular classifiers (NASA OSDR)

| Model | Task | Rows / groups | Held-out result | Null |
| --- | --- | --- | --- | --- |
| `tomato-flight-response-v1` | flight vs ground context (OSD-767) | 36 / 21 plants | accuracy 0.917, macro-F1 0.916, ROC-AUC 0.975 | macro-F1 0.444 |
| `radiation-quality-osd46-v1` | 3-class radiation quality (OSD-46) | 44 / 22 biological groups | balanced accuracy 0.898, macro-F1 0.906 | labels permuted between groups |
| `radiation-exposure-osd46-v1` | irradiated vs control (OSD-46) | 44 / 22 | balanced accuracy 0.910, macro-F1 0.891 | labels permuted between groups |

All three use in-fold gene selection (ANOVA) and in-fold scaling; the radiation models are
leave-one-biological-group-out with 22 groups and report which held-out groups contained only one
class. Bootstrap confidence intervals are stratified over held-out predictions (e.g. balanced
accuracy 0.910, 95 % CI 0.771–1.000 — a wide interval, honestly reported, because n = 44).

**Attribution limit.** In OSD-46, 100 Gy gamma and 30 Gy Fe-56 differ in *both* radiation quality and
absorbed dose. A classifier separating those classes cannot attribute the difference to either
factor. The regression of molecular response onto a "gravity" or "radiation quality" slider is
therefore not offered, and no Moon or Mars yield claim is derived from these classifiers.

---

## 5. Simulation

Validation here is internal consistency, because there is no independent yield dataset for space
crops to validate against:

* mass balance holds exactly on every simulated day, for every crop and duration
  (28 crop × duration combinations);
* harvest removes standing biomass; standing mass never goes negative; growth is monotone within a
  cycle;
* water conservation holds and demand is zero at planting;
* photosynthesis stoichiometry matches `6 CO2 + 6 H2O → C6H12O6 + 6 O2` with carbon fraction 0.42;
* harvest index consistency, linear area scaling, bounded growth factors, and Earth reference never
  worse than space;
* every reported quantity is finite, and relative humidity changes water demand in the expected
  direction.

**Verdict `experimental`.** The gravity (15 % at 0 g) and radiation (0.25 per mGy/day) coefficients are
assumptions with no supporting crop dataset; they are disclosed at the constant and in
`model_description`, and no user-facing surface presents them as measurements.

---

## 6. What is not validated, stated plainly

1. No crop-yield model here is externally validated. The one external test that was run (lettuce v3)
   **failed**.
2. No spaceflight crop-yield dataset with light, temperature and duration exists in this repository,
   so no space yield prediction is offered.
3. Cultivar effects are unrepresented in the only model with external data, and the development set
   shows that effect to be larger than the modelled light effect.
4. The simulation's gravity and radiation coefficients are scenario assumptions.
5. `mizuna-harvest-v1` does not beat the mean on held-out data.
