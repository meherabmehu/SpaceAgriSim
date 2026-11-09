# Data Quality and Harmonization

SpaceAgriSim, 2026-11-09. Scope: every dataset that currently enters a computation, and the rules
any future dataset must satisfy before it is allowed to.

This document describes what was actually done to the data in this repository. Where a check was
run, the artefact holding its output is named. Where a check was not run, it is listed as not run.

---

## 1. What data is in play

| Dataset | Rows | Where it lives | Enters a model? |
|---|---|---|---|
| NASA POWER daily agroclimatology, 6 sites | 17,021 | `data/raw/nasa_power/*.json`, `data/processed/power_daily/*.csv`, `data/processed/et0_dataset.csv` | yes - ET0 target and emulator features |
| NASA OSDR / GeneLab study corpus | small, per-study | `data/metadata/dataset_manifest.json` | yes - provenance only, not as a feature |
| Published lettuce light/temperature trial (PeerJ 17085) | 6 observations | `data/literature/external_lettuce_peerj17085.json` | validation only, never training |

Nothing else in `data/` feeds a computation. The catalogue at `data/research/DATASET_CATALOG.md`
lists the 21 datasets that were evaluated and why the other 18 were not imported.

## 2. Acquisition hygiene

The POWER acquirer (`ml/research/acquire_power_climate.py`) enforces four rules:

1. **Every request is retried three times with exponential backoff** on network and 5xx errors. A
   site that still fails is recorded as failed and does not silently become an absent site.
2. **The raw response is written before it is parsed.** A parse bug can be fixed and the file
   re-read; it cannot be fixed if the response was discarded.
3. **Each raw file is checksummed (SHA-256) and its byte size recorded** in
   `data/metadata/power_acquisition_manifest.json`, along with the API version (`v2.10.3`), the
   request parameters, the grid elevation and the retrieval timestamp.
4. **Fill values are converted to missing, not to numbers.** POWER uses `-999.0`.

The manifest is what makes the dataset reproducible. The processed CSV carries a checksum of
`7a95ee67752778be34ff654b45d8bf1fca54b040f7dcdc2c20a233105d1c6131`, and the trainer refuses to run
if the dataset it reads does not match the digest it records in the model artifact.

**Not done:** no resume-from-partial-download logic, because the acquirer fetches one JSON document
per site in a single request and a partial document is simply retried. If a future dataset arrives
as many files, resume support becomes mandatory and is not yet written.

## 3. Unit harmonization

Every quantity is converted at the boundary and stored in one unit, so no downstream code has to
know which provider it came from.

| Quantity | Unit stored | Notes |
|---|---|---|
| temperature | degrees C | POWER returns C for community AG; no conversion, asserted by the parameter's `units` field |
| irradiance (Rs, Ra) | MJ m^-2 day^-1 | POWER ALLSKY_SFC_SW_DWN is already MJ/m^2/day for community AG |
| wind | m s^-1 at 2 m | POWER WS2M is at 2 m; the FAO-56 eq. 47 height correction exists in the code but is a no-op for this source |
| vapour pressure | kPa | derived from dew point via FAO-56 eq. 14 |
| pressure | kPa | POWER PS; used instead of the FAO-56 standard-atmosphere estimate |
| precipitation | mm day^-1 | used only for context, never as an ET0 input |
| ET0 | mm day^-1 | the FAO-56 native unit; multiplied by crop area to reach litres |

The one conversion that caused a real bug is documented in section 7.

## 4. Vapour pressure: dew point, not relative humidity

FAO-56 offers two routes to actual vapour pressure:

- eq. 14 from dew point: `ea = 0.6108 * exp(17.27*Tdew / (Tdew+237.3))`
- eq. 17 from relative humidity, or eq. 19 from RHmax/RHmin.

The pipeline uses **dew point**, because:

1. Dew point is a temperature, so it is conserved through the day and does not have the
   aggregation problem that relative humidity has - averaging two RH values is not the RH at the
   average temperature.
2. POWER supplies `T2MDEW` directly, so no assumption is needed.
3. Where a caller supplies relative humidity instead (the API accepts either), the service derives
   dew point with the Magnus formula and returns the derived value in `inputs.tdewC` so the caller
   can see what was used.

`ea` is clamped to be no greater than the saturation vapour pressure at the daily mean temperature,
so VPD cannot go negative and the aerodynamic term cannot invert.

## 5. Quality checks, and what counts as an issue

`build_et0_dataset.py::quality_checks()` returns two dictionaries: **issues**, which are hard
failures worth stopping for, and **informational**, which are expected features of the data that
must not be "fixed".

### Issues (zero tolerated)

| Check | Why it is an issue | Result on the delivered dataset |
|---|---|---|
| missing values per parameter | a missing input silently becomes a wrong ET0 | 0 |
| duplicate dates | two rows for one day double-counts it | 0 |
| calendar gaps | a missing day breaks the daily series a model learns from | 0 |
| Tmax < Tmin | physically impossible | 0 |
| values outside physical range (Rs < 0 or > 50 MJ/m^2/day, RH outside [0,100], wind < 0, pressure outside [50,110] kPa, temperature outside [-90,60] C) | a sensor or encoding failure | 0 |
| `T2MDEW > T2M + 0.5` with `RH2M < 90` | supersaturation with a clearly non-saturated humidity reading is a contradiction | 0 |

Every one of the six sites reports `qualityIssues: {}` in `ml/evaluation/et0_dataset_quality.json`.

### Informational (recorded, never removed)

| Check | Why it is informational | Observed |
|---|---|---|
| dew point above the daily minimum temperature | Tmin and Tdew are different aggregations of the same day and cross routinely in humid climates; the crossing is a real feature of the atmosphere, not a data error | Wageningen 2,291 of 2,848 days, Dhaka 1,529, Reykjavik 1,394, Nairobi 297, Singapore 103, Tucson 21 |
| dew point above the daily *mean* temperature within a near-saturated day | A daily mean dew point more than 0.5 degC above the daily mean temperature while RH was at least 90 %: the shape a saturated marine day takes once compressed into daily aggregates. The ET0 computation clamps the dew point to the daily mean and flags the row in `tdewClamped`; the row is kept because the weather is real | 21 rows of 17,021 (Wageningen 5, Reykjavik 16) |

**This check was initially coded as an issue and it was wrong.** Had it stayed an issue it would
have failed 2,291 of Wageningen's 2,848 days, 1,529 in Dhaka and 1,394 in Reykjavik, so the QA
report would have read as if the wettest sites in the set were the most broken. The mistake was
treating a physical expectation about instantaneous values as though it applied to daily aggregates.
The corrected test is the supersaturation contradiction in the table above - the same physical
intuition, applied where it is actually valid: dew point above the mean temperature *while* the
humidity reading says the air is not saturated. This is recorded because a reader should know the
"0 issues" result was reached by fixing a broken test, not by relaxing a real one.

## 6. Date and time alignment

- Dates are stored as ISO `YYYY-MM-DD`, UTC day boundaries, no local-time shift. POWER daily data is
  defined on UTC days, so shifting to local time would create and destroy days at the boundary
  without improving the daily ET0 calculation.
- The day of year used in the extraterrestrial-radiation calculation is the **calendar** day number,
  not a water-year offset. Leap years are handled by the calendar library rather than by an
  arithmetic assumption.
- Each site's series is checked for the expected number of days between its first and last date;
  2,861 days for 2018-01-01 to 2025-10-31 inclusive is asserted, which is how the calendar-gap check
  is enforced at the series level as well as the row level.

## 7. The Hargreaves units bug (recorded in full)

The first implementation of Hargreaves-Samani used

```
ET0 = 0.0023 * Ra * (Tmean + 17.8) * sqrt(Tmax - Tmin)
```

with `Ra` in MJ m^-2 day^-1. That is wrong by the factor 0.408 (the latent heat conversion from
MJ m^-2 day^-1 to mm day^-1), and it made the baseline 2.45x too large: MAE 4.66 mm/day against the
Penman-Monteith target, with R^2 of -4.97.

The unit error was caught by checking against the worked comparison in the source document itself:
FAO-56 chapter 4, Example 20, states that Hargreaves predicts **5.0 mm/day** for Lyon in July. The
implementation returned roughly 2.45 times that (about 12.3 mm/day). With the 0.408 factor it returns
5.03.

Two consequences, both recorded:

- **The scope of the pipeline: it is a validation, not a formality.** `run_published_examples()` now
  checks Examples 17 (5.72), 18 (3.88) and 20 (5.0) on every import of the physics module, and the
  test suite asserts all three.
- **The effect on the model comparison.** Before the fix, the learned emulator looked better than
  the baseline by an implausible margin. After the fix the honest numbers are +30.7 % better on the
  temporal holdout and **-13.8 % worse on unseen sites**, which is the result the model is judged
  on. A baseline that is wrong by 2.45x flatters every model compared to it.

## 8. Dropped rows

ET0 <= 0 is not physically meaningful for a daily step (it would imply condensation onto the
reference surface as a net daily flux). Rows with non-positive ET0 are **removed and counted**, never
clipped to zero and never imputed:

- `removed.nonPositiveEt0Rows` in `ml/evaluation/et0_dataset_quality.json`
- the count is reported in the training run and stored in the artifact

On the delivered dataset this count is **145**: 13 rows at Wageningen and 132 at Reykjavik, where a
winter day's net radiation is a net loss and ET0 goes negative. Those rows are absent from the
17,021 that remain, and `ml/evaluation/et0_dataset_quality.json` records the count per site under
`removed.nonPositiveEt0Rows` with the policy string "removed and counted, never clipped to zero and
never imputed". An earlier draft of this section said the count was 0; that was wrong, and it is
corrected here rather than deleted.

## 9. Harmonization contract for future datasets

A dataset is only allowed into `data/processed/` if all of the following are true. This is the
checklist the catalogue's class A/B assignments imply.

1. **Publisher, URL, version and access date are recorded** in `data/research/dataset_catalog.json`.
2. **The licence is checked against the distribution the project actually makes.** "Open for
   research" is not enough if the product is offered commercially. Non-commercial and
   no-derivatives licences are disqualifying (see `plantwild` and `waPOR` in the catalogue).
3. **Units are declared per variable and converted at the boundary** into the canonical unit table
   in section 3.
4. **Missing-value sentinels are declared and mapped to null**, with counts recorded.
5. **A checksum of the raw download is stored in `data/metadata/`** before parsing.
6. **The processed output gets its own checksum**, and the model that consumes it records that
   checksum.
7. **Spatial and temporal support are stated** (grid cell size, aggregation period), because both
   determine what claims the data can support: country-year FAOSTAT yields cannot validate a
   per-square-metre crop model.
8. **The licence status is graded** as verified / documented-secondary / not-verified, and anything
   less than verified is named as such wherever the dataset is cited.

## 10. What is not covered

- **No independent weather source.** Every ET0 number in this project traces to one provider. POWER
  is reanalysis built on MERRA-2; a shared lineage means it cannot validate itself. ERA5-Land is the
  obvious cross-check and needs a CDS token.
- **No measurement of crop water use.** ET0 is a computed reference flux for a hypothetical grass
  surface. Converting it into "litres per plant" needs a crop coefficient and a water balance that
  are not yet built from data.
- **No ground-truth soil or substrate data.** See `docs/DATASET_GAP_MATRIX.md`.
- **No cross-validation of the quality checks themselves.** They are assertions about physical
  ranges, not statistical tests, so they cannot detect a value that is plausible but wrong - a
  mis-scaled radiation sensor reading of 20 MJ/m^2/day instead of 10 would pass every check in
  section 5.
