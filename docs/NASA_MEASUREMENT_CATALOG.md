# Phase 7 — Measurement Catalog

The twelve targets requested in Phase 7, each with the status of the evidence and
what that evidence can actually carry. This document is generated from
`data/metadata/phase7_measurement_catalog`, which is itself built from the
extraction CSVs by `scripts/build_measurement_catalog.py` — a target cannot cite a
value that was never extracted.

## Status and eligibility vocabularies

| Status | Meaning |
|---|---|
| `measured` | a number was printed in the source, with a page citation |
| `measured-approximate` | graph-read, or a stated-range midpoint |
| `measured-derivable` | not printed, but exactly recomputable from printed values |
| `not-measured` | searched for and absent from the recovered corpus |

| Eligibility | Meaning |
|---|---|
| `ready` | clean per-sample target with replication; trainable now |
| `statistical` | replicated, but too small or single-study for predictive CV |
| `mechanistic` | usable to constrain an equation, not to fit a learner |
| `plausibility-only` | bounds and signs only |
| `insufficient` | cannot support any quantitative claim |

**Headline: 8 of 12 targets are measured, 3 are genuinely absent, and not one of
the 12 is `ready` for predictive training.** That last number is the scientifically
important one.

---

## Master table

| # | Target | Status | Eligibility | Primary source | Replicates |
|---|---|---|---|---|---|
| 1 | Biomass time series | measured | statistical | TM-102784 Tables 9–10 (p.43) | 7 ages, 1 tray each |
| 2 | Fresh/dry harvest yield | measured | statistical | TM-102784 Tables 6–7 (p.40–41) | 16 trays, dry basis only |
| 3 | Water uptake | measured | plausibility-only | TM-102788 p.3, 15; TM-103494 p.12–13 | 2 studies, stand level |
| 4 | Transpiration | measured | plausibility-only | TM-102788 p.3, 15; TM-103494 p.12 | stand level only |
| 5 | Water recovery | measured-approximate | plausibility-only | TM-103494 p.12–13 | 1 study, 1 balance |
| 6 | CO₂ assimilation | measured | plausibility-only | TM-102788 p.3, 11, 12 | 2 studies, stand level |
| 7 | O₂ evolution | **not-measured** | insufficient | — | none |
| 8 | Photosynthetic response to irradiance | measured | plausibility-only | TM-102788 p.13; TM-103494 p.24 | 2 anchor points |
| 9 | PPFD / photoperiod response | measured | insufficient | TM-102788 p.7; TM-103494 p.9, 18 | 2–3 confounded points |
| 10 | Gravity-dependent growth | **not-measured** | insufficient | — | none |
| 11 | Radiation dose-response | **not-measured** | insufficient | — | none |
| 12 | Measured stress outcomes | measured | insufficient | TM-102784 p.40 footnotes; TM-103494 p.19 | 5 binary labels |

Summary: 8 measured, 1 measured-approximate, 3 not-measured; 2 statistical,
5 plausibility-only, 5 insufficient, **0 ready**.

---

## Per-target notes

**1. Biomass time series — statistical.** Seven destructive harvests at seven
distinct ages, one tray per age. A growth curve can be fitted and its residuals
characterised. It cannot be cross-validated, because every age has n = 1 and the
day-46 mass is below day 37.

**2. Fresh and dry harvest yield — statistical.** 16 trays with counts, masses and
EBI, plus a documented binary stress allocation. The unit is **dry matter**. The
simulator expresses yield as edible **fresh** weight per m², so a conversion needs
an assumed dry-matter fraction — which is exactly the kind of assumption Phase 7
is supposed to expose rather than bury. Note also that these are *wheat* seeds:
edible fraction is grain, not leaf or root, so this cannot calibrate a
lettuce/tomato/radish harvest-index parameter.

**3. Water uptake — plausibility-only.** Two studies. TM-102788 gives 4.5
L/m²/day (gas-exchange integration); TM-103494 gives 6.1 L/m²/day (condensate).
Same order, different quantity, both leak-confounded. They bound the simulator's
assumption; they do not define a response surface.

**4. Transpiration — plausibility-only.** Peak 120 L/day on 20 m² (6.0 L/m²/day at
full canopy) and cycle mean 90 L/day (4.5 L/m²/day). No per-day series exists in
the corpus, so the *shape* the simulator assumes (a canopy-cover ramp) can only be
checked qualitatively against the authors' statement that transpiration plateaued
after full ground cover and stayed flat to senescence.

**5. Water recovery — measured-approximate.** One ratio: 3615 L condensed / 3914 L
added = 0.924, over 74 days, in a chamber leaking 20–40 %/day with the added total
including plumbing losses. It is a **lower bound**, and the authors present
condensate as a transpiration proxy rather than a recovery test. The Phase 6
`blockedTargets` entry is replaced by this, with the caveat attached rather than
dropped.

**6. CO₂ assimilation — plausibility-only.** Peak 27 µmol/m²/s, mean 15, dark
respiration 7.2 (peak 13), net fixation 19.5 mol/day ≈ 860 g/day. Stand-integrated
values from ground studies. Usable for sign, order of magnitude and mass-balance
sanity; not usable to fit a response.

**7. O₂ evolution — not-measured.** Oxygen appears only in CELSS framing sentences.
Deriving an O₂ rate from the CO₂ figures is a stoichiometric *assumption*, and this
catalog refuses to relabel it as a measurement. **This stays blocked**, and it is
the one part of the Phase 6 conclusion that survives intact.

**8. Photosynthetic response to irradiance — plausibility-only.** Net CO₂
production at 60 µmol/m²/s, compensation point at 190 (≈200 at day 41), linear
increase to the 750 maximum tested. Described in prose, not tabulated. Sign and
compensation point are usable; a slope is not, because no replicate exists at any
irradiance.

**9. PPFD and photoperiod response — insufficient.** This is the most tempting
target and the most misleading. Three operating points exist (534/20 h, 660/24 h,
530/20 h) and each has a yield. But they come from different system phases with
different sealing, nutrient-control maturity, and a documented copper deficiency in
Phase IV. **Confounded in at least four ways; two or three points cannot identify a
response.** Rated insufficient despite being measured — evidence existing is not
evidence that identifies.

**10. Gravity-dependent growth — not-measured.** Every recovered report is a 1 g
ground chamber. The single 'gravity' hit is a citation. The simulator's
`microgravity_sensitivity` coefficients remain **unsupported assumptions** and are
labelled as such wherever they surface.

**11. Radiation dose-response — not-measured.** 'Radiation' in these reports means
lamp spectra, i.e. a lighting variable. No absorbed dose is paired with any plant
response. The `radiation_sensitivity` coefficients remain **unsupported
assumptions**.

**12. Measured stress outcomes — measured, but insufficient.** Water stress on
trays 1, 2, 4, 8 and Mn stress on trays 6, 7, plus a narrative account of
copper-related flag-leaf rolling. Binary labels, no severity, no stressor
measurement, no control arm. Using this as a regression target would manufacture a
label the source never measured — so it is kept as a descriptive grouping variable
and explicitly barred from training.

---

## What the catalog is for

Three downstream consumers, all of which read this catalog rather than a
hand-written claim:

1. **Part B** turns the eligibility column into a training matrix and refuses to
   train anything not rated `ready` or `statistical`.
2. **Part C** uses the plausibility-only rows as bounds on the simulator's
   assumed parameters — as *checks*, never as new output definitions.
3. **The final report** quotes the counts, so "measured" and "trainable" cannot
   drift apart in the summary.
