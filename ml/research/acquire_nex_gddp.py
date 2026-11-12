#!/usr/bin/env python3
"""Acquire NASA NEX-GDDP-CMIP6 daily projections for the six SpaceAgriSim reference sites.

Why this exists
---------------
Gap ``long-run-climate`` in ``data/research/dataset_gap_matrix.json`` records that the platform
can say what the weather was at a site but not what it is projected to become, so any statement
about whether a location stays viable under mid-century forcing had no evidence behind it.

Why the extraction is done this way
-----------------------------------
A NEX-GDDP-CMIP6 file is a global 0.25 deg daily grid for one variable and one year, about
220-280 MB compressed, chunked one time step per chunk. Reading a single grid cell therefore
costs a full chunk, and a year of chunks costs about the whole file. The honest options are
(a) download the file and keep it, or (b) download it, extract the six cells, checksum it and
discard it. Option (a) would put ~12 GB of globally redundant gridded data in the repository for
six point series; option (b) is what this script does. The SHA-256 of every source object is
computed while the bytes stream through, so the derived series stays traceable to an exact
source object even though the object is not retained.

Grid conventions that bite
--------------------------
* Longitudes run 0..360, not -180..180. A naive nearest-neighbour search sends Reykjavik
  (-21.90) to the cell at 0.125 E, which is Atlantic fill value, and the result is a series of
  1e20 that still looks like a download.
* Fill value is 1e20, not -999. It is mapped to None, never to a number.
* ``time`` is "days since 1850-01-01". Dates are rebuilt from the file's own year and the
  number of time steps, and asserted against the calendar, so a wrong number of days fails loudly.

    python3 ml/research/acquire_nex_gddp.py [--model ACCESS-CM2] [--write-manifest-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed" / "nex_gddp"
MANIFEST = ROOT / "data" / "metadata" / "nex_gddp_acquisition_manifest.json"
STAGING = Path("/var/tmp/spaceagrisim_nex")

BUCKET = "https://nex-gddp-cmip6.s3.amazonaws.com"
FILL = 1.0e20

SITES = [
    {"siteId": "wageningen_nl", "latitude": 51.97, "longitude": 5.67},
    {"siteId": "tucson_us", "latitude": 32.28, "longitude": -110.95},
    {"siteId": "singapore_sg", "latitude": 1.35, "longitude": 103.82},
    {"siteId": "dhaka_bd", "latitude": 23.81, "longitude": 90.41},
    {"siteId": "reykjavik_is", "latitude": 64.13, "longitude": -21.90},
    {"siteId": "nairobi_ke", "latitude": -1.29, "longitude": 36.82},
]

# Two windows, one model: a 5-year historical baseline and a 5-year mid-century window under
# SSP2-4.5. Five years is enough for a monthly climatology; one model is enough for a direction
# and magnitude, and explicitly NOT enough for an uncertainty range, which the report states.
WINDOWS = [
    {"scenario": "historical", "years": [2000, 2001, 2002, 2003, 2004]},
    {"scenario": "ssp245", "years": [2045, 2046, 2047, 2048, 2049]},
]
VARIABLES = ["tas", "tasmax", "hurs", "pr", "rsds"]
VARIANTS = ["v2.0"]

COLUMN = {"tas": "tas_c", "tasmax": "tasmax_c", "hurs": "hurs_pct", "pr": "pr_mm_d",
          "rsds": "rsds_wm2"}

# Published units per variable, asserted against the file's own `units` attribute before any
# arithmetic. NEX-GDDP-CMIP6 stores temperature in KELVIN and precipitation as a kg m-2 s-1
# FLUX. A temperature read as degC puts every VPD through the Magnus equation around 285 instead
# of 12; a flux rounded to three decimals becomes exactly zero everywhere. Neither looks like an
# error in the output table, which is why the conversion happens here and the units are checked
# rather than assumed.
EXPECTED_UNITS = {
    "tas": "K", "tasmax": "K", "hurs": "%", "pr": "kg m-2 s-1", "rsds": "W m-2",
}
KELVIN_OFFSET = 273.15
SECONDS_PER_DAY = 86400.0


def to_display_units(variable: str, values):
    """Convert a source variable to the unit this repository stores, returning (array, unit)."""
    if variable in ("tas", "tasmax"):
        return values - KELVIN_OFFSET, "degC"
    if variable == "pr":
        # kg m-2 s-1 of water == mm s-1 of water depth
        return values * SECONDS_PER_DAY, "mm day-1"
    if variable == "hurs":
        return values, "%"
    if variable == "rsds":
        return values, "W m-2"
    raise ValueError(f"no conversion defined for {variable}")


def object_url(model: str, scenario: str, variable: str, year: int, version: str) -> str:
    name = f"{variable}_day_{model}_{scenario}_r1i1p1f1_gn_{year}_{version}.nc"
    return f"{BUCKET}/NEX-GDDP-CMIP6/{model}/{scenario}/r1i1p1f1/{variable}/{name}"


def download(url: str, target: Path) -> tuple[int, str]:
    """Download to disk, then hash. Returns (bytes, sha256).

    Uses curl rather than ``urllib``: streaming 250 MB through ``urllib.read`` measured at
    4.5 MB/s in this environment against 54 MB/s for the same object through curl, which turns a
    six-minute acquisition into three quarters of an hour. curl is invoked with ``-f`` so an HTTP
    error is a non-zero exit rather than a 404 page written to a .nc file.
    """
    result = subprocess.run(
        ["curl", "-sSfL", "--retry", "3", "--retry-delay", "2", "--max-time", "600",
         "-A", "SpaceAgriSim/1.0", "-o", str(target), url],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed ({result.returncode}): {result.stderr.strip()[:200]}")
    digest = hashlib.sha256()
    size = 0
    with target.open("rb") as handle:
        while True:
            block = handle.read(1 << 22)
            if not block:
                break
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def nearest_index(axis, value: float) -> int:
    best, index = None, 0
    for i, candidate in enumerate(axis):
        distance = abs(float(candidate) - value)
        if best is None or distance < best:
            best, index = distance, i
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ACCESS-CM2")
    args = parser.parse_args()

    import h5py  # imported here so --help works without the optional dependency
    import numpy as np

    PROCESSED.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": {
            "name": "NASA NEX-GDDP-CMIP6 statistically downscaled daily projections",
            "publisher": "NASA Earth Exchange (NEX)",
            "bucket": BUCKET,
            "model": args.model,
            "member": "r1i1p1f1",
            "variant": VARIANTS[0],
            "windows": WINDOWS,
            "variables": VARIABLES,
            "license": ("NASA NEX-GDDP-CMIP6 is distributed as open data; CMIP6 model output "
                        "carries the CMIP6 terms of use and a citation request"),
            "licenseUrl": "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6",
            "retention": ("source objects are streamed, SHA-256 checksummed and discarded; only "
                          "the six point series are retained"),
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "files": [],
        "cells": {},
    }

    # siteId -> date -> row
    series: dict[str, dict[str, dict]] = {s["siteId"]: {} for s in SITES}
    cell_lookup: dict[str, dict] = {}

    failures = 0
    for window in WINDOWS:
        scenario = window["scenario"]
        for year in window["years"]:
            for variable in VARIABLES:
                for version in VARIANTS:
                    url = object_url(args.model, scenario, variable, year, version)
                    staged = STAGING / Path(url).name
                    try:
                        size, sha = download(url, staged)
                    except Exception as error:  # noqa: BLE001 - recorded, not swallowed
                        print(f"[FAIL] {url}: {error}")
                        manifest["files"].append({"url": url, "status": "failed",
                                                  "error": str(error)})
                        failures += 1
                        continue
                    with h5py.File(staged, "r") as handle:
                        lat = handle["lat"][:]
                        lon = handle["lon"][:]
                        data = handle[variable]
                        reported_units = (data.attrs.get("units") or "").decode() \
                            if isinstance(data.attrs.get("units"), bytes) \
                            else str(data.attrs.get("units"))
                        if reported_units != EXPECTED_UNITS[variable]:
                            raise ValueError(
                                f"{url}: units {reported_units!r} != expected "
                                f"{EXPECTED_UNITS[variable]!r}")
                        steps = data.shape[0]
                        # Rebuild the calendar from the file's own year and length, then assert
                        # it agrees with the number of time steps actually stored.
                        start = date(year, 1, 1)
                        days = [start + timedelta(days=i) for i in range(steps)]
                        if days[-1].year != year:
                            raise ValueError(f"{url}: {steps} steps spill past {year}")
                        # One pass over the chunks. The dataset is chunked one time step per
                        # chunk, so indexing a single cell six times decompresses the same chunk
                        # six times, which measured at ~100 s per file. Reading the six rows in a
                        # single request decompresses each chunk once and slices in memory after.
                        rows_wanted = []
                        for site in SITES:
                            lon360 = float(site["longitude"]) % 360.0
                            iy = nearest_index(lat, float(site["latitude"]))
                            ix = nearest_index(lon, lon360)
                            rows_wanted.append((site["siteId"], iy, ix))
                            if site["siteId"] not in cell_lookup:
                                cell_lookup[site["siteId"]] = {
                                    "requestedLat": site["latitude"],
                                    "requestedLon": site["longitude"],
                                    "cellLat": float(lat[iy]),
                                    "cellLon": float(lon[ix]),
                                    "cellLonDegreesEast": float(lon[ix]) if lon[ix] <= 180
                                    else float(lon[ix]) - 360.0,
                                }
                        lats = sorted({iy for _, iy, _ in rows_wanted})
                        block = data[:, lats, :]
                        lat_slot = {iy: position for position, iy in enumerate(lats)}
                        values = {}
                        for site_id, iy, ix in rows_wanted:
                            raw_column = np.asarray(block[:, lat_slot[iy], ix], dtype="float64")
                            converted, stored_unit = to_display_units(variable, raw_column)
                            values[site_id] = converted
                    fill_count = {}
                    for site in SITES:
                        column = values[site["siteId"]]
                        filled = int(np.sum(np.abs(column - FILL) < 1.0))
                        fill_count[site["siteId"]] = filled
                        for i, day in enumerate(days):
                            value = float(column[i])
                            if abs(value - FILL) < 1.0:
                                continue
                            row = series[site["siteId"]].setdefault(
                                day.isoformat(), {"date": day.isoformat(), "scenario": scenario})
                            row[COLUMN[variable]] = round(value, 3)
                            row.setdefault("units", {})[COLUMN[variable]] = stored_unit
                    staged.unlink(missing_ok=True)
                    manifest["files"].append({
                        "url": url, "status": "ok", "bytes": size, "sha256": sha,
                        "rows": steps, "fillCells": fill_count,
                        "sourceUnits": EXPECTED_UNITS[variable],
                        "storedUnits": to_display_units(variable, np.zeros(1))[1],
                        "firstDay": days[0].isoformat(), "lastDay": days[-1].isoformat(),
                    })
                    print(f"[OK]   {scenario} {year} {variable:<7} {size/1e6:6.1f} MB "
                          f"{steps} days fill={sum(fill_count.values())}")

    # Derived columns. VPD uses the same FAO-56 Magnus form as the hourly acquisition, so the
    # two products cannot disagree about what VPD means.
    import math
    for site_id, rows in series.items():
        for row in rows.values():
            if row.get("tas_c") is not None and row.get("hurs_pct") is not None:
                es = 0.6108 * math.exp(17.27 * row["tas_c"] / (row["tas_c"] + 237.3))
                ea = es * max(0.0, min(100.0, row["hurs_pct"])) / 100.0
                row["vpd_kpa"] = round(max(0.0, es - ea), 4)
            if row.get("rsds_wm2") is not None:
                row["dli_mol_m2_d"] = round(row["rsds_wm2"] * 0.45 * 4.57 * 86400 / 1e6, 3)
        target = PROCESSED / f"{site_id}.csv"
        columns = ["date", "scenario", "tas_c", "tasmax_c", "hurs_pct", "pr_mm_d", "rsds_wm2",
                   "vpd_kpa", "dli_mol_m2_d"]
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(",".join(columns) + "\n")
            for day in sorted(rows):
                handle.write(",".join("" if rows[day].get(c) is None else str(rows[day][c])
                                      for c in columns) + "\n")
        manifest["cells"][site_id] = cell_lookup.get(site_id, {})

    manifest["summary"] = {
        "objectsRequested": len(WINDOWS) * sum(len(w["years"]) for w in WINDOWS) // len(WINDOWS)
        * len(VARIABLES) * len(VARIANTS),
        "objectsOk": sum(1 for f in manifest["files"] if f["status"] == "ok"),
        "objectsFailed": failures,
        "bytesTransferred": sum(f.get("bytes", 0) for f in manifest["files"]),
        "blockedCells": {k: v for k, v in manifest["cells"].items()},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"\nmanifest -> {MANIFEST.relative_to(ROOT)}")
    print(json.dumps(manifest["summary"], indent=2)[:600])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
