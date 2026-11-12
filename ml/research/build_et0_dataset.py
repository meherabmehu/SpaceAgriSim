#!/usr/bin/env python3
"""Build the reference-ET0 dataset from the acquired NASA POWER responses.

The label is FAO-56 Penman-Monteith ET0 computed here, from radiation, temperature, humidity,
wind and pressure. It is a *standard*, not a measurement: it reflects the reference grass surface
under the reanalysis weather, so a model trained on it learns the FAO-56 equation and the
weather climatology behind it - nothing about a real crop or a real field.

Missing-data policy (FAO-56 chapter 3 procedural rules, applied at daily resolution):

    wind speed missing        -> 2.0 m/s
    dew point missing         -> dew point := Tmin
    radiation missing         -> Rs = 0.16 * sqrt(Tmax - Tmin) * Ra  (Rs is then flagged)

A row that loses its temperature or is otherwise unusable is dropped and counted by reason; no row
is imputed with a neighbouring day's value, because that leaks the label backwards in time.

Outputs
-------
    data/processed/et0_dataset.csv              the modelling table, one row per site-day
    data/processed/et0_dataset.metadata    columns, row counts, checksum, provenance
    data/processed/power_daily/<site>.csv       the harmonized weather, before ET0 is applied
    ml/evaluation/et0_dataset_quality      the quality report, issues and informational

    python3 ml/research/build_et0_dataset.py [--check]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))

from app.simulation import et0_fao56  # noqa: E402

RAW = ROOT / "data" / "raw" / "nasa_power"
MANIFEST = ROOT / "data" / "metadata" / "power_acquisition_manifest"
OUT_CSV = ROOT / "data" / "processed" / "et0_dataset.csv"
OUT_META = ROOT / "data" / "processed" / "et0_dataset.metadata"
OUT_DAILY = ROOT / "data" / "processed" / "power_daily"
OUT_QUALITY = ROOT / "ml" / "evaluation" / "et0_dataset_quality"

COLUMNS = [
    "siteId", "date", "dayOfYear", "latitude", "elevationM",
    "T2M_MAX", "T2M_MIN", "T2M", "T2MDEW", "RH2M", "WS2M", "PS", "PRECTOTCORR",
    "raMj", "daylightHours", "dliMolPerM2Day", "vpdKpa",
    "et0MmPerDay", "radiationTermMm", "aeroTermMm",
    "tdewClamped", "windImputed", "dewpointImputed", "radiationImputed",
]

# Physical plausibility bands. A value outside these is a sensor or encoding failure, not weather.
RANGES = {
    "ALLSKY_SFC_SW_DWN": (0.0, 50.0),
    "RH2M": (0.0, 100.0),
    "WS2M": (0.0, 70.0),
    "PS": (50.0, 110.0),
    "T2M_MAX": (-90.0, 60.0),
    "T2M_MIN": (-90.0, 60.0),
    "T2MDEW": (-100.0, 60.0),
}
# POWER states these units in the parameter metadata; community AG returns them in this form.
EXPECTED_UNITS = {
    "ALLSKY_SFC_SW_DWN": "MJ m^-2 d^-1",
    "T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "T2MDEW": "C",
    "RH2M": "%", "WS2M": "m s^-1", "PS": "kPa", "PRECTOTCORR": "mm day^-1",
}
# POWER spells the same unit differently across products ("MJ/m^2/day", "degC", "m/s"). The
# comparison is made on a canonical spelling so a format change is a mismatch and a synonym is not.
_UNIT_ALIASES = {
    "mj/m^2/day": "MJ m^-2 d^-1", "mj m-2 d-1": "MJ m^-2 d^-1", "mj m^-2 d^-1": "MJ m^-2 d^-1",
    "degc": "C", "c": "C",
    "%": "%",
    "m/s": "m s^-1", "m s-1": "m s^-1", "m s^-1": "m s^-1",
    "kpa": "kPa",
    "mm/day": "mm day^-1", "mm day-1": "mm day^-1", "mm day^-1": "mm day^-1",
}


def canonical_unit(text: str) -> str:
    stripped = str(text).strip()
    return _UNIT_ALIASES.get(stripped.lower(), stripped)


def load_manifest() -> dict:
    if not safedata.exists(MANIFEST):
        raise SystemExit("run ml/research/acquire_power_climate.py first "
                         f"(missing {MANIFEST.relative_to(ROOT)})")
    return safedata.load(MANIFEST)


def quality_checks(site_id: str, payload: dict, rows: list[dict],
                   days: list[str]) -> dict:
    """Hard issues (a wrong ET0 is being computed) and informational findings (real features).

    The split matters: dew point sitting above the daily minimum temperature is routine in humid
    climates and was initially, wrongly, coded as an issue - it flagged 2,304 of Wageningen's
    2,848 days. The issue that survives is the genuine contradiction: dew point above the daily
    *mean* temperature while the humidity reading says the air is not saturated.
    """
    series = payload["properties"]["parameter"]
    fill = float(payload["header"].get("fill_value", -999.0))
    units = payload["parameters"] if isinstance(payload.get("parameters"), dict) else {}

    def values(code: str) -> list[float]:
        return [float(v) for v in (series.get(code) or {}).values()
                if v is not None and float(v) != fill]

    issues: dict[str, object] = {}

    missing = sum(1 for code in EXPECTED_UNITS for day in days
                  if (series.get(code) or {}).get(day) in (None, fill))
    if missing:
        issues["missingValues"] = missing

    if len(set(days)) != len(days):
        issues["duplicateDates"] = len(days) - len(set(days))

    first, last = (date.fromisoformat(f"{d[0:4]}-{d[4:6]}-{d[6:8]}") for d in (days[0], days[-1]))
    expected = (last - first).days + 1
    if expected != len(days):
        issues["calendarGaps"] = expected - len(days)

    out_of_range = {}
    for code, (low, high) in RANGES.items():
        bad = sum(1 for value in values(code) if not (low <= value <= high))
        if bad:
            out_of_range[code] = bad
    if out_of_range:
        issues["valuesOutsidePhysicalRange"] = out_of_range

    tmax_below_tmin = sum(1 for day in days
                          if (series.get("T2M_MAX") or {}).get(day) not in (None, fill)
                          and (series.get("T2M_MIN") or {}).get(day) not in (None, fill)
                          and float(series["T2M_MAX"][day]) < float(series["T2M_MIN"][day]))
    if tmax_below_tmin:
        issues["tmaxBelowTmin"] = tmax_below_tmin

    # Two thresholds, because the two cases are different findings. A dew point more than half a
    # degree above the daily mean temperature while the humidity reading says the air is far from
    # saturated is a contradiction. The same excess at 90 %+ RH is what a daily aggregation of a
    # nearly saturated marine day looks like; it is recorded and clamped, not treated as a fault.
    contradiction = 0
    near_saturated = 0
    above_tmax = 0
    for row in rows:
        if row["RH2M"] == "" or row["T2M"] == "":
            continue
        tdew, tmean, rh = float(row["T2MDEW"]), float(row["T2M"]), float(row["RH2M"])
        if tdew > float(row["T2M_MAX"]):
            above_tmax += 1
        if tdew > tmean + 0.5:
            if rh < 90.0:
                contradiction += 1
            else:
                near_saturated += 1
    if contradiction:
        issues["dewpointAboveMeanTemp"] = contradiction
    if above_tmax:
        issues["dewpointAboveTmax"] = above_tmax

    unit_mismatches = {}
    for code, expected_unit in EXPECTED_UNITS.items():
        found = (units.get(code) or {}).get("units")
        if found is not None and canonical_unit(found) != expected_unit:
            unit_mismatches[code] = {"expected": expected_unit, "found": found}
    if unit_mismatches:
        issues["unitMismatch"] = unit_mismatches

    dewpoint_above_tmin = sum(
        1 for row in rows
        if row["T2MDEW"] != "" and row["T2M_MIN"] != ""
        and float(row["T2MDEW"]) > float(row["T2M_MIN"]))

    return {
        "siteId": site_id,
        "daysInRaw": len(days),
        "rowsKept": len(rows),
        "qualityIssues": issues,
        "informational": {
            "dewpointAboveMeanTempNearSaturatedRows": near_saturated,
            "dewpointAboveMeanTempNote": (
                "Dew point more than 0.5 degC above the daily mean while RH is at least 90 %: a "
                "near-saturated marine day compressed into daily aggregates. The ET0 computation "
                "clamps the dew point to the daily mean and flags the row in `tdewClamped`."),
            "dewpointAboveTminDays": dewpoint_above_tmin,
            "dewpointAboveTminNote": (
                "Tmin and Tdew are different aggregations of the same day and cross routinely in "
                "humid climates. Recorded, never removed."),
        },
    }


def build_site(site_meta: dict) -> tuple[list[dict], dict, dict]:
    raw = ROOT / site_meta["rawFile"]
    payload = safedata.load(raw)
    series = payload["properties"]["parameter"]
    fill = float(payload["header"].get("fill_value", -999.0))
    days = sorted({day for values in series.values() for day in values})

    rows: list[dict] = []
    dropped: dict[str, int] = {}
    imputed = {"windImputed": 0, "dewpointImputed": 0, "radiationImputed": 0}

    def value(code: str, day: str) -> float | None:
        raw_value = (series.get(code) or {}).get(day)
        if raw_value is None:
            return None
        raw_value = float(raw_value)
        return None if raw_value == fill else raw_value

    for day in days:
        tmax, tmin = value("T2M_MAX", day), value("T2M_MIN", day)
        if tmax is None or tmin is None:
            dropped["missing temperature"] = dropped.get("missing temperature", 0) + 1
            continue
        if tmax < tmin:
            dropped["Tmax below Tmin"] = dropped.get("Tmax below Tmin", 0) + 1
            continue

        parsed = date(int(day[0:4]), int(day[4:6]), int(day[6:8]))
        doy = parsed.timetuple().tm_yday
        tmean = (tmax + tmin) / 2.0
        ra, daylight = et0_fao56.extraterrestrial_radiation(site_meta["latitude"], doy)

        # FAO-56 fallbacks, in the order the manual presents them.
        rs = value("ALLSKY_SFC_SW_DWN", day)
        radiation_imputed = rs is None
        if radiation_imputed:
            rs = 0.16 * math.sqrt(max(tmax - tmin, 0.0)) * ra

        u2 = value("WS2M", day)
        wind_imputed = u2 is None
        if wind_imputed:
            u2 = 2.0

        tdew = value("T2MDEW", day)
        dewpoint_imputed = tdew is None
        if dewpoint_imputed:
            tdew = tmin
        # A daily dew point above the daily mean cannot happen; it is a reanalysis artefact. The
        # CSV keeps the raw value and flags the clamp, so the whole history is auditable.
        tdew_clamped = tdew > tmean
        tdew_used = min(tdew, tmean)

        pressure = value("PS", day) or et0_fao56.atmospheric_pressure(site_meta["elevationM"])
        ea = et0_fao56.actual_vapour_pressure_from_dewpoint(tdew_used)

        result = et0_fao56.reference_et0(
            tmax=tmax, tmin=tmin, ea=ea, rs=rs, wind_2m=u2, pressure_kpa=pressure,
            day_of_year=doy, latitude_deg=site_meta["latitude"],
            elevation_m=site_meta["elevationM"])

        rh = value("RH2M", day)
        precipitation = value("PRECTOTCORR", day)
        row = {
            "siteId": site_meta["siteId"],
            "date": parsed.isoformat(),
            "dayOfYear": doy,
            "latitude": site_meta["latitude"],
            "elevationM": site_meta["elevationM"],
            "T2M_MAX": round(tmax, 3),
            "T2M_MIN": round(tmin, 3),
            "T2M": round(tmean, 3),
            "T2MDEW": round(tdew, 3),
            "RH2M": round(rh, 3) if rh is not None else "",
            "WS2M": round(u2, 3),
            "PS": round(pressure, 4),
            "PRECTOTCORR": round(precipitation, 3) if precipitation is not None else "",
            "raMj": round(ra, 4),
            "daylightHours": round(daylight, 4),
            "dliMolPerM2Day": round(et0_fao56.daily_light_integral(rs)["dliMolPerM2PerDay"], 4),
            "vpdKpa": round(result["vpdKpa"], 4),
            "et0MmPerDay": round(result["et0MmPerDay"], 4),
            "radiationTermMm": round(result["radiationTermMm"], 4),
            "aeroTermMm": round(result["aeroTermMm"], 4),
            "tdewClamped": int(tdew_clamped),
            "windImputed": int(wind_imputed),
            "dewpointImputed": int(dewpoint_imputed),
            "radiationImputed": int(radiation_imputed),
        }

        if not (result["et0MmPerDay"] > 0):
            # A negative daily ET0 means net condensation onto the reference surface. It is not a
            # water demand and it is not clipped to zero, because clipping would invent data.
            dropped["non-positive ET0"] = dropped.get("non-positive ET0", 0) + 1
            continue

        for key, flag in (("windImputed", wind_imputed), ("dewpointImputed", dewpoint_imputed),
                          ("radiationImputed", radiation_imputed)):
            if flag:
                imputed[key] += 1
        rows.append(row)

    stats = {"daysInRaw": len(days), "rowsKept": len(rows), "dropped": dropped,
             "imputed": imputed}
    quality = quality_checks(site_meta["siteId"], payload, rows, days)
    quality["dropped"] = dropped
    quality["imputed"] = imputed
    return rows, stats, quality


def write_daily(rows_by_site: dict[str, list[dict]]) -> None:
    OUT_DAILY.mkdir(parents=True, exist_ok=True)
    for site_id, rows in rows_by_site.items():
        path = OUT_DAILY / f"{site_id}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="rebuild and compare against the committed manifest, write nothing")
    args = parser.parse_args()

    manifest = load_manifest()
    all_rows: list[dict] = []
    rows_by_site: dict[str, list[dict]] = {}
    per_site: dict[str, dict] = {}
    quality_reports: dict[str, dict] = {}
    for key, site_meta in manifest["sites"].items():
        if site_meta.get("status") != "ok":
            continue
        rows, stats, quality = build_site(site_meta)
        all_rows.extend(rows)
        rows_by_site[site_meta["siteId"]] = rows
        per_site[site_meta["siteId"]] = stats
        quality_reports[site_meta["siteId"]] = quality

    all_rows.sort(key=lambda row: (row["siteId"], row["date"]))
    if not all_rows:
        raise SystemExit("no rows built; check the acquisition manifest")

    body = (",".join(COLUMNS) + "\n"
            + "\n".join(",".join(str(row[name]) for name in COLUMNS) for row in all_rows)
            + "\n").encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()

    means = {}
    for site_id in per_site:
        values = [row["et0MmPerDay"] for row in all_rows if row["siteId"] == site_id]
        means[site_id] = round(sum(values) / len(values), 3)

    removed_total = sum(sum(stats["dropped"].values()) for stats in per_site.values())
    metadata = {
        "dataset": "SpaceAgriSim reference ET0 (FAO-56) over NASA POWER reanalysis",
        "labelDefinition": ("FAO-56 Penman-Monteith reference evapotranspiration for a 0.12 m "
                            "grass surface, computed from reanalysis weather. Not a measurement."),
        "rows": len(all_rows),
        "columns": COLUMNS,
        "sites": sorted(per_site),
        "perSite": per_site,
        "perSiteMeanEt0MmPerDay": means,
        "removedRows": removed_total,
        "removedReasons": {site: stats["dropped"] for site, stats in per_site.items()},
        "sha256": digest,
        "bytes": len(body),
        "generatedBy": "ml/research/build_et0_dataset.py",
        "provenance": {
            "weather": "data/metadata/power_acquisition_manifest",
            "weatherLicense": "NASA POWER, no restrictions, citation requested",
            "physics": "backend/app/simulation/et0_fao56.py (FAO-56, Ex. 17/18/20 asserted)",
        },
    }

    quality_report = {
        "generatedBy": "ml/research/build_et0_dataset.py",
        "datasetSha256": digest,
        "issuesTolerance": "zero; any key under qualityIssues is a hard failure",
        "sites": quality_reports,
        "siteCount": len(quality_reports),
        "sitesWithIssues": sorted(site for site, report in quality_reports.items()
                                  if report["qualityIssues"]),
        "removed": {
            "nonPositiveEt0Rows": sum(stats["dropped"].get("non-positive ET0", 0)
                                      for stats in per_site.values()),
            "missingTemperatureRows": sum(stats["dropped"].get("missing temperature", 0)
                                          for stats in per_site.values()),
            "total": removed_total,
            "policy": ("negative daily ET0 means net condensation on the reference surface; the "
                       "row is removed and counted, never clipped to zero and never imputed"),
        },
    }

    if args.check:
        if not safedata.exists(OUT_CSV) or not safedata.exists(OUT_META):
            print(f"MISSING {OUT_CSV.relative_to(ROOT)}; run without --check")
            return 1
        current = hashlib.sha256(safedata.bytes(OUT_CSV)).hexdigest()
        committed = safedata.load(OUT_META)["sha256"]
        if current != digest:
            print(f"STALE dataset: on disk {current[:12]} != rebuilt {digest[:12]}")
            return 1
        if current != committed:
            print(f"metadata sha256 {committed[:12]} does not match file {current[:12]}")
            return 1
        print(f"dataset up to date: {len(all_rows)} rows, sha256 {digest[:16]}...")
        return 0

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_QUALITY.parent.mkdir(parents=True, exist_ok=True)
    OUT_CSV.write_bytes(body)
    safedata.dump(metadata, OUT_META)
    safedata.dump(quality_report, OUT_QUALITY)
    write_daily(rows_by_site)

    print(f"{len(all_rows)} rows from {len(per_site)} sites; {removed_total} removed; "
          f"sha256 {digest[:16]}...")
    for site_id, mean in means.items():
        report = quality_reports[site_id]
        issues = "clean" if not report["qualityIssues"] else report["qualityIssues"]
        print(f"  {site_id:14s} mean ET0 {mean:5.3f} mm/day  rows {report['rowsKept']:5d}  "
              f"dropped {sum(report['dropped'].values()):3d}  issues {issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
