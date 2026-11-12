# Phase 7 — NASA Technical Report Data

What each recovered NASA report actually contains, at the level of detail needed
to judge a claim made from it. Machine-readable equivalents are in
`data/processed/` and `data/metadata/phase7_measurement_catalog`.

---

## TM-102784 — Continuous Hydroponic Wheat Production Using a Recirculating System

*Mackowiak, Owens, Hinkle & Prince, NASA TM-102784, 1989. NTRS 19900009537, 60 pp.*

**Design.** *Triticum aestivum* cv. Yecora Rojo in the Biomass Production
Chamber, nutrient-film technique with recirculating solution. 16 trays per test.
No independent replicate of the whole study; trays within a test are the
replicate unit, and one tray is a destructive harvest at a distinct age.

### Table 6 + Table 7 (p.40–41) — per-tray harvest at maturity

16 trays, ages 71–75 d, with age, height, plant/head/spikelet/seed counts, seed
mass, total biomass, non-primary heads, seeds and mass per plant, seed mass per
m² and per m³, root %, and edible biomass index.

Published means/STDs, all eight of which the extraction reproduces:

| Column | Mean | STD | Recomputed mean | Recomputed STD |
|---|---|---|---|---|
| Age (d) | 72 | 1 | 72.19 | 0.98 |
| Height (mm) | 514 | 41 | 514.12 | 41.34 |
| Plants | 271 | 27 | 270.50 | 27.17 |
| Heads | 424 | 76 | 423.69 | 76.10 |
| Spikelets | 5777 | 1033 | 5776.81 | 1033.37 |
| Seeds | 3930 | 1362 | 3930.19 | 1362.09 |
| Seed mass (g) | 123.83 | 50.46 | 123.83 | 50.46 |
| Total biomass (g) | 371 | 96 | 371.00 | 95.40 |

Tray-level stress allocation, from the table footnotes: **water stress** on trays
1, 2, 4, 8; **micronutrient stress (particularly Mn)** on trays 6 and 7. This is
the only stress label in the corpus and it is binary, not a severity measurement.

**Units.** These are **dry-matter** masses, not fresh weight. The authors state
520 g/m² seed dry matter and 1546 g/m² total plant dry matter. That matters for
calibration: the simulator's yield parameter is edible **fresh** weight per m², so
these numbers bound the dry-matter side only.

### Tables 9 + 10 (p.43) — dry matter across seven ages

Seven trays destructively harvested at 9, 18, 27, 37, 46, 54 and 63 days:

| Age (d) | DW g/m² | Root DW (g) | % root | Plants |
|---|---|---|---|---|
| 9 | 86 | 4.82 | 22.0 | 306 |
| 18 | 235 | 12.98 | 23.0 | 294 |
| 27 | 357 | 13.63 | 16.0 | 291 |
| 37 | 1052 | 21.86 | 8.7 | 256 |
| 46 | 1008 | 21.33 | 8.9 | 237 |
| 54 | 1325 | 22.93 | 7.3 | 297 |
| 63 | 1211 | 19.78 | 6.8 | 273 |

This is a real, measured **biomass time series**. It is also *one tray per age*,
so it has no within-age replication and the day-46 value sits below day 37 — a
non-monotonicity that cannot be separated from tray-to-tray variation.

**Reports supported:** a growth curve; a root-shoot partitioning trend; no
per-day resolution and no replicate at any age.

---

## TM-102788 — Carbon Dioxide and Water Exchange Rates by a Wheat Crop in NASA's Biomass Production Chamber

*Wheeler & Sager, NASA TM-102788, 1990. NTRS 19900016137, 32 pp.*

**Design.** A single 86-day wheat stand in the BPC, instrumented for continuous
CO₂ and water-vapour exchange. 20 m² stand, 112 600 L chamber, 1500 plants/m²,
photoperiod 20 h light / 4 h dark, canopy PPF 534 ± 42 µmol/m²/s, air 20.36 °C
light / 16.8 °C dark, RH 81/82 %, CO₂ setpoint 1000 ppm. Harvest 40 kg, against a
gas-exchange estimate of 44 kg — a **+10 % closure discrepancy** the authors
report themselves.

Every value below carries its page and is re-checked on every extraction build:

| Quantity | Value | Unit | Page |
|---|---|---|---|
| Transpiration peak | 120 | L/day (20 m² stand) | 3 |
| Transpiration, cycle mean | 90 | L/day | 3 |
| Transpiration, areal mean | 4.5 | L/m²/day | 15 |
| Photosynthesis peak | 27 | µmol/m²/s | 3 |
| Photosynthesis, cycle mean | 15 | µmol/m²/s | 3 |
| Dark respiration mean | 7.2 | µmol/m²/s | 3 |
| Dark respiration peak | 13 | µmol/m²/s | 11 |
| Net carbon fixed | 19.5 | mol/day | 12 |
| Net carbon fixed, mass basis | 860 | g/day | 12 |
| Light compensation point | 190 (≈200 at day 41) | µmol/m²/s | 13 |
| PPF, growth mean | 534 ± 42 | µmol/m²/s | 7 |
| PPF response range | 60 → 750, linear | µmol/m²/s | 13 |
| Harvest biomass | 40 | kg per 20 m² stand | 12 |

**What is *not* here.** No oxygen measurement. No per-day transpiration series. No
tabulated irradiance response — only the statement that net CO₂ uptake rose
linearly with PPF between 60 and 750 µmol/m²/s and crossed zero near 190–200.

---

## TM-103494 — System Development and Early Biological Tests in NASA's Biomass Production Chamber

*Wheeler, Mackowiak, Dreschel, Sager, Prince, Knott, Hinkle & Strayer, NASA
TM-103494, April 1990. NTRS 19900016140, 32 pp.*

**Design.** Five sequential system phases (I–V) in the same BPC, each with its own
sealing, nutrient-control and lighting configuration. Phase II: 660 µmol/m²/s,
24 h continuous light, 57 mol/m²/day, 1600 seeds/m², 23 °C, 65 % RH, 1000 ppm CO₂,
chamber leakage 20–40 %/day. Phase IV: 530 µmol/m²/s for 20 h/day (38 mol/m²/day),
leakage reduced to 5–10 %/day, *copper deficiency* documented in the tissue.

### The water balance — the Phase 6 "blocked" target

| Quantity | Value | Page |
|---|---|---|
| Water condensed from chamber | 3615 L | 12 |
| Water added to nutrient systems | 3914 L | 13 |
| Areal transpiration | 6.1 L/m²/day (8 m², 74 d) | 12 |
| **Implied recovered fraction** | **0.924** | derived, 12–13 |

The report states plainly that "water condensed from the air handling heat
exchangers closely represented transpiration from the wheat stand". That is the
authors' own framing: **condensate is a transpiration proxy, not a closed-loop
water-recovery test**, and in this phase the chamber was leaking 20–40 % of its
volume per day. The 0.924 figure is therefore a lower bound on what a well-sealed
system achieves, not a design target. It is recorded as `measured-approximate`,
the only approximate value in the catalog, precisely because it is a midpoint-free
single ratio with a known leak confound.

### Yield at two irradiance/photoperiod points

| Quantity | Phase II | Phase IV |
|---|---|---|
| PPF | 660 µmol/m²/s, 24 h | 530 µmol/m²/s, 20 h |
| Daily light integral | 57 mol/m²/day | 38 mol/m²/day |
| Growing area | 8 m² (32 × 0.25 m²) | 16 m² (64 trays) |
| Total biomass | 23.07 kg | 44.24 kg |
| Seed mass | 9.25 kg | — |
| Harvest index | 40 % | 29 % |
| Cycle | 74 d | 85 d |
| Biomass growth rate | 39.0 g/m²/day | 32.5 g/m²/day |
| Seed growth rate | 15.6 g/m²/day | — |
| Best four trays | 908 g biomass, 391 g seed, 50.4 / 21.7 g/m²/day | — |

The extraction recomputes all of these from primaries: 23.07 kg / 8 m² / 74 d =
39.0, 9.25 / 8 / 74 = 15.6, 9.25/23.07 = 40.1 %, 908/0.25/72 = 50.4, 3615/8/74 =
6.11 L/m²/day, 530 × 20 × 3.6 = 38.2 mol/m²/day. Every one lands on the printed
value.

**Why this does not become a photoperiod response curve.** Phase II and Phase IV
differ in irradiance *and* photoperiod *and* leakage *and* nutrient control
maturity, and Phase IV carried a documented copper deficiency. Two points
confounded in four ways cannot identify a response. The catalog accordingly rates
target 9 (PPFD/photoperiod response) as `insufficient`.

---

## N91-20026, 19900001255 and TM-109192

Surveyed and recorded, but not used as physiology evidence:

- **N91-20026** (Corey, 1990, soybean biomass production centre) — 27 pp. The
  abstract-level production claims are present but no per-tray or per-age table
  was recovered at a quality the safeguards would accept. Excluded rather than
  half-extracted.
- **19900001255** (carbon-flow mass balance) — 40 pp. Useful as context for how
  CELSS carbon accounting was done; contains no crop growth response data.
- **TM-109192** (BWT931 surface volatile organic compounds) — 68 pp. This is
  air-quality chemistry on a materials test, **not** a plant-physiology target.
  It was investigated on the strength of its numeric density and deliberately
  excluded. Recording the exclusion is as important as recording an inclusion.

## Cross-report consistency

The two independent transpiration figures — 4.5 L/m²/day (integrator-based,
TM-102788) and 6.1 L/m²/day (condensate-based, TM-103494) — are the same order of
magnitude but not the same number, and they measure different things. Both are
kept, labelled by measurement basis, and never averaged. The simulator's
`peak_water_l_per_day` is compared against the *peak* (120 L/day per 20 m² =
6.0 L/m²/day at full canopy) rather than against either mean, because that is the
quantity the parameter actually represents.
