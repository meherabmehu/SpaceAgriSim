# Independent ET0 validation: ERA5, ERA5-Land, NASA POWER, NOAA stations

**Status:** cross-source validation executed and reproducible. **ERA5-Land full hourly retrieval
is NOT executed** — no Copernicus CDS token exists in this environment (see §2). **Not** field
validation.
**Run:** 2021-01-01 → 2023-12-31, six sites, 6 570 site-days.
**Artefacts:** `data/validation/et0/harmonised_daily.csv`, `validation_summary`,
`attribution`.
**Code:** `scripts/et0_validation/` — `sources.py`, `methods.py`, `era5_land.py`, `scoring.py`,
`attribute.py`, `run_validation.py`.
**Tests:** `backend/tests/test_phase25_et0_validation.py` (60 tests).
**Production ET0 method: unchanged.** This work measures the reference-ET0 path; it does not alter it.

---

## 1. What this establishes, and what it does not

It supports these claims:

1. Our FAO-56 implementation, driven by ERA5 hourly forcing, agrees with the same equation driven
   by NASA POWER forcing to a pooled **MAE 0.566 mm d⁻¹** (RMSE 0.794, bias −0.344, R² 0.899)
   over 6 570 site-days.
2. **The equation is not the source of that disagreement.** Our daily form and the provider's
   independent FAO-56 ET0 on the same ERA5 forcing agree to **bias +0.009 mm d⁻¹** (MAE 0.181,
   R² 0.987). Two implementations converge; the residual is forcing and estimator form.
3. **The estimator form matters and is now measured, not assumed.** Applying the daily equation
   to daily aggregates instead of summing 24 hourly values changes ET0 by **0.273 mm d⁻¹** MAE
   (bias −0.213) on identical forcing.
4. A third, observational leg (NOAA ISD station temperatures through Hargreaves-Samani — no
   reanalysis input) agrees with the ERA5 PM series to **MAE 0.598**, pooled bias **+0.007**.
5. **Where each site disagrees is attributable.** A Shapley decomposition over the five daily
   drivers assigns 69.7 % of the Tucson difference to wind and 42.7 % of Nairobi's to wind, while
   elevation contributes <0.005 mm d⁻¹ at every site (§5).
6. Dropping the wind input costs −6 % (Singapore) to −39 % (Tucson) of ET0; omitting the 10 m→2 m
   wind conversion would have cost 1.8–10.3 % by site, and 52 % on the worst day at Reykjavík
   (§5.4).

It does **not** establish, and no artefact here may be read as claiming:

- that the values are correct **for a crop surface** — every leg is a *reference* surface (0.12 m
  grass, fixed surface resistance). No lysimeter, gravimetric, eddy-covariance or sap-flow
  measurement is involved anywhere;
- that reanalyses agreeing means either is right — ERA5 and MERRA-2 share much of their observing
  system, and agreement bounds *implementation and forcing* error, not physical truth;
- anything about controlled-environment agriculture: these are open-field weather sites;
- anything about microgravity or fractional gravity.

`measured-eta` — the gap between a computed reference flux and a crop's actual water use — is
untouched by this work and remains blocking. See
`docs/EXPERIMENTAL_WATER_USE_VALIDATION_PROTOCOL.md`.

---

## 2. ERA5-Land: what is implemented, what was executed, what is blocked

ERA5-Land is the right product for this purpose — 0.1° (≈9 km) rather than 0.25° (≈28 km). It is
distributed through the Copernicus CDS API, which requires a personal access token.

| Route | Product | Hourly radiation + wind? | Status in this run |
|---|---|---|---|
| `sources.fetch_cds_era5_land` | ERA5-Land 0.1°, all six FAO-56 variables | **yes** | **NOT RUN** — `MissingCredentialError`; recorded in `provenance.routesNotRun` with the missing variable names |
| `sources.fetch_open_meteo(site, model="era5_land")` (daily) | ERA5-Land 0.1°, temperature and dew point | no | executed — temperature-only Hargreaves leg |
| `sources.fetch_open_meteo(site, model="era5")` | ERA5 0.25°, all five FAO-56 fields | yes | executed — primary leg |

**The credential-free ERA5-Land delivery exposes temperature, dew point, relative humidity and
VPD, but returns `null` for shortwave radiation and for wind speed at every hour.** Full FAO-56
therefore cannot be evaluated from it, and the temperature-only leg is labelled as such. This is
a property of that route, verified by request, not an assumption.

**No retrieval was fabricated.** The missing-credential path is a hard, tested failure that names
`CDSAPI_URL` / `CDSAPI_KEY`, echoes no value, writes no file, and records itself as not run. A
fallback to a different product would let a future report claim ERA5-Land coverage that was never
retrieved.

### What is ready for the moment a token exists

* `sources.cds_request_payload()` — the exact CDS request as a pure function (variable list, all
  24 hours, a 0.1° area box around the site, NetCDF). Its shape is pinned by tests so it cannot
  drift from what the method consumes.
* `era5_land.hourly_series_from_netcdf()` — reads the CDS NetCDF with the CDS short names
  (`t2m`, `d2m`, `ssrd`, `10u`, `10v`, `sp`) and applies every conversion: K→°C, J m⁻² per hour
  → W m⁻², (u,v)→speed, Pa→hPa, plus longitude normalisation for 0–360 grids.
* `era5_land.radiation_energy_check()` — daily Rs must be a fraction of extraterrestrial
  radiation. This catches a radiation unit error the per-hour plausibility band misses, because
  an *over*-division produces small, plausible-looking fluxes that read as permanent overcast.
* **Tested end to end on synthetic NetCDF files** with the exact CDS variable names, units and
  step types, including two parametrised tests that assert both directions of the factor-of-3600
  error are rejected. What that proves is the parsing and unit handling. It does **not** prove
  that CDS returns what its documentation says, and no document may claim a real retrieval has
  been validated while none has run.

Manual setup, once a token is issued:

```bash
export CDSAPI_URL=https://cds.climate.copernicus.eu/api   # never committed
export CDSAPI_KEY=<your token>                            # never committed
pip install cdsapi netCDF4
python scripts/et0_validation/run_validation.py --start 2021-01-01 --end 2023-12-31
# -> era5_land_cds_pm_mm appears in the CSV and two extra comparisons in the summary
```

---

## 3. Sources and provenance

Every leg writes a provenance block into `validation_summary` under
`provenance.legs.<leg>.<site>`: product, route, temporal and spatial resolution, fields with
units, licence, the request URL (no credentials), and the payload SHA-256 that was parsed.

| Leg | Product | Resolution | Temporal | Units as received → used | Licence |
|---|---|---|---|---|---|
| `era5_hourly_pm` | ERA5 (C3S) | 0.25° | hourly UTC | °C; °C; W m⁻²; m s⁻¹ @10 m; hPa → °C, W m⁻², m s⁻¹ @2 m, kPa | Open-Meteo CC BY 4.0; values Copernicus licence |
| `era5_land_hargreaves` | ERA5-Land (C3S) | 0.1° | daily | °C | as above |
| `power_daily_pm` | NASA POWER (MERRA-2 based) | 0.5°×0.625° | daily | °C; MJ m⁻² d⁻¹; m s⁻¹ @2 m; kPa | NASA open data, CC BY 4.0 |
| `isd_hargreaves` | NOAA ISD-Lite | point | hourly UTC | ×10-scaled columns → SI | U.S. Government work, public domain |
| `om_et0_era5` | provider FAO-56 ET0 on ERA5 | 0.25° | daily | mm d⁻¹ | Open-Meteo CC BY 4.0 |

Sites (fixed before any comparison was run):

| Key | Site | Lat / Lon | Grid elev. | ISD station | Distance | Station elev. |
|---|---|---|---|---|---|---|
| `wageningen_nl` | Wageningen, NL | 51.97 / 5.67 | 16 m | DEELEN 062750 | 17 km | 48.2 m |
| `tucson_us` | Tucson, AZ | 32.28 / −110.95 | 824 m | TUCSON INTL 722740 | 16 km | 777.6 m |
| `singapore_sg` | Singapore | 1.35 / 103.82 | 15 m | CHANGI 486980 | 19 km | 6.7 m |
| `dhaka_bd` | Dhaka, BD | 23.81 / 90.41 | 9 m | HAZRAT SHAHJALAL 419220 | 4 km | 9.1 m |
| `reykjavik_is` | Reykjavik, IS | 64.13 / −21.90 | 53 m | REYKJAVIK 040300 | 2 km | 14.6 m |
| `nairobi_ke` | Nairobi, KE | −1.29 / 36.82 | 1798 m | NAIROBI WILSON 637420 | 4 km | 1687.4 m |

Two station substitutions were made **after** checking hourly coverage, and are recorded rather
than silently applied: Tejgaon (419230) is 4 km from the Dhaka grid point but reports only
29–365 days per year with no complete diurnal cycles, so the complete airport station was used;
Reykjavik 041300 was replaced by 040300 (1 085 versus 919 usable days) and Nairobi's JKIA record
by Wilson (1 031 versus 1 000).

---

## 4. Method

### 4.1 Hourly FAO-56, not the daily equation on hourly means

Allen et al. (1998) Ch. 3 is explicit that the daily form assumes daily means and G = 0. The ERA5
leg therefore uses eq. 53 per hour: `[0.408 Δ(Rn−G) + γ(37/(T+273))u₂(eₛ−eₐ)] / [Δ+γ(1+0.34u₂)]`,
with G = 0.1Rn in daylight and 0.5Rn at night (eq. 45–46), `ssrd`→Rs per hour, `u₂` from the 10 m
wind via eq. 47, and Ra integrated over the hour at the local solar-time midpoint
(longitude/15° shift). Daily ET0 is the **sum of 24 hourly values**. Daylight is flagged from
Ra > 0, not from clock time, so polar day and night follow physics.

### 4.2 Controls that separate forcing from implementation

| Comparison | What it isolates |
|---|---|
| `era5_daily_pm` vs `power_daily_pm` | forcing only (same equation, same code) |
| `era5_hourly_pm` vs `era5_daily_pm` | estimator form only (same forcing) |
| `era5_daily_pm` vs `om_et0_era5` | implementation only (same forcing, same form, different code) |

POWER's own `ET0` parameter is **not requestable** on the v2 daily endpoint (HTTP 422, "One of
your parameters is incorrect: ET0", in every community). The pipeline records
`POWER_ET0_AVAILABLE = False` and a test asserts it, so a future reviewer must consciously
re-check rather than assume.

### 4.3 The observational leg

ISD-Lite gives hourly station temperature, dew point, pressure, wind, sky code and precipitation
— but **no radiation or sunshine**, which is why GHCN and ISD both cannot support full FAO-56. The
observational leg therefore uses **Hargreaves-Samani** (eq. 52), the temperature-only method
FAO-56 documents for exactly this. A day is used only if ≥18 of 24 hours carry temperature. This
is a *different method on different data*: it bounds common-mode temperature error and cannot
confirm the radiation term.

### 4.4 Attribution: substitution with Shapley values

Both PM legs use the same equation, so their difference has exactly five forcing drivers (Tmax,
Tmin, ea, Rs, u2). Swapping a subset of drivers from ERA5 to POWER values and recomputing gives a
path between the two. Because the radiation and aerodynamic terms share the denominator
`Δ+γ(1+0.34u₂)`, the swaps are not additive and the order matters — so **every permutation of the
five drivers is evaluated (5! = 120)** and each driver's marginal contribution is averaged. That
is the Shapley value of the swap game: the contributions sum exactly to the difference, and no
ordering is privileged.

Surface pressure is held at the ERA5 value inside the game, because it is not an independent
forcing but a function of elevation and synoptic state, and the two sources agree to <0.2 kPa
everywhere. Its contribution is reported separately as `pressureRemainderMm`, which is what makes
the efficiency check exact. The first version of this code did *not* do that and left a silent
0.003 mm d⁻¹ residual — the kind of unexplained gap that later gets mistaken for noise. A
cross-check test now compares the substitution result against the stored-ET0 difference and
caught a second, real defect: the emitted `ea` column was the mean of hourly `es`, while the
equation used `es` of the mean dew point.

### 4.5 Three defects found and fixed during construction

1. **Hourly Ra bracket.** Reusing the daily eq. 21 clipped bracket in eq. 28 double-counted
   sin φ sin δ, driving Ra negative in the afternoon and mis-flagging daylight as night.
2. **Stefan-Boltzmann constant.** 4.903e-9 MJ K⁻⁴ m⁻² **d⁻¹** multiplied by 3600 instead of
   divided by 24 → ET0 of −75 000 mm d⁻¹.
3. **Pressure units.** ERA5 hPa passed as kPa inflated γ tenfold → 12–16 mm d⁻¹ in Tucson.

All three are regression-tested. They are recorded because a validation pipeline that reports only
its successes is not auditable.

---

## 5. Results

### 5.1 Pooled comparisons, 2021–2023, six sites

| Comparison | n | MAE | RMSE | Bias | R² |
|---|---|---|---|---|---|
| ERA5 hourly PM vs POWER daily PM | 6570 | 0.566 | 0.794 | −0.344 | 0.899 |
| ERA5 daily PM vs POWER daily PM *(forcing only)* | 6570 | 0.519 | 0.703 | −0.132 | 0.907 |
| ERA5 hourly PM vs ERA5 daily PM *(estimator form only)* | 6570 | 0.273 | 0.328 | −0.213 | 0.985 |
| ERA5 daily PM vs provider ET0 *(implementation only)* | 6570 | 0.181 | 0.228 | **+0.009** | 0.987 |
| ERA5 hourly PM vs provider ET0 | 6570 | 0.204 | 0.216 | −0.204 | 0.999 |
| Provider ET0 vs POWER daily PM *(forcing, both daily)* | 6570 | 0.525 | 0.704 | −0.140 | 0.908 |
| ERA5 hourly PM vs ISD Hargreaves *(observational)* | 6470 | 0.598 | 0.807 | +0.007 | 0.841 |
| POWER daily PM vs ISD Hargreaves | 6470 | 0.706 | 1.011 | +0.344 | 0.834 |
| ERA5-Land Hargreaves vs ISD Hargreaves *(both temperature-only)* | 6470 | 0.332 | 0.470 | −0.143 | 0.935 |
| ERA5-Land Hargreaves vs ERA5 hourly PM | 6570 | 0.578 | 0.777 | −0.148 | 0.862 |
| ERA5 hourly PM with wind = 0 vs POWER | 6570 | 1.115 | 1.548 | −1.058 | 0.776 |
| ERA5 hourly PM with wind = 2 m s⁻¹ vs POWER | 6570 | 0.605 | 0.852 | −0.360 | 0.882 |
| ERA5-Land hourly PM (CDS) | — | — | — | — | **not run** |

**What R² means here.** It is the squared Pearson correlation of the paired values, computed on the
pooled 6 570 rows. Pooled across six climates that differ by a factor of six in mean ET0, a large
part of the variance is *between* sites, so the pooled R² flatters every leg; the per-site table in
§5.2 is the honest view and is what should be quoted for a single site. The implementation control
is the one case where the pooled figure is the right one, because both series share the forcing.

**Reading the controls.** The equation implementations agree (bias +0.009, R² 0.980 at matched
form). The estimator form alone accounts for 0.273 mm d⁻¹ — and independently, the provider's
daily ET0 differs from our hourly sum by 0.204. The forcing difference alone is 0.519. So the
headline 0.566 is half formulation, half forcing: reporting it as a single number would have been
misleading, and reporting only the favourable control would have been dishonest.

### 5.2 Per site, ERA5 hourly PM vs POWER daily PM

| Site | n | MAE | RMSE | Bias | R² | slope | mean POWER |
|---|---|---|---|---|---|---|---|
| wageningen_nl | 1095 | 0.279 | 0.368 | −0.105 | 0.946 | 1.016 | 1.91 |
| tucson_us | 1095 | 0.569 | 0.748 | −0.290 | 0.920 | 0.897 | 5.67 |
| singapore_sg | 1095 | 0.408 | 0.530 | −0.173 | 0.669 | 0.906 | 3.61 |
| dhaka_bd | 1095 | 0.485 | 0.673 | −0.206 | 0.765 | 0.780 | 3.71 |
| reykjavik_is | 1095 | 0.270 | 0.349 | +0.088 | 0.867 | 1.002 | 0.95 |
| nairobi_ke | 1095 | 1.386 | 1.496 | −1.383 | 0.797 | 0.928 | 5.37 |

Annual means of the ERA5 hourly leg: Wageningen 1.80, Tucson 5.39, Singapore 3.44, Dhaka 3.50,
Reykjavik 1.04, Nairobi 3.98 mm d⁻¹ — inside the published order of magnitude for these climates.
A sanity check against unit errors, not evidence of accuracy.

### 5.3 Temporal holdout (2023) vs calibration years (2021–2022)

| Comparison | Calibration MAE | Holdout MAE |
|---|---|---|
| ERA5 hourly vs POWER | 0.577 | 0.545 |
| ERA5 daily vs POWER | 0.525 | 0.506 |
| ERA5 daily vs provider ET0 | 0.181 | 0.182 |

**No parameter is fitted anywhere in this pipeline**, so the holdout is a stability check, not a
generalisation test. Differences of ≤0.03 mm d⁻¹ say the disagreement is stationary — a
systematic product difference, not drift.

### 5.4 Wind sensitivity across all six sites

| Site | ERA5 hourly ET0 | Aerodynamic share | mean u₂ | wind = 0 | wind = 2 m s⁻¹ | cost of omitting the height conversion |
|---|---|---|---|---|---|---|
| wageningen_nl | 1.80 | 43 % | 2.86 | −26.8 % | −5.4 % | +0.104 mm d⁻¹ (5.8 %), p95 31 % |
| tucson_us | 5.39 | 47 % | 1.99 | −38.5 % | +0.2 % | +0.553 mm d⁻¹ (10.3 %), p95 15 % |
| singapore_sg | 3.44 | 19 % | 1.74 | −6.3 % | +1.9 % | +0.061 mm d⁻¹ (1.8 %), p95 5 % |
| dhaka_bd | 3.50 | 23 % | 1.79 | −13.3 % | +2.2 % | +0.129 mm d⁻¹ (3.7 %), p95 7 % |
| reykjavik_is | 1.04 | 51 % | 3.19 | −31.6 % | −7.8 % | +0.059 mm d⁻¹ (5.6 %), p95 52 % |
| nairobi_ke | 3.98 | 31 % | 1.96 | −17.9 % | −1.6 % | +0.185 mm d⁻¹ (4.7 %), p95 7 % |

Two conclusions with consequences for the product:

* **The 2 m s⁻¹ fallback is not a safe default.** It moves ET0 by −7.8 % at Reykjavík and +2.2 % at
  Dhaka — the sign depends on the site. This is why `backend/app/et0.py` declines to return a
  Penman-Monteith number when wind is missing rather than substituting one.
* **Omitting the 10 m→2 m conversion would have been a 1.8–10.3 % error** on the site mean, and up
  to 52 % on the worst day at Reykjavík, where a small mean ET0 makes any absolute error look
  large. It is a one-line conversion and it is tested.

### 5.5 Site-by-site attribution (Shapley, mm d⁻¹)

| Site | mean diff (POWER − ERA5) | Tmax | Tmin | ea | Rs | u2 | dominant |
|---|---|---|---|---|---|---|---|
| wageningen_nl | −0.042 | +0.035 | −0.071 | −0.060 | +0.032 | +0.022 | Tmin (32.3 %) |
| tucson_us | +0.265 | −0.003 | −0.066 | +0.038 | −0.024 | **+0.320** | **u₂ (70.8 %)** |
| singapore_sg | −0.234 | **−0.132** | +0.059 | −0.069 | −0.119 | +0.027 | Tmax (32.4 %) |
| dhaka_bd | −0.129 | −0.070 | −0.085 | +0.104 | −0.077 | +0.000 | spread: ea 31 %, Rs 23 %, Tmax 21 % |
| reykjavik_is | −0.191 | **−0.109** | −0.067 | −0.043 | +0.002 | +0.025 | Tmax (44.4 %) |
| nairobi_ke | +1.127 | +0.444 | −0.020 | +0.082 | +0.120 | **+0.500** | **u₂ (42.9 %), Tmax (38.0 %)** |

Shares are each driver's mean signed contribution divided by the sum of the absolute mean
contributions, so they do not sum to 100 % when drivers pull in opposite directions. The strength
of the swap game is that the contributions sum exactly to the difference
(`residual ±0.00000` at every site); a single "dominant driver" label is a convenience, and at
Dhaka no driver exceeds a third.

**Elevation is excluded as an explanation everywhere:** using the station elevation instead of the
grid elevation changes daily ET0 by at most 0.007 mm d⁻¹ at any of the six sites (grid–station
elevation differences of 0.1–110 m). The largest single elevation effect is Nairobi's 110 m
(0.007 mm d⁻¹), two orders of magnitude below its 1.13 mm d⁻¹ difference.

### 5.6 The three prioritised discrepancies

**Nairobi — wind, and it is POWER that is the outlier.** POWER's 2 m wind averages 3.23 m s⁻¹
against 2.33 m s⁻¹ at the Wilson station and 1.97 m s⁻¹ in ERA5. POWER is 0.90 m s⁻¹ *above* the
station; ERA5 is 0.37 m s⁻¹ *below* it. Wind is 42.7 % of the ET0 difference and Tmax 38.0 %. The
station value lies *between* the two reanalyses, so neither is vindicated: the defensible
statement is that POWER's wind at this 1 798 m highland site is anomalously high, which is a known
characteristic of coarse-grid reanalysis over heterogeneous terrain, and that ERA5 is closer to the
observation while still biased low. Radiation and temperature agree closely there (Rs 19.6 vs
20.7 MJ m⁻² d⁻¹; Tmax 25.29 vs 25.11 °C against the station).

**Dhaka — representativeness is *not* the problem, which is itself informative.** The station is
4 km from the grid point, its elevation matches the grid to 0.1 m, and its Tmax bias against ERA5
is only −0.21 °C. So the 0.13 mm d⁻¹ ET0 difference cannot be blamed on the station being in the
wrong place; it is a genuine reanalysis forcing difference spread across ea (31 %), Tmin (25 %) and
Rs (23 %). Notably Dhaka is where the two sources' radiation differs most (ERA5 0.85 MJ m⁻² d⁻¹
above POWER, MAE 2.27) — consistent with the monsoon/haze regime being represented differently by
a reanalysis that assimilates aerosol versus one that does not. Stated as an interpretation of the
evidence, not as a demonstration.

**Singapore — low R² is a narrow-signal artefact, and ERA5 is too cool.** R² 0.669 comes with MAE
0.408 mm d⁻¹ on a 3.61 mm d⁻¹ mean and a reference standard deviation of only 0.778 mm d⁻¹
(CV 0.216). At an equatorial site there is almost no seasonal signal, so R² is dominated by
day-to-day cloudiness disagreement while the absolute error stays small (11 % of the mean). The
attribution adds a second, independent finding: **ERA5's Tmax is 0.85 °C *below* the Changi station**
— the largest Tmax bias of the six sites — and Tmax is 32.5 % of the ET0 difference. Changi is a
coastal airport on reclaimed land inside a 0.25° cell that mixes sea and city; that is a
representativeness hypothesis, supported by the coastal sites (Singapore, Dhaka) showing the
largest Tmax bias, but not proven here.

### 5.7 A finding that cuts against the expected direction: 0.1° is *not* closer to the station

Tile 0.1° ERA5-Land temperature leg was expected to sit closer to the station than 0.25° ERA5. It
does not:

| Site | Tmax bias ERA5 0.25° − station | Tmax bias ERA5-Land 0.1° − station |
|---|---|---|
| wageningen_nl | −0.18 °C | −0.41 °C |
| tucson_us | −0.47 °C | −0.77 °C |
| singapore_sg | −0.85 °C | **−2.26 °C** |
| dhaka_bd | −0.21 °C | −1.13 °C |
| reykjavik_is | −0.35 °C | −0.81 °C |
| nairobi_ke | +0.15 °C | −0.35 °C |

At every one of the six sites the finer grid is *further* from the station, and at both coastal
airports the gap widens dramatically. The most plausible reading is that a 0.1° land-surface model
resolves vegetation and water and so does **not** carry the airport-tarmac warmth that a point
station sitting on asphalt measures, while a 0.25° cell partly averages it in. That is a hypothesis
consistent with the pattern; it is not established by this data, and it would take a
land-cover-aware comparison to settle.

The consequence for planning is concrete and worth stating plainly: **finer resolution is not
automatically closer to a station**, so "ERA5-Land will fix the disagreement" was an assumption
that this evidence does not support. What ERA5-Land would still buy is the correct *variable set*
at 0.1° (hourly radiation and wind), which the credential-free route does not expose at all.

### 5.8 Missing values

| Series | Rows | Missing | Fraction | Longest run |
|---|---|---|---|---|
| `era5_hourly_pm_mm` | 6570 | 0 | 0.0 % | 0 |
| `era5_daily_pm_mm` | 6570 | 0 | 0.0 % | 0 |
| `power_daily_pm_mm` | 6570 | 0 | 0.0 % | 0 |
| `era5_land_hargreaves_mm` | 6570 | 0 | 0.0 % | 0 |
| `om_et0_era5_mm` | 6570 | 0 | 0.0 % | 0 |
| `isd_hargreaves_mm` | 6570 | 100 | 1.5 % | 12 |
| `era5_land_cds_pm_mm` | 6570 | 6570 | 100 % | — (leg not run) |

ISD gaps are days with fewer than 18 hourly temperatures. Missing pairs are dropped, never
zero-filled.

---

## 6. Reproduce

```bash
# full run, ~40 s over the network, no credentials required
python scripts/et0_validation/run_validation.py --start 2021-01-01 --end 2023-12-31
python scripts/et0_validation/attribute.py        # ~16 s, Shapley attribution

# offline replay of exactly the bytes the committed artefact used (6 s, no network)
SPACEAGRISIM_ET0_HTTP_CACHE=~/.cache/et0http \
  python scripts/et0_validation/run_validation.py --start 2021-01-01 --end 2023-12-31

cd backend && python -m pytest tests/test_phase25_et0_validation.py -q   # 60 tests
```

### 6.1 Reproducibility, measured rather than asserted

Two consecutive full runs, and a replay from the response cache, produce a **byte-identical**
`harmonised_daily.csv` and a `validation_summary` whose only differing field is
`generatedAt`. That was checked with `cmp` and a field-by-field diff, not assumed.

One caveat had to be measured too. Each response's raw bytes are digested as `payloadSha256`, and
**all 24 of those digests changed between two fetch sessions hours apart while every metric, every
derived value and the whole CSV stayed byte-identical**. Live archive services are not byte-stable
(key ordering, generation-time metadata), so a raw-payload hash cannot answer "did the re-run get
the same data". A second digest, `seriesSha256`, covers the canonicalised numeric series that the
computation actually consumes; that is the one that is stable across runs and the one to compare
when re-checking reproducibility. Both are recorded for every leg, so the audit trail keeps the
as-received bytes *and* a usable content fingerprint.

The optional `SPACEAGRISIM_ET0_HTTP_CACHE` directory makes a re-run independent of the upstream
service being reachable or rate-limiting, and each leg's provenance records `httpCacheEnabled`, so a
cached replay cannot be mistaken for a fresh retrieval. It is off unless set, and the cache is
keyed by request URL — the same query always returns the same bytes, so a cache hit cannot silently
mix two different responses.

Outputs in `data/validation/et0/`: `harmonised_daily.csv` (6 570 rows, one per site-day, every
leg's ET0 plus the inputs each leg used), `validation_summary` (metrics, per-site/month/
season/year breakdowns, holdout, missingness, provenance with payload and series SHA-256, and
`routesNotRun`), `attribution` (Shapley contributions, elevation and wind-height checks,
representativeness diagnostics). Only derived tables are committed — bulk reanalysis data does not
belong in git.

---

## 7. What this does and does not save

**Cheaper now.** An ET0 question is answered by a 40-second re-run rather than an argument. A
change to the radiation or wind path can be scored against four sources per site before it ships.
"Is the 2 m s⁻¹ wind fallback defensible?" has a measured, per-site answer. And a future ERA5-Land
retrieval needs one environment variable, not new code.

**Still open.** `independent-et0` remains partially addressed: two of the four legs are reanalyses
with overlapping observing systems, the ERA5-Land leg is temperature-only, and the station leg is
a point measurement of temperature. A 0.5 mm d⁻¹ mutual agreement among reanalyses is fully
compatible with a 1 mm d⁻¹ bias against a real surface. The gap that matters — measured crop water
use — is exactly as open as it was; see `docs/EXPERIMENTAL_WATER_USE_VALIDATION_PROTOCOL.md`.
