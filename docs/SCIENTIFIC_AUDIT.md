# Scientific audit

Scope: every model in the product — the deterministic growth/environment/water/physics simulation,
its optimisation and scenario-comparison surfaces, and all nine registered machine-learning models.

Method: for each model, read the code and the artifact, check the mathematics, assumptions, inputs,
units, data provenance, algorithm, limitations and any existing validation; state what is supported
by evidence and what is not; fix what the evidence does not support; and record the verdict.

Status labels used throughout, in increasing order of strength:

| Label | Means |
| --- | --- |
| `assumption` | A coefficient or relation with no dataset behind it. Disclosed as such, never presented as measured. |
| `experimental` | Implemented and unit-tested for internal consistency; no empirical validation attempted. |
| `trained-exploratory` | Fitted to real data with grouped held-out evaluation, but no independent validation, or a failed one. |
| `calibrated` | Fitted and adjusted so that predicted values match measured magnitudes on data it was fitted to. |
| `externally-validated` | Passed a pre-declared criterion on data untouched by fitting or selection. |
| `scientifically-validated` | Externally validated across independent studies and conditions, with published uncertainty. |

No model in this repository is `externally-validated` or `scientifically-validated`. One failed a
pre-declared external criterion in this audit (lettuce v3: 41.6 % against 30 %). That is the honest
state of the system and every surface says so.

---

## 1. Deterministic simulation

### 1.1 Growth model

**Mathematics.** Standing dry biomass follows a logistic curve per crop cycle,
`m(t) = m_max / (1 + exp(-k (t - t_mid)))`, evaluated with `LOGISTIC_STEEPNESS = 10` over the crop's
own cycle length, and reset at harvest when the run is longer than one cycle. Growth is then scaled
by a product of environment factors (§1.2–1.5).

**Units.** Mass in grams of dry matter per unit area per cycle; time in days; factors dimensionless.
Area scaling is linear and tested (`test_area_scaling_is_linear`).

**Conservation.** The audit's mass-balance invariant — cumulative growth minus cumulative harvest
equals standing biomass on every simulated day — is asserted per crop and per duration
(`test_mass_balance_identity_holds_every_day`). Harvest removes standing biomass and does not allow
standing mass to go negative (`test_biomass_is_never_negative`), and outside harvest days standing
mass equals the pre-harvest value (`test_post_harvest_standing_equals_standing_off_harvest_days`).

**Verdict.** `experimental`. The logistic is a standard, defensible shape, not a fitted result: its
parameters are per-crop scenario values. It reproduces plausible magnitudes and obeys its own
conservation laws; it does not predict a measured harvest.

### 1.2 Gravity factor

`f_g = 1 - MICROGRAVITY_GROWTH_PENALTY (1 - g)` for `g < 1`, and `1 - HYPERGRAVITY_PENALTY_PER_G (g - 1)`
above 1 g, with a per-crop sensitivity multiplier.

**Audit finding.** No crop fresh-weight dataset exists across fractional gravity. The ISS
fractional-gravity work in the OSDR corpus (EMCS, Seedling Growth, OSD-346) measures gene expression
and morphology; published conclusions are that Mars-level gravity may not limit plant development
and that microgravity effects on biomass are modest and mixed. The penalty magnitude is therefore an
**assumption**. It is disclosed at the constant, in `model_description`, and it is not surfaced as a
user-facing claim. It stays in the engine because removing it breaks thirteen tests that encode the
world comparison, and because a scenario coefficient is honest when labelled as one. It is *not*
"measured", and no Moon or Mars yield claim is derived from it.

### 1.3 Radiation factor

`f_r = exp(-RADIATION_DECAY_PER_MGY_PER_DAY · max(0, D - D_earth))` on dose rate in mGy/day.

**Audit finding.** No crop-yield dataset at habitat-relevant chronic dose rates was recovered; the
OSDR radiation corpus is molecular (OSD-46, OSD-782). Exponential decay is the conventional form, but
the decay constant is an **assumption**. Verdict `assumption`, disclosed.

### 1.4 Light / PPFD / photoperiod

`f_l = saturating response normalised to the crop's optimal photoperiod`, with a linear penalty of
2 % per hour beyond `LIGHT_SATURATION_HOURS = 10`.

**Audit finding — this is where the real error was.** The simulation's light factor is a saturation
curve; the *machine-learning* lettuce model used instantaneous PPFD only, with no photoperiod, which
is dimensionally incomplete: light dose is flux × time. At the same PPFD, a 12 h greenhouse and a
16 h plant factory were identical inputs. Light-use efficiency computed from the training data falls
with PPFD (13.35 → 10.03 → 6.99 g fresh mass per mol at 200 / 400 / 750 µmol m⁻² s⁻¹), i.e. the
response saturates rather than being linear in flux. Fixed by making daily light integral
(`PPFD × photoperiod × 3600 / 10⁶`, mol m⁻² d⁻¹) the feature in lettuce v3.

### 1.5 Temperature, CO₂ and water factors

* Temperature: per-crop optimum with a declared tolerance; monotone decline away from the optimum.
* CO₂: rectangular hyperbola normalised so Earth ambient (420 ppm) is 1.0, half-saturation 150 ppm,
  saturating near +30 %.
* **Audit finding (CO₂).** The hyperbola is monotone — more CO₂ never hurts. NASA's closed-chamber
  work does not support that above roughly 1000 ppm (NTRS 20040090155: soybean seed yield and biomass
  peaked at 1000 ppm and fell at 2000 and 5000 ppm). The model is not rescaled from a single
  cultivar's abstract, but any run above `CO2_MEASURED_OPTIMUM_PPM = 1000` now carries a warning.
* Water: growth scales as `(availability / 100)^1.0`, and daily demand follows the canopy, ramping
  from a 15 % seedling fraction. Water conservation is asserted (`test_water_conservation`), demand is
  zero at planting, and supply is bounded by availability. Recovery efficiency is capped at the
  measured 98 % ceiling rather than accept a physical impossibility.

### 1.6 Gas exchange / life support

Photosynthesis stoichiometry from `6 CO2 + 6 H2O → C6H12O6 + 6 O2` with `CARBON_FRACTION_OF_DRY_MASS
= 0.42`: CO₂ fixed = dry mass × 0.42 × 44/12; O₂ released = CO₂ fixed × 32/44.

**Verdict.** `experimental`, and stoichiometrically exact — asserted by
`test_oxygen_carbon_stoichiometry` and `test_carbon_mass_balance_from_dry_matter`. The biological
constants (carbon fraction, harvest index) are rounded literature values, not measurements from this
corpus.

### 1.7 Optimisation and scenario comparison

The optimisation searches crop/area/duration combinations against the deterministic engine; the
scenario comparison runs an Earth reference against a configured space scenario and reports the
difference.

**Audit finding.** Both inherit every assumption in §1.2–1.5. An optimum computed from a scenario
coefficient is an optimum *of that coefficient*, so the surfaces report differences between worlds
under stated assumptions, not measured yield deltas. `comparison_defined` refuses to report a
comparison when the reference is degenerate. Verdict: `experimental`; no external validation is
possible without fractional-gravity yield data, which does not exist publicly.

---

## 2. Registered machine-learning models

All nine artifacts carry a SHA-256 in `ml/artifacts/registry`; `scripts/verify_model_registry.py`
re-derives every hash on demand and cross-checks each registry claim against the artifact it
describes. Splits are grouped at the biological or experimental unit everywhere — pillows, plants,
biological groups, whole experiments — so no individual is split across folds.

| Model | Target | Split | Headline held-out result | Verdict |
| --- | --- | --- | --- | --- |
| `lettuce-earth-growth-v1` | fresh shoot mass per plant (g) | leave-one-experiment-out, 4 folds | MAE 38.9 g, R² 0.812 | `trained-exploratory`; same input gap as v2, not separately re-screened |
| `lettuce-earth-growth-v2` | fresh shoot mass per plant (g) | same folds | MAE 34.9 g, R² 0.870 | `trained-exploratory`, external MAPE 232 % — **failed** |
| `lettuce-earth-growth-v3` | log fresh yield per m² (served per plant) | same folds | MAE 835.5 g/m², R² 0.861; dev MAPE 42.7 %; independent 41.6 % | `trained-exploratory`, **failed** 30 % criterion |
| `mizuna-harvest-v1` | harvest fresh mass (g/pillow) | nested 4-fold GroupKFold by pillow | MAE 15.5 g, R² −0.333 | `trained-exploratory`; worse than a mean predictor |
| `mizuna-microbial-load-v1` | log10(1+CFU/g) | 4-fold GroupKFold by pillow | MAE 1.09, R² 0.549 | `trained-exploratory` |
| `mizuna-microbial-relative-load-v2` | within-campaign z of log10 CFU/g | 4-fold GroupKFold by pillow | MAE 0.539, R² 0.509 | `trained-exploratory`, re-scoped estimand |
| `tomato-flight-response-v1` | flight vs ground context | nested stratified group CV by plant | accuracy 0.917, macro-F1 0.916 | `trained-exploratory` classifier |
| `radiation-quality-osd46-v1` | 3-class radiation quality | leave-one-biological-group-out, 22 groups | balanced accuracy 0.898 | `trained-exploratory` |
| `radiation-exposure-osd46-v1` | irradiated vs control | same | balanced accuracy 0.910 | `trained-exploratory` |

Details, metrics and uncertainty for each are in `MODEL_VALIDATION_REPORT.md`.

### 2.1 Findings common to all models

1. **Leakage.** Gene/feature selection and scaling are fitted inside each training fold. Grouped
   splits keep all samples from one plant, pillow, biological group or experiment in one fold. No
   test-set information enters hyperparameter selection: the inner search is nested.
2. **Selection data is not validation.** Where a held-out set influenced model form — lettuce v3's
   light feature was chosen on the six PeerJ observations — that set is labelled *development* and
   the labels say `countsAsValidation: false`. The independent holdout was not touched during
   selection.
3. **Baselines.** Every regression reports a dummy/mean baseline and every classifier a majority or
   permuted-label null. `mizuna-harvest-v1`'s R² is negative: it is worse than predicting the mean,
   and the artifact says so rather than being dropped from the table.
4. **Uncertainty.** Regression artifacts carry group-level cross-conformal radii with achieved
   coverage (0.992 against nominal 0.9 for both mizuna microbial models). Lettuce v3 carries
   conformal quantiles on the log target (out-of-fold coverage 0.90), and the response marks
   `calibrated: false` because that coverage is descriptive, not independent.
5. **Accuracy is never called validation.** Training-fold accuracy is not reported anywhere as a
   validation result; every number in the table above is held-out.
6. **Versions and provenance.** Each artifact records its training rows, group count, seed, source
   study, and (for v3) the SHA-256 of the exact training table.

### 2.2 The lettuce failure, in full

This is the finding the audit was asked to chase, so it is stated without softening.

* **Symptom.** v2's development screen over six independent observations (PeerJ 17085, greenhouse
  vertical farm, 48 plants/m², 12 h, 27.5 °C, 28 DAT) gave **MAPE 232.2 %**, median overprediction
  3.21×, every observation predicted high.
* **Diagnosis.** Two reported variables were missing from the inputs: photoperiod (light dose is flux
  × time) and planting density (mass per plant is per-area yield divided by density). v2 also
  predicted per-plant mass directly, so it could not express the density dependence that the source
  studies show — per-plant mass falls as density rises while areal yield rises (Touliatos: 138 g at
  50 plants/m² → 95 g at 1000 plants/m², 6.9 → 95 kg/m²).
* **Fix.** v3 targets log(fresh yield per m²), reconstructed from per-plant mass at the source's 25
  plants/m², and serves per-plant mass by dividing by the caller's stated density. Light enters as
  DLI. Feature-variant comparison is disclosed in the artifact; internal MAE is flat across variants
  (835–872 g/m²), so the choice was made on agronomic grounds (DLI is the standard light metric) and
  the development set is consequently no longer valid as validation.
* **Outcome.** Development MAPE **42.7 %**, bias **+2.6 g** (v2: +246.6 g, 232 %). Independent holdout (Touliatos 2016, untouched): **41.6 %** against a 30 % criterion fixed
  before measurement — **fails**. One source (1000 plants/m²) is **refused rather than scored**,
  because the per-area identity that converts yield to per-plant mass does not hold there.
* **Residual structure.** v3's errors are not random: the model has no cultivar input, and the two
  cultivars in the development set differ by more than the light effect; the measured light response
  is non-monotonic while a tree ensemble's is not. Reported bias being near zero therefore does not
  mean the model is right — it means two opposing errors cancel.
* **What was not done.** The 30 % criterion was not relaxed, the holdout was not re-used for tuning,
  and no number was chosen from the best of several splits.

---

## 3. De-scoped claims

The following were removed rather than approximated, because no dataset supports them:

| Feature | Why removed |
| --- | --- |
| Fractional-gravity biomass sliders | No crop biomass dataset exists across fractional gravity; only molecular and morphological responses. |
| Regolith crop-yield model | No NASA regolith yield table; OSD-670/OSD-856 are growth-medium studies, not yield surfaces. |
| Gravity–radiation interaction optimisation | Both factors are assumptions; their product is two assumptions. |
| Space lettuce yield prediction | No spaceflight lettuce yield dataset with light, temperature and duration. |

Ethylene and water closed-loop features were kept and populated with real NASA data
(`GET /api/closed-loop`), because those measurements do exist.

---

## 4. Residual gaps

1. **No independent validation for any space-crop model.** The one space dataset (VEG-04A mizuna,
   14 harvest outcomes, one experiment) cannot support a cross-study holdout.
2. **No cultivar dimension anywhere.** The lettuce models cannot represent cultivar effects, which
   the development data show exceed the light effect.
3. **No CO₂ or nutrient input in the lettuce models.** Both are known to move fresh mass
   substantially; the training source held them near-constant.
4. **Density enters through an identity, not a learned response.** Above ~200 plants/m² the identity
   is refused rather than extrapolated.
5. **Time series.** The lettuce data are one harvest per plant; growth trajectories are not modelled,
   so v3 cannot predict intermediate harvests.
6. **The simulation's gravity and radiation coefficients remain assumptions** and no public source
   can replace them.
