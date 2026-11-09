# Scientific AI & Data Intelligence Upgrade — Report

SpaceAgriSim, 2026-11-09.

This report covers one work phase: taking the existing assumption-based simulator and giving it
(a) a published, validated physical basis for water demand, (b) a learned model built on real
acquired data and evaluated honestly enough to be *rejected* for the use it was built for, (c) a
catalogue of what data exists in the world and what it would take to use it, and (d) the audit,
registry and test machinery that keeps those claims true.

Every number below is reproducible from a file in this repository. Where something was not done,
it says so in the section where a reader would expect it.

---

## 1. What existed before this phase

The simulator computed growth from a logistic curve multiplied by eight environment factors. Every
curve shape and steepness was an engineering assumption, stated as such. Nine models were
registered, all `trained-exploratory`; one had a negative R², one had failed its independent
criterion, and the API said so. There was no weather data of any kind, no water-demand physics, and
no dataset catalogue.

The gap that motivated this phase was narrow and specific: **water demand was a constant per crop.**
`peak_water_l_per_day × area × lightFactor × canopyScale` says a hot dry day and a cool humid day
need exactly the same water. That is the single most obviously wrong thing in the model, and it is
fixable with published physics and free data.

## 2. The physics, and why it is trustworthy

`backend/app/simulation/et0_fao56.py` implements FAO-56 daily Penman-Monteith (Allen et al. 1998,
eq. 6) plus the supporting equations for extraterrestrial radiation, clear-sky radiation, net
shortwave and longwave, vapour pressure, slope of the saturation curve, psychrometric constant and
wind-height conversion. Hargreaves-Samani is included as the temperature-only fallback, and daily
light integral as a light descriptor.

The equation has **no free parameters**. That is why it can be trusted where the rest of the
simulator cannot: there is nothing to fit. What must be verified is the implementation, and the
source document supplies worked examples:

| Check | Published | Computed |
|---|---|---|
| Example 17, Bangkok, monthly | 5.72 mm/day | 5.72 |
| Example 18, Uccle, daily | 3.88 mm/day | 3.88 |
| Example 20, Lyon, Hargreaves | 5.0 mm/day | 5.03 |

All three run on every import and are asserted in the test suite.

**The third check found a real bug.** The first Hargreaves implementation omitted the 0.408 factor
that converts MJ m⁻² day⁻¹ to mm day⁻¹, making the baseline 2.45× too large. Against the
Penman-Monteith target that produced an MAE of 4.66 mm/day and an R² of −4.97, which flattered
every learned model compared to it. Without a published number to check against, that error would
have shipped as a "baseline" and the comparison in section 5 would have been meaningless.

## 3. Data acquisition

Six sites, chosen for climate spread rather than convenience:

| Site | Latitude | Mean ET0 (mm/day) | Role |
|---|---|---|---|
| Wageningen, NL | 51.97 | 1.97 | temperate maritime |
| Tucson, US | 32.28 | 5.72 | hot arid, high elevation |
| Singapore, SG | 1.35 | 3.69 | equatorial humid |
| Dhaka, BD | 23.81 | 3.64 | monsoon subtropical |
| Reykjavik, IS | 64.13 | 1.03 | sub-polar maritime |
| Nairobi, KE | −1.29 | 5.17 | tropical highland |

NASA POWER daily, 2018-01-01 to 2025-10-31, **17,021 rows, 0 missing values**. Each raw response is
checksummed and recorded in `data/metadata/power_acquisition_manifest.json` with the API version
(`v2.10.3`), the request parameters and the grid elevation. Licence: no restrictions on use or
download, citation requested (verified at the POWER site and the AWS Open Data registry).

Acquisition is retried three times with backoff, the raw body is written before parsing, and fill
values (`-999.0`) become explicit missing counts rather than numbers.

## 4. Data engineering and quality

The processed dataset carries a SHA-256 that the trainer verifies before fitting and records in the
artifact. Quality checks split into **issues** (zero tolerated) and **informational** (recorded,
never removed):

- issues: missing values, duplicate dates, calendar gaps, Tmax < Tmin, out-of-physical-range
  values, supersaturation contradictions (`T2MDEW > T2M + 0.5` with `RH2M < 99`)
- informational: dew point above the daily minimum temperature

**One check was wrong and was fixed.** "Dew point above Tmin" was originally an issue. It failed
2,291 of Wageningen's 2,848 kept days and 1,394 in Reykjavik — a normal feature of humid climates,
where Tmin and Tdew are different aggregations of the same day. Demoting it is not the same as
relaxing a test: the real test is the supersaturation contradiction (dew point more than half a
degree above the daily mean while RH is below 90 %), which stays at zero tolerance. All six sites
now report **no issues**, and the 21 near-saturated rows that sit between the two thresholds are
recorded rather than hidden.

Full detail: `docs/DATA_QUALITY_AND_HARMONIZATION.md`.

## 5. The learned model, and its rejection

`et0-emulator-v1` (`ml/research/train_et0_emulator.py`) estimates ET0 from temperature, dew point,
date and location alone — no radiation, no wind — so a site with only a thermometer can still get a
water-demand driver.

| Model | Temporal holdout MAE (mm/day) | R² | Leave-one-site-out MAE |
|---|---|---|---|
| Hargreaves-Samani | 0.575 | 0.863 | **0.579** |
| Climatology | 0.632 | 0.839 | — |
| Ridge (linear) | 0.570 | 0.883 | — |
| Temperature-only GBM, 5 features | 0.513 | 0.894 | — |
| **GBM, 9 features** | **0.398** | **0.934** | 0.659 |

Temporal holdout 2024-2025: **30.7 % better than Hargreaves**. Unseen sites: **13.8 % worse**.
Conformal 95 % interval ±0.999 mm with **91.99 %** measured coverage on the holdout.

| Site (leave-one-out) | Hargreaves MAE | Emulator MAE |
|---|---|---|
| Dhaka | 0.495 | 0.628 |
| Nairobi | 0.635 | 1.003 |
| Reykjavik | 0.214 | 0.232 |
| Singapore | 0.700 | 0.520 |
| Tucson | 1.073 | 1.033 |
| Wageningen | 0.355 | 0.536 |

The emulator wins on two of six sites - the two hottest and driest, where the temperature range
carries more of the signal - and loses everywhere the weather is mild or humid.

**Decision: not deployed as primary.** The service returns three methods; when radiation and wind
are supplied it serves Penman-Monteith; otherwise it names whichever method it used and returns the
Hargreaves value beside the emulator.

**Research-integrity note.** The pre-declared acceptance gate had three criteria, all passed. The
cross-site criterion was added *after* the leave-one-site-out result was seen, because that result
showed the model would otherwise be used where it is worse than the baseline. The amendment is
disclosed in the trainer docstring, in the artifact (`addedAfterFirstRun: true`) and here, and it
can only restrict use. A reader should treat the pre-declared gate as passed and the deployed
status as failed.

## 6. Hybrid architecture

Mechanistic and learned, kept separable rather than blended:

```
weather ──► FAO-56 Penman-Monteith ──► ET0 (primary when radiation + wind are known)
       └──► GBM emulator ───────────► ET0 (when they are not; flagged, interval shown)
                                     │
                          × Kc × area × canopyScale
                                     ▼
                            crop water demand  ──► water balance ──► litres
```

The `1 mm over 1 m² = 1 litre` identity is why the conversion is one multiplication with no hidden
constant. Kc values are FAO-56 Table 12 mid-season coefficients (lettuce 1.00, tomato 1.15,
radish 0.90), stored on the crop profile. The path is **opt-in** (`et0MmPerDay` on
`POST /api/simulate`); with it absent, every number is identical to before.

## 7. API surface

| Endpoint | Purpose |
|---|---|
| `GET /api/reference-et0/estimate` | ET0 from weather inputs, all three methods, stated primary |
| `GET /api/reference-et0/model` | The model card: gates, failures, deployment decision |
| `POST /api/simulate` | Now accepts optional `et0MmPerDay` / `cropCoefficient`; returns `demandBasis` |
| `GET /api/config` | Now describes the ET0 path and lists scientific references |
| `GET /api/research/models` | Now lists 10 models including the externally served one |
| `GET /api/workflow/catalogue` | Lists the ET0 model as `external-service` with its endpoint |

Backward compatibility: new request fields are optional, new response fields are additive, and no
existing field was renamed, removed or retyped. Saved scenarios replay identically — asserted by a
test that compares default-path water demand before and after the hybrid feature exists.

## 8. Registry, catalogue and audit coherence

Adding a model served by a different runtime exposed a real gap: the registry, the research
catalogue, the workflow catalogue, the science classification and the audit each had their own idea
of "the set of models", and a model could be registered but invisible.

Fixed by making the distinction explicit everywhere:

- `research.EXTERNAL_SERVICES` declares which models are served by a dedicated endpoint, why, and
  where. `research.CATALOGUE_MODEL_IDS` is the union of runner models and those.
- Registry entries carry `servedBy`; rows carry `runnable: false`, `servedAt`, and a reason.
- `workflow.model_catalogue()` reports `runStatus: external-service` and names the endpoint;
  `POST /api/workflow/run` refuses such a model with a message pointing at the right surface.
- `scripts/audit_models.py` accepts `external-service` **only when the catalogue names the serving
  endpoint** — it cannot become a way to park a model that runs nowhere.
- `scripts/verify_model_registry.py` loads such a model through its own service rather than the JSON
  loader, and its independent-validation check is now direction-aware and per-criterion, because a
  "higher is better" improvement metric evaluated with a "lower is better" rule inverts the verdict.

Results: audit **141 checks, 0 failures**; registry verifier **60/60**; the 10-model catalogue
consistent across API, registry, classification and audit.

## 9. Scientific classification of the new surface

`et0-emulator-v1` is classified **category 4 — mechanistic calculation with explicit assumptions**,
with notes stating that the emulator is a *surrogate of a formula*, that its error is measured
against FAO-56 and never against a lysimeter, and that it loses to the physics baseline on unseen
sites. No surface claims measurement.

## 10. Dataset catalogue

`data/research/DATASET_CATALOG.md` (generated from `dataset_catalog.json`, with `--check` to prevent
drift): **21 datasets**, each with publisher, URL, format, coverage, variables, units, licence,
licence-evidence grade, commercial-use verdict and an A–F usability class.

| Class | Meaning | Count |
|---|---|---|
| A | acquired and used here | 1 (NASA POWER) |
| B | usable after preprocessing | 6 (SMAP L4, MOD13Q1, GPM IMERG, ERA5-Land, SoilGrids, CHIRPS) |
| C | external validation only | 5 |
| D | scientific reference only | 3 |
| E | needs an agreement or a licence decision | 5 |
| F | not suitable (licence prohibits use) | 1 (PlantWild, CC BY-NC-ND) |

Licence evidence is graded, not assumed: 7 verified by reading the terms, 10 from credible secondary
records, 4 unverified and labelled as unverified.

## 11. Gap matrix

`docs/DATASET_GAP_MATRIX.md` (generated from `dataset_gap_matrix.json`): **12 gaps** —
3 blocking, 4 major, 5 minor. The two that matter:

- **`measured-eta`** (blocking): no open dataset measures per-plant water use in a controlled
  environment. This is an experiment to commission, not a download.
- **`independent-et0`** (major, credential-blocked): every ET0 number traces to one provider whose
  reanalysis lineage (MERRA-2) means it cannot validate itself. ERA5-Land would fix it for the price
  of a free CDS token.

## 12. What did not change

- No model was replaced. `et0-emulator-v1` is additive; the production simulation is unchanged.
- No paid service, GPU or cloud resource was used.
- No worker count change (still `--workers 1` while the rate limiter is process-local).
- No production data was touched, and no migration was run.
- The UI was not redesigned; no frontend source file changed.

## 13. Verification performed

| Check | Result |
|---|---|
| Backend suite (SQLite) | **846 passed, 24 skipped, 0 failed** |
| Physics self-checks | 5.72 / 3.88 / 5.03 vs 5.72 / 3.88 / 5.0 |
| Model audit | 141 checks, 0 failed |
| Registry verification | 60/60 |
| Catalogue and gap-matrix drift checks | up to date |
| New endpoint smoke tests | `/api/reference-et0/estimate` 200; `/model` 200 |

Not performed: PostgreSQL run of the suite, browser E2E, frontend build. See section 17.

## 14. Errors found, and what each one taught

1. **Hargreaves missing 0.408** — a 2.45× baseline error, caught only by a published example.
2. **Dew-point quality check inverted** — a physical expectation about instantaneous values applied
   to daily aggregates.
3. **pandas non-contiguous index** in the LOSO loop — fixed with `reset_index`/boolean masks.
4. **`extra="forbid"` on the request schema** — adding optional fields is fine; forgetting the
   response schema's strict `dict[str, float]` for a new assumption entry was not, and the API
   returned 500 until fixed.
5. **Registry/catalogue divergence** — a registered model invisible to three catalogues.
6. **Inverted criterion logic in the verifier** for a higher-is-better metric.

## 15. Honest limitations

- The ET0 target is *computed* from reanalysis, so the emulator's error is measured against a
  formula, not against the world.
- Six sites cannot establish global validity; the cross-site result is the evidence for that
  limitation, not a footnote to it.
- ET0 is a reference flux for a hypothetical grass surface. It becomes crop water use only after a
  crop coefficient and a water balance, and those are not validated against measurement.
- The microgravity response remains an assumption. Nothing here is microgravity validation.
- The catalogue contains no dataset that could close the measured-ET gap, at any price.

## 16. Reproducibility

```bash
python3 ml/research/acquire_power_climate.py      # 6 sites -> data/raw/nasa_power + manifest
python3 ml/research/build_et0_dataset.py          # -> data/processed/et0_dataset.csv + QA report
python3 ml/research/train_et0_emulator.py         # -> artifact, evaluation, registry entry
python3 ml/research/build_catalog.py              # -> DATASET_CATALOG.md
python3 ml/research/build_gap_matrix.py           # -> DATASET_GAP_MATRIX.md
python3 scripts/audit_models.py --write
PYTHONPATH=backend python3 scripts/verify_model_registry.py
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

The trainer refuses to run if the dataset digest does not match the one recorded in the artifact
chain, and every acquisition is checksummed before parsing.

## 17. What remains manual

1. **Push and deploy.** No credential is present in this environment, so the work is committed
   locally and not pushed; Render deployment status is therefore unverifiable from here.
2. **PostgreSQL suite run** — needs a live database; the PG clusters in this sandbox are not a
   production mirror.
3. **Browser E2E and frontend build** — `node_modules` is not installed in this environment. No
   frontend source changed, so the risk is confined to additive API fields.
4. **CDS API token** for ERA5-Land, the highest-value remaining validation.
5. **A measured water-use trial** for `measured-eta`, which no download can replace.

## 18. Files changed

Phase 23 is commit **`d92b0a7`** (57 files, 41,030 insertions); Phase 22 is `088e339`. The full
per-file list with counts is in `docs/DELIVERY_REPORT.md` section F, derived from the commit rather
than retyped. In summary:

New: the physics module and the service (`backend/app/simulation/et0_fao56.py`,
`backend/app/et0.py`), 54 tests (`backend/tests/test_phase23_reference_et0.py`), six research
scripts, the emulator card and binary, the evaluation tables, the six raw POWER responses, the
harmonized daily series, the processed dataset and its metadata, the catalogue JSON and markdown,
the gap-matrix JSON, and the five documents.

Modified: `backend/app/{research,workflow,science_classification}.py`,
`backend/app/routes/{research,simulation,workflow}.py`, `backend/app/models/simulation.py`,
`backend/app/simulation/{water,engine,serializers,model_description}.py`,
`backend/app/config/simulation_constants.py`, both audit scripts, four existing test files, and the
two regenerated audit artefacts.

Six corrections to earlier statements are folded into these documents rather than appended: the
dataset checksum, the non-positive-ET0 row count (145, not 0), the dew-point informational counts,
the model metrics, the audit check counts, and the licence-evidence distribution.

## 19. What would change the conclusions

| Change | Effect |
|---|---|
| A second weather source (ERA5-Land) | Tests whether the emulator fits POWER's bias rather than the physics |
| 20+ more POWER sites | Directly tests whether the cross-site loss is a six-site artefact |
| A lysimeter or gravimetric water-use trial | Turns "reference flux" into measured crop water use |
| Measured harvests with recorded light and temperature | The 41.7 % MAPE on the lettuce model is a data limit, not a modelling one |
| A second flight campaign with balanced ground controls | The molecular classifiers' batch confounding |

None of these is available inside a repository. Each is named so that the next person knows exactly
which wall they are standing in front of.
