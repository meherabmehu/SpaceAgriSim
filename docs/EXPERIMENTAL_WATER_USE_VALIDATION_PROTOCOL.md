# Experimental water-use validation protocol

**Purpose.** Specify the physical measurement that would close the `measured-eta` gap — the
difference between the reference evapotranspiration SpaceAgriSim computes (ET0, a weather-driven
flux from a hypothetical grass surface) and a crop's actual water use in the modelled growth
system (ETa, litres per plant per day).

**Status.** Open, blocking, and not closeable by acquiring more data. No open dataset measures
per-plant water use in a controlled-environment facility for the modelled crops. This document is
the commissioning brief for the measurement. **No trial has been performed**; every number in the
worked examples below is an illustrative calculation, not a result.

**Ready in the repository** (so the trial does not have to invent its own data format):

| Artefact | Purpose |
|---|---|
| `data/experiments/water_use_schema.json` | machine-readable schema: 23 required columns, 18 optional, per-column units and ranges, cross-field rules, quality rules, pre-registered analysis plan |
| `scripts/experiment/validate_water_use.py` | ingestion validator: 18 checks (schema, units, timestamps, ranges, cross-field, missingness, water-balance closure, replication, Kc provenance), non-zero exit on failure |
| `scripts/experiment/make_synthetic_fixture.py` | generates the clearly-labelled synthetic fixtures the validator's tests run against |
| `backend/tests/test_phase25_experimental_ingestion.py` | 31 tests, including one per defect class the validator must catch |

**Why the gap matters numerically.** The delivery report records a ~60 % difference between
weather-driven reference demand and crop-relative water demand at the same conditions. That
number is not an error to be tuned away: it is the product of a reference-surface definition
(0.12 m grass, surface resistance 70 s m⁻¹, 24 h aerodynamically closed canopy) being applied to
a plant in a substrate whose actual water loss is governed by leaf area, stomatal control,
substrate evaporation and irrigation schedule. The correct fix is a measured crop coefficient —
`Kc = ETa / ET0` measured in the target system — **not** a change to ET0 and **not** a change to
the default crop water demand. Any proposal to resolve the gap by making ET0 the default must be
rejected: it replaces a stated limitation with a false claim.

---

## 1. What must be measured

| # | Quantity | Symbol | Why it cannot be estimated | Required? |
|---|---|---|---|---|
| 1 | Actual crop water use per unit per day | ETa | Integrates transpiration + substrate evaporation over a real diurnal cycle | **required** |
| 2 | Reference ET0 at the same place and time | ET0 | Denominator of Kc; must be measured *in situ*, never taken from a reanalysis 9–28 km away | **required for Kc** |
| 3 | Model covariates | — | DLI/PPFD, photoperiod, T, RH/VPD, CO₂, EC/pH, irrigation, drainage | **required** |
| 4 | Drainage / leachate | — | In a free-draining substrate, a large part of applied water bypasses the plant; without it the balance is not closable | **required** |
| 5 | Transpiration / evaporation partition | — | Distinguishes canopy control from substrate evaporation | optional, strongly advised |
| 6 | Destructive endpoints | — | Harvest mass and leaf area, to join to the models' targets | required at harvest |

---

## 2. Equipment specification

### 2.1 Mass measurement (the primary instrument)

| Item | Specification | Rationale |
|---|---|---|
| Load cell / platform scale | Capacity 10 kg, resolution **≤ 1 g**, repeatability ≤ 0.5 g, drift ≤ 0.02 % FS/day | At 1 g resolution the balance resolves ≈1 mL. A lettuce unit using 50–200 mL d⁻¹ is then measured to ≤ 2 % — comfortably inside the 10 % closure budget. A 5 g scale would already consume half the budget. |
| Temperature compensation | Specified over 15–30 °C, or the rig is enclosed and its temperature logged | Load-cell zero drifts with temperature; an uncompensated 10 kg cell moves several grams across a 10 K swing, which is a day's signal |
| Sampling | 1-minute raw logging; 10-minute means retained for analysis | The night-time drainage plateau must be resolvable; 1 h means smear it |
| Mounting | Isolated from irrigation lines and from airflow; drainage collected off-balance | The single most common cause of an unclosable balance is a hose touching the platform |
| Calibration masses | Traceable set covering 0.1×, 0.5× and 1.0× working mass | Linearity, not just span |

### 2.2 Drainage

| Item | Specification | Rationale |
|---|---|---|
| Leachate gauge | Gravimetric receiver on a second load cell, **or** tipping bucket with ≤ 5 mL tip | At 5 mL per tip and ~50 tips d⁻¹ the quantisation error is ~5 % of a 100 mL drainage; a 20 mL bucket would be 20 % |
| Tare/empty schedule | Continuous weighing preferred; if manual, ≥ 2× daily and logged | Discrete emptying creates gaps exactly at the drainage peak |
| Recirculating systems | Reservoir on a load cell; `delta_storage_ml` then carries the reservoir term | A closed system without a weighed reservoir has no measurable drainage at all |

### 2.3 Radiation

| Item | Specification | Rationale |
|---|---|---|
| Quantum sensor (PPFD) | Cosine-corrected, calibrated within 12 months, ±5 % absolute against a reference | An uncalibrated sensor is a 20–30 % DLI error, which propagates into every light term |
| Placement | Canopy height, same plane as the canopy, ≥ 3 positions if the bench has a light gradient | One sensor in the brightest spot biases DLI high |
| Pyranometer (if ET0 is computed from measured inputs) | ISO 9060 Class C or better | Needed for the FAO-56 radiation term |

### 2.4 Air temperature, humidity, CO₂

| Item | Specification | Rationale |
|---|---|---|
| T/RH probe | Shielded and aspirated, ±0.2 K, ±2 % RH | Unshielded probes read radiative error of several K under lamps |
| Placement | Inside the canopy volume, not in the inlet airstream | The plant experiences canopy air, not supply air |
| CO₂ | NDIR, ±50 ppm | Only needed if it is held away from ambient |
| Logging | 1-minute samples, 10-minute means | VPD excursions are the modelled quantity |

### 2.5 Substrate and solution

| Item | Specification |
|---|---|
| Water potential | Capacitance or tensiometer, ≥ 2 depths per unit, calibrated per substrate batch by oven-drying at 105 °C |
| EC / pH | Handheld or inline, daily, ±0.05 dS m⁻¹ / ±0.05 pH |
| Irrigation | Per-event dosing log or flow meter, ≤ 1 mL per event resolution |

---

## 3. Measurement frequency

| Quantity | Frequency | Aggregation for the schema |
|---|---|---|
| Mass | 1 min | Daily ETa from the balance over the integration window; retained 10-min means for the plateau detection |
| Drainage | 1 min (gravimetric) / per tip (volumetric) | Daily total |
| PPFD | 1 min | Daily integral (DLI) and photoperiod mean |
| T / RH | 1 min | Daily mean, max, min, mean VPD |
| CO₂, EC, pH | 15 min / daily | Daily mean |
| Substrate water potential | 15 min | Daily mean and daily minimum |
| Reference-surface mass (if used) | 1 min | Daily ET0 |

The schema's unit is **one row per unit per day**. Higher-frequency data stays in the raw
archive and is referenced by `mass_instrument_id` / `calibration_id`; it is not squeezed into the
daily table.

---

## 4. Replication and sample size

**Minimum: 6 independent units per treatment**, two treatments, 14 days minimum (a full
transplant-to-harvest cycle is strongly preferred and is what the protocol asks for).

*Justification.* The quantity of interest is a per-unit daily water use with unit-to-unit
coefficient of variation (CV) typically 10–20 % in controlled environments. With n = 6 and
CV = 15 %, the standard error of a treatment mean is 6.1 %; with n = 3 it is 8.7 % and the 95 %
half-width roughly doubles. Since the acceptance decision compares measured ETa against a model
prediction whose own spread is of the same order, n < 6 makes the trial unable to distinguish a
real 20 % model bias from noise. These are *design* calculations from an assumed CV — the actual
CV must be reported from the trial and used to state the achieved precision, not the intended one.

**Blocking.** Randomise units within blocks (a bench or shelf), never across time. Light and
airflow gradients are spatial and stable; assigning one treatment to the sunny bench is the
single easiest way to manufacture a difference.

**Independence.** Units must not share a reservoir or a drainage path if the analysis treats them
as independent replicates. If they do, the model needs a group random effect and the effective
n is smaller than the unit count.

---

## 5. Calibration procedures

| Instrument | Before trial | During | After |
|---|---|---|---|
| Load cells | Zero and span with traceable masses at 0.1/0.5/1.0 FS; record slope, intercept, residual | Weekly zero check against a known mass; log the drift | Repeat span; a post-trial shift > 0.05 % FS invalidates the affected window |
| Tipping bucket | Deliver a known volume at a known rate; record mL per tip | Confirm tips with a graduated cylinder weekly | Repeat |
| Quantum sensor | Manufacturer certificate within 12 months; field cross-check against a second sensor | Clean weekly; log the cleaning | Repeat field cross-check; record the relative bias |
| T/RH probe | 2-point check (ice bath 0 °C / saturated NaCl 75 % RH at 20 °C) | Monthly single-point check | Repeat |
| CO₂ | Zero (N₂) and span (known gas) | Fortnightly zero | Repeat |
| Substrate water potential | Batch calibration by oven-drying at 105 °C | Spot-check per batch | — |

Every calibration is recorded with instrument serial, date, slope, intercept and residual, and
referenced from the data rows through `calibration_id`. A derived table without its calibration
records is not auditable and must not be ingested.

---

## 6. Water input and drainage measurement

The water balance per unit per day:

```
ETa = irrigation − drainage − Δstorage − residual
```

with the drainage-fraction diagnostic `DF = drainage / irrigation`.

Rules that the validator enforces:

1. `irrigation_ml`, `drainage_ml`, `delta_storage_ml` and `et_a_ml` are all required, in mL.
2. `drainage_ml > irrigation_ml` is only accepted when `delta_storage_ml` is negative enough to
   explain it.
3. The residual `irrigation − drainage − Δstorage − ETa` must be within **10 % of ETa**; days
   outside that are marked invalid and **counted**, not averaged in.
4. A closed recirculating system must still weigh the reservoir, otherwise Δstorage is unknown
   and the balance is not closed at all.
5. `et_a_ml_per_plant` is derived as `et_a_ml / plants_per_unit`; the validator recomputes it and
   flags a per-plant value outside 0–2000 mL plant⁻¹ d⁻¹ as implausible for the modelled crops.

---

## 7. Environmental logging to deliver

Achieved values, never setpoints: `t_air_mean_c`, `t_air_max_c`, `t_air_min_c`, `rh_mean_pct`,
`vpd_mean_kpa`, `co2_ppm`, `ppfd_mean_umol_m2_s` (photoperiod mean), `photoperiod_h`,
`dli_mol_m2_d`, `ec_ds_m`, `ph`, `substrate_wp_kpa`, plus `utc_offset_hours` so daily aggregates
can be placed in local solar time.

A chamber cannot hold a setpoint. The achieved series is the data; the setpoint is context. If
the two differ by more than the model's stated tolerance, that is a finding to report.

---

## 8. ET calculation and the Kc rule

1. **Measured ETa** comes from the water balance only. It is never back-calculated from a model.
2. **In-situ ET0** comes from a well-watered reference surface (or atmometer) weighed in the same
   chamber, or from a full sensor set feeding the repository's FAO-56 implementation. Which one
   was used is recorded in `et0_source`.
3. **Kc = ETa per unit area / ET0_in_situ** and is written to `kc_measured` **only** when
   `et0_source == "in_situ"`. The validator fails the run otherwise. This is the central
   integrity rule of the whole protocol: a Kc computed against a reanalysis ET0 is a
   model-to-model comparison wearing a measurement's clothes.
4. If no reference surface exists, the trial still produces measured ETa — which is the primary
   outcome — but it produces **no Kc**, and the export is only complete once `et0_source` says so.

---

## 9. Uncertainty budget

Reported per trial, with each term either measured or explicitly estimated. Targets are for a
trial intended to support a claim about per-plant water use to ±10 %.

| # | Source | Typical magnitude | How to obtain it | Effect on ETa |
|---|---|---|---|---|
| 1 | Load-cell resolution | 1 g ≈ 1 mL | Specification | ≤ 2 % of a 50 mL d⁻¹ unit; ≤ 0.5 % of 200 mL d⁻¹ |
| 2 | Load-cell calibration and drift | 0.02–0.05 % FS ≈ 1–5 g | Span/zero checks | 1–5 % if drift is not corrected; ~0 if corrected |
| 3 | Drainage quantisation | 5 mL per tip | Specification | ~5 % of drainage; 1–2 % of ETa |
| 4 | Δstorage estimate | substrate water content × bulk volume | Substrate sensor calibration | 2–5 % on days with a large WC change |
| 5 | Irrigation metering | ≤ 1 mL per event | Dosing log | < 1 % |
| 6 | Reference-surface ET0 (if used) | 3–5 % | Sensor calibration | propagates 1:1 into Kc, not into ETa |
| 7 | Time-window alignment | 1 logging interval | Timestamp audit | < 1 % if windows are exact, more if drifting |
| 8 | Biological variability (not an instrument term) | CV 10–20 % | Observed across units | Dominates the *treatment-mean* uncertainty; reported as the standard error, never folded silently into instrument error |

Combined instrument uncertainty (terms 1–5 and 7, root-sum-square, correlated terms not assumed
independent): roughly **4–8 % of daily ETa** for a well-run rig. The water-balance residual from
§6 is the empirical check on that claim: if the observed residual is larger than the budget
predicts, the budget is wrong and the larger number is the honest one.

---

## 10. Data schema, template and ingestion

* Schema: `data/experiments/water_use_schema.json` (23 required columns, 18 optional, 2 derived;
  units and physical ranges per column; cross-field rules; quality rules; pre-registered analysis
  plan).
* Template: generated, never hand-written, and **header-only**:

  ```bash
  python scripts/experiment/validate_water_use.py --emit-template trial_2027.csv
  # -> trial_2027.csv            (header + no rows, deliberately)
  # -> trial_2027.units.json
  ```

* Ingest and validate:

  ```bash
  python scripts/experiment/validate_water_use.py my_trial.csv --report my_trial_report.json
  ```

  Exit code is non-zero if any hard check fails. The **18 checks** are, in the order the validator
  reports them: units file present; required columns; undeclared columns; unit declarations; unit
  match against the schema; row parsing; required values; value ranges; enum values; cross-field
  consistency (temperature ordering, drainage versus irrigation, storage consistency, canopy-area
  plausibility, QC note requirement); row-grain uniqueness; daily continuity; timezone declared;
  optional-column missingness; water-balance closure; per-plant plausibility; replication and trial
  duration; and Kc provenance.

* Units file: a `units.json` beside the CSV, declaring each volume's unit. The validator compares
  the declaration to the schema and **rejects equivalents**: `L` against a column the schema
  defines in `mL` fails the run. This is deliberate — both parse as a number, and the
  difference is a silent factor of 1000.

---

## 11. Analysis and acceptance criteria (pre-registered)

Fixed **before** data collection, so no result is a post-hoc choice.

1. **Primary outcome.** Bias between measured ETa per plant and the product's water-demand
   prediction: `mean(ETa_measured − ETa_predicted)`, with MAE, RMSE, and a paired bootstrap 95 %
   CI (10 000 resamples, resampling units within treatment).
2. **Crop coefficient.** `Kc` per treatment with its CI and residual scatter, from in-situ ET0
   only. Kc is a fitted parameter of *this system*, not a universal constant, and is never
   presented as one.
3. **Source sensitivity.** Recompute Kc with ET0 from ERA5 hourly, ERA5-Land and NASA POWER
   (available today via `scripts/et0_validation/`) and report the spread. This quantifies how much
   of Kc's uncertainty is the weather source — and it is explicitly *not* a substitute for the
   in-situ denominator.
4. **Regime dependence.** Mixed-effects model with unit as a random intercept: does Kc differ
   between the non-limiting and deficit treatments? A significant difference means the product
   needs a stress factor, which the current models do not have.
5. **Closure.** Report the residual per day; reject days above the 10 % limit and report how many
   were rejected and why.
6. **Acceptance.** The trial is informative regardless of outcome. If measured ETa falls inside
   the product's current stated uncertainty, the limitation text may be narrowed **with the trial
   cited**. If it does not, the limitation text stays, and the measured Kc becomes a new,
   separately-versioned model input with the trial as provenance. **No threshold may be retuned to
   convert a failure into a pass**, and a failed trial may not be reported as a partial success.

---

## 12. What the result is allowed to support

| Claim | Supported by this protocol? |
|---|---|
| "Water demand per plant in this system is X mL d⁻¹" | Yes, for the tested cultivar, system, substrate and climate setpoints |
| "Kc for this crop in this system is X ± CI" | Yes, as a system-specific fitted value with an in-situ denominator |
| "The model's water-use prediction is validated for this system" | Only if the §11.6 acceptance is met and reported |
| "ET0 is wrong and should be replaced by crop demand" | **No.** ET0 is a defined reference flux; a measured ETa changes the crop coefficient, not the reference |
| "This generalises to other cultivars, substrates or facilities" | No — any extrapolation is an assumption and must be labelled |
| Anything about spaceflight or fractional gravity | **No.** This is a 1 g terrestrial controlled-environment trial |

---

## 13. Cost, schedule and what stops the trial

A six-unit, two-treatment, full-cycle lettuce trial with a load-cell rig, one quantum sensor, one
aspirated T/RH probe and a reference surface is a modest build: roughly 2–3 weeks of facility time
plus instrument lead time. The dominant risk is not money but **mass-balance hygiene** — irrigation
lines touching the balance, air movement loading the platform, and zero drift. A trial that closes
the water balance to 10 % is worth doing; one that does not is not usable, whatever its ETa says.

If the trial cannot be run, the honest state is what the product already states: ET0 is a computed
reference flux, the crop coefficient is an assumption, and per-plant water demand in litres is a
modelled quantity with an unquantified bias. That limitation must stay visible in the API response
and the UI until a measurement replaces it.
