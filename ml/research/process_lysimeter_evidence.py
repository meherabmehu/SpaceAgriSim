#!/usr/bin/env python3
"""Convert the raw Agroscope and TERENO archives into tidy, unit-explicit CSV.

Raw files stay raw: nothing here edits, resamples or gap-fills a measurement. Every conversion
is a rename plus an explicit unit conversion, and every conversion is listed in
``UNIT_CONVERSIONS`` so a reader can check it rather than trust it.

Layout quirks handled here
--------------------------
* Agroscope ``DATA_ETa.csv`` is a semicolon file with a units row and ``DD.MM.YYYY HH:MM:SS``
  timestamps, one column per lysimeter, in mm/day.
* Agroscope ``DATA_FDR/Lysi_FDR<depth>.csv`` repeats a ``Lys N`` header twice because there are
  two sensors per depth; the header is rebuilt from the duplicated group labels rather than from
  the ``FDR<depth>.<rep>`` sub-labels, because the latter repeat across lysimeters.
* TERENO workbooks carry live Excel formulas in the ``LY`` and ``LY minus LE`` columns. Only the
  numeric columns are read; a formula column read through openpyxl (non-``data_only``) is a
  string and would silently poison an arithmetic column with text.

    python3 ml/research/process_lysimeter_evidence.py
"""
from __future__ import annotations
import sys

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "lysimeter"
MANIFEST = ROOT / "data" / "metadata" / "lysimeter_processing_manifest"

UNIT_CONVERSIONS = {
    "agroscope.eta": "none - already mm/day for a 1 m2 weighable lysimeter",
    "agroscope.fdr": "none - already volumetric % at the stated depth",
    "tereno.vapour_pressure_hpa_to_kpa": "hPa / 10 = kPa",
    "tereno.wm2_to_mm_per_hour": "LE [W m-2] * 0.0036 / 2.45 = mm h-1 (latent heat of vaporisation 2.45 MJ kg-1)",
    "tereno.available_energy": "A is Rn - G as measured by the station; used directly, not re-modelled",
}

ZSITE = RAW / "zenodo_20825203"
TSITE = RAW / "zenodo_3957208"


def parse_timestamp(text: str) -> str:
    """DD.MM.YYYY HH:MM:SS -> YYYY-MM-DD. Returns the date only."""
    return datetime.strptime(text.strip(), "%d.%m.%Y %H:%M:%S").date().isoformat()


def read_agroscope_eta() -> list[dict]:
    path = ZSITE / "DATA_ETa.csv"
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        header = next(reader)              # ;Lys 1;Lys 5;...
        labels = next(reader)              # Date & Time;Actual ET;...
        units = next(reader)               # ;mm;mm;...
        assert labels[0].strip() == "Date & Time", f"unexpected ETa label row: {labels[:2]}"
        assert units[1].strip() == "mm", f"unexpected ETa units row: {units[:3]}"
        lysimeters = [cell.strip() for cell in header[1:] if cell.strip()]
        for record in reader:
            if not record or not record[0].strip():
                continue
            day = parse_timestamp(record[0])
            for index, lysimeter in enumerate(lysimeters):
                raw = record[index + 1].strip() if index + 1 < len(record) else ""
                if raw and raw.upper() not in {"NA", "NAN"}:
                    rows.append({"date": day, "lysimeter": lysimeter.replace("Lys ", "L"),
                                 "eta_mm_d": float(raw)})
    return rows


def read_treatments() -> dict[str, dict]:
    path = ZSITE / "KEY_TreatmentsByLysi.csv"
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for record in reader:
            # The header carries a trailing space ("Soil "); strip keys as well as values.
            record = {(k or "").strip(): (v or "").strip() for k, v in record.items()}
            if not record.get("Lysi"):
                continue
            key = f"L{record['Lysi']}"
            out[key] = {"treatment": record["Treatment"], "soil": record["Soil"]}
    return out


def read_agroscope_fdr() -> list[dict]:
    rows: list[dict] = []
    for depth in (10, 30, 60, 90):
        path = ZSITE / "DATA_FDR" / f"Lysi_FDR{depth}.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=";")
            group = next(reader)
            sub = next(reader)
            units = next(reader)
            assert units[1].strip() == "[Vol%]", f"unexpected FDR units row in {path.name}"
            columns = []
            current = None
            for index in range(1, len(group)):
                label = group[index].strip()
                if label:
                    current = label.replace("Lys ", "L")
                columns.append((current, sub[index].strip()))
            for record in reader:
                if not record or not record[0].strip():
                    continue
                day = parse_timestamp(record[0])
                for index, (lysimeter, sensor) in enumerate(columns):
                    cell = record[index + 1].strip() if index + 1 < len(record) else ""
                    if cell and cell.upper() not in {"NA", "NAN"}:
                        rows.append({"date": day, "lysimeter": lysimeter, "depth_cm": depth,
                                     "sensor": sensor, "vwc_vol_pct": float(cell)})
    return rows


# TERENO sheets are not interchangeable. Several workbooks repeat the same observations in two
# or three sheets (a raw sheet and a filtered or re-arranged copy), and one of them - the 2013
# Graswang sheet - carries no wind speed at all, so no aerodynamic term can be computed from it.
# The canonical sheet per workbook is therefore pinned by name, and every workbook that is not
# used is listed with the reason, rather than being skipped silently.
TERENO_SHEETS = [
    {"file": "FE_2013.xlsx", "sheet": "FE13_crono", "site": "Fendt", "year": 2013,
     "hourColumn": "hr"},
    {"file": "FE_2014.xlsx", "sheet": "EC_vs_LY", "site": "Fendt", "year": 2014,
     "hourColumn": "hrs"},
    {"file": "GW_2014.xlsx", "sheet": "GW14_crono", "site": "Graswang", "year": 2014,
     "hourColumn": "place"},
]
TERENO_EXCLUDED = [
    {"file": "GW2013_.xlsx", "sheet": "all Data",
     "reason": "no wind speed column (Ta/ea/pa/ra/oA/oH/oLE only); the aerodynamic term of "
               "Penman-Monteith cannot be evaluated without u2"},
    {"file": "FE_2013.xlsx", "sheet": "dE&wLin", "reason": "re-arranged copy of FE13_crono"},
    {"file": "FE_2014.xlsx", "sheet": "only flags 000 (2)",
     "reason": "quality-flag filtered subset of EC_vs_LY; the unfiltered sheet is used instead"},
    {"file": "FE_2014.xlsx", "sheet": "FE 14 full", "reason": "no DoY header block"},
    {"file": "GW2013_SM.xlsx", "sheet": "*", "reason": "soil-moisture workbook, not a flux table"},
]
TERENO_COLUMNS = {"Ta": "t_c", "T_ref": "t_c", "ea": "ea_hpa", "pa": "p_hpa", "p_ref": "p_hpa",
                  "ra": "ra_s_m", "oA": "available_wm2", "A": "available_wm2",
                  "oH": "h_wm2", "HTs": "h_wm2", "oLE": "le_wm2", "LvE": "le_wm2",
                  "v": "u_ms"}


def read_tereno() -> tuple[list[dict], list[dict]]:
    import openpyxl

    rows: list[dict] = []
    inventory: list[dict] = []
    for spec in TERENO_SHEETS:
        path = TSITE / "Graswang_Fendt_data" / spec["file"]
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = workbook[spec["sheet"]]
        header: list[str] | None = None
        kept = 0
        for record in sheet.iter_rows(values_only=True):
            if header is None:
                cells = [str(cell).strip() if cell is not None else "" for cell in record]
                if "DoY" in cells:
                    header = cells
                continue
            values = dict(zip(header, record))
            day = values.get("DoY")
            hour = values.get(spec["hourColumn"])
            if day is None or hour is None:
                continue
            if hasattr(hour, "hour"):
                hour = hour.hour
            try:
                day_number, hour_number = int(float(day)), int(float(hour))
            except (TypeError, ValueError):
                continue
            row = {"file": spec["file"], "sheet": spec["sheet"], "site": spec["site"],
                   "year": spec["year"], "day_of_year": day_number, "hour": hour_number}
            for source, target in TERENO_COLUMNS.items():
                cell = values.get(source)
                if isinstance(cell, (int, float)):
                    row[target] = float(cell)
            if "t_c" in row and "le_wm2" in row:
                rows.append(row)
                kept += 1
        inventory.append({"file": spec["file"], "sheet": spec["sheet"], "site": spec["site"],
                          "year": spec["year"], "rows": kept})
        workbook.close()
    return rows, inventory


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(",".join(columns) + "\n")
        for row in rows:
            handle.write(",".join("" if row.get(c) is None else str(row[c]) for c in columns)
                         + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"generatedAt": datetime.now(timezone.utc).isoformat(),
                    "unitConversions": UNIT_CONVERSIONS}

    eta = read_agroscope_eta()
    treatments = read_treatments()
    for row in eta:
        row.update(treatments.get(row["lysimeter"], {}))
    write_csv(OUT / "zurich_eta_daily.csv", eta,
              ["date", "lysimeter", "eta_mm_d", "treatment", "soil"])
    report["zurichEta"] = {
        "rows": len(eta),
        "lysimeters": sorted({r["lysimeter"] for r in eta}),
        "firstDate": min(r["date"] for r in eta),
        "lastDate": max(r["date"] for r in eta),
        "missingCells": None,
    }

    fdr = read_agroscope_fdr()
    write_csv(OUT / "zurich_fdr_daily.csv", fdr,
              ["date", "lysimeter", "depth_cm", "sensor", "vwc_vol_pct"])
    report["zurichFdr"] = {
        "rows": len(fdr),
        "depthsCm": sorted({r["depth_cm"] for r in fdr}),
        "firstDate": min(r["date"] for r in fdr),
        "lastDate": max(r["date"] for r in fdr),
        "vwcRangePct": [round(min(r["vwc_vol_pct"] for r in fdr), 2),
                        round(max(r["vwc_vol_pct"] for r in fdr), 2)],
    }

    tereno, inventory = read_tereno()
    for row in tereno:
        row["et_measured_mm_h"] = round(row["le_wm2"] * 0.0036 / 2.45, 5)
        row["ea_kpa"] = round(row["ea_hpa"] / 10.0, 4) if row.get("ea_hpa") is not None else None
    write_csv(OUT / "tereno_hourly.csv", tereno,
              ["file", "sheet", "site", "year", "day_of_year", "hour", "t_c", "ea_hpa",
               "ea_kpa", "p_hpa",
               "u_ms", "ra_s_m", "available_wm2", "h_wm2", "le_wm2", "et_measured_mm_h"])
    report["tereno"] = {
        "rows": len(tereno),
        "files": inventory,
        "excludedSheets": TERENO_EXCLUDED,
        "sites": sorted({r["site"] for r in tereno}),
        "yearRange": [min(r["year"] for r in tereno), max(r["year"] for r in tereno)],
        "hoursMissingWind": sum(1 for r in tereno if r.get("u_ms") is None),
        "hoursWithNegativeLe": sum(1 for r in tereno if r["le_wm2"] < 0),
    }

    safedata.dump(report, MANIFEST)
    print(json.dumps(report, indent=2)[:1600])
    print(f"\nmanifest -> {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
