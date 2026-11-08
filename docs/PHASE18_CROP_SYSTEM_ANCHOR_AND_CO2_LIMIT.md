# Phase 18 — NASA's space-crop reference, and the CO₂ limit the model was missing

Two more records were supplied by the owner. Both are usable, and they do different jobs:

| Record | What it is | What it was used for |
|---|---|---|
| [20250001897](https://ntrs.nasa.gov/citations/20250001897) | *Space Crop Considerations for Human Exploration* — NASA HRP technical memorandum, 82 pp, July 2024 | **An anchor.** NASA's own planning arithmetic for leafy / pick-and-eat production, which the simulator never had a yardstick for |
| [20040090155](https://ntrs.nasa.gov/citations/20040090155) | *Supraoptimal carbon dioxide effects on growth of soybean* — reprint, 1993 | **A limit.** Shows the plant response turns down above ≈1000 ppm CO₂, which the simulator's monotonic CO₂ factor does not represent |

Neither record is fitted into a model. One supplies an external yardstick, the other a
disclosure that now reaches the user at the point of use.

---

## 1. The anchor the platform was missing

Until now every external comparison in this repository was against the wheat BPC campaign —
a high-density mature crop, 5–8× above what the simulator predicts per m². That left an obvious
question open: *is the model also wrong for the leafy catch crops it actually simulates?*

The reference document answers it, twice, with the same number:

> "A small, dedicated area of about 0.030 m² … is required to grow 25 g of harvest mass of
> microgreens. Microgreens take approximately 14 days to grow … a total area of 0.84 m² would be
> needed per crew member or 3.36 m² for a four-person crew." (p. A-4)

- 25 g ÷ 0.030 m² ÷ 14 days = **59.5 g m⁻² day⁻¹** fresh
- 50 g/day ÷ 0.84 m² = **59.5 g m⁻² day⁻¹** fresh — the same figure from a second direction

Against that anchor, the simulator's own baselines:

| Crop | Fresh harvest | × anchor |
|---|---|---|
| **Lettuce** | **57.1 g m⁻² d⁻¹** | **0.96** |
| Radish | 42.9 g m⁻² d⁻¹ | 0.72 |
| Tomato | 43.8 g m⁻² d⁻¹ | 0.74 |

**Lettuce lands within 4 % of NASA's planning figure.** That is the first external evidence that a
simulator baseline is in the right place rather than merely conservative — and it is a check, not a
tune: no crop baseline was changed.

Radish and tomato sit 25–30 % below the anchor, which is the expected direction for a longer-cycle
crop compared with a 14-day microgreen catch crop, and is not treated as a defect.

## 2. The CO₂ limit

The simulator's CO₂ response is `response(c) = c / (c + 150 ppm)` normalised to 420 ppm. It is
**monotonic**: 420 ppm → 1.00, 1000 ppm → 1.18, 3000 ppm → 1.29. More CO₂ never hurts.

NASA's closed-chamber soybean work says otherwise above the optimum:

> "Seed yield and total biomass were greatest at 100 Pa for cv. McCall, suggesting that higher CO₂
> levels were supraoptimal … Average stomatal conductance of upper canopy leaves at 50 Pa CO₂
> approximately 500 Pa > 200 Pa > 100 Pa."
> — NTRS 20040090155 abstract (levels tested: 500 / 1000 / 2000 / 5000 ppm)

The platform lets a user select up to 3000 ppm. Above 1000 ppm it was silently claiming a gain that
the evidence does not support.

**What was done:** the model is **not** bent to one abstract — that would be a fabricated response
surface. Instead:

- `CO2_MEASURED_OPTIMUM_PPM = 1000.0` is now a named constant with the reason written next to it.
- Any run above it returns a warning: *"Above 1000 ppm CO₂ the model still predicts a small yield
  gain, but NASA closed-chamber soybean data show yield peaking near 1000 ppm and declining at
  2000–5000 ppm (NTRS 20040090155). No supraoptimal penalty is modelled…"*
- The coverage table gains a **CO2 supraoptimal response** row stating what the model does and does
  not represent.
- A test pins the factor exactly as it was, so the disclosure can never quietly become a silent
  model change.

If the owner later wants the factor capped at 1000 ppm, that is a one-line change plus a test
update — but it is a modelling decision, not an extraction, and it is not taken here.

## 3. What else the reference document supplied

- **Crop qualification** (Table A-3, p. 20): of **376** crops tested by KSC and Growing Beyond
  Earth, only **9** have reached Crop Readiness Level 9 — 7 leafy greens, 1 pepper, 1 radish; no
  herb, microgreen or legume. New coverage row **Crop qualification status**.
- **Volumetric productivity** (p. A-5): microgreens reach 177 g m⁻³ d⁻¹, and 298 g d⁻¹ m⁻³ on a
  50 g/day per-crew basis — "nearly double that of mature leafy greens". Recorded because the
  simulator is areal-only and cannot represent stacked production.
- **Crew area planning** (p. A-4): 0.84 m² per crew member, 3.36 m² for four — recorded for the
  same reason.

## 4. Verified results

- `backend/tests` — **620 passed, 1 skipped** (604 before this phase; +16 in
  `test_phase18_space_crop_system.py`).
- Every excerpt from the 82-page reference is checked against its cited page's text layer, the same
  treatment TM 102788 gets.
- Evidence corpus: **79 passages**, literature 27 (was 21), quarantine 0.
- Coverage table: **20 rows** (was 18).
- Assistant still returns `insufficient`, zero claims, zero citations for Moon/Mars yield questions.
- The only runtime behaviour change is the added warning above 1000 ppm CO₂; every simulated number
  is unchanged and a test asserts it.

## 5. Why there is no trained model in this phase

The request was to "train on this data". It was not done, deliberately:

- 20250001897 reports **planning arithmetic and programme status**, not per-sample growth records.
  There is nothing to train a supervised model on.
- 20040090155 is an **abstract only** (NTRS hosts no full text): it gives four CO₂ levels for two
  cultivars with no numeric yields per level. Fitting a curve to that would mean inventing the
  values in between.
- The project's existing rule — a model is only served when it was trained on a per-sample dataset
  with pinned provenance and passed validation (as with the OSD-655 mizuna work) — is exactly what
  stops this from becoming a fabricated accuracy claim.

What the records *could* support honestly was extracted: an external anchor, two coverage rows, a
runtime disclosure, and citable passages.
