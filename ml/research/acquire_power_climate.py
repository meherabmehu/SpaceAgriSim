#!/usr/bin/env python3
"""Acquire NASA POWER daily agroclimatology for the SpaceAgriSim reference sites.

Why these six sites: they span the climate range a controlled-environment system could be sited
in, which is the only way to test whether a model fitted on weather generalises or merely
memorises. Wageningen (temperate maritime), Tucson (hot arid, 738 m), Singapore (equatorial),
Dhaka (monsoon subtropical), Reykjavik (sub-polar maritime) and Nairobi (tropical highland) have
pairwise-different radiation, humidity and wind regimes.

What the script guarantees
--------------------------
1. Three retries with exponential backoff on network and 5xx errors; a site that still fails is
   recorded as failed, never silently dropped.
2. The raw response body is written BEFORE it is parsed, so a parse bug is fixable without
   re-downloading.
3. Every raw file is SHA-256 checksummed and its byte size recorded, along with the API version,
   the exact request parameters and the grid elevation.
4. POWER's fill value (-999.0) becomes an explicit missing count, never a measurement.

    python3 ml/research/acquire_power_climate.py [--start 20180101] [--end 20251031]
"""
from __future__ import annotations
import sys

import argparse
import hashlib
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
RAW = ROOT / "data" / "raw" / "nasa_power"
MANIFEST = ROOT / "data" / "metadata" / "power_acquisition_manifest"

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL_VALUE = -999.0

# Community "AG" is the agroclimatology community: the product set intended for agricultural
# modelling, with its own bias corrections applied to MERRA-2.
PARAMETERS = [
    "ALLSKY_SFC_SW_DWN",  # all-sky surface shortwave downward irradiance, MJ m^-2 d^-1
    "T2M",                # 2 m air temperature, degC
    "T2M_MAX",
    "T2M_MIN",
    "T2MDEW",             # 2 m dew point, degC
    "RH2M",               # 2 m relative humidity, %
    "WS2M",               # 2 m wind speed, m s^-1
    "PS",                 # surface pressure, kPa
    "PRECTOTCORR",        # bias-corrected precipitation, mm/day
]

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


def fetch(url: str, attempts: int = 3, timeout: int = 90) -> tuple[bytes, str]:
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
    raise RuntimeError(f"POWER request failed after {attempts} attempts: {last_error}")


def to_rows(payload: dict) -> tuple[list[dict], dict]:
    """Flatten a POWER point response into one row per day plus a provenance dict.

    POWER returns `properties.parameter.<CODE>` as a {YYYYMMDD: value} map directly - there is NO
    `values` wrapper. Reading it as `parameter[code]["values"]` returns nothing and produces a
    dataset of Nones that looks like a complete download.
    """
    header = payload.get("header", {})
    fill = float(header.get("fill_value", FILL_VALUE))
    parameters = payload.get("properties", {}).get("parameter", {})
    if not parameters:
        raise ValueError("POWER payload has no properties.parameter block")

    dates = sorted({day for series in parameters.values() for day in series})
    missing_counts: dict[str, int] = {}
    for code in PARAMETERS:
        series = parameters.get(code) or {}
        missing_counts[code] = sum(
            1 for day in dates
            if series.get(day) is None or float(series.get(day)) == fill)

    rows: list[dict] = []
    for day in dates:
        row: dict = {"date": f"{day[0:4]}-{day[4:6]}-{day[6:8]}"}
        for code in PARAMETERS:
            value = (parameters.get(code) or {}).get(day)
            row[code] = "" if value is None or float(value) == fill else float(value)
        rows.append(row)

    coordinates = payload.get("geometry", {}).get("coordinates") or []
    meta = {
        "missingPerParameter": missing_counts,
        "apiVersion": (header.get("api") or {}).get("version"),
        "sources": header.get("sources"),
        "elevationM": coordinates[2] if len(coordinates) > 2 else None,
        "dayCount": len(dates),
        "firstDay": rows[0]["date"] if rows else None,
        "lastDay": rows[-1]["date"] if rows else None,
    }
    return rows, meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="20180101")
    parser.add_argument("--end", default="20251031")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": {
            "name": "NASA POWER daily agroclimatology (community AG)",
            "publisher": "NASA Langley Research Center, POWER Project",
            "endpoint": ENDPOINT,
            "license": ("No restrictions on use, access or download; citation requested. "
                        "Verified at https://power.larc.nasa.gov/ and "
                        "registry.opendata.aws/nasa-power"),
            "fillValue": FILL_VALUE,
            "parameters": PARAMETERS,
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "sites": {},
    }

    failures = 0
    for site in SITES:
        key = f"{site['siteId']}_{args.start}_{args.end}"
        url = build_url(site, args.start, args.end)
        target = RAW / f"power_{site['siteId']}"
        try:
            body, fetched_at = fetch(url)
            # Write first, parse second: a parse bug must not cost a download.
            target.write_bytes(body)
        except RuntimeError as error:
            print(f"[FAIL] {site['siteId']}: {error}")
            manifest["sites"][key] = {**site, "status": "failed", "error": str(error)}
            failures += 1
            continue

        payload = json.loads(body)
        rows, meta = to_rows(payload)
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
            **meta,
        }
        print(f"[OK]   {site['siteId']}: {meta['dayCount']} days, "
              f"elev {meta['elevationM']} m, API {meta['apiVersion']}, "
              f"missing {sum(meta['missingPerParameter'].values())}")

    safedata.dump(manifest, MANIFEST)
    print(f"\nwrote {MANIFEST.relative_to(ROOT)} "
          f"({len(SITES) - failures}/{len(SITES)} sites)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
