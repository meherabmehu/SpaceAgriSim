# Scientific Simulation Calibration & Invariant Audit — Phase 6

Reproduce: `python scripts/calibrate_simulation.py`
Output: `docs/phase6/simulation_calibration.json`

---

## 1. What was calibrated, and what was not

The simulation's crop baselines are `harvest_biomass_g` — edible fresh biomass
per **m² per cycle**. The only measured, crop-resolved, per-area edible fresh
mass in the acquired NASA data is the EDEN ISS 2018 summary (OSD-895).

### 1.1 Normalisation policy

`harvest_biomass_g` is per m² per **cycle**. EDEN ISS values are cumulative over
a whole experiment phase whose length varies by crop (22.6 days for radish,
286 days for tomato). A direct comparison is only valid when the recorded
harvest age is close to one simulator cycle. The rule implemented:

* **Comparable** — harvest age within ±25 % of one simulator cycle → direct comparison.
* **Normalised (assumption)** — otherwise scaled by `cycleDays / harvestAgeDays`
  assuming linear accumulation. This supports *plausibility only* and is never
  treated as a calibration target.

### 1.2 Results

| Crop | Baseline (kg/m²) | Cycle (d) | EDEN ISS measured (kg/m²) | n | Evidence level | Verdict |
|---|---|---|---|---|---|---|
| **Lettuce** | 2.00 | 35 | **1.56 – 2.77** (mean 2.18) | 4 | `measured-comparable` | ✅ **retained — inside measured range** (−9.2 % vs mean) |
| Tomato | 3.50 | 80 | 3.65 – 4.17 (age-normalised) | 2 | `measured-normalised-assumption` | ⚠️ flagged (−10.5 %); suggestion recorded, not applied |
| Radish | 1.20 | 28 | 1.33 – 1.82 (mean 1.58) | 2 | `measured-comparable` | ⚠️ flagged (−23.8 %); suggestion recorded, not applied |

**Lettuce is now evidence-supported.** Its long-standing 2,000 g/m² value falls
inside the measured EDEN ISS range for four lettuce cultivars, so it is no
longer a pure guess. This is a real improvement in the platform's scientific
standing.

**Tomato and radish remain flagged.** Their suggested values
(3.91 and 1.58 kg/m²) are recorded as `proposed, NOT applied` because:

1. they would change numbers the existing UI displays (UI-preservation constraint),
2. the supporting n is 2,
3. the tomato figure additionally rests on a linear-accumulation assumption.

Promotion requires explicit owner approval.

### 1.3 What could not be calibrated, and why

| Parameter | Status | Reason |
|---|---|---|
| `growth_duration_days` | assumption | No NASA dataset records a controlled cycle length matched to these crops and hardware |
| `harvest_index` | assumption | Requires paired edible + whole-plant mass; not published in any acquired file |
| `dry_matter_fraction` | assumption | No dry-mass measurements acquired |
| `peak_water_l_per_day` | assumption | No transpiration or uptake measurement exists in the corpus |
| `optimal_light_hours` | assumption | Light recorded categorically (red/blue), never as measured PPFD × photoperiod |
| `radiation_sensitivity` | assumption | No plant-specific dose-response dataset |
| `microgravity_sensitivity` | assumption | Flight/ground is a *classification* label, not a continuous gravity response |
| gravity / radiation / light / temperature / humidity **curve shapes** | assumption | Documented placeholders with stated magnitudes |
| `WATER_RECOVERY_EFFICIENCY` | assumption | A configured loop efficiency, not a measured recovery fraction |

**These remain assumptions and are labelled as such everywhere they surface.**
No value was invented to make the simulator look calibrated.

## 2. Invariant and dimensional audit

`scripts/calibrate_simulation.py` runs **1,170 checks** across a sweep of
{3 crops} × {7, 30, 35, 60, 90 days} × {0.1, 1.0, 10.0 m²} × {space, earth}.
**All 1,170 pass.**

Checks performed:

| Group | Assertion |
|---|---|
| Non-negativity | daily standing biomass ≥ 0; cumulative ≥ 0; harvested ≥ 0 |
| Mass balance | `cumulative == harvested_through_previous_day + standing` for **every** day |
| Harvest semantics | `post_harvest_standing == 0` iff harvest day; `== standing` otherwise |
| Monotonicity | standing biomass non-decreasing **within** a cycle |
| Harvest trigger | `is_harvest_day` iff the cycle boundary is reached |
| Water | deficit ≥ 0; supplied ≤ demand; recovered ≤ supplied; `demand − deficit == supplied`; zero demand at planting |
| Carbon | O₂:CO₂ == 32/44 exactly; CO₂ fixed reconciles with whole-plant dry mass × carbon fraction × 44/12 |
| Totals | `harvested + standing == crop_yield` |
| Finiteness | no NaN/inf in any reported quantity |

A matching, permanent subset lives in
`backend/tests/test_scientific_invariants.py` (55 tests), so a future edit to the
growth or water maths cannot silently break the physics.

## 3. Defect found and fixed

### 3.1 The mass-balance identity was violated on harvest days

**Symptom.** On a harvest day the engine reported
`cumulative_biomass_g == harvested_g + biomass_g` **false**, off by exactly one
cycle's potential harvest.

Reproduced for a 35-day lettuce cycle (2,000 g/m²):

```
day=34  biomass=1995.55  cum=1995.55  harvested=   0.00   identity residual = 0.00
day=35  biomass=2000.00  cum=2000.00  harvested=2000.00   identity residual = 2000.00   <-- harvest day
day=36  biomass=   4.45  cum=2004.45  harvested=2000.00   identity residual = 0.00
```

**Root cause.** Two accounting cut-offs coexisted silently. `cumulative_biomass_g`
counts production up to the **start** of the day's harvest; `harvested_g` counts
through the **end** of it. The dataclass docstring claimed
`cumulative = standing + everything harvested so far`, which the code did not
satisfy on harvest days. The summary helper `standing_biomass_g()` derived
standing as `cumulative − harvested` (= 0 on a harvest day, correct), so it
disagreed with the per-day `biomass_g` field (= 2,000, also correct as the
pre-cut peak) — two defensible numbers, one contradictory definition.

**Fix (`backend/app/simulation/growth.py`).** Additive and non-breaking:

* added `harvested_through_previous_day_g` and `post_harvest_standing_g` fields,
* added a `mass_balance_residual_g` property that must be zero,
* corrected the docstring to state the identity that actually holds and to
  explain why the naive form does not.

**No previously emitted value changed.** `biomass_g`, `cumulative_biomass_g`,
`harvested_g`, all summary helpers, every API response field and therefore every
rendered number are identical. The full backend suite (155 tests) passes, and
the 1,170 sweep checks now pass with zero residual.

## 4. Evidence labels attached to simulation output

Every simulation quantity now carries one of these in documentation and API
metadata:

| Label | Meaning | Examples |
|---|---|---|
| **measured** | a NASA-measured value, with study id and file | OSD-655 pillow masses; OSD-780 CFU/g |
| **measured-supported baseline** | a simulator constant lying inside a measured range for that crop | lettuce `harvest_biomass_g` |
| **model estimate** | a transparent mass-balance or stoichiometric calculation | CO₂ fixed, O₂ released |
| **assumption** | a documented placeholder with stated magnitude | gravity/radiation/light response curves |
| **scenario hypothesis** | a user-configurable counterfactual | Moon/Mars gravity settings |

Measured values, calibrated estimates, uncalibrated simulation output, ML
predictions and hypothetical lunar/Martian scenarios are kept in separate fields
and are never blended into a single number presented as "the prediction".
