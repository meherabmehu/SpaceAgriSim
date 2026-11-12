#!/usr/bin/env python3
"""Acquire NASA POWER hourly agroclimatology for the SpaceAgriSim reference sites.

Why this exists
---------------
Every weather input this repository had was a *daily* aggregate (``acquire_power_climate.py``).
That is enough to fit an ET0 model but not enough to say anything about the diurnal cycle, which
is the part of the environment a controlled-environment system actually has to manage: the hour
of peak VPD, the daily temperature amplitude, the number of hours a crop spends above a VPD
threshold. Gap ``sub-daily-weather`` in ``data/research/dataset_gap_matrix`` records that
limitation. This script closes it by acquiring the hourly product directly from the same NASA
POWER service, so the hourly and daily series share an upstream lineage and cannot disagree
because of a provider change.

What it does *not* do
---------------------
It does not re-derive ET0 from the hourly series. That would be a different model with a different
calibration, and blending it into the existing daily validation would be a silent change of
target. The hourly series is used for diurnal statistics only, and each derived column here is
labelled as derived in ``COLUMN_PROVENANCE``.

What the script guarantees
--------------------------
1. Three retries with exponential backoff on network and 5xx errors; a site that still fails is
   recorded as failed, never silently dropped.
2. The raw response body is written BEFORE it is parsed, so a parse bug is fixable without
   re-downloading.
3. Every raw file is SHA-256 checksummed and its byte size recorded, along with the API version,
   the exact request parameters and the grid elevation.
4. POWER's fill value (-999.0) becomes an explicit missing count, never a measurement.

    python3 ml/research/acquire_power_hourly.py [--start 20230101] [--end 20231231]
"""
from __future__ import annotations
import sys

import argparse
import hashlib
import math
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "nasa_power_hourly"
PROCESSED = ROOT / "data" / "processed" / "power_hourly"
MANIFEST = ROOT / "data" / "metadata" / "power_hourly_manifest"

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"
FILL_VALUE = -999.0

PARAMETERS = [
    "T2M",                # 2 m air temperature, degC
    "RH2M",               # 2 m relative humidity, %
    "T2MDEW",             # 2 m dew point, degC
    "WS2M",               # 2 m wind speed, m s^-1
    "PS",                 # surface pressure, kPa
    "ALLSKY_SFC_SW_DWN",  # all-sky surface shortwave downward irradiance, W m^-2
    "PRECTOTCORR",        # bias-corrected precipitation, mm h^-1
]

# Same six sites, same coordinates and same rationale as the daily acquisition. Re-using the
# coordinate table is deliberate: an hourly series that sits on a different grid cell from the
# daily series would make the two products silently incomparable.
SITES = [
    {"siteId": "wageningen_nl", "siteName": "Wageningen, Netherlands",
     "latitude": 51.97, "longitude": 5.67, "rationale": "temperate greenhouse research cluster"},
    {"siteId": "tucson_us", "siteName": "Tucson, United States",
     "latitude": 32.28, "longitude": -110.95, "rationale": "hot arid, high elevation (738 m)"},
    {"siteId": "singapore_sg", "siteName": "Singapore",
     "latitude": 1.35, "longitude": 103.82,
     "rationale": "equatorial, high humidity, low seasonality"},
    {"siteId": "dhaka_bd", "siteName": "Dhaka, Bangladesh",
     "latitude": 23.81, "longitude": 90.41,
     "rationale": "monsoon subtropical, large seasonal range"},
    {"siteId": "reykjavik_is", "siteName": "Reykjavik, Iceland",
     "latitude": 64.13, "longitude": -21.90,
     "rationale": "sub-polar maritime, extreme daylight range"},
    {"siteId": "nairobi_ke", "siteName": "Nairobi, Kenya",
     "latitude": -1.29, "longitude": 36.82, "rationale": "tropical highland, equatorial but cool"},
]

# Which output column is measured, which is derived, and from what. Anything the platform shows
# must be traceable to this table.
COLUMN_PROVENANCE = {
    "t2m_c": ("measured", "POWER T2M, hourly, MERRA-2 reanalysis on the AG grid"),
    "rh2m_pct": ("measured", "POWER RH2M, hourly"),
    "t2mdew_c": ("measured", "POWER T2MDEW, hourly"),
    "ws2m_ms": ("measured", "POWER WS2M, hourly"),
    "ps_kpa": ("measured", "POWER PS, hourly"),
    "sw_wm2": ("derived", "POWER ALLSKY_SFC_SW_DWN hourly [MJ/hr] / 0.0036 = W m-2"),
    "precip_mm": ("measured", "POWER PRECTOTCORR, hourly"),
    "vpd_kpa": ("derived", "e_s(T2M) - e_s(T2MDEW); Magnus coefficients 0.6108/17.27/237.3"),
    "par_umol_m2_s": ("derived", "SW x 0.45 (PAR fraction) x 4.57 (umol J^-1) = SW x 2.0565"),
    "dli_mol_m2_d": ("derived", "sum over the day (UTC) of par_umol_m2_s x 3600 / 1e6"),
    "sw_daily_mj_m2": ("derived", "sum over the day (UTC) of sw_wm2 x 0.0036"),
}

# POWER returns "YYYYMMDDHH" keys and states the time standard in the response header. The hourly
# endpoint answers with "LST" whether or not a UTC standard is requested, so the timestamps are
# kept exactly as published and named `timestamp_lst`. They are never silently relabelled as UTC:
# a one-hour mislabelling is invisible in a daily mean and wrong in a diurnal statistic.
KEY_LEN = 10

# Units the provider publishes for each parameter. The response carries a `parameters` block with
# the units actually returned, and these are asserted against it - not against a memory of the
# documentation. ALLSKY_SFC_SW_DWN is the one that bites: the hourly endpoint returns MJ/hr, not
# W/m2, and a value of 2.65 read as W/m2 is a 278-fold underestimate that still looks like a
# number. It is converted to W/m2 here with the factor recorded in COLUMN_PROVENANCE.
EXPECTED_UNITS = {
    "T2M": "C", "RH2M": "%", "T2MDEW": "C", "WS2M": "m/s", "PS": "kPa",
    "ALLSKY_SFC_SW_DWN": "MJ/hr", "PRECTOTCORR": "mm/hour",
}
MJ_PER_HOUR_TO_W_M2 = 1.0 / 0.0036


def build_url(site: dict, start: str, end: str) -> str:
    query = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": site["longitude"],
        "latitude": site["latitude"],
        "start": start,
        "end": end,
        "format": "JSON",
    }
    return f"{ENDPOINT}?{urllib.parse.urlencode(query)}"


def fetch(url: str, attempts: int = 3, timeout: int = 120) -> tuple[bytes, str]:
    """Fetch with backoff. Returns (body, fetched_at)."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SpaceAgriSim/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), datetime.now(timezone.utc).isoformat()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"POWER hourly request failed after {attempts} attempts: {last_error}")


def saturation_vapour_pressure(temp_c: float) -> float:
    """FAO-56 saturation vapour pressure in kPa (Magnus form, Eq. 11 of FAO-56)."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def to_rows(payload: dict) -> tuple[list[dict], dict]:
    """Flatten a POWER hourly response into one row per hour plus a provenance dict.

    As with the daily product, ``properties.parameter.<CODE>`` is a plain {YYYYMMDDHH: value}
    map; there is no ``values`` wrapper. Reading it the wrong way yields a table of Nones that
    still looks like a successful download.
    """
    header = payload.get("header", {})
    fill = float(header.get("fill_value", FILL_VALUE))
    parameters = payload.get("properties", {}).get("parameter", {})
    if not parameters:
        raise ValueError("POWER hourly payload has no properties.parameter block")

    stamps = sorted({stamp for series in parameters.values() for stamp in series})
    bad_key = [s for s in stamps if len(s) != KEY_LEN]
    if bad_key:
        raise ValueError(f"unexpected timestamp keys, e.g. {bad_key[:3]}")

    missing_counts: dict[str, int] = {}
    rows: list[dict] = []
    for stamp in stamps:
        row: dict = {
            "timestamp_lst": f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[8:10]}:00:00",
            "date": f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}",
        }
        for code in PARAMETERS:
            value = (parameters.get(code) or {}).get(stamp)
            missing = value is None or float(value) == fill
            missing_counts[code] = missing_counts.get(code, 0) + int(missing)
            if missing:
                row[code] = None
            elif code == "ALLSKY_SFC_SW_DWN":
                row[code] = float(value) * MJ_PER_HOUR_TO_W_M2
            else:
                row[code] = float(value)
        # Derived columns are only computed when both parents are present; otherwise None, so a
        # gap in the reanalysis never turns into a zero.
        if row["T2M"] is not None and row["T2MDEW"] is not None:
            row["vpd_kpa"] = round(
                saturation_vapour_pressure(row["T2M"]) - saturation_vapour_pressure(row["T2MDEW"]), 4)
        else:
            row["vpd_kpa"] = None
        row["par_umol_m2_s"] = (
            None if row["ALLSKY_SFC_SW_DWN"] is None
            else round(row["ALLSKY_SFC_SW_DWN"] * 0.45 * 4.57, 3))
        rows.append(row)

    coordinates = payload.get("geometry", {}).get("coordinates") or []
    reported = {code: (payload.get("parameters", {}).get(code) or {}).get("units")
                for code in PARAMETERS}
    mismatched = {code: {"expected": EXPECTED_UNITS[code], "reported": reported[code]}
                  for code in PARAMETERS if reported[code] != EXPECTED_UNITS[code]}
    if mismatched:
        raise ValueError(f"provider changed published units: {mismatched}")

    meta = {
        "missingPerParameter": missing_counts,
        "timeStandard": header.get("time_standard"),
        "reportedUnits": reported,
        "apiVersion": (header.get("api") or {}).get("version"),
        "sources": header.get("sources"),
        "elevationM": coordinates[2] if len(coordinates) > 2 else None,
        "hourCount": len(stamps),
        "firstHour": rows[0]["timestamp_lst"] if rows else None,
        "lastHour": rows[-1]["timestamp_lst"] if rows else None,
    }
    return rows, meta


def daily_rows(rows: list[dict]) -> list[dict]:
    """Aggregate the hourly rows to the diurnal statistics the daily product cannot express."""
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[row["date"]].append(row)

    out: list[dict] = []
    for date in sorted(buckets):
        hours = buckets[date]
        par = [h["par_umol_m2_s"] for h in hours if h["par_umol_m2_s"] is not None]
        sw = [h["ALLSKY_SFC_SW_DWN"] for h in hours if h["ALLSKY_SFC_SW_DWN"] is not None]
        temp = [h["T2M"] for h in hours if h["T2M"] is not None]
        vpd = [h["vpd_kpa"] for h in hours if h["vpd_kpa"] is not None]
        out.append({
            "date": date,
            "hours_observed": len(hours),
            "dli_mol_m2_d": round(sum(par) * 3600 / 1e6, 4) if par else None,
            "sw_daily_mj_m2": round(sum(sw) * 0.0036, 4) if sw else None,  # W/m2 h -> MJ/m2
            "t2m_min_c": round(min(temp), 3) if temp else None,
            "t2m_max_c": round(max(temp), 3) if temp else None,
            "t2m_amplitude_c": round(max(temp) - min(temp), 3) if temp else None,
            "vpd_mean_kpa": round(sum(vpd) / len(vpd), 4) if vpd else None,
            "vpd_max_kpa": round(max(vpd), 4) if vpd else None,
            "vpd_p95_kpa": round(sorted(vpd)[int(0.95 * (len(vpd) - 1))], 4) if vpd else None,
            "hours_vpd_gt_1p5": sum(1 for v in vpd if v > 1.5),
            "hours_vpd_gt_2p5": sum(1 for v in vpd if v > 2.5),
        })
    return out


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(",".join(columns) + "\n")
        for row in rows:
            handle.write(",".join("" if row.get(c) is None else str(row[c]) for c in columns) + "\n")


HOURLY_COLUMNS = ["timestamp_lst", "date", "t2m_c", "rh2m_pct", "t2mdew_c", "ws2m_ms", "ps_kpa",
                  "sw_wm2", "precip_mm", "vpd_kpa", "par_umol_m2_s"]
SOURCE_TO_COLUMN = {"T2M": "t2m_c", "RH2M": "rh2m_pct", "T2MDEW": "t2mdew_c", "WS2M": "ws2m_ms",
                    "PS": "ps_kpa", "ALLSKY_SFC_SW_DWN": "sw_wm2", "PRECTOTCORR": "precip_mm"}
DAILY_COLUMNS = ["date", "hours_observed", "dli_mol_m2_d", "sw_daily_mj_m2", "t2m_min_c",
                 "t2m_max_c", "t2m_amplitude_c", "vpd_mean_kpa", "vpd_max_kpa", "vpd_p95_kpa",
                 "hours_vpd_gt_1p5", "hours_vpd_gt_2p5"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="20230101")
    parser.add_argument("--end", default="20231231")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": {
            "name": "NASA POWER hourly agroclimatology (community AG)",
            "publisher": "NASA Langley Research Center, POWER Project",
            "endpoint": ENDPOINT,
            "license": ("No restrictions on use, access or download; citation requested. "
                        "Verified at https://power.larc.nasa.gov/ and "
                        "registry.opendata.aws/nasa-power"),
            "fillValue": FILL_VALUE,
            "parameters": PARAMETERS,
            "columnProvenance": COLUMN_PROVENANCE,
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "sites": {},
    }

    failures = 0
    for site in SITES:
        key = f"{site['siteId']}_{args.start}_{args.end}"
        url = build_url(site, args.start, args.end)
        target = RAW / f"power_hourly_{site['siteId']}"
        try:
            body, fetched_at = fetch(url)
            target.write_bytes(body)
        except RuntimeError as error:
            print(f"[FAIL] {site['siteId']}: {error}")
            manifest["sites"][key] = {**site, "status": "failed", "error": str(error)}
            failures += 1
            continue

        payload = json.loads(body)
        rows, meta = to_rows(payload)
        for row in rows:
            for source, column in SOURCE_TO_COLUMN.items():
                row[column] = row[source]
        hourly_csv = PROCESSED / f"{site['siteId']}_hourly.csv"
        write_csv(hourly_csv, rows, HOURLY_COLUMNS)
        daily = daily_rows(rows)
        daily_csv = PROCESSED / f"{site['siteId']}_daily.csv"
        write_csv(daily_csv, daily, DAILY_COLUMNS)

        manifest["sites"][key] = {
            **site,
            "status": "ok",
            "requestedStart": args.start,
            "requestedEnd": args.end,
            "apiUrl": url,
            "fetchedAt": fetched_at,
            "rawFile": str(target.relative_to(ROOT)),
            "rawBytes": len(body),
            "rawSha256": hashlib.sha256(body).hexdigest(),
            "hourlyCsv": str(hourly_csv.relative_to(ROOT)),
            "dailyCsv": str(daily_csv.relative_to(ROOT)),
            "dayCount": len(daily),
            **meta,
        }
        print(f"[OK]   {site['siteId']}: {meta['hourCount']} hours over {len(daily)} days, "
              f"elev {meta['elevationM']} m, API {meta['apiVersion']}, "
              f"missing {sum(meta['missingPerParameter'].values())}")

    manifest["summary"] = {
        "sitesRequested": len(SITES),
        "sitesOk": len(SITES) - failures,
        "sitesFailed": failures,
    }
    safedata.dump(manifest, MANIFEST)
    print(f"\nmanifest -> {MANIFEST.relative_to(ROOT)} ({manifest['summary']})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
