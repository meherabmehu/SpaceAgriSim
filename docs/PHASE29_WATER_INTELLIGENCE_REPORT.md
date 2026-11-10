# Phase 29 — Water Intelligence Report

**What changed.** W1 answered "how much water does this canopy want today", with two demand equations
and one measured bench. Phase 29 adds the question an irrigator actually asks: **"if I deliver this
much, this often, how many days does the crop spend short of water, and how many litres go on over
the cycle?"** That needs a storage term, and it is now an optional layer on the same endpoint.

**What did not change.** `POST /api/workflows/water-demand/run` still answers on the same contract,
with every existing key, warning and caveat. The measured bench still says `arbitrated: false`. Nothing
was extrapolated to tomato or radish. No yield claim was invented.

Artefacts: `backend/app/simulation/irrigation.py`, `backend/app/workflows/water_demand.py`,
`backend/app/routes/workflows.py`, tests in `backend/tests/test_phase29_workflows.py`.

---

## 1. The addition: an FAO-56 soil water balance

Everything in `irrigation.py` is FAO-56 (Allen et al. 1998) closed form:

```
TAW = total available water in the root zone [mm]        (supplied by the caller)
RAW = p · TAW                                            (p = depletion fraction for no stress)
Ks  = 1                            if Dr ≤ RAW
Ks  = (TAW − Dr) / (TAW − RAW)     if Dr >  RAW           (eq. 84)
ETa = Ks · ETc                                            (eq. 80)
Dr(t+1) = Dr(t) + ETc(t) − I(t) − DP(t)                   (eq. 85, no rain)
```

with deep percolation occurring only when an irrigation would push depletion below zero.

The depletion fraction `p` comes from FAO-56 **Table 22**, grouped by crop type (leafy vegetables
0.30–0.40, solanaceous fruit 0.35–0.45, root and tuber vegetables), and it carries the ETc adjustment
of eq. 83 — `p_adj = p + 0.04 · (5 − ETc)` — so a dry day is not judged by a wet-day rule. Both the
base `p` and the adjusted value are returned with their source string; neither is silently assumed.

### New inputs, all optional

| Field | Unit | Range | Meaning |
|---|---|---|---|
| `totalAvailableWaterMm` | mm | 1–400 | root-zone storage between field capacity and wilting point |
| `initialDepletionMm` | mm | 0–400 | how dry the root zone already is on day one |
| `irrigationAmountMm` | mm | 0–200 | net depth delivered at the root zone per event |
| `irrigationIntervalDays` | day | 1–30 | how often that event is delivered |

Only `totalAvailableWaterMm` is required for the schedule, and even it is optional for the workflow:
without it the endpoint returns `irrigationSchedule: { available: false, reason: ... }` and the rest
of the answer is unchanged. **The workflow is complete without this layer.**

### New outputs

`totals`: days simulated, cumulative ETc and ETa (mm), relative transpiration deficit, irrigation
depth and litres, deep percolation depth and litres, number of irrigation events, stress days, and a
note that the litres are net at the root zone with pump and distribution losses not modelled.

`daily[]` (first 120 days): ETc, Ks, ETa, irrigation applied, deep percolation, depletion at day end.

`stress`: an explicit statement that the deficit **is not** a yield claim, with the reason.

`requirementIfReplacedDaily`: the depth that would exactly replace crop ET over the remaining cycle —
the zero-deficit case, for comparison against a real schedule.

---

## 2. A worked example, and why the schedule is worth having

Lettuce, 10 m², day 10 after transplant, 30/20 °C, 55 % RH, 20 MJ/m²/day, 2 m/s wind, 25 plants/m²,
TAW 40 mm, initial depletion 10 mm, 6 mm every 2 days:

| Quantity | Value |
|---|---|
| Days simulated (to end of cycle) | 25 |
| Crop ETc over the cycle | 93.1 mm |
| Actual ETa | 84.8 mm |
| **Relative transpiration deficit** | **8.92 %** |
| Irrigation applied | 78.0 mm = **780 L** over 10 m² |
| Deep percolation | 1.59 mm = 15.9 L |
| Irrigation events | 13 |
| **Stress days** | **7** |

Two diagnostics come out of this that the old single-day number could not produce: the schedule wastes
about 16 L to deep percolation, and the crop spends 7 of its 25 remaining days below the no-stress
threshold. Both are actionable, and both are arithmetic on the FAO-56 balance rather than a model.

The schedule responds the way an irrigator would expect: extending the interval from 1 to 6 days
increases both stress days and the relative transpiration deficit, and setting the irrigation depth to
zero reports the deficit the crop would run rather than an error. Tests assert both.

---

## 3. What was deliberately refused

**No yield-loss conversion.** The temptation is to take the 8.92 % transpiration deficit and turn it
into lost biomass via a FAO-33 `Ky` factor. That would be a fabricated forecast: FAO-33 publishes `Ky`
per crop group, but **no `Ky` value for this crop and this environment exists in this repository**.
The response returns the deficit, states it is a deficit, and says a yield conversion needs a
yield-response factor the platform does not hold. A test asserts the refusal is in the response.

**No weather forecast.** The schedule repeats the single supplied climate across the remaining cycle.
That is a real limitation and it is disclosed three ways: in `assumptions.climateHeldConstant`, in the
capability document under `capabilities.dailyWeatherSeries.available: false`, and in the workflow's
limitations list. A per-day weather series is named as a Phase 30 candidate rather than approximated
by holding one day constant and calling it a season.

**No rain, runoff, capillary rise or water table.** A controlled environment has none of them;
modelling them silently would be a different study.

**No extrapolation of the lettuce bench to tomato or radish.** The Schröder et al. (2021) bench is a
lettuce measurement. For other crops the workflow still computes a demand and still states that no
measurement exists.

---

## 4. What was preserved from W1, item by item

| Phase 28 property | Status |
|---|---|
| `POST /api/workflows/water-demand/run` path and request/response envelope | unchanged |
| FAO-56 Penman-Monteith with explicit fallbacks | unchanged |
| Measured / reference-calculation / estimated distinction, per evidence layer | unchanged |
| ET0-reference vs crop-relative comparison with an explanation of why they differ | unchanged |
| `agreement.arbitrated: false` | unchanged, still unarbitrated |
| Schröder bench with its denominator limits and hash verification | unchanged |
| No extrapolation to tomato/radish | unchanged |
| Every existing warning string | unchanged; two limitations were **added**, none removed |

The comparison table gained three columns (`irrigationLitres`, `stressDays`,
`relativeTranspirationDeficit`) which are `null` when no schedule was requested, so a client reading
the old columns is unaffected.

---

## 5. Geometry and validation gaps, documented rather than invented

The Schröder bench's known weakness is unchanged and still stated: the study publishes neither pot
diameter nor spacing, so converting a per-pot measurement into a per-area flux requires an assumption,
and the sign of the platform-vs-measurement discrepancy depends on which denominator you pick
(0.247× on a pot-surface basis, 2.7× on a canopy-area basis, from
`ml/evaluation/phase26_measured_et_validation.json`).

Phase 29 did **not** resolve that, and it deliberately did not let the new irrigation layer launder it:
the schedule is labelled `isReferenceCalculation: true`, `isMeasurement: false`, and the measured
bench keeps its own `comparisonCaveat`. The new layer adds a storage term and a stress-day count. It
adds no measurement.

Likewise, the depletion fraction `p` is a **tabulated literature value**, not a fitted parameter. It is
returned with its source so a reader can disagree with it.

---

## 6. Tests

| What is checked | Test |
|---|---|
| No storage term → schedule absent, workflow still complete | `test_irrigation_schedule_is_absent_without_a_storage_term` |
| The balance is a balance: ETa ≤ ETc, deficit in [0, 1], DP ≥ 0, depletion ≥ 0 | `test_irrigation_schedule_runs_a_water_balance` |
| A longer interval costs more stress days and a larger deficit | `test_irrigation_interval_changes_the_stress_burden` |
| Zero irrigation reports the deficit instead of failing | `test_no_irrigation_reports_the_deficit_rather_than_a_failure` |
| Depths are area-invariant and volumes scale with area | `test_irrigation_volume_scales_with_area` |
| The yield claim is refused in the response | `test_irrigation_schedule_refuses_a_yield_claim` |
| Impossible soil inputs are rejected with 422 | `test_irrigation_schedule_rejects_impossible_soil_inputs` |
| Every unit on the wire is registered | `test_light_stress_units_are_registered`, `test_water_and_harvest_contracts_survive_phase29` |

---

## 7. Verdict

W1 remains **complete** and its scientific status is unchanged: `research-ready`. The new irrigation
layer is a **reference calculation** that makes the workflow useful for scheduling decisions without
extending any claim beyond FAO-56 arithmetic plus caller-supplied soil parameters.

The honest summary: this phase made W1 answer a second question, and the second question's answer is
still not a measurement of anything — it is a water balance, and it says so on every response.
