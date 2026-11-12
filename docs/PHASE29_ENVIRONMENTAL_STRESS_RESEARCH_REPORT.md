# Phase 29 — Environmental Stress: Research Report

**Question.** Can the platform offer a W3 workflow for environmental stress — spectral composition,
irradiance, photoperiod, CO₂, temperature, humidity — that is supported by evidence rather than by a
curve drawn through whatever data happens to be lying around?

**Answer in one paragraph.** A measured comparison over four spectral regimes is supportable from one
openly licensed trial, and that is what W3 now is. A **response surface is not supportable**: no
dataset in hand, and none found in this phase's search, varies any of those factors over a yield
response in lettuce with enough levels to fit a surface. So W3 ships as a measured comparison with
four named regimes and an explicit "unsupported" list, and the response-surface capability stays
**blocked**. This report is the evidence trail for both halves of that decision.

Artefacts: `ml/research/build_light_stress_dataset.py`,
`ml/research/build_phase29_readiness.py`, `data/processed/phase29/*`,
`data/research/phase29/environmental_stress_search`.

---

## 1. What was required before any code

The brief set an evidence-first order, and it was followed: publishers and licences verified, files
hashed, preprocessing reproducible, exclusions documented, and **no treatment value fabricated or
imputed** at any point.

| Requirement | Where it is satisfied |
|---|---|
| Controlled-environment evidence | Greenlight 2024 hydroponic trial, 35 DAS harvest, constant 200 µmol/m²/s, 16 h |
| Documented cultivar | Red Batavia, recorded in `light_spectrum_treatments.csv` |
| Documented treatments | Four named regimes with their spectral descriptions and time courses |
| PPFD / photoperiod / spectrum | 200 µmol/m²/s · 16 h · four spectral regimes (green fraction 5.08 / 24 / 16→24→32 / 16→24→32 %) |
| CO₂ / T / RH | **not reported in the deposit**, therefore not claimed; listed as unsupported |
| Growth stage | 28 and 35 DAS for fluorescence and SPAD; 35 DAS for harvest |
| Measured biomass | Destructive harvest, fresh and dry mass per plant |
| Replicates | 48–80 per regime depending on trait — unequal, and reported as such |
| Duration / units | 35 days; units taken from the workbook's own `Unit` column |
| DOI + licence | `10.5281/zenodo.20394352`, CC BY 4.0, both verified |

---

## 2. The acquired dataset

| Field | Value |
|---|---|
| Record | Zenodo 20394352 — *Optimising Spectral Composition in Hydroponic Lettuce Cultivation: The Role of Green Light, Open Data* |
| DOI | `10.5281/zenodo.20394352` |
| Licence | CC BY 4.0 (verified on the record) |
| File | `green_light_lettuce_open_data_(1).xlsx`, 94 162 bytes |
| SHA-256 | `cb79481841d520cdf741dff2a0857127817284a068fcc6f809cee8039f3b6f4c` |
| Hash verified against | `data/metadata/phase26_acquisition_manifest` |
| Sheets | `Treatment_metadata`, `Destructive_harvest`, `MultispeQ`, `Postharvest_assays` |

The hash was recomputed in Phase 29 and matched the acquisition manifest. A test asserts the raw
file still hashes to the manifest value and to the value recorded in
`data/processed/phase29/light_stress_quality`, so a silently swapped source would fail the suite.

### The design, as published

| Regime | Description | Green fraction | Spectrum fixed? | Relative planting density |
|---|---|---|---|---|
| `control` | red-blue dominant control | ≈5.08 % | yes | 1.00 |
| `t1` | fixed green fraction | 24 % | yes | 1.00 |
| `t2` | green increasing over time | 16 % → 24 % → 32 % (weeks 1–3) | no | 1.00 |
| `t3` | the t2 time course **at 1.25× density** | 16 % → 24 % → 32 % | no | 1.25 |

Common conditions across all four: 200 µmol/m²/s, 16 h photoperiod, DLI 11.52 mol/m²/day, Red
Batavia, harvest 35 days after sowing.

The tabulated green fraction for the control is marked `greenFractionIsApproximate: true` in the
treatments file, because the deposit describes it qualitatively rather than as a measured spectrum.

---

## 3. What was built, and what was deliberately not

`build_light_stress_dataset.py` produces four long-format tables plus a quality record:

| File | Contents |
|---|---|
| `light_spectrum_treatments.csv` | the design table above, with source labels preserved |
| `light_stress_harvest.csv` | 1552 rows; 252 per destructive trait; **40 for leaf area** |
| `light_stress_photosynthesis.csv` | 1476 rows; 9 traits × 164 observations at 28 / 35 DAS |
| `light_stress_pigments.csv` | 168 rows; 7 traits × 24 (upper / lower leaf) |
| `light_stress_quality` | source, licence, counts, exclusions, transformations, limits |

**Exclusions: none.** `exclusions.harvest`, `exclusions.photosynthesisMissingCells` and
`exclusions.pigments` are all empty. Nothing was imputed, nothing was unit-converted, and no outlier
was removed. The build is byte-reproducible: re-running it produces identical CSV hashes, which a
test asserts.

### The traps this data sets, and how the pipeline handles them

1. **`Destructive_harvest` is long format** (`Variable / Treatment / Observation_number_within_treatment
   / Value / Unit`). Pivoting it into a wide frame silently aligns observation numbers across
   variables, which would invent pairings. The pipeline keeps it long and never pivots.
2. **Leaf area has 10 replicates per regime against 60–80 for fresh mass.** A summary that reports
   "n = 60–80" for every trait misstates the evidence for leaf area. The quality file records
   per-trait counts and a test asserts they are unequal.
3. **`MultispeQ` rows exist at both 28 and 35 DAS with unequal n per regime.** The measurement day is
   therefore an explicit input of the workflow, not a default.
4. **t3 changes two things at once.** Spectrum *and* density. This is not a defect of the platform's
   using it — it is a defect of attributing any t3 difference to spectrum, and the workflow says so in
   the response as well as the interface.

---

## 4. The search for a response surface, and why it failed

To claim the surface is blocked rather than merely unbuilt, the search has to be recorded. It is, in
`data/research/phase29/environmental_stress_search`: endpoints, queries, result counts, the
candidates returned, and the reason each was not acquired.

**Endpoints reached without credentials:** Zenodo (`/api/records`), Dryad (`/api/v2/search`),
figshare (`/api/v2/articles`; the `/v2/articles/search` path rejects the call). Earlier phases also
established the state of FAO, NASA POWER, Copernicus CDS (needs a token), NEON, ICOS, AmeriFlux,
USDA-NAL, WorldClim, SoilGrids (502), OpenET and ESA Copernicus OData.

**Queries and verdicts**

| Query | Returned | Verdict |
|---|---|---|
| `lettuce light spectrum growth open data` | 8 | no dataset; the hits match on individual words (museum collections) |
| `lettuce photoperiod daily light integral dataset` | 8 | one relevant record (pak choi photoperiod at constant DLI), rest unrelated |
| `controlled environment lettuce PPFD response data` | 8 | two relevant records, neither carrying a yield-versus-PPFD surface |

**Candidates examined, none acquired**

| Record | Licence | Why not acquired |
|---|---|---|
| Zenodo 16271245 — *Extended Photoperiod Improves Growth and Nutritional Quality of Pak Choi Under Constant Daily Light Integral* (4.4 MB XLSX, 2025-07-21) | CC BY 4.0 | a real photoperiod axis, but in **pak choi** and at **constant DLI**. Acquiring it would extend the crop set, not validate a lettuce photoperiod response. Recorded as the most promising next acquisition. |
| Zenodo 20759414 — *Multi-Sensor High-Throughput Phenotyping Dataset of Hydroponic Lettuce under Variable Fertigation Conditions* (39.1 GB) | CC BY 4.0 | lettuce, but the varied factor is **fertigation**, not light. Also 39 GB, outside what this repository stores. |
| Zenodo 22004997 — *Dataset for Multispectral PPFD and DLI Monitoring under Dynamic Plant-Factory Lighting* (33.7 MB XLSX, 2026-08-19) | CC BY 4.0 | measures **the light, not the crop**. It could calibrate a light-delivery model; the missing quantity is the plant's response. |

**Conclusion recorded in the artefact.** A response surface needs a design varying the factor over at
least three levels with the others held or recorded. No openly licensed dataset found here varies
PPFD, photoperiod, CO₂ or temperature over a lettuce yield response. The trial in hand varies
spectral composition at one PPFD and one photoperiod: enough for a four-regime measured comparison,
nothing continuous.

---

## 5. What the evidence supports — precisely

**Supported, and shipped:**

- group means with bootstrap intervals for 16 traits across four spectral regimes;
- within-experiment Welch tests and Hedges' g against the control, for each trait and day;
- a statement that the intervals overlap for some traits and not others, per comparison;
- a disclosure that replicate plants shared a chamber, so p-values are within-experiment quantities;
- verified provenance (DOI, licence, SHA-256, record counts) travelling with every response.

**Not supported, and named as such in the API response and the UI:**

| Factor | Why unsupported |
|---|---|
| PPFD / DLI | held constant at 200 µmol/m²/s in every regime. There is no gradient to learn from. |
| Photoperiod | held constant at 16 h. Photoperiod has **no data at all** in this repository. |
| CO₂ | not varied and not reported in the deposit. |
| Air / root temperature | not varied; not reported per-plant in the deposit. |
| Humidity / VPD | not varied; not reported. |
| Continuous spectral response | two regimes hold a fixed spectrum and one of them is the control; the other two vary spectrum over time. Four points, one confound. |

A single composite stress score is also absent by choice: collapsing Fv'/Fm', PhiNO, NPQt and yield
into one index requires weights nobody measured.

---

## 6. The experiment that would move this

Named in priority order, so a future phase has a shopping list rather than a vague intention:

1. **A PPFD series in lettuce** at fixed photoperiod and spectrum, ≥ 3 levels, ≥ 20 plants each, fresh
   and dry mass, with cultivar and CO₂ recorded. This is the single highest-value acquisition: it
   would give the harvest model its missing light-intensity axis *and* the stress workflow a real
   gradient.
2. **A photoperiod series at fixed DLI.** Currently a completely empty axis.
3. **A CO₂ × temperature trial in a controlled environment.** Needed before any CO₂ claim, and the
   platform currently makes none.
4. **Independent spectral replicates** in a second facility or season, which would let the spectral
   comparison be checked rather than merely reported.

None of these is downloadable. Each is a measurement to commission, and the gap matrix says so.

---

## 7. Verdict carried into the workflow

W3 is **complete as a measured comparison** and **the response surface remains blocked**. That split
is not a compromise wording: it is what the data allow. The workflow declares
`isSimulation: false`, `evidenceClass: "measured-observation"`, one supported factor
(`greenLightFractionPct`, and even that only as four named regimes), and marks every other
environmental factor unsupported with its reason.

The corresponding gap (`environmental-stress-response-surface` in the workflow catalogue,
`led-spectrum-response` in the dataset gap matrix) was updated with this phase's evidence and its
severity was **not** lowered. See `docs/DATASET_GAP_MATRIX.md` and
`docs/PHASE29_WORKFLOW_COVERAGE_MATRIX.md`.
