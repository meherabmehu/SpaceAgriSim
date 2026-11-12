# Phase 7 — Scientific Calibration

Part C asks for the simulator to be calibrated against measured data, with three
hard constraints: **do not auto-apply** Phase 6's suggested tomato (3.91 kg/m²)
and radish (1.58 kg/m²) baselines, **preserve the mass-balance invariant**, and
**preserve output definitions**.

Evidence: `docs/phase7/scientific_calibration`, produced by
`scripts/calibrate_phase7.py`. Enforced by
`backend/tests/test_phase7_calibration.py` (7 tests).

---

## 1. The policy, stated before the results

A calibration is applied **only** when the measurement is the *same physical
quantity* on the *same class of crop*. Everything else is recorded as a check.

That rule produces a result that looks like inaction and is not:

> **Zero parameters changed. Four parameters were checked, three of them
> positively. "We looked and it holds" is a different claim from "we did not
> look".**

Manufacturing a delta out of wheat data to show that Phase 7 "calibrated
something" would be exactly the failure Phase 6 was criticised for. The table
below is the alternative.

## 2. What was checked

| Parameter | Assumed | Measured | Verdict | Applied |
|---|---|---|---|---|
| `WATER_RECOVERY_EFFICIENCY` | 0.90 | 0.9236 | inside measured interval (+2.6 %) | no |
| `peak_water_l_per_day` (3 crops) | 2.0–4.5 L/m²/d | 6.0 peak / 4.5–6.1 mean (wheat) | plausibility envelope; lettuce + radish inside, tomato outside | no |
| `CARBON_FRACTION_OF_DRY_MASS` + 44/12 chain | 0.42 | 0.504 implied | within 20 % of a measured CO₂ balance | no |
| `LOGISTIC_STEEPNESS` (curve shape) | 10.0 | dry-matter series | max residual 0.147, mean 0.074 of peak | no |

### Water recovery — the assumption is *correctly conservative*

The engine assumes 90 % of supplied water is recovered as condensate. The one
measured balance in the corpus gives **0.9236** (3615 L condensed / 3914 L added).

The naive move is to "calibrate up" to 0.924. That would be backwards. The
measured chamber was **leaking 20–40 % of its volume per day**, and its added-water
total includes plumbing losses — so 0.924 is a **lower bound** on what a sealed
loop achieves. Raising the assumption toward a leak-limited lower bound would make
the simulator *less* honest, not more calibrated. A regression test
(`test_water_recovery_assumption_is_not_raised_to_a_leaking_measurement`) locks
this reasoning in so a later phase cannot do it by accident.

### Peak water demand — supports two crops, is silent on the third

Measured wheat transpiration is 6.0 L/m²/day at full canopy (120 L/day over 20 m²)
with a cycle mean of 4.5 (integrator-based) to 6.1 (condensate-based). Wheat ran
at 38–57 mol/m²/day of light; the simulator's crops run at ~15–17. Scaling
linearly by daily light integral (**an assumption, and the weakest link in this
check**):

| Crop | Simulator DLI | Assumed peak | DLI-scaled measured range | Inside? |
|---|---|---|---|---|
| Lettuce | 17.3 mol/m²/d | 2.5 L/m²/d | 2.05 – 2.77 | **yes** |
| Radish | 15.1 mol/m²/d | 2.0 L/m²/d | 1.79 – 2.43 | **yes** |
| Tomato | 17.3 mol/m²/d | 4.5 L/m²/d | 2.05 – 2.77 | **no** (1.6× above) |

The tomato result is reported rather than fixed. It is **not** evidence the
tomato assumption is wrong: tomato is a much larger plant with a longer cycle and
a lower harvest index, so a higher areal demand is entirely plausible. The
correct reading is that **a wheat stand cannot bound a tomato parameter in either
direction** — which is precisely why no change is applied. For lettuce and radish,
where the species are closer in stature, the check is genuinely supportive.

### Carbon stoichiometry — the chain is not off by an order of magnitude

The engine derives CO₂ removal from biomass via dry-matter fraction → 42 % carbon
→ 44/12. A measured 86-day CO₂ balance (860 g CO₂/day against 40 kg harvested)
implies a carbon fraction of **0.504** versus the assumed **0.42** — a 20 %
difference, comparable to the report's own 10 % harvest-versus-gas-exchange
discrepancy and inside the 0.40–0.45 range usually quoted for herbaceous tissue.

This confirms the chain is sound to within a factor of 1.2. It is recorded as a
consistency check rather than a calibration because it depends on reading the
reported 40 kg as dry matter; if that mass were fresh weight the implied fraction
would collapse and the check would be inconclusive. That sensitivity is written
into the artifact rather than resolved by assumption.

### Growth curve shape — supported, with a structural caveat

Expressed as fractions of the cycle, the measured dry-matter series tracks the
assumed logistic shape with **max residual 0.147 and mean 0.074** of peak biomass.
The residual is structural, not noise: the logistic cannot represent the
post-anthesis decline the data shows (day 54 = 1.00, day 63 = 0.91 of peak).
Fitting the steepness to seven single-tray points would be fitting the tray, not
the crop — so the assumption is retained and the agreement is recorded.

## 3. Phase 6's suggestions — explicitly declined

| Crop | Simulator now | Phase 6 suggested | Applied |
|---|---|---|---|
| Tomato | 3.50 kg/m² | 3.91 kg/m² | **no** |
| Radish | 1.20 kg/m² | 1.58 kg/m² | **no** |

Both remain at their original values, in the constants and in the evidence
artifact. Reasons, unchanged from Phase 6 and unaffected by Phase 7:

1. The suggestion rests on **n = 2** measurements from a single Antarctic
   analogue greenhouse — not ISS, lunar or Martian data.
2. It is **age-normalised** by assuming linear accumulation across a 286-day
   multi-harvest phase down to an 80-day cycle. That is a model assumption
   stacked on two points.
3. **No Phase 7 evidence changes this.** The recovered NTRS corpus contains no
   tomato or radish data at all; it is entirely wheat.

Part C's instruction not to auto-apply these is therefore satisfied by
construction, and a regression test asserts the live constants still equal the
original values.

## 4. Output definitions preserved — proven, not promised

The script hashes every output field (`crop_yield_g`, `growth_rate_g_per_day`,
`water_used_l`, `water_recovered_l`, `co2_removed_g`, `o2_produced_g`, plus all
environment factors) across a 27-scenario grid spanning 3 crops × 3 gravity/
radiation conditions × 3 resource conditions, for both space and Earth blocks:

**`outputFingerprint.sha256` = a single digest of 54 scenario blocks.**

`test_output_fingerprint_is_unchanged` recomputes it on every test run and fails
if any number, unit or field moves. A later phase that changes a baseline must
therefore regenerate the artifact and justify the diff in review. That converts
"we did not change the outputs" from a claim into a mechanism.

## 5. Mass balance preserved

54 invariant checks re-verified across the same grid, all passing:

- recovered water never exceeds supplied water;
- O₂/CO₂ keeps the engine's stoichiometric ratio to within 1e-9;
- yield is never negative.

## 6. What this phase did not calibrate, and cannot yet

- **Gravity and radiation response.** No measurement exists; the coefficients are
  labelled unsupported assumptions wherever they surface. Calibrating them would
  require a flight or irradiator experiment that this project does not have.
- **Light and photoperiod response.** Three confounded operating points, no
  series — rated `insufficient` in the measurement catalog.
- **Per-crop harvest baselines for any of the three crops.** Wheat grain dry
  matter cannot calibrate a leafy or fruiting fresh-weight baseline.
- **Water recovery for a non-leaking loop.** No such measurement was recovered.

The single most valuable thing this phase could add to the evidence base is a
*clean* water-recovery test on a sealed chamber and any replicated
partial-gravity plant-growth dataset. Neither is in NASA's recovered public
corpus.
