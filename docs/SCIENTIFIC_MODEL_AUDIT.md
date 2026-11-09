# Scientific Model Audit

SpaceAgriSim, 2026-11-09. Every model that produces a number a user can see, audited against the
same ten questions: purpose, formulation, inputs, outputs, data source, calibration, validation,
limitations, missing variables, improvement path.

Two families are audited separately, because they fail differently. A **mechanistic** model can be
wrong because its equations are wrong (audited against published worked examples). A **learned**
model can be wrong because its data is thin (audited against held-out data it never saw). Presenting
a learned model as if it were mechanistic, or a mechanistic model as if it were validated against
measurements, is the failure mode this document exists to prevent.

Nothing in this audit was written from memory of the code. Every formulation below was read out of
the file named in its heading.

---

## 0. Headline findings

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | The Hargreaves-Samani baseline was missing the 0.408 MJ m^-2 d^-1 to mm d^-1 factor, making it 2.45x too large | **high** - it flattered every model compared to it | fixed; FAO-56 Example 20 (5.0 mm/day) added as a permanent self-check |
| F2 | The dataset quality check treated "dew point above daily Tmin" as an error; it is a normal feature of humid climates | medium - the QA report was inverted | fixed; demoted to informational, real test is supersaturation |
| F3 | `et0-emulator-v1` beats the physics baseline on a temporal holdout and loses to it on unseen sites | **high** - it decides whether the model may be used | disclosed; 4th acceptance gate added post hoc, model not deployed |
| F4 | `mizuna-harvest-v1` has R^2 of -0.333 against a held-out fold set: worse than predicting the mean | **high** | registered as exploratory; nothing in the product depends on it |
| F5 | `lettuce-earth-growth-v3` MAPE is 41.7 % against an independent study, criterion 30 % | **high** | criterion not met; reported as such through the API |
| F6 | The simulation's environment factors are illustrative curves, not fitted physiology | medium | each factor is labelled exploratory in its docstring; no fitted parameter is claimed |
| F7 | Water demand is a constant per crop scaled by growth and light, with no weather input until now | medium | a weather-driven ET0 alternative now exists behind `/api/reference-et0/estimate`, not yet wired into the engine |

The rest of this document is the evidence for those seven lines.

---

# Part I - Mechanistic models

## M1. Growth trajectory and environment scaling

`backend/app/simulation/growth.py`, `backend/app/simulation/engine.py`

| Question | Answer |
|---|---|
| **Purpose** | Produce daily standing biomass and cumulative production over a crop cycle, and across repeated cycles in continuous production. |
| **Formulation** | Logistic curve over the cycle: `biomass(day) = harvestBiomass x combinedFactor x area x L(day/cycleLength)` with `L(x) = 1/(1+exp(-k(x-x0)))`. On the harvest day the crop is cut and a new cycle starts the next day. Three quantities are kept separate: standing biomass, harvested yield (whole cycles only), and cumulative biomass (standing + harvested). |
| **Inputs** | Crop profile (cycle length, harvest biomass, optimal photoperiod), growing area, the eight environment factors, number of days. |
| **Outputs** | `DailyGrowthPoint` per day: standing biomass, cumulative biomass, harvested mass, growth fraction, cycle index, harvest flag. |
| **Data source** | Crop parameters are literature values in `backend/app/simulation/crops.py`. The curve shape is a modelling choice, not a fitted result. |
| **Calibration** | None. No parameter in this module was fitted to measured data. |
| **Validation** | No independent validation of the curve shape. What is tested is internal consistency: the mass-balance identity `cumulative = harvested_through_previous_day + standing` holds on every harvest day, and the logistic curve is monotone between harvests. |
| **Limitations** | A single logistic curve cannot represent a lag phase followed by exponential growth followed by senescence with different rates; it is symmetric. Growth is linear in the combined factor, so the factors multiply without interaction, which is known to be false for, e.g., high temperature plus low light. |
| **Missing variables** | Leaf area index as a state variable; assimilate partitioning; respiration; cultivar; day/night temperature difference; canopy height. |
| **Improvement** | Replace the symmetric logistic with a three-parameter beta or a piecewise vegetative/reproductive curve fitted to the OSDR harvest masses. Growth fraction is already the integration point - `water.py` and `gas_exchange.py` both consume it - so the substitution is contained. |

## M2. Environmental response factors

`backend/app/simulation/factors.py`

| Question | Answer |
|---|---|
| **Purpose** | Map each environment input to a dimensionless multiplier where 1.0 means "no effect relative to the crop's Earth reference condition", so the effect of each driver can be shown separately in the UI. |
| **Formulation** | light: saturating `h/(h+k)`, normalised to the optimum, with a linear penalty above the optimum. CO2: rectangular hyperbola `c/(c+150)`, normalised to 420 ppm. water: `(availability/100)^1.0`. gravity: linear penalty reaching `MICROGRAVITY_GROWTH_PENALTY x cropSensitivity` at 0 g. radiation: `exp(-k x sensitivity x excessDose)` above Earth background. PPFD, temperature and humidity: exploratory Gaussian or saturating curves. |
| **Inputs** | Gravity (g), dose rate (mGy/day), water availability (%), photoperiod (h), CO2 (ppm), PPFD, temperature (C), RH (%). |
| **Outputs** | Eight factors plus their product. |
| **Data source** | Curve *shapes* are conventional plant-physiology forms. The *steepness* constants live in `backend/app/config/simulation_constants.py` and are engineering assumptions, not regression results. |
| **Calibration** | None. `temperature_factor` and `humidity_factor` say so in their own docstrings ("exploratory", "not fitted crop physiology"). |
| **Validation** | No dataset validates these curves. The only published observation used anywhere is the six-point lettuce trial, which is applied to the yield model, not to these factors. |
| **Limitations** | The product form assumes independence of drivers. The gravity factor is linear in g, which is a placeholder for a response that the data cannot resolve at any gravity level except 1 g. The humidity factor peaks at 60 % RH, which is a convention, not a finding. |
| **Missing variables** | Interaction terms; cultivar-specific optima; acclimation over time; VPD rather than RH as the humidity driver (VPD is computed in this module but not used as a factor). |
| **Improvement** | The light factor should become a PPFD response with a measured light-saturation point per crop; the temperature factor should use cardinal temperatures (Tmin, Topt, Tmax), which the crop profiles could carry. Both are cheap and reduce invented curvature. |

## M3. Water demand, supply and recovery

`backend/app/simulation/water.py`

| Question | Answer |
|---|---|
| **Purpose** | Daily water demand, supplied volume, unmet demand (deficit) and condensate recovery, kept as four separate quantities. |
| **Formulation** | `demand = peakWaterPerDay x area x lightScale x (seedling + (1-seedling) x growthFraction)`; `supplied = demand x availability`; `deficit = demand - supplied`; `recovered = supplied x recoveryEfficiency`. |
| **Inputs** | Crop peak water use, growing area, growth fraction, light factor, water availability %, recovery efficiency. |
| **Outputs** | Daily and cumulative litres for each of the four quantities. |
| **Data source** | `peak_water_l_per_day` per crop from literature; recovery efficiency is a constant in `simulation_constants.py`. |
| **Calibration** | None. |
| **Validation** | No measured water use to validate against. The deficit path is tested for monotonicity and bounds, not accuracy. |
| **Limitations** | **The default demand path does not depend on weather at all.** It is a constant per crop scaled by growth and photoperiod, so a hot dry day and a cool humid day produce identical demand. A weather-driven path now exists but is opt-in and off by default, so it changes no existing result. Recovery efficiency is a fixed fraction rather than a function of cabin humidity and condenser performance. |
| **Missing variables** | Reference evapotranspiration as the default, substrate water-holding capacity, drainage fraction, condensate recovery as a function of RH. |
| **Improvement** | Replace `peakWaterPerDay x lightScale` with `ET0 x Kc x area` (implemented, opt-in via `et0MmPerDay`). Making it the default requires evaporative-demand data for the target chamber, because the two curves are not interchangeable: at 4 mm/day reference ET0 with Kc 1.0 and 10 m2 over 30 days the ET0 path gives 623 L against 389 L from the crop-constant curve at default settings (+60 %), and only a measurement can decide which is right for a given chamber. |

## M4. Gas exchange (CO2 removal, O2 production)

`backend/app/simulation/gas_exchange.py`

| Question | Answer |
|---|---|
| **Purpose** | Turn biomass accumulation into CO2 removal and O2 production so the three outputs cannot drift apart. |
| **Formulation** | `totalFreshGain = edibleGain/harvestIndex`; `dryGain = totalFreshGain x dryMatterFraction`; `carbonFixed = dryGain x 0.45`; `co2Removed = carbonFixed x 44/12`; `o2Produced = co2Removed x 32/44`. |
| **Inputs** | Daily edible biomass gain, crop harvest index and dry-matter fraction. |
| **Outputs** | Daily and cumulative grams of CO2 removed and O2 produced. |
| **Data source** | Stoichiometry is exact (44/12, 32/44); `CARBON_FRACTION_OF_DRY_MASS = 0.45` is a standard approximation; harvest index and dry-matter fraction are crop constants. |
| **Calibration** | None. |
| **Validation** | The stoichiometric ratios are exact and unit-tested. The physiological constants are not validated against a closed-chamber measurement. |
| **Limitations** | Assumes all fixed carbon stays in the plant: no respiration, no root exudates, no litter. A real cabin's net CO2 drawdown is lower. Treats CO2 removal as unlimited by CO2 concentration even though `co2_factor` already limits growth - correct, but it means the gas numbers inherit whatever error the growth curve has. |
| **Missing variables** | Dark respiration, root respiration, microbial respiration (the mizuna microbial artefacts in this repo are unrelated to gas exchange but hint at the biology), chamber leakage. |
| **Improvement** | Add a respiration term proportional to standing dry mass; the coefficient is published for lettuce and would turn a one-way conversion into a net exchange model. |

## M5. Impact decomposition

`backend/app/simulation/impact.py`

| Question | Answer |
|---|---|
| **Purpose** | Explain the space-versus-Earth yield gap as a waterfall of per-driver contributions that sum exactly to the total. |
| **Formulation** | Because growth is linear in the combined factor and the factor is a product, `spaceYield/earthYield = PROD(f_i^space/f_i^earth)`. Drivers are applied one at a time in a fixed order and each step's percentage-point contribution is recorded. |
| **Inputs** | The two factor sets. |
| **Outputs** | Per-driver `percent` (own effect) and `contributionPoints` (share of the final gap), plus a residual that is exactly zero. |
| **Data source** | None - this is arithmetic over M2's outputs. |
| **Calibration** | Not applicable. |
| **Validation** | The exactness property is a test: the steps sum to the total, and the residual is asserted zero. |
| **Limitations** | The decomposition is order-dependent in presentation but not in total; the order is fixed, so `contributionPoints` are not unique. They must be read as "with this order of application", which the docstring states. |
| **Missing variables** | Interaction terms - by construction the model has none, so no interaction can be attributed. |
| **Improvement** | None needed while M2 is multiplicative. If M2 gains interactions, this module must switch to a Shapley decomposition to stay honest. |

## M6. Reference evapotranspiration (FAO-56) - **new in this phase**

`backend/app/simulation/et0_fao56.py`

| Question | Answer |
|---|---|
| **Purpose** | Compute daily reference evapotranspiration for a hypothetical well-watered grass surface from standard weather variables, as the physical basis for crop water demand. |
| **Formulation** | FAO-56 Penman-Monteith, eq. 6: `ET0 = (0.408 D (Rn-G) + g (900/(T+273)) u2 (es-ea)) / (D + g(1+0.34 u2))`. Supporting equations: Ra (21), Rso (37), Rns (38), Rnl (39 with cloudiness clamped to [0,1]), ea from dew point (14), es (11-12), D (13), g (7-8), u2 from wind at height (47). Hargreaves-Samani as fallback: `0.0023 x 0.408 x Ra x (Tmean+17.8) x sqrt(Tmax-Tmin)`. DLI: `Rs x 0.45 x 4.57`. |
| **Inputs** | Tmax, Tmin, dew point (or RH), solar radiation, wind speed at 2 m, pressure, day of year, latitude, elevation. |
| **Outputs** | ET0 in mm/day, split into radiation and aerodynamic terms, plus VPD and net radiation. |
| **Data source** | FAO Irrigation and Drainage Paper 56 (Allen et al., 1998), chapter 4. |
| **Calibration** | **None, and none is possible**: the equation has no free parameters. That is the point of using it. |
| **Validation** | Against three worked examples in the source document: Example 17 (Bangkok, monthly, 5.72 mm/day), Example 18 (Uccle, daily, 3.88 mm/day), Example 20 (Lyon, Hargreaves, 5.0 mm/day). All three are asserted in `backend/tests/test_phase23_reference_et0.py` and printed by `run_published_examples()`. |
| **Limitations** | It is a **reference** flux for a hypothetical grass, not a measurement of any crop's water use. Daily step only (the formulation is the daily one; the hourly FAO-56 variant is not implemented). Assumes no water stress. Requires radiation and wind to be complete; with either missing, the module refuses to fall back silently and the service reports Hargreaves or the emulator instead, with the method named. |
| **Missing variables** | Crop coefficient Kc, water stress coefficient Ks, soil evaporation, canopy interception, advection from a dry surrounding. |
| **Improvement** | The next step is `ETc = Kc x ET0` with Kc from the FAO-56 crop tables, then a single-layer soil water balance. Both are published and neither needs new data beyond what POWER already provides. |

## M7. Daily light integral

`backend/app/simulation/et0_fao56.py::daily_light_integral`

| Question | Answer |
|---|---|
| **Purpose** | Convert daily solar radiation to the mol m^-2 d^-1 units that controlled-environment light research uses. |
| **Formulation** | `DLI = Rs [MJ m^-2 d^-1] x 0.45 [PAR/global] x 4.57 [mol MJ^-1]`. |
| **Inputs** | Rs. |
| **Outputs** | DLI in mol m^-2 d^-1. |
| **Data source** | PAR fraction 0.45 is a standard convention for sunlight; the 4.57 mol MJ^-1 conversion is exact for the mean photon energy of PAR. |
| **Calibration** | None. |
| **Validation** | Dimensional check only. |
| **Limitations** | **For sunlight, not for LEDs.** An LED spectrum has a different PAR fraction and a different photon energy distribution, so applying this to an indoor fixture output is an estimate, and it is labelled as one. It also uses outdoor irradiance for an indoor system - a real greenhouse's DLI will be lower by the glazing transmissivity. |
| **Missing variables** | Fixture spectrum, glazing transmissivity, shading, canopy reflectance. |
| **Improvement** | Accept fixture efficiency (umol/J) and photoperiod directly for indoor runs, and keep the solar route for greenhouse runs, with two clearly named methods. |

---

# Part II - Learned models

All nine registered models are `trained-exploratory`. None is used to make a claim the product
presents as established.

## L1. `et0-emulator-v1` - reduced-input ET0 emulator (**new in this phase**)

`ml/research/train_et0_emulator.py`, artifact `ml/artifacts/et0-emulator-v1.json`

| Question | Answer |
|---|---|
| **Purpose** | Estimate ET0 from temperature, dew point, date and location alone - no radiation, no wind - so a site with only a thermometer and a weather feed's temperature fields can still get a usable water-demand driver. |
| **Formulation** | HistGradientBoostingRegressor on 9 features (Tmax, Tmin, Tdew, sin/cos of day of year, latitude, elevation, extraterrestrial radiation, daylight hours); a Ridge model as a linear reference; split conformal prediction for the interval. |
| **Inputs** | Tmax, Tmin, dew point, day of year, latitude, elevation. |
| **Outputs** | ET0 in mm/day with a 95 % conformal interval, an out-of-distribution flag and the offending features. |
| **Data source** | NASA POWER daily, 6 sites, 2018-2025, 17,021 rows. **The target is itself computed** (FAO-56 from reanalysis), so the model is emulating a formula, not learning agronomy. |
| **Calibration** | 2023 slice reserved for conformal calibration, never used in fitting. |
| **Validation** | Temporal holdout 2024-01-01..2025-10-31 (n=3,994): MAE **0.398** vs Hargreaves **0.575** (30.7 % better), climatology 0.632, R^2 0.934; conformal coverage 91.99 % at 95 % nominal. Leave-one-site-out: pooled MAE **0.659** vs Hargreaves **0.579** - **13.8 % worse**, winning on 2 of 6 sites. |
| **Limitations** | Fails the cross-site criterion. Six sites in four climate zones is a small basis for a generalising model. Out-of-distribution inputs are flagged but still answered, so a caller who ignores the flag gets an extrapolation. Intervals widen on unseen sites by an amount not quantified (conformal validity is only guaranteed under exchangeability, which LOSO breaks). |
| **Missing variables** | Radiation and wind, which are the two variables that make the problem easy; a wider set of sites, especially arid high-altitude and maritime sub-polar; hourly structure. |
| **Improvement** | (a) more sites, (b) predict a *correction to* Hargreaves rather than the level, so the model starts from the cross-site-safe baseline instead of beating it only in-distribution, (c) conformal intervals conditioned on climate zone. |
| **Deployment decision** | **Not deployed as primary.** The service returns all three methods, uses Penman-Monteith when radiation and wind are supplied, and otherwise names whichever of emulator/Hargreaves it used. Whenever the emulator is returned, the Hargreaves value is returned alongside it. |
| **Research-integrity note** | The acceptance gate as pre-declared had three criteria, all of which this model passes. The cross-site criterion was added **after** the leave-one-site-out result was seen, because the result showed the model would be misused otherwise. The amendment is documented in the trainer docstring and can only restrict use, never expand it. A reader should treat the pre-declared gate as passed and the deployed status as failed. |

## L2. `lettuce-earth-growth-v3` (and the v1/v2 lineage)

Artifacts `ml/artifacts/lettuce-earth-growth-v{1,2,3}.json`

| Question | Answer |
|---|---|
| **Purpose** | Predict fresh lettuce yield per square metre from growth duration, air and root temperature and daily light integral, for a controlled-environment lettuce crop on Earth. |
| **Formulation** | Gradient-boosted regression on `log(freshYieldGPerM2)`, with `daysAfterTransplant`, `airTemperature`, `rootTemperature`, `dailyLightIntegral`. |
| **Inputs** | Four features as above. |
| **Outputs** | log yield, exponentiated to g/m^2. |
| **Data source** | Published controlled-environment lettuce trials; the independent check is Touliatos, Dodd & McAinsh (2016). |
| **Calibration** | None beyond the fit; no hyperparameter tuning on the held-out folds. |
| **Validation** | Internal: leave-one-experiment-out, 4 folds, n=1,648 - MAE 835.5 g/m^2, R^2 0.861, MAPE **41.68 %**, bias -249.3 g/m^2. Independent: Touliatos 2016, MAPE **41.6 %** against a 30 % criterion - **failed**. |
| **Limitations** | One cultivar (Batavia Othilie), one production system. Per-area yield in the training system is higher than an ambient-CO2 greenhouse, hence the negative bias. Density enters only through the per-area identity, so density effects are not learned. |
| **Missing variables** | CO2, photoperiod as a separate axis, cultivar, nutrient management, harvest index. |
| **Improvement** | More independent studies (the literature has them; the raw data is rarely shared), and a model of density rather than a per-area assumption. |
| **Status** | Exploratory, criterion failed, failure exposed through the API's model listing. |

## L3. `mizuna-harvest-v1`

| Question | Answer |
|---|---|
| **Purpose** | Predict harvest fresh mass of mizuna from irrigation and light conditions in a spaceflight growth chamber. |
| **Formulation** | Regularised linear model on `waterSuppliedL`, `establishedPlants`, `flight`, `blue`. |
| **Inputs** | As above. |
| **Outputs** | Harvest fresh mass, grams. |
| **Data source** | VEG-04A, 14 measured harvest outcomes. |
| **Calibration** | Nested 4-fold GroupKFold with pillows kept together; inner 3-fold alpha search. |
| **Validation** | MAE 15.50 g, R^2 **-0.333** - worse than predicting the fold mean. |
| **Limitations** | 14 outcomes, one experiment. `waterSuppliedL` is a full-period retrospective quantity, so this is not a forecast and not a causal irrigation recommendation. |
| **Missing variables** | Everything about the flight environment that varies between pillows; per-pillow sensor data was not available. |
| **Improvement** | This model should not be improved, it should be **replaced or retired**. With 14 outcomes and one campaign, no modelling choice will produce a defensible predictor. It is registered and disclosed, and no product feature uses it. |
| **Status** | Exploratory, negative R^2, kept for provenance rather than use. |

## L4. `mizuna-microbial-load-v1` and `mizuna-microbial-relative-load-v2`

| Question | Answer |
|---|---|
| **Purpose** | Relate flight/light/sanitation conditions to microbial load on mizuna leaf tissue. |
| **Formulation** | v1: regression on `log10(1+CFU/g)` from flight, blue light, campaign, sanitisation, tissue fresh weight, harvest index. v2: predicts a **within-campaign z-score**, removing the campaign mean and sd so the target is relative. |
| **Inputs** | As above. |
| **Outputs** | v1 log CFU/g; v2 a z-score. |
| **Data source** | VEG-04A and VEG-04B microbial plate counts. |
| **Calibration** | 4-fold GroupKFold by pillow, nested alpha search. |
| **Validation** | v1 MAE 1.087 log units, R^2 0.549. v2 MAE 0.539 z units, R^2 0.509. |
| **Limitations** | Plate counts capture only culturable aerobic organisms. The target is not biomass, yield or shelf life, and the fresh weight in the features is the assay subsample, not harvest biomass. v2 **cannot predict an absolute level** for a new campaign without baseline samples from it. |
| **Missing variables** | Water activity, tissue age, sanitisation dose and timing, air microbial load. |
| **Improvement** | v2's relative formulation is the right idea; the next step is a hierarchical model with campaign as a random effect, which would give a partially pooled absolute prediction instead of a z-score. |

## L5. `tomato-flight-response-v1`

| Question | Answer |
|---|---|
| **Purpose** | Classify tomato tissue samples as flight or ground from gene expression, as evidence that flight conditions leave a measurable molecular signature. |
| **Formulation** | Regularised classifier over selected genes, nested grouped CV. |
| **Inputs** | Gene expression, with selection fitted inside each training fold. |
| **Outputs** | Flight/ground class and a probability. |
| **Data source** | VEG-05. |
| **Calibration** | Probability uncalibrated - stated in the artifact. |
| **Validation** | Nested stratified group CV: accuracy 0.917, macro-F1 0.916 vs 0.444 baseline, ROC-AUC 0.975. |
| **Limitations** | One experiment; flight/ground batch confounding cannot be excluded. The class is not disease, health, stress severity or biomass. |
| **Missing variables** | Replicate flights, a ground control with matched handling. |
| **Improvement** | Nothing model-side will fix confounding; a second campaign with balanced batches would. |

## L6. `radiation-exposure-osd46-v1` and `radiation-quality-osd46-v1`

| Question | Answer |
|---|---|
| **Purpose** | Test whether Arabidopsis seedlings exposed to different radiation types are separable by transcriptome, at all. |
| **Formulation** | Regularised classifier with in-fold ANOVA gene selection; permutation null and bootstrap intervals reported alongside. |
| **Inputs** | Gene expression. |
| **Outputs** | Class label (control/irradiated; or control/gamma/HZE). |
| **Data source** | OSDR OSD-46. |
| **Calibration** | None. |
| **Validation** | Leave-one-biological-group-out over 22 groups: accuracy 0.932, balanced accuracy 0.910/0.898, macro-F1 0.891/0.906. |
| **Limitations** | Ground-based irradiation of Arabidopsis, not spaceflight and not a crop. Control samples appear on only two of three array batches, so condition is partly confounded with batch (Cramer's V 0.506). Gamma 100 Gy and Fe-56 30 Gy differ in **both** quality and dose, so the classifier cannot attribute the difference to either. Three discrete conditions are not a dose-response surface. |
| **Missing variables** | A dose-matched photon control; balanced batches; a crop species. |
| **Improvement** | Report it as a separability demonstration and nothing more - which is what the artifact says. |

---

## 3. Cross-cutting validation problems

1. **The ET0 target validates a formula, not the world.** Every ET0 number in this project is
   computed from one provider's reanalysis and then compared to the same formula computed differently.
   The FAO-56 checks validate the *implementation*. Validating the *weather* needs a second source
   (ERA5-Land) and validating the *water use* needs a measurement, which does not exist in the public
   record at plant scale.
2. **Microgravity is never available as a label.** No dataset here contains growth measurements at
   gravity levels other than 1 g with matched protocols. The gravity factor is an assumption stated as
   an assumption. No result in this repository may be described as microgravity validation.
3. **Small n, grouped structure.** Every learned model sits on 6 experiments or fewer. Grouped CV is
   used everywhere (experiment, pillow, plant, biological group) because the naive alternative leaks,
   but grouped CV with 4 folds and 14 samples has very wide intervals, and the intervals that are
   reported are honest about that.
4. **Failures are visible in the product, not only in this file.** The model listing endpoint returns
   status, gate results and the deployment decision for each model. A user who asks what the lettuce
   model achieves is told 41.7 % MAPE and that the criterion is 30 %.

## 4. What would change these conclusions

| Change | Which finding it would overturn |
|---|---|
| A second ET0 source (ERA5-Land) over the same six sites | F3's context: a model calibrated on POWER may be fitting provider-specific bias |
| 20+ additional POWER sites spanning arid and sub-polar climates | F3 directly - the cross-site loss is plausibly a six-site artefact, and more sites is the cheapest test |
| A lysimeter or gravimetric water-use trial | M3 and M6 - would replace "reference flux" with measured crop water use |
| A second flight campaign with balanced ground controls | L5, L6 confounding |
| Measured harvests with recorded light and temperature | L2 - 41.7 % MAPE is a data limitation more than a modelling one |
