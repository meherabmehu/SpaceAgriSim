#!/usr/bin/env python3
"""Acquire NASA POWER daily agroclimatology for the two *measurement* sites.

Why this is separate from ``acquire_power_climate.py``
------------------------------------------------------
That script covers the six siting-reference sites and writes a manifest the rest of the platform
reads. Adding the measurement sites to it would change the shape of an artefact other code
depends on. This script writes its own manifest and its own files, so the siting dataset and the
validation dataset stay separable and neither can be mistaken for the other.

Why these two sites
-------------------
The Agroscope weighable lysimeter at Zurich-Reckenholz measures actual ET daily for 2013-2016.
To turn that into a statement about the ET0 model - rather than a description of the weather -
the model has to be evaluated at the same place on the same days, which needs POWER forcing on
the lysimeter's own grid cell.

    python3 ml/research/acquire_power_validation_sites.py
"""
from __future__ import annotations
import sys

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
RAW = ROOT / "data" / "raw" / "nasa_power_validation"
PROCESSED = ROOT / "data" / "processed" / "power_validation"
MANIFEST = ROOT / "data" / "metadata" / "power_validation_manifest"

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL_VALUE = -999.0
PARAMETERS = ["ALLSKY_SFC_SW_DWN", "T2M", "T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M", "WS2M", "PS",
              "PRECTOTCORR"]

SITES = [
    {"siteId": "zurich_reckenholz_ch", "siteName": "Zurich-Reckenholz lysimeter, Switzerland",
     "latitude": 47.428, "longitude": 8.518, "start": "20130801", "end": "20160731",
     "rationale": "weighable-lysimeter ETa measurement site (Agroscope, Zenodo 20825203)"},
]

COLUMNS = ["date", "sw_mj_m2", "t2m_c", "t2m_max_c", "t2m_min_c", "t2mdew_c", "rh2m_pct",
           "ws2m_ms", "ps_kpa", "precip_mm"]


def build_url(site: dict) -> str:
    query = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": site["longitude"],
        "latitude": site["latitude"],
        "start": site["start"],
        "end": site["end"],
        "format": "JSON",
    }
    return f"{ENDPOINT}?{urllib.parse.urlencode(query)}"


def fetch(url: str, attempts: int = 3, timeout: int = 120) -> tuple[bytes, str]:
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


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": {
            "name": "NASA POWER daily agroclimatology (community AG) - measurement sites",
            "publisher": "NASA Langley Research Center, POWER Project",
            "endpoint": ENDPOINT,
            "license": ("No restrictions on use, access or download; citation requested. "
                        "Verified at https://power.larc.nasa.gov/"),
            "fillValue": FILL_VALUE,
            "parameters": PARAMETERS,
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "sites": {},
    }

    failures = 0
    for site in SITES:
        url = build_url(site)
        target = RAW / f"power_{site['siteId']}"
        try:
            body, fetched_at = fetch(url)
            target.write_bytes(body)
        except RuntimeError as error:
            print(f"[FAIL] {site['siteId']}: {error}")
            manifest["sites"][site["siteId"]] = {**site, "status": "failed", "error": str(error)}
            failures += 1
            continue

        payload = json.loads(body)
        header = payload.get("header", {})
        fill = float(header.get("fill_value", FILL_VALUE))
        parameters = payload["properties"]["parameter"]
        days = sorted({day for series in parameters.values() for day in series})
        rows = []
        missing = {code: 0 for code in PARAMETERS}
        for day in days:
            row = {"date": f"{day[0:4]}-{day[4:6]}-{day[6:8]}"}
            for code in PARAMETERS:
                value = parameters[code].get(day)
                if value is None or float(value) == fill:
                    missing[code] += 1
                    row[code] = None
                else:
                    row[code] = float(value)
            rows.append(row)
        mapping = {"ALLSKY_SFC_SW_DWN": "sw_mj_m2", "T2M": "t2m_c", "T2M_MAX": "t2m_max_c",
                   "T2M_MIN": "t2m_min_c", "T2MDEW": "t2mdew_c", "RH2M": "rh2m_pct",
                   "WS2M": "ws2m_ms", "PS": "ps_kpa", "PRECTOTCORR": "precip_mm"}
        for row in rows:
            for source, column in mapping.items():
                row[column] = row[source]
        csv_path = PROCESSED / f"{site['siteId']}.csv"
        with csv_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(",".join(COLUMNS) + "\n")
            for row in rows:
                handle.write(",".join("" if row.get(c) is None else str(row[c])
                                      for c in COLUMNS) + "\n")
        elevation = (payload.get("geometry", {}).get("coordinates") or [None, None, None])
        manifest["sites"][site["siteId"]] = {
            **site,
            "status": "ok",
            "apiUrl": url,
            "fetchedAt": fetched_at,
            "rawFile": str(target.relative_to(ROOT)),
            "rawBytes": len(body),
            "rawSha256": hashlib.sha256(body).hexdigest(),
            "processedCsv": str(csv_path.relative_to(ROOT)),
            "apiVersion": (header.get("api") or {}).get("version"),
            "elevationM": elevation[2] if len(elevation) > 2 else None,
            "dayCount": len(rows),
            "missingPerParameter": missing,
        }
        print(f"[OK]   {site['siteId']}: {len(rows)} days, missing "
              f"{sum(missing.values())}, elev {elevation[2] if len(elevation) > 2 else '?'} m")

    manifest["summary"] = {"sitesRequested": len(SITES), "sitesFailed": failures}
    safedata.dump(manifest, MANIFEST)
    print(f"manifest -> {MANIFEST.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
