# Phase 16 — BPC measurements as a structured table, and the simulator held against them

Phase 15 acquired the NASA Biomass Production Chamber (BPC) reports and made them citable.
This phase turns the most useful one — **TM 102788**, the 86-day wheat stand study — into a
structured table, and then uses that table for the thing the numbers were acquired for:
**comparing the simulator's per-area assumptions with real measurements.**

Two rules governed the whole phase:

1. **No fitting.** Nothing here tunes a constant, fits a coefficient, or writes back into the
   model. The simulator runs unchanged; the measurements are an external yardstick.
2. **No invented numbers.** Every value is either quoted from the report's text or computed by
   arithmetic on quoted values, and every quote is machine-checked against the pinned PDF.

---

## 1. What was extracted

`data/literature/ntrs_bpc_measurements` — schema `spaceagrisim.bpc_measurements/1`.

| Group | Count | Examples |
|---|---|---|
| `measurements` (reported) | 23 | photoperiod, PPF 534 µmol m⁻² s⁻¹, CO₂ 1000 ppm, chamber 112,600 L, stand 20 m², respiration 7.2 µmol m⁻² s⁻¹, photosynthesis peak 27 at day 25, cycle mean 15, net 19.5 mol = 860 g CO₂/day, harvest 40 kg, transpiration peak 120 L/day, mean 4.5 L m⁻² d⁻¹ |
| `derived` (arithmetic on the above) | 6 | 47.5 g CO₂ m⁻² d⁻¹ (light period), 43.0 g CO₂ m⁻² d⁻¹ (report's net), 85.5 g CO₂ m⁻² d⁻¹ peak, 6.0 L m⁻² d⁻¹ peak, 23.3 g dry m⁻² d⁻¹, 34.5 g O₂ m⁻² d⁻¹ |
| `limits` | 4 | one chamber, one cultivar, one campaign; ground-based; total biomass ≠ edible yield; whole-stand fluxes |

Each row carries: `quantity`, `value`, `unit`, `kind`, `page`, **`quote`** (verbatim from the PDF
text layer), and `reading` (same value in conventional notation).

The source `pdf_sha256` is the same digest pinned in `data/literature/ntrs_bpc`, so the
table can only ever describe the exact file the literature bundle cites.

## 2. How it is verified

`backend/tests/test_phase16_bpc_measurements.py` — 36 tests:

- **Quote-on-page**: for every one of the 23 rows, the stored quote must be a substring of the
  cited page's text layer of the pinned PDF. A transcription slip fails the build.
- **Derived rows recompute**: each of the 6 derived values is recalculated from its named inputs
  (e.g. 15 µmol m⁻² s⁻¹ × 20 h × 3600 s × 44.01 µg/µmol = 47.5 g CO₂ m⁻² d⁻¹).
- **Internal agreement**: the light-period anchor (47.5) and the report's own net figure (43.0)
  must sit inside the report's stated ~10 % gap — two independent routes to one number.
- **Provenance**: digest, NTRS id, page count, URL.
- **Guard rails**: the campaign limits must stay in the file; no row may be labelled as a lunar
  or Martian yield; the no-digitisation decision must be recorded with its reason.

## 3. What was tried and rejected: pixel-digitising the figures

The obvious second step was to read the daily time series straight off Figs. 4 and 10 (CO₂
exchange and water volume). That was attempted and **abandoned**, deliberately.

- The scans are dot plots joined by thin rules, with annotation arrows and label glyphs printed at
  the same ink density as the markers.
- Threshold-based marker detection produced 57–68 candidate points for Fig. 4 (the plot holds
  roughly 85), and a parameter sweep over three thresholds returned the same failure every time:
  **a false peak of 38.2 µmol m⁻² s⁻¹ at day 59.8**, where the report states **27 at day 25**.
  Mean net photosynthesis came out at ~20.5 against the report's stated 15.
- Shape filters (erosion cores, annulus ring detection for the open circles in Fig. 10) found the
  real markers but also swallowed annotation ink; nothing tried separated the two reliably.

A curve that the eye can see in the original but the extractor cannot reproduce within its own
stated error is not evidence. It would have put a made-up daily series into a NASA register. The
decision is recorded inside the JSON (`conventions.no_digitisation`) and pinned by a test, so it
cannot be quietly reversed later without deleting a test.

**Consequence:** the table contains only values the report states in words or numbers. Continuous
daily series remain available to a human reader at the cited pages.

## 4. The comparison

`scripts/benchmark_bpc_vs_simulation.py` runs the unchanged engine at the BPC's own operating
point (1 g, 1000 ppm CO₂, 20 h photoperiod, 534 µmol m⁻² s⁻¹, 20 °C, 80 % RH, 1 m²) and prints
the measured/modelled ratio. Output also written to `data/derived/bpc_benchmark`.

Measured anchors (20 m² wheat stand, days 0–86):

```
CO2  net 43.0   light-period 47.5   peak 85.5      g m-2 day-1
H2O  mean 4.50  peak 6.00                           L m-2 day-1
dry biomass 23.3                                    g m-2 day-1
O2  34.5 (stoichiometric on the measured CO2)        g m-2 day-1
```

Modelled, per crop, one cycle:

| crop | CO₂ g m⁻² d⁻¹ | × | water L m⁻² d⁻¹ | × | dry g m⁻² d⁻¹ | × |
|---|---|---|---|---|---|---|
| lettuce | 5.8 | 0.13 | 0.65 | 0.14 | 3.2 | 0.14 |
| radish | 6.6 | 0.15 | 0.52 | 0.12 | 3.6 | 0.15 |
| tomato | 8.0 | 0.19 | 1.15 | 0.26 | 4.4 | 0.19 |

(× = modelled / measured.)

### What this says, and what it does not

- **Says**: the platform's per-area resource fluxes are **5–8× below** what a maximally managed
  closed chamber achieved with wheat. The model is conservative, not optimistic — a useful
  property for a teaching/planning tool, and now a documented, measured statement rather than an
  impression.
- **Says**: the water anchor is the largest gap (0.12–0.26×). Lettuce at 2.5 L m⁻² d⁻¹ peak against
  the BPC's 6.0 L m⁻² d⁻¹ peak (dense wheat canopy at 534 µmol m⁻² s⁻¹) is internally consistent —
  different canopy, different crop — but the gap is now written down.
- **Does not say** the simulator is wrong, or that it should be scaled up to match. Different
  crops (wheat to grain vs lettuce/tomato/radish), different canopy density, different management
  target. Any rescaling would be a modelling decision that needs its own evidence, and doing it
  here would have been fitting to a single campaign.
- **Does not say** anything about reduced gravity, the Moon or Mars. The report is ground-based;
  the comparison is ground-based; the assistant's refusal to answer lunar/Martian yield questions
  is unchanged.

## 5. Verified results

- `backend/tests` — **604 passed, 1 skipped** (554 before this phase; +36 here and +14 in Phase 17).
- Every quote in the table is machine-verified against the pinned PDF on its cited page.
- Benchmark reproducible with one command; JSON is committed so the numbers can be inspected
  without re-running the engine.
- No runtime change: no constant, factor, crop baseline or API response was modified. The
  application behaves exactly as it did at `ac23d40`.

## 6. Where the files are

| Path | Role |
|---|---|
| `data/literature/ntrs_bpc_measurements` | the structured, quote-verified table |
| `backend/tests/test_phase16_bpc_measurements.py` | 36 verification tests |
| `scripts/benchmark_bpc_vs_simulation.py` | comparison run (no fitting) |
| `data/derived/bpc_benchmark` | committed output of that run |
| `data/raw/NTRS/19900016137.pdf` | the pinned source report (Phase 15) |

## 7. Next, in order

1. Structured extraction of the **soybean** stand report (N91-20026) the same way — it is the
   second study with daily CO₂/water exchange in text form, and a second crop widens the
   comparison without touching the model.
2. Publish the comparison in the app's coverage table (text only, no new numbers) so a user sees
   that per-area demand sits below measured closed-chamber values.
3. Deferred from earlier: Neon Postgres for durable storage; external model validation.
