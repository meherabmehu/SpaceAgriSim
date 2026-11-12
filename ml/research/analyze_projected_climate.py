#!/usr/bin/env python3
"""Quantify the mid-century shift at the six reference sites from NEX-GDDP-CMIP6.

What this is
------------
A single-model, single-scenario, two-window comparison: ACCESS-CM2, SSP2-4.5, 2000-2004 against
2045-2049, five daily variables, extracted at the six siting sites. It answers "in which
direction and roughly how much does the outdoor environment at each site move", which is what a
siting discussion needs and what the platform previously had no evidence for at all.

What this is not
----------------
* Not an ensemble. One model's response is not the CMIP6 distribution, and no uncertainty range is
  derived from it. The inter-model spread is the uncertainty and it is not characterised here.
* Not a prediction of crop yield. It is an environmental driver.
* Not a statement about a greenhouse interior. A controlled-environment system modifies
  temperature and VPD; the projections describe the outdoor forcing a system would have to
  reject.

Every derived quantity is labelled. A site whose grid cell is ocean in the source - which happens
because the grid is 0.25 degrees and coastlines are finer than that - is reported as unavailable
rather than silently filled.

    python3 ml/research/analyze_projected_climate.py
"""
from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed" / "nex_gddp"
MANIFEST = ROOT / "data" / "metadata" / "nex_gddp_acquisition_manifest.json"
OUT = ROOT / "data" / "research" / "phase36"
REPORT = OUT / "projected_climate.json"

SITES = ["wageningen_nl", "tucson_us", "singapore_sg", "dhaka_bd", "reykjavik_is", "nairobi_ke"]
BASELINE = "2000-2004"
FUTURE = "2045-2049"


def load(site: str) -> list[dict]:
    path = PROCESSED / f"{site}.csv"
    rows = []
    for row in csv.DictReader(path.open()):
        parsed = {"date": row["date"], "scenario": row["scenario"]}
        for key in ("tas_c", "tasmax_c", "hurs_pct", "pr_mm_d", "rsds_wm2", "vpd_kpa",
                    "dli_mol_m2_d"):
            parsed[key] = float(row[key]) if row[key] else None
        rows.append(parsed)
    return rows


def window_summary(rows: list[dict], year_from: int, year_to: int) -> dict:
    selected = [r for r in rows if year_from <= int(r["date"][:4]) <= year_to]

    def values(key: str) -> list[float]:
        return [r[key] for r in selected if r[key] is not None]

    temperature = values("tas_c")
    hot_days = values("tasmax_c")
    precipitation = values("pr_mm_d")
    years = year_to - year_from + 1
    return {
        "days": len(selected),
        "meanTasC": round(statistics.fmean(temperature), 3) if temperature else None,
        "meanTasmaxC": round(statistics.fmean(hot_days), 3) if hot_days else None,
        "daysAbove30C": sum(1 for t in hot_days if t > 30.0),
        "daysAbove35C": sum(1 for t in hot_days if t > 35.0),
        "meanVpdKpa": (round(statistics.fmean(values("vpd_kpa")), 4)
                       if values("vpd_kpa") else None),
        "meanDliMolM2D": (round(statistics.fmean(values("dli_mol_m2_d")), 3)
                          if values("dli_mol_m2_d") else None),
        "annualPrecipMm": (round(sum(precipitation) / years, 1) if precipitation else None),
        "daysMeasured": len(temperature),
    }


def delta(baseline: dict, future: dict) -> dict:
    out = {}
    for key in ("meanTasC", "meanTasmaxC", "meanVpdKpa", "meanDliMolM2D", "annualPrecipMm"):
        a, b = baseline.get(key), future.get(key)
        out[key] = round(b - a, 3) if a is not None and b is not None else None
    for key in ("daysAbove30C", "daysAbove35C"):
        out[key] = future[key] - baseline[key]
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": []}
    blocked: dict[str, int] = {}
    for entry in manifest.get("files", []):
        for site, count in (entry.get("fillCells") or {}).items():
            blocked[site] = blocked.get(site, 0) + int(count)

    per_site: dict[str, dict] = {}
    for site in SITES:
        path = PROCESSED / f"{site}.csv"
        if not path.exists():
            per_site[site] = {"status": "UNAVAILABLE", "reason": "processed series missing"}
            continue
        rows = load(site)
        baseline = window_summary(rows, 2000, 2004)
        future = window_summary(rows, 2045, 2049)
        # A site whose cell is ocean in some file is not silently averaged: its missing days are
        # visible in `daysMeasured` against the 1826 days a five-year window contains.
        complete = baseline["daysMeasured"] >= 1800 and future["daysMeasured"] >= 1800
        per_site[site] = {
            "status": "COMPUTED" if complete else "PARTIAL",
            "gridCell": (manifest.get("cells", {}) or {}).get(site),
            "fillValuesInSource": blocked.get(site, 0),
            "baseline": baseline,
            "midCentury": future,
            "delta": delta(baseline, future),
        }

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/analyze_projected_climate.py",
        "source": {
            "product": "NASA NEX-GDDP-CMIP6",
            "model": "ACCESS-CM2",
            "member": "r1i1p1f1",
            "scenario": "SSP2-4.5",
            "windows": {"baseline": BASELINE, "midCentury": FUTURE},
            "gridResolution": "0.25 degree",
        },
        "evidenceLabel": {
            "measured": "none - these are model projections, not observations",
            "predicted": "ACCESS-CM2 SSP2-4.5 daily fields, statistically downscaled by NEX",
            "derived": "window means, threshold-day counts, VPD and DLI computed from the fields",
        },
        "limitations": [
            "single GCM: no inter-model spread is characterised",
            "single scenario: SSP2-4.5 only",
            "grid-cell values at 0.25 degree, not site observations",
            "DLI from rsds uses the PAR fraction and photon conversion conventions, which "
            "describe solar spectrum, not a lamp",
        ],
        "sites": per_site,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{'site':<14}{'dT':>7}{'dTmax':>7}{'dVPD':>7}{'dDLI':>7}{'d>30C':>7}{'dPrec':>8}")
    for site, values in per_site.items():
        if values.get("status") == "UNAVAILABLE":
            print(f"{site:<14} UNAVAILABLE")
            continue
        d = values["delta"]
        print(f"{site:<14}{d['meanTasC']:>7.2f}{d['meanTasmaxC']:>7.2f}{d['meanVpdKpa']:>7.2f}"
              f"{d['meanDliMolM2D']:>7.2f}{d['daysAbove30C']:>7}{d['annualPrecipMm']:>8.0f}")
    print(f"\nreport -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
