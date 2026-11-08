# Phase 17 — two NASA records evaluated on request

The project owner supplied two NTRS records and asked whether they are usable. Both were
retrieved, read, and judged separately, because they answer different questions.

| Record | What it is | Verdict |
|---|---|---|
| [20160006559](https://ntrs.nasa.gov/citations/20160006559) | KSC poster: lettuce + radish under red+blue LEDs vs white fluorescent at equal PPF | **Used.** Measured endpoints, citable in the assistant, added to the light-spectrum coverage row |
| [20040087496](https://ntrs.nasa.gov/citations/20040087496) | Klassen & Bugbee (2002), ethylene sensitivity of wheat and rice in closed chambers | **Used as disclosure.** Cited, but it adds a coverage row for an unmodelled risk instead of a coefficient |

Neither record changes a single simulated number.

---

## 1. 20160006559 — the useful one

**Why it matters:** light spectrum was the platform's weakest evidence row. It said "NASA data
available but requiring processing", sourced to OSD-767/OSD-655, with no quantitative spectrum
response. This poster compares two light treatments **at equal PPF** for **lettuce and radish** —
two of the three crops the simulator models — with n = 20 plants per treatment and printed standard
deviations.

**What was extracted** (`data/literature/ntrs_supplement.json`):

| Crop | Parameter | RB (red+blue LED) | FL (white fluorescent) | Sig. |
|---|---|---|---|---|
| Lettuce | shoot length (mm) | 150.6 ± 3.145 | 178.0 ± 2.956 | *** |
| Lettuce | shoot diameter (mm) | 261.7 ± 5.843 | 314.1 ± 4.061 | *** |
| Lettuce | total fresh mass (g) | 13.09 ± 0.579 | 16.58 ± 0.919 | ** |
| Lettuce | leaf area (cm²) | 343.5 ± 14.90 | 462.7 ± 18.23 | *** |
| Lettuce | chlorophyll (g·m⁻²) | 27.77 ± 0.553 | 27.94 ± 0.549 | NS |
| Radish | shoot length (mm) | 145.8 ± 4.093 | 119.0 ± 2.800 | *** |
| Radish | shoot diameter (mm) | 272.5 ± 7.226 | 220.0 ± 4.023 | *** |
| Radish | leaf fresh mass (g) | 4.645 ± 0.221 | 3.620 ± 0.126 | *** |
| Radish | root fresh mass (g) | 20.50 ± 0.925 | 23.25 ± 0.961 | * |
| Radish | total fresh mass (g) | 25.14 ± 1.103 | 26.87 ± 1.065 | NS |
| Radish | leaf area (cm²) | 139.9 ± 7.453 | 103.6 ± 4.314 | ** |
| Radish | chlorophyll (g·m⁻²) | 47.97 ± 1.103 | 53.88 ± 0.828 | *** |

Conditions as printed: PPF ~200 µmol m⁻² s⁻¹ for both treatments, 18 h light / 6 h dark, 23 °C,
70 % RH, 1200 µmol mol⁻¹ CO₂, RB = 50 W "UFO" AIBC at 8:1 red:blue, FL = daylight T5 tri-phosphor
(CCT ~5000 K), both in one chamber behind a non-reflective black separator.

**How it is held.** The endpoints are recorded and citable, and the direction of the effect is
consistent with the poster's own summary (lettuce does better in broad spectrum; radish sends more
mass to the root under broad spectrum; total fresh mass does not differ significantly for either
crop). But **no spectrum coefficient is fitted**: two treatments cannot define a wavelength-to-yield
curve, so the simulator keeps spectrum as a recorded annotation.

**Honest caveats.** The poster has no text layer — it is a raster image. The values were read off the
rendered page, so the record hash-pins the *rendered region* (dpi 300, clip box, pixel digest)
instead of quoting text. That is weaker than Phase 16's page-quote verification, and the file says so.

## 2. 20040087496 — the one that exposes a gap

**Why it matters:** SpaceAgriSim models a sealed habitat and has **no ethylene term at all**.
Ethylene accumulates in closed chambers. This study quantifies the size of the omission:

- continuous 50 ppb ethylene: **wheat yield −36 %**, **rice yield −63 %**
- continuous 1000 ppb: both species **virtually sterile**
- exposure stopped at anthesis: much smaller losses → damage concentrates around seed set
- greenhouse, 50 ppb: **Super Dwarf wheat −60 %**, USU-Apogee not significantly affected
- elevated CO₂ (350 / 1200 / 5000 ppm) **did not change** ethylene sensitivity

**How it is held.** NTRS lists no downloadable file for this record, so only the published abstract
is used — no page-level quote is possible, and the record says exactly that. The numbers go into the
app's coverage table as a disclosed, **unmodelled** risk, and a test asserts that no ethylene term
has appeared in the simulation package. Turning one crop pair into a yield factor would have been a
fabricated coefficient.

## 3. What changed in the product

| Change | Detail |
|---|---|
| Evidence corpus | 17 → **21 literature passages** (total corpus 69 → **73**), still zero quarantined |
| Coverage table | 17 → **18 rows**: "Light spectrum" now names the acquired NASA comparison; new row "Trace-gas accumulation (ethylene)" |
| Assistant | both records are retrievable and citable with their ground-based limits attached |
| Simulator | **unchanged** — no constant, factor or crop baseline touched |
| Register PDF | new section 6 lists both records with links and how each is held |

Verified: `backend/tests` — **604 passed, 1 skipped** (590 before this phase; +14 in
`test_phase17_ntrs_supplement.py`). Moon/Mars yield questions still return `insufficient` with zero
claims and zero citations.

## 4. What is still not possible with these two records

- No lunar/Martian statement — both are ground-based.
- No spectrum response surface — two treatments, two cultivars, one campaign.
- No ethylene model — one abstract, wheat and rice only, no lettuce/tomato/radish dose-response.
- No new yield prediction of any kind.
