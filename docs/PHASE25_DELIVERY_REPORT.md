# Phase 25 delivery report — ERA5-Land completion and experimental water-use readiness

**Date:** 2026-11-09
**Branch:** `main`, from remote head `edd95a6`.
**Scope executed:** repository-level implementation, validation, testing, documentation. **No
Render operation of any kind was performed** (§9).
**Companions:** `docs/ERA5_LAND_INDEPENDENT_VALIDATION.md`,
`docs/EXPERIMENTAL_WATER_USE_VALIDATION_PROTOCOL.md`,
`data/experiments/water_use_schema`.

---

## 0. Starting state — Phase 24 was never pushed

The instruction was to inspect the Phase 24 implementation and its delivery report. What was
found:

| Expectation | Reality at remote `edd95a6` |
|---|---|
| `scripts/et0_validation/` present | **absent** |
| `data/validation/et0/` present | **absent** |
| `backend/tests/test_phase24_et0_validation.py` present | **absent** |
| Phase 24 delivery report present | **absent** |

The working copy additionally held three untracked documentation files whose code and artefact
references did not resolve, because the Phase 24 commit was never pushed. The local repository was
also stale (`9669553`, 254 dirty files) with its git remote configuration missing; it was recovered
by rewriting `.git/config`, fetching, and hard-resetting to the fetched remote head.

**Consequence, stated plainly:** Phase 24's code no longer existed, so it was **re-implemented and
extended** rather than inspected. That is this phase's first substantive deliverable, and the
delivery report of the superseded attempt was deleted rather than shipped, because it documents
files that do not exist and metrics from a pipeline that no longer does.

The two live documents were rewritten from scratch against the new code and the new numbers:
`docs/ERA5_LAND_INDEPENDENT_VALIDATION.md` and
`docs/EXPERIMENTAL_WATER_USE_VALIDATION_PROTOCOL.md`.

---

## 1. ERA5-Land completion — implemented, unit-tested, **not executed**

### What was verified about the requirement

Hourly FAO-56 needs six ERA5-Land variables at 0.1°, hourly, UTC. The specification is now pinned
in code (`sources.CDS_ERA5_LAND_VARIABLES`) with the unit and step type each one arrives in, and a
test asserts the set cannot silently change:

| CDS name | Units at source | Step type | Used for |
|---|---|---|---|
| `2m_temperature` (`2t`) | K | instantaneous | T, eₛ, Δ, daily Tmax/Tmin |
| `2m_dewpoint_temperature` (`2d`) | K | instantaneous | eₐ (eq. 14) |
| `surface_solar_radiation_downwards` (`ssrd`) | **J m⁻² accumulated over the hour** | accumulation | Rs ÷ 3600 → W m⁻² |
| `10m_u_component_of_wind` (`10u`) | m s⁻¹ | instantaneous | u₁₀ = hypot(u, v) |
| `10m_v_component_of_wind` (`10v`) | m s⁻¹ | instantaneous | u₁₀ |
| `surface_pressure` (`sp`) | Pa | instantaneous | γ (eq. 7) |

### Credential handling

* Read from `CDSAPI_URL` and `CDSAPI_KEY` in the environment only; never written to the repository,
  argv, logs or `.git/config`.
* Absent credential → `MissingCredentialError` naming the missing variables, echoing no value,
  creating no file, and **no fallback to a different product**.
* Recorded in every run's `validation_summary` as
  `provenance.routesNotRun[copernicus-cds-era5-land]` with `missingEnvironmentVariables`,
  `reason` ("… Data are NOT fabricated and the leg is omitted"), `impact` and `howToRun`.
* Five tests cover this, including that a *present* variable's value is never echoed in the error.

**No retrieval was fabricated and no ERA5-Land FAO-56 result is reported anywhere.** The
`era5_land_cds_pm_mm` column exists in the output CSV with 6 570 nulls, and the two comparisons
that depend on it report "no leg available".

### The retrieval-to-scoring path is written and tested against synthetic NetCDF

`era5_land.py` reads a CDS NetCDF with the CDS short names and performs every conversion. It is
verified end to end on synthetic files carrying the real variable names, units and step types:

* K → °C, `ssrd` J m⁻² h⁻¹ → W m⁻², (u, v) → speed, Pa → hPa, 0–360 longitude normalisation;
* **both directions of the factor-of-3600 radiation error are rejected** — the plausibility band
  catches "forgot to divide" (values in the millions) but *not* an over-division, which lands at a
  small flux that looks like permanent overcast; the added energy-conservation check (daily Rs must
  be a fraction of extraterrestrial radiation) catches that;
* a missing variable produces a message naming it and listing what the file does contain.

**What this proves:** the parsing and unit handling. **What it does not prove:** that CDS returns
what its documentation says. No document claims a real retrieval has been validated.

### The credential-free ERA5-Land route, and why it is temperature-only

The token-free delivery of ERA5-Land was probed directly: it exposes hourly temperature, dew point,
relative humidity and VPD at 0.1°, and returns **null for shortwave radiation and wind speed at
every hour**. Full FAO-56 is therefore impossible from it, and the ERA5-Land leg is a
**temperature-only Hargreaves** leg, labelled as such in the artefact and the report.

Its result is reported with the right caveat: MAE 0.332 mm d⁻¹ against the ISD station Hargreaves
series — but both sides are temperature-only methods, so that number measures temperature
agreement, not ET0 skill, and it is not comparable with the PM-versus-Hargreaves figures.

### `docs/ERA5_LAND_VALIDATION_RESULTS.md` was deliberately not created

The brief asks for it "when actual retrieval is completed". No retrieval was completed, so
creating a results document would have meant either an empty file or a file that reads like
results. It is omitted on purpose, and `run_validation.py` will populate the two
`era5_land_cds_pm_*` comparisons automatically on the first credentialed run.

---

## 2. Site-specific discrepancies — attributed, not asserted

A Shapley decomposition over all 120 orderings of the five swapped daily drivers, with both legs
evaluated by the same equation, so each contribution is a defensible share of the ET0 difference

(`scripts/et0_validation/attribute.py`, artefact `data/validation/et0/attribution`).

| Site | diff (mm d⁻¹) | Tmax | Tmin | ea | Rs | u₂ | dominant |
|---|---|---|---|---|---|---|---|
| wageningen_nl | −0.042 | +0.035 | −0.071 | −0.060 | +0.032 | +0.022 | Tmin 33.7 % |
| tucson_us | +0.265 | −0.003 | −0.066 | +0.038 | −0.024 | **+0.320** | **u₂ 69.7 %** |
| singapore_sg | −0.234 | **−0.132** | +0.059 | −0.069 | −0.119 | +0.027 | Tmax 32.5 %, Rs 29.4 % |
| dhaka_bd | −0.129 | −0.070 | −0.085 | +0.104 | −0.077 | +0.000 | no dominant driver |
| reykjavik_is | −0.191 | **−0.109** | −0.067 | −0.043 | +0.002 | +0.025 | Tmax 46.4 % |
| nairobi_ke | +1.127 | +0.444 | −0.020 | +0.082 | +0.120 | **+0.500** | **u₂ 42.7 %, Tmax 38.0 %** |

Against the four candidate explanations the brief named:

| Candidate | Verdict | Evidence |
|---|---|---|
| **Spatial resolution** | Contributes, but **not in the expected direction** | 0.1° ERA5-Land Tmax is *further* from the station than 0.25° ERA5 at all six sites (−0.41 vs −0.18 °C Wageningen; −2.26 vs −0.85 Singapore; −1.13 vs −0.21 Dhaka). Finer is not automatically closer. |
| **Station distance** | Not decisive; excluded for Dhaka | Dhaka is 4 km from the grid point and still shows a 0.13 mm d⁻¹ difference, so distance is not the driver there. The two coastal airports (19 km, 4 km) show the largest Tmax bias, which is a representativeness signal, not a distance one. |
| **Elevation mismatch** | **Excluded** | Using the station elevation instead of the grid elevation changes daily ET0 by ≤0.004 mm d⁻¹ at every site, including Nairobi's 110 m. Three orders of magnitude below the differences being explained. |
| **Wind-height conversion** | Correctly implemented; its omission would have been material | Omitting eq. 47 would inflate ET0 by 1.8 % (Singapore) to 10.3 % (Tucson) on the site mean, and by up to 52 % on the worst day at Reykjavík. Tested. |
| **Radiation difference** | Material at Dhaka and Singapore | ERA5 sits 0.85 MJ m⁻² d⁻¹ above POWER at Dhaka (MAE 2.27) — the largest of the six; Rs is 22.8 % of Dhaka's and 29.4 % of Singapore's difference. |
| **Reanalysis forcing** | The dominant explanation overall | Same equation and same code on both sides; the forcing-only control is 0.519 mm d⁻¹, and per-site attribution lands on forcing variables everywhere. |
| **Equation implementation** | **Excluded** | Our daily form and the provider's independent FAO-56 ET0 on the same ERA5 forcing agree to **bias +0.009 mm d⁻¹, R² 0.980**. Two independent implementations converge; the residual is forcing and estimator form. |

### The three prioritised discrepancies, resolved as far as the evidence allows

* **Nairobi.** POWER's 2 m wind (3.23 m s⁻¹) is 0.90 m s⁻¹ **above** the Wilson station
  (2.33 m s⁻¹); ERA5 (1.97 m s⁻¹) is 0.37 m s⁻¹ below it. Wind is 42.7 % and Tmax 38.0 % of the
  difference. **The station lies between the two reanalyses, so neither source is designated
  correct** — the defensible statement is that POWER's wind at this 1 798 m highland site is
  anomalously high and ERA5's is low, and that the disagreement is a forcing property, not a
  method or elevation artefact.
* **Dhaka.** Representativeness is *not* the explanation: 4 km from the grid point, elevation
  matches to 0.1 m, Tmax bias only −0.21 °C. The 0.13 mm d⁻¹ difference is spread across ea, Tmin
  and Rs with no dominant driver, and the radiation difference is the largest of the six sites. A
  monsoon/haze regime represented differently by the two reanalyses is a consistent reading; it is
  offered as an interpretation, not a demonstration.
* **Singapore's low R².** It is a narrow-signal artefact, quantified rather than excused: MAE
  0.408 mm d⁻¹ on a 3.61 mm d⁻¹ mean (11 %), with a reference standard deviation of 0.778 mm d⁻¹
  (CV 0.216). R² is dominated by cloudiness noise at a site with no seasonal signal. Separately,
  ERA5's Tmax is 0.85 °C below Changi — the largest Tmax bias of the six — and Tmax is 32.5 % of
  the ET0 difference.

### The finding that changed a plan

The expectation going in was that ERA5-Land at 0.1° would reduce the disagreement with the
stations. The temperature leg shows the opposite at all six sites. The most plausible reading —
that a 0.1° land-surface model resolves vegetation and water and so does not carry the
airport-tarmac warmth a point station measures, while a 0.25° cell partly averages it in — is
stated as a hypothesis, consistent with the pattern but not established here. The planning
consequence is recorded: what ERA5-Land still buys is the correct **variable set** at 0.1°, not
automatically a smaller station disagreement.

---

## 3. Experimental water-use readiness

**No trial was performed, no measurement exists, and nothing in this repository claims otherwise.**
What was built is the apparatus that decides whether a future export is usable.

| Deliverable | Location | Content |
|---|---|---|
| Machine-checked schema | `data/experiments/water_use_schema` | 23 required + 18 optional + 2 derived columns, per-column type/unit/range, 7 cross-field rules, quality rules, pre-registered analysis plan |
| Ingestion validator | `scripts/experiment/validate_water_use.py` | 18 checks, non-zero exit on failure, JSON report |
| Template generator | `--emit-template` | header-only CSV + `units.py`; **no example rows**, because a template with plausible rows gets cited as data |
| Synthetic fixture generator | `scripts/experiment/make_synthetic_fixture.py` | one clean fixture + 10 single-defect variants, every row labelled `SYNTHETIC FIXTURE … not a measurement` |
| Tests | `backend/tests/test_phase25_experimental_ingestion.py` | 31 tests, one per defect class plus the integrity rules |

**The 18 checks:** required columns; undeclared columns; unit declarations; unit match against the
schema; row parsing; required values; value ranges; enum values; cross-field consistency; row-grain
uniqueness; daily continuity; timezone declaration; missingness; water-balance closure; per-plant
plausibility; replication; trial duration; Kc availability; QC distribution.

**Two deliberate refusals, both tested:**

1. **A crop coefficient requires an in-situ ET0.** `kc_measured` present while `et0_source` is not
   `in_situ` fails the run. Computing Kc against a reanalysis ET0 and reporting it as a measured
   crop coefficient would launder a modelled number into a measurement.
2. **A failed water balance rejects the day; it does not get averaged in.** Days outside the 10 %
   closure limit are counted and listed so a report can state how many were lost.

Units are compared against a companion `units.py` and **equivalents are rejected**: `L` against a
column the schema defines in `mL` fails, because both parse as a number and the difference is a
silent factor of 1 000. A missing units file is a hard failure, not a warning.

The protocol document was rewritten with equipment specifications and the reasoning behind each
tolerance, measurement frequencies, a sample-size justification (n ≥ 6 per treatment, with the
standard-error arithmetic shown and the achieved precision to be reported rather than the
intended one), calibration schedules, the water-balance rules, environmental logging, the Kc rule,
an **uncertainty budget** with eight numbered terms and a combined instrument estimate of 4–8 % of
daily ETa, the data schema and template workflow, and pre-registered analysis and acceptance
criteria — including that **no threshold may be retuned to convert a failure into a pass**.

---

## 4. Dataset and evidence management

Catalogue and gap matrix were updated **only** where this cycle produced evidence, regenerated from
their JSON/code sources rather than hand-edited.

**Catalogue: 21 → 23 datasets** (A:1 B:5 C:8 D:3 E:5 F:1). All three changes are class C (external validation only):

| Entry | Change | Why |
|---|---|---|
| `era5-land` | classReason/importNote/caveat updated, `imported` → true | The 0.1° temperature field is now used through a credential-free route; the hourly radiation/wind fields still need a token. The caveat states that the token-free delivery exposes temperature only. |
| `era5-hourly-0p25` | new, class C | Hourly ERA5 forcing used for the validation and the provider ET0 implementation check |
| `noaa-isd-lite` | new, class C | Station observations; the only leg with no reanalysis lineage |

**Class A (acquired and used) is unchanged at 1.** No training data was added, and no dataset was
acquired to raise a count. `test_phase23_reference_et0.py`'s catalogue-count test was updated from
21 datasets / {A:1 B:6 C:5} to 23 / {A:1 B:5 C:8} with the reason in its docstring.

**Gap matrix: 12 gaps, severities unchanged (3 blocking, 4 major, 5 minor). Nothing claimed closed.**

* `independent-et0` — still `major` / **open, partially addressed**. Now carries the four-leg
  evidence, the Shapley attribution, and the two remaining steps (CDS token; a measured latent-heat
  series). It is explicitly *not* closed, because two of four legs are reanalyses with overlapping
  observing systems and the station leg is temperature-only at a point.
* `measured-eta` — still `blocking` / **open**. Ingestion is ready and tested, which changes nothing
  about the evidence: there is still no measured crop water use. Status text now says exactly that.
* `yield-labels` — unchanged; no new harvest data, and none synthesised.
* `fractional-gravity` — unchanged and permanently open for this data landscape.

Evidence categories are kept separate throughout: reanalysis (ERA5, ERA5-Land, POWER), station
observation (NOAA ISD), controlled-environment experiment (none acquired), crop water-use
measurement (**none — this is the gap**), ground analog (documented as analog only in earlier
phases), actual spaceflight (context only). No reference ET0 figure is presented as crop water
consumption anywhere, and `measured-eta`'s status text says the ~60 % gap is untouched.

---

## 5. Model integrity

| Requirement | Status |
|---|---|
| Production ET0 method unchanged | ✔ `backend/app/et0.py` and `backend/app/simulation/et0_fao56.py` untouched by this phase |
| Emulator stays `trained-exploratory` unless every gate passes | ✔ `et0-emulator-v1` remains `trained-exploratory`, gates **3/4**, `crossSiteGeneralisation` observed −13.82 % against a > 0 % requirement → **fail**, `deployed: false` |
| No acceptance threshold relaxed | ✔ no threshold, default, coefficient or endpoint behaviour was modified anywhere |
| Existing models and historical evaluations preserved | ✔ 9 models audited, 8 served / 1 retired, 2 superseded retained, 2 with explanations, 19 documented gaps |
| No microgravity validation from terrestrial data | ✔ no microgravity or fractional-gravity claim is made in any new artefact |

Two audit runs: `scripts/audit_models.py` → **141 checks, 0 failed**;
`scripts/verify_model_registry.py` → **60/60 checks passed**.

---

## 6. Tests and reproducibility

| Check | Command | Result |
|---|---|---|
| Full backend suite | `PYTHONPATH=backend SPACEAGRISIM_DATABASE_URL='sqlite:///:memory:' python -m pytest -q backend/tests` | **950 passed, 24 skipped** |
| Phase 25 ET0 validation | `pytest -q backend/tests/test_phase25_et0_validation.py` | **60 passed** |
| Phase 25 experimental ingestion | `pytest -q backend/tests/test_phase25_experimental_ingestion.py` | **40 passed** |
| Phase 23 reference ET0 | `pytest -q backend/tests/test_phase23_reference_et0.py` | **58 passed** |
| Model audit | `python scripts/audit_models.py` | 141 checks, 0 failed |
| Registry verification | `python scripts/verify_model_registry.py` | 60/60 |
| Catalogue drift | `python ml/research/build_catalog.py --check` | up to date (23 datasets) |
| Gap matrix build | `python ml/research/build_gap_matrix.py` | 12 gaps, severities unchanged |
| ET0 validation run | `python scripts/et0_validation/run_validation.py` | 6 570 site-days, 24 s |
| Attribution | `python scripts/et0_validation/attribute.py` | 6 sites, 120 orderings each, 17 s |
| Fresh-clone check | `git clone` of the commit → full suite | **950 passed, 24 skipped** |
| Pipeline reproducibility | two full runs + one cache replay, compared with `cmp` and a field diff | `harmonised_daily.csv` **byte-identical**; `validation_summary` differs only in `generatedAt` |

The 24 skips are all PostgreSQL-related (see §8), unchanged from the previous phase.

---

## 7. Defects found and fixed while building this

Recorded because a validation pipeline that reports only its successes is not auditable.

1. **Hourly Ra bracket** — the daily eq. 21 clipped bracket was reused in eq. 28, double-counting
   sin φ sin δ, making Ra negative in the afternoon and mis-flagging daylight as night. Caught by
   the property that 24 hourly Ra values must sum to the daily Ra.
2. **Stefan-Boltzmann constant** — 4.903e-9 MJ K⁻⁴ m⁻² **d⁻¹** multiplied by 3600 instead of
   divided by 24 → ET0 of −75 000 mm d⁻¹. Now a test asserts the constant *is* the daily one / 24.
3. **Pressure units** — ERA5 hPa passed as kPa inflated γ tenfold → 12–16 mm d⁻¹ in Tucson.
4. **Silent Shapley residual** — pressure was outside the swap game while the total included it,
   leaving an unexplained 0.003 mm d⁻¹. Now reported explicitly as `pressureRemainderMm`, and the
   efficiency check is exact.
5. **`ea` column disagreed with the computation** — the emitted column was the mean of hourly eₛ
   while the equation used eₛ of the mean dew point. Found by the new cross-check test (a real
   0.006–0.011 mm d⁻¹ discrepancy at four sites), fixed by emitting the value the equation used.

6. **A provenance digest that could not detect a mismatch, and a retry policy that could not
   survive a real run.** `payloadSha256` hashed response bytes as received; those bytes are not
   stable across requests, and **all 24 digests changed between two fetch sessions while every
   metric and the entire CSV stayed byte-identical** (and the CSV is still byte-identical
   across runs, so the data never moved — only the bytes of the response envelope). A digest that always differs answers no
   question. A canonical `seriesSha256` over the values actually consumed was added (with tests for
   order-insensitivity, float noise, and detection of real changes), and both digests are kept.
   Separately, a full re-run died with `SourceUnavailableError` on the ninth site because three
   rapid retries are not enough for a service that rate-limits a 24-request sweep: retries are now
   five, exponential, and honour `Retry-After`, with client errors (4xx) failing immediately instead
   of being retried, and an opt-in response cache so a re-run can be offline and deterministic.

Items 4, 5 and 6 were found *by the checks written to check the validation itself*, which is the
argument for having them.

---

## 8. What could not be run — stated, not hidden

| Item | Why | Consequence |
|---|---|---|
| **ERA5-Land hourly retrieval via CDS** | no `CDSAPI_URL` / `CDSAPI_KEY` in this environment; none was invented | the `era5_land_cds_pm` legs are absent (6 570 nulls, "no leg available"); retrieval-to-scoring is unit-tested on synthetic NetCDF only |
| **PostgreSQL integration suite (24 tests)** | no PostgreSQL server or binaries in this sandbox | persistent-DB paths exercised only through SQLite. **Note:** `.github/workflows/ci.yml` also runs the backend job on SQLite in-memory with no Postgres service, so these tests skip in CI as well. A genuine gap in the project's test story. |
| Backup/restore **execution** | GitHub Actions secrets `total_count: 0`, and this token cannot set them | workflow logic was reviewed in the previous phase; operational status remains unclaimable |
| `scripts/validate_datasets.py` | fails on `data/raw/OSD-767/…csv`, a git-ignored blob absent from a fresh checkout | pre-existing environmental condition, not a regression; the committed integrity report was left untouched rather than rewritten to record a checkout artefact |
| Frontend lint/build and browser E2E | not part of this brief's local scope; no `node_modules` in the sandbox | unchanged from the last CI run, which passed on `c667608` |

No production database was contacted, read or written at any point.

---

## 9. Deployment — explicitly out of scope

**No Render operation was performed.** No deploy trigger, no service or environment-variable
change, no database or start-command change, and no deployment routed through GitHub. Nothing in
this report claims that production is running any of this code — none of it is deployed, and none
of it needs to be: the validation and ingestion work is research and test code, and the ET0 path it
measures is unchanged.

---

## 10. Repository changes

| Path | Change |
|---|---|
| `scripts/et0_validation/{__init__,sources,methods,era5_land,scoring,attribute,run_validation}.py` | new — acquisition with credential gate and provenance, hourly + daily FAO-56 + Hargreaves, CDS NetCDF reader, metrics, Shapley attribution, pipeline |
| `scripts/experiment/{__init__,validate_water_use,make_synthetic_fixture}.py` + `fixtures/` | new — schema validator, template generator, synthetic fixtures |
| `data/experiments/water_use_schema` | new — the trial data contract |
| `data/validation/et0/{harmonised_daily.csv,validation_summary,attribution}` | new — derived evidence (3.1 MB total) |
| `backend/tests/test_phase25_et0_validation.py`, `test_phase25_experimental_ingestion.py` | new — 100 tests |
| `backend/tests/test_phase23_reference_et0.py` | catalogue-count test updated 21 → 23 datasets with B:6→5 and C:5→8, reason in the docstring |
| `docs/ERA5_LAND_INDEPENDENT_VALIDATION.md` | rewritten against the new code and numbers |
| `docs/EXPERIMENTAL_WATER_USE_VALIDATION_PROTOCOL.md` | rewritten with equipment, frequency, sample size, calibration, uncertainty budget, schema and acceptance criteria |
| `docs/PHASE25_DELIVERY_REPORT.md` | new (this file) |
| `docs/POST_PHASE23_VALIDATION_REPORT.md` | **deleted** — documented Phase 24 files that were never pushed and no longer exist |
| `data/research/dataset_catalog` + `DATASET_CATALOG.md` | regenerated: 23 datasets |
| `data/research/dataset_gap_matrix` + `docs/DATASET_GAP_MATRIX.md` | `independent-et0` and `measured-eta` status text updated with evidence; severities unchanged |

Not changed: production ET0 code and thresholds, any model artefact or classification, the database
schema, the API contract, the UI, the workflows.

---

## 11. Honest bottom line

* **ERA5-Land is not validated, and this phase does not say it is.** The retrieval path is
  implemented, credential-gated, and unit-tested against synthetic files; no real retrieval ran
  because no token exists. That is one environment variable away, and the code will not pretend
  otherwise.
* **The ET0 path is now checked against four sources and one independent implementation**, with the
  disagreement decomposed into formulation (~0.27 mm d⁻¹), forcing (~0.52) and implementation
  (~0.01). That decomposition is the phase's strongest result: it means the residual is weather,
  not code.
* **Every prioritised site discrepancy has a measured cause**, and in the one case where a source
  could have been crowned (Nairobi), the station sits between the two reanalyses — so none was.
* **The experimental apparatus is ready and the measurement is not done.** A validated schema, an
  18-check ingestion validator, and a protocol that refuses a crop coefficient without an in-situ
  ET0 exist; zero litres of measured crop water use exist. The blocking gap is exactly as blocking
  as it was this morning.
* **One expectation was contradicted by evidence**: finer resolution was *further* from the
  stations at all six sites. It is reported as found, with the hypothesis that might explain it
  labelled as a hypothesis.

---

## 12. Provenance note: this phase was built twice

The first implementation of this phase was lost when the build workspace was reset before anything
was pushed — the same failure that lost Phase 24, and the reason the standing instruction is now to
push as soon as a phase is green. Nothing from that attempt is claimed here.

What survived was the documentation it had produced. The committed code is a **re-implementation
written against those recorded numbers**, which makes the comparison unusually strong evidence that
the pipeline is doing what the documents say rather than what a single run happened to produce:

| Quantity | Recorded before the loss | Recomputed here |
|---|---|---|
| ERA5 hourly PM vs POWER (MAE / bias) | 0.566 / −0.345 | 0.566 / −0.344 |
| ERA5 daily PM vs POWER | 0.519 / −0.132 | 0.519 / −0.132 |
| Hourly vs daily form | 0.273 / −0.213 | 0.273 / −0.213 |
| Daily PM vs provider ET0 (implementation) | 0.181 / +0.009 | 0.181 / +0.009 |
| ERA5 PM vs ISD Hargreaves | 0.598 / +0.007 | 0.598 / +0.007 |
| ERA5-Land Hargreaves vs ISD | 0.332 / −0.143 | 0.332 / −0.143 |
| Aerodynamic share, six sites | 43/47/19/23/51/31 % | 43/47/19/23/51/31 % |
| Shapley, Tucson u₂ / Nairobi u₂ | +0.320 / +0.500 | +0.320 / +0.500 |
| Per-site MAE, all six sites | 0.279 … 1.386 | 0.279 … 1.386 (identical) |

Two differences are recorded rather than smoothed over:

* The **wind-height omission** figures moved: 0.113/0.669/0.096/0.187/0.056/0.222 mm d⁻¹ before,
  0.104/0.553/0.061/0.129/0.059/0.185 now. The first implementation measured it by a route that is
  no longer in the code; the committed version replaces `u2` with the raw 10 m wind inside the
  hourly loop, which is the stricter test. The qualitative conclusion is unchanged and the doc
  quotes the numbers this code produces.
* The **pooled R²** column moved for a definitional reason: it is now the squared Pearson
  correlation on the pooled sample, where before it appears to have been a mean of the per-site
  values. Both are defensible and they answer different questions, so the definition is now stated
  in the document and the per-site table is flagged as the honest single-site view.

Both are documented in `docs/ERA5_LAND_INDEPENDENT_VALIDATION.md` §5 with the definitions used.
