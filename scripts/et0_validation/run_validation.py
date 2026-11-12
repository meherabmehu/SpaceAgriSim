"""Cross-source reference-ET0 validation: fetch, compute, score, record provenance.

    python3 scripts/et0_validation/run_validation.py --start 2021-01-01 --end 2023-12-31

Writes ``data/validation/et0/harmonised_daily.csv`` and ``validation_summary``. Every leg
is either computed from data that was actually retrieved, or recorded as not run with the reason.
Nothing is fabricated and nothing is silently substituted.
"""
from __future__ import annotations
import safedata

import argparse
import csv
import datetime as _dt
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.et0_validation import methods, scoring, sources  # noqa: E402
from scripts.et0_validation.sources import (  # noqa: E402
    MissingCredentialError,
    Site,
    SourceUnavailableError,
    sites,
)

DEFAULT_START = "2021-01-01"
DEFAULT_END = "2023-12-31"
DEFAULT_OUT = _REPO_ROOT / "data" / "validation" / "et0"
HOLDOUT_YEAR = 2023

SERIES_COLUMNS = (
    "era5_hourly_pm_mm",
    "era5_daily_pm_mm",
    "era5_pm_no_wind_mm",
    "era5_pm_wind_2ms_mm",
    "era5_pm_no_height_conversion_mm",
    "power_daily_pm_mm",
    "om_et0_era5_mm",
    "era5_land_hargreaves_mm",
    "isd_hargreaves_mm",
    "era5_land_cds_pm_mm",
)

DRIVER_COLUMNS = (
    "era5_aero_term_mm", "era5_rad_term_mm",
    "era5_tmax_c", "era5_tmin_c", "era5_ea_kpa", "era5_rs_mjm2", "era5_u2_ms",
    "era5_pressure_kpa", "era5_ra_mjm2",
    "power_tmax_c", "power_tmin_c", "power_ea_kpa", "power_rs_mjm2", "power_u2_ms",
    "power_pressure_kpa",
    "era5_land_tmax_c", "era5_land_tmin_c",
    "isd_tmax_c", "isd_tmin_c", "isd_hours_used",
)

IDENTITY_COLUMNS = (
    "date", "site", "latitude", "longitude", "grid_elevation_m",
    "isd_station", "station_distance_km", "station_elevation_m",
)

# (id, left series, right series, what it isolates)
COMPARISONS: tuple[tuple[str, str, str, str], ...] = (
    ("era5_hourly_pm_vs_power_daily_pm", "era5_hourly_pm_mm", "power_daily_pm_mm",
     "cross-product: ERA5 hourly forcing vs NASA POWER daily forcing"),
    ("era5_daily_pm_vs_power_daily_pm", "era5_daily_pm_mm", "power_daily_pm_mm",
     "forcing only: same equation, same code, different weather"),
    ("era5_hourly_pm_vs_era5_daily_pm", "era5_hourly_pm_mm", "era5_daily_pm_mm",
     "estimator form only: hourly-summed vs daily-equation on identical forcing"),
    ("era5_daily_pm_vs_om_et0_era5", "era5_daily_pm_mm", "om_et0_era5_mm",
     "implementation only: same forcing, same daily form, independent code"),
    ("era5_hourly_pm_vs_om_et0_era5", "era5_hourly_pm_mm", "om_et0_era5_mm",
     "form plus implementation, same reanalysis"),
    ("om_et0_era5_vs_power_daily_pm", "om_et0_era5_mm", "power_daily_pm_mm",
     "forcing with both daily forms supplied by other implementations"),
    ("era5_hourly_pm_vs_isd_hargreaves", "era5_hourly_pm_mm", "isd_hargreaves_mm",
     "observational leg: PM against station temperature through Hargreaves"),
    ("power_daily_pm_vs_isd_hargreaves", "power_daily_pm_mm", "isd_hargreaves_mm",
     "observational leg for POWER"),
    ("era5_land_hargreaves_vs_isd_hargreaves", "era5_land_hargreaves_mm", "isd_hargreaves_mm",
     "temperature-only vs temperature-only: agreement of temperature fields"),
    ("era5_land_hargreaves_vs_era5_hourly_pm", "era5_land_hargreaves_mm", "era5_hourly_pm_mm",
     "ERA5-Land 0.1 deg temperature against ERA5 0.25 deg full PM"),
    ("era5_hourly_pm_no_wind_vs_power_daily_pm", "era5_pm_no_wind_mm", "power_daily_pm_mm",
     "wind sensitivity: ERA5 PM with u2 = 0"),
    ("era5_hourly_pm_wind_2ms_vs_power_daily_pm", "era5_pm_wind_2ms_mm", "power_daily_pm_mm",
     "wind sensitivity: ERA5 PM with u2 replaced by a 2 m s-1 default"),
    ("era5_land_cds_pm_vs_om_et0_era5", "era5_land_cds_pm_mm", "om_et0_era5_mm",
     "ERA5-Land hourly PM (CDS) against provider ET0"),
    ("era5_land_cds_pm_vs_power_daily_pm", "era5_land_cds_pm_mm", "power_daily_pm_mm",
     "ERA5-Land hourly PM (CDS) against POWER"),
)

SEASONS = {
    "DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11),
}


def _log(message: str) -> None:
    print(message, flush=True)


def _safe_fetch(leg: str, site: Site, call: Callable[[], dict[str, Any]],
                provenance: dict[str, Any], routes_not_run: dict[str, Any]) -> dict[str, Any] | None:
    """Run one acquisition; a failure is recorded, never papered over with a substitute."""
    try:
        return call()
    except MissingCredentialError as exc:
        routes_not_run.setdefault("copernicus-cds-era5-land", {
            "route": "copernicus-cds-era5-land",
            "leg": leg,
            "site": site.key,
            "status": "not-run",
            "missingEnvironmentVariables": ["CDSAPI_URL", "CDSAPI_KEY"],
            "reason": str(exc),
            "impact": "era5_land_cds_pm_mm stays empty; ERA5-Land FAO-56 metrics are not reported",
            "howToRun": (
                "export CDSAPI_URL=https://cds.climate.copernicus.eu/api and CDSAPI_KEY=<token>, "
                "pip install cdsapi, then re-run this script"
            ),
        })
        return None
    except SourceUnavailableError as exc:
        provenance.setdefault("failedLegs", {})[f"{leg}:{site.key}"] = str(exc)
        return None


def _daily_of(series: dict[str, list[float | None]], day: str, index: dict[str, int]) -> Any:
    position = index.get(day)
    return None if position is None else series[position]


def _build_rows(site: Site, era5_hourly: dict[str, Any], era5_daily: dict[str, Any],
                power: dict[str, Any], era5_land: dict[str, Any],
                isd: dict[str, Any]) -> list[dict[str, Any]]:
    """Assemble one row per site-day, with every leg's ET0 and the inputs it used."""
    hourly_daily = methods.hourly_series_to_daily(era5_hourly, site)
    no_wind = methods.hourly_series_to_daily(era5_hourly, site, u2_override=0.0)
    wind_2ms = methods.hourly_series_to_daily(era5_hourly, site, u2_override=2.0)
    no_conversion = methods.hourly_series_to_daily(era5_hourly, site, u2_from_wind_raw=True)

    power_index = {day: i for i, day in enumerate(power["days"])}
    om_index = {day: i for i, day in enumerate(era5_daily["days"])}
    land_index = {day: i for i, day in enumerate(era5_land["days"])}
    isd_daily = methods.isd_daily_temperature(isd, site)
    land_series = era5_land["series"]

    rows: list[dict[str, Any]] = []
    for day in sorted(hourly_daily):
        hour = hourly_daily[day]
        day_of_year = _dt.date.fromisoformat(day).timetuple().tm_yday
        ra, _ = methods.extraterrestrial_radiation(site.latitude, day_of_year)
        ea = methods.saturation_vapour_pressure(hour["dewMean"])

        daily_pm = methods.daily_et0(
            tmax=hour["tmax"], tmin=hour["tmin"], ea_kpa=ea, rs_mj=hour["rsMJm2"],
            wind_2m_ms=hour["u2Mean"], pressure_kpa=hour["pressureKpa"],
            day_of_year=day_of_year, latitude_deg=site.latitude,
            elevation_m=site.elevation_m,
        )

        power_position = power_index.get(day)
        if power_position is None:
            power_values = None
        else:
            power_values = {
                "tmax": _daily_of(power["series"]["T2M_MAX"], day, power_index),
                "tmin": _daily_of(power["series"]["T2M_MIN"], day, power_index),
                "dew": _daily_of(power["series"]["T2MDEW"], day, power_index),
                "rs": _daily_of(power["series"]["ALLSKY_SFC_SW_DWN"], day, power_index),
                "u2": _daily_of(power["series"]["WS2M"], day, power_index),
                "ps": _daily_of(power["series"]["PS"], day, power_index),
            }

        power_pm = None
        if power_values and None not in power_values.values():
            power_pm = methods.daily_et0(
                tmax=float(power_values["tmax"]), tmin=float(power_values["tmin"]),
                ea_kpa=methods.saturation_vapour_pressure(float(power_values["dew"])),
                rs_mj=float(power_values["rs"]), wind_2m_ms=float(power_values["u2"]),
                pressure_kpa=float(power_values["ps"]), day_of_year=day_of_year,
                latitude_deg=site.latitude, elevation_m=site.elevation_m,
            )

        om_position = om_index.get(day)
        om_et0 = None if om_position is None else era5_daily["series"][
            "et0_fao_evapotranspiration"][om_position]
        land_tmax = _daily_of(land_series["temperature_2m_max"], day, land_index)
        land_tmin = _daily_of(land_series["temperature_2m_min"], day, land_index)
        land_hargreaves = None
        if land_tmax is not None and land_tmin is not None:
            land_hargreaves = methods.hargreaves_for_day(
                float(land_tmax), float(land_tmin), site.latitude, day_of_year)

        isd_day = isd_daily.get(day)
        rows.append({
            "date": day,
            "site": site.key,
            "latitude": site.latitude,
            "longitude": site.longitude,
            "grid_elevation_m": site.elevation_m,
            "isd_station": f"{site.isd_usaf}-{site.isd_wban}",
            "station_distance_km": site.station_distance_km,
            "station_elevation_m": site.station_elevation_m,
            "era5_hourly_pm_mm": hour["et0Mm"],
            "era5_daily_pm_mm": daily_pm["et0MmPerDay"],
            "era5_pm_no_wind_mm": no_wind[day]["et0Mm"],
            "era5_pm_wind_2ms_mm": wind_2ms[day]["et0Mm"],
            "era5_pm_no_height_conversion_mm": no_conversion[day]["et0Mm"],
            "power_daily_pm_mm": None if power_pm is None else power_pm["et0MmPerDay"],
            "om_et0_era5_mm": om_et0,
            "era5_land_hargreaves_mm": land_hargreaves,
            "isd_hargreaves_mm": None if isd_day is None else isd_day["et0"],
            "era5_land_cds_pm_mm": None,  # requires the CDS route; never fabricated
            "era5_aero_term_mm": hour["aeroTermMm"],
            "era5_rad_term_mm": hour["radiationTermMm"],
            "era5_tmax_c": hour["tmax"],
            "era5_tmin_c": hour["tmin"],
            "era5_ea_kpa": ea,
            "era5_rs_mjm2": hour["rsMJm2"],
            "era5_u2_ms": hour["u2Mean"],
            "era5_pressure_kpa": hour["pressureKpa"],
            "era5_ra_mjm2": ra,
            "power_tmax_c": None if not power_values else power_values["tmax"],
            "power_tmin_c": None if not power_values else power_values["tmin"],
            "power_ea_kpa": (None if not power_values or power_values["dew"] is None
                             else methods.saturation_vapour_pressure(float(power_values["dew"]))),
            "power_rs_mjm2": None if not power_values else power_values["rs"],
            "power_u2_ms": None if not power_values else power_values["u2"],
            "power_pressure_kpa": None if not power_values else power_values["ps"],
            "era5_land_tmax_c": land_tmax,
            "era5_land_tmin_c": land_tmin,
            "isd_tmax_c": None if isd_day is None else isd_day["tmax"],
            "isd_tmin_c": None if isd_day is None else isd_day["tmin"],
            "isd_hours_used": None if isd_day is None else isd_day["hoursUsed"],
        })
    return rows


def _metrics_for(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, Any] | None:
    return scoring.paired([r[left] for r in rows], [r[right] for r in rows])


def _by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


def _comparisons_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def site_blocks(left: str, right: str) -> dict[str, Any]:
        return {site: _metrics_for(site_rows, left, right)
                for site, site_rows in _by_key(rows, "site").items()}

    def month_blocks(left: str, right: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["date"][:7], []).append(row)
        return {month: _metrics_for(month_rows, left, right)
                for month, month_rows in sorted(grouped.items())}

    def season_blocks(left: str, right: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            month = int(row["date"][5:7])
            for season, months in SEASONS.items():
                if month in months:
                    grouped.setdefault(season, []).append(row)
                    break
        return {season: _metrics_for(season_rows, left, right)
                for season, season_rows in sorted(grouped.items())}

    def year_blocks(left: str, right: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["date"][:4], []).append(row)
        return {year: _metrics_for(year_rows, left, right)
                for year, year_rows in sorted(grouped.items())}

    out: dict[str, Any] = {}
    for comparison_id, left, right, description in COMPARISONS:
        available = [row for row in rows if row.get(left) is not None and row.get(right) is not None]
        pooled = _metrics_for(rows, left, right)
        block: dict[str, Any] = {
            "id": comparison_id,
            "left": left,
            "right": right,
            "description": description,
            "pooled": pooled,
            "available": bool(available),
        }
        if pooled is None:
            block["status"] = (
                "no leg available: neither side has any value in this run "
                "(the CDS retrieval route was not executed)"
                if left.startswith("era5_land_cds")
                else "no paired values"
            )
            out[comparison_id] = block
            continue
        block["perSite"] = site_blocks(left, right)
        block["perMonth"] = month_blocks(left, right)
        block["perSeason"] = season_blocks(left, right)
        block["perYear"] = year_blocks(left, right)
        calibration = [row for row in rows if row["date"][:4] != str(HOLDOUT_YEAR)]
        holdout = [row for row in rows if row["date"][:4] == str(HOLDOUT_YEAR)]
        block["holdout"] = {
            "holdoutYear": HOLDOUT_YEAR,
            "calibrationYears": sorted({row["date"][:4] for row in calibration}),
            "calibration": _metrics_for(calibration, left, right),
            "holdout": _metrics_for(holdout, left, right),
            "note": (
                "No parameter is fitted anywhere in this pipeline, so this is a stability "
                "check on the disagreement, not a generalisation test."
            ),
        }
        out[comparison_id] = block
    return out


def _wind_sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """How much of each site's ET0 the wind input carries, and what a default would cost."""
    out: dict[str, Any] = {}
    for site, site_rows in _by_key(rows, "site").items():
        base = [r["era5_hourly_pm_mm"] for r in site_rows if r["era5_hourly_pm_mm"] is not None]
        no_wind = [r["era5_pm_no_wind_mm"] for r in site_rows
                   if r["era5_pm_no_wind_mm"] is not None]
        wind_2ms = [r["era5_pm_wind_2ms_mm"] for r in site_rows
                    if r["era5_pm_wind_2ms_mm"] is not None]
        no_conv = [r["era5_pm_no_height_conversion_mm"] for r in site_rows
                   if r["era5_pm_no_height_conversion_mm"] is not None]
        u2 = [r["era5_u2_ms"] for r in site_rows if r["era5_u2_ms"] is not None]
        aero = [r["era5_aero_term_mm"] for r in site_rows
                if r["era5_aero_term_mm"] is not None]
        if not base:
            continue
        mean_base = sum(base) / len(base)
        mean_no_wind = sum(no_wind) / len(no_wind)
        mean_2ms = sum(wind_2ms) / len(wind_2ms)
        # Positive means ET0 would have been higher if eq. 47 had been skipped: u10 > u2 at
        # this height, so omitting the conversion inflates the aerodynamic term.
        deltas = [c - b for b, c in zip(base, no_conv)]
        mean_delta = sum(deltas) / len(deltas)
        relative = [(c - b) / b * 100.0 for b, c in zip(base, no_conv) if b > 0.1]
        out[site] = {
            "meanEt0Mm": mean_base,
            "aeroSharePct": (sum(aero) / len(aero)) / mean_base * 100.0 if aero else None,
            "meanU2Ms": sum(u2) / len(u2) if u2 else None,
            "windZeroMeanMm": mean_no_wind,
            "windZeroDeltaPct": (mean_no_wind - mean_base) / mean_base * 100.0,
            "windDefault2msMeanMm": mean_2ms,
            "windDefault2msDeltaPct": (mean_2ms - mean_base) / mean_base * 100.0,
            "heightConversionOmittedMeanMm": mean_delta,
            "heightConversionOmittedDeltaPct": mean_delta / mean_base * 100.0,
            "heightConversionOmittedP95Pct": scoring._percentile(relative, 0.95),
            "heightConversionOmittedDays": len(relative),
        }
    return out


def _missingness_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {column: scoring.missingness([row[column] for row in rows])
            for column in SERIES_COLUMNS}


def run(start: str, end: str, out_dir: Path, site_list: list[Site] | None = None,
        *, holdout_year: int = HOLDOUT_YEAR, include_cds: bool = True) -> dict[str, Any]:
    site_list = site_list or sites()
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance: dict[str, Any] = {"legs": {}, "routesNotRun": {}, "failedLegs": {}}
    all_rows: list[dict[str, Any]] = []
    cds_credential = sources.cds_credentials_present()
    _log(f"CDS credential present: {cds_credential}")

    for site in site_list:
        if include_cds:
            # Attempting the credentialed route is what records it as not run. It raises on
            # the first missing variable, so nothing is retrieved and nothing is written.
            _safe_fetch("era5_land_cds_pm", site,
                        lambda site=site: sources.fetch_cds_era5_land(site, start, end),
                        provenance, provenance["routesNotRun"])
        _log(f"[{site.key}] fetching era5 hourly, era5/era5-land daily, POWER, ISD")
        era5_hourly = _safe_fetch(
            "era5_hourly", site, lambda: sources.fetch_open_meteo(site, start, end, "era5"),
            provenance, provenance["routesNotRun"])
        era5_daily = _safe_fetch(
            "om_et0_era5", site,
            lambda: sources.fetch_open_meteo_daily(site, start, end, "era5"),
            provenance, provenance["routesNotRun"])
        era5_land = _safe_fetch(
            "era5_land_hargreaves", site,
            lambda: sources.fetch_open_meteo_daily(site, start, end, "era5_land"),
            provenance, provenance["routesNotRun"])
        power = _safe_fetch(
            "power_daily", site, lambda: sources.fetch_power_daily(site, start, end),
            provenance, provenance["routesNotRun"])
        isd = _safe_fetch(
            "isd_hargreaves", site, lambda: sources.fetch_isd_hourly(site, start, end),
            provenance, provenance["routesNotRun"])

        for leg, payload in (("era5_hourly_pm", era5_hourly), ("om_et0_era5", era5_daily),
                             ("era5_land_hargreaves", era5_land), ("power_daily_pm", power),
                             ("isd_hargreaves", isd)):
            if payload is not None:
                provenance["legs"].setdefault(leg, {})[site.key] = payload["provenance"]

        if era5_hourly is None or power is None or isd is None:
            _log(f"[{site.key}] skipped: required leg unavailable")
            continue

        # An empty daily payload is still a payload; only a failed fetch is None.
        empty_daily = {"days": [], "series": {"temperature_2m_max": [],
                                             "temperature_2m_min": [],
                                             "et0_fao_evapotranspiration": []},
                       "provenance": {}}
        all_rows.extend(_build_rows(
            site, era5_hourly, era5_daily or empty_daily, power,
            era5_land or empty_daily, isd,
        ))
        _log(f"[{site.key}] {len(all_rows)} cumulative rows")

    if not all_rows:
        raise SystemExit("no site produced a row; refusing to write an empty artefact")

    all_rows.sort(key=lambda row: (row["site"], row["date"]))
    csv_path = out_dir / "harmonised_daily.csv"
    columns = IDENTITY_COLUMNS + SERIES_COLUMNS + DRIVER_COLUMNS
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({column: ("" if row.get(column) is None else row[column])
                             for column in columns})

    summary = {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"start": start, "end": end},
        "rowCount": len(all_rows),
        "sites": [site.key for site in site_list],
        "siteMetadata": [
            {"key": site.key, "label": site.label, "latitude": site.latitude,
             "longitude": site.longitude, "gridElevationM": site.elevation_m,
             "climate": site.climate, "isdStation": f"{site.isd_usaf}-{site.isd_wban}",
             "isdStationName": site.isd_name,
             "stationDistanceKm": site.station_distance_km,
             "stationElevationM": site.station_elevation_m}
            for site in site_list
        ],
        "comparisons": _comparisons_block(all_rows),
        "windSensitivity": _wind_sensitivity(all_rows),
        "missingness": _missingness_block(all_rows),
        "provenance": {
            "legs": provenance["legs"],
            "routesNotRun": provenance["routesNotRun"],
            "failedLegs": provenance["failedLegs"],
            "cdsCredentialPresent": cds_credential,
            "powerEt0Available": sources.POWER_ET0_AVAILABLE,
            "httpCache": {
                "envVar": sources.CACHE_ENV_VAR,
                "enabled": sources._cache_dir() is not None,
            },
        },
        "claims": {
            "supports": "implementation and forcing agreement between ET0 computations",
            "doesNotSupport": [
                "crop water use: every leg is a reference surface, no measurement is involved",
                "physical ground truth: two of the legs are reanalyses sharing observations",
                "ERA5-Land FAO-56 skill: the CDS route never ran",
            ],
        },
    }
    safedata.dump(summary, out_dir / "validation_summary")

    _log(f"Wrote {csv_path} ({len(all_rows)} rows) and validation_summary")
    for comparison_id, block in summary["comparisons"].items():
        pooled = block.get("pooled")
        if pooled is None:
            _log(f"  {comparison_id:48s} not computed ({block.get('status')})")
        else:
            _log(f"  {comparison_id:48s} n={pooled['n']:5d} MAE {pooled['mae']:.3f} "
                 f"bias {pooled['bias']:+.3f} R2 {pooled['r2']:.3f}")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--holdout-year", type=int, default=HOLDOUT_YEAR)
    parser.add_argument("--site", action="append", dest="site_keys",
                        help="restrict to one or more site keys (repeatable)")
    parser.add_argument("--no-cds", action="store_true",
                        help="skip the credentialed CDS route entirely")
    args = parser.parse_args(argv)

    chosen = sites()
    if args.site_keys:
        wanted = set(args.site_keys)
        chosen = [site for site in chosen if site.key in wanted]
        unknown = wanted - {site.key for site in chosen}
        if unknown:
            parser.error(f"unknown site(s): {', '.join(sorted(unknown))}")

    run(args.start, args.end, Path(args.out), chosen,
        holdout_year=args.holdout_year, include_cds=not args.no_cds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
