#!/usr/bin/env python3
"""What the nutrient-dosing trial supports, and the step it does not support.

The gap this is for
-------------------
``nutrient-balance`` asked for "ion concentrations, uptake rates and EC/pH response per crop".

Zenodo 10.5281/zenodo.17794636 measures eight ions (nitrate, phosphate, potassium, calcium,
magnesium, sulphate, iron, manganese) plus electrical conductivity across three independent
nutrient systems and three management regimes, over a 28-day Red Batavia lettuce cycle, with
destructive harvest fresh and dry mass.

The step this script will not take
----------------------------------
Turning a concentration change into an *uptake rate in mass per plant per day* needs three things:
a solution volume, a set of dosing events, and a sample labelled unambiguously as taken before or
after each event. The deposit supplies the volume (70 L per dosing event, in the economic sheet)
but its pre/post labels are not self-consistent: in the Treatment 1 sheet the two samples taken on
3 March are both labelled "Pre dose", and the sample labelled "Post dose" sits on a column headed
10 March while a further "Pre dose" follows it. Any pairing of those labels is an assumption, and
an uptake rate built on an assumed pairing is a modelled number wearing a measurement's clothes.

So this script reports what the deposit does support - the measured concentration trajectory, the
measured EC trajectory, and the measured harvest - and computes interval depletion rates from
dated consecutive samples, which needs no pre/post interpretation because both endpoints are real
measurements on known dates. It does not publish an ion mass balance, and the gap it belongs to
stays partially closed rather than being talked into a closure.

    python3 ml/research/analyze_nutrient_balance.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "zenodo_17794636"
OUT = ROOT / "data" / "research" / "phase37"
PROCESSED = ROOT / "data" / "processed" / "nutrient_dosing"

WORKBOOK = RAW / "Raw_data_Dosing_Experiment.xlsx"
IONS = ("Nitrate", "Phosphate", "Potassium", "Calcium", "Magnesium", "Sulphate", "Iron",
        "Manganese")
SHEETS = {"Treatment 1": "treatment1", "Treatment 2": "treatment2", "Control": "control"}
# From the economic sheet: 70 L per solution change. Recorded here as the deposit states it, not
# inferred, and only used for the concentration-to-mass conversion that the script does not publish
# as an uptake rate.
SOLUTION_VOLUME_L = 70.0


def _parse_system(rows: list[tuple], start: int) -> tuple[dict, int]:
    """Read one stacked system block.

    The block layout is: a header row carrying dates, a label row carrying Pre/Post text, eight ion
    rows, and an EC row. Blocks repeat down the sheet. Returns the parsed block and the index of the
    next row, so the caller never has to guess where a block ended.
    """
    header = rows[start]
    labels = rows[start + 1]
    dates = [value if isinstance(value, dt.datetime) else None for value in header]
    # Merged date cells report their value at the left edge only; carry it forward across the blank
    # cells that belong to the same merged span.
    carried: list[dt.datetime | None] = []
    last = None
    for value in dates:
        if value is not None:
            last = value
        carried.append(last)

    series = []
    for column in range(4, len(header)):
        if not isinstance(header[column], dt.datetime):
            continue
        date = header[column]
        label = labels[column]
        label = label.strip() if isinstance(label, str) else None
        series.append({"column": column, "date": date.date().isoformat(), "label": label})

    ions: dict[str, list[float | None]] = {}
    ec: list[float | None] = []
    index = start + 2
    while index < len(rows):
        row = rows[index]
        name = row[0]
        if name is None or str(name).strip() not in IONS + ("EC",):
            break
        values = [row[s["column"]] if s["column"] < len(row) else None for s in series]
        cleaned = [float(v) if isinstance(v, (int, float)) else None for v in values]
        if str(name).strip() == "EC":
            ec = cleaned
        else:
            ions[str(name).strip()] = cleaned
        index += 1
    return {"samples": series, "ions": ions, "ec": ec}, index


def _parse_sheet(sheet) -> dict:
    rows = list(sheet.iter_rows(values_only=True))
    systems = []
    index = 0
    while index < len(rows):
        cell = rows[index][0]
        if isinstance(cell, str) and cell.strip().lower().startswith("system"):
            block, index = _parse_system(rows, index)
            block["system"] = cell.strip()
            systems.append(block)
        else:
            index += 1
    return {"systems": systems}


def _depletion_rates(block: dict, ion: str) -> list[dict]:
    """Per-day change between consecutive dated samples, per system.

    Uses every consecutive pair regardless of the Pre/Post label, because the labels are not
    self-consistent. A negative rate is depletion from solution; a positive one is replenishment.
    Both are measured facts about the solution; only the *attribution* to plant uptake would need
    the missing labels.
    """
    values = block["ions"].get(ion) or []
    samples = block["samples"]
    out = []
    for i in range(len(samples) - 1):
        a, b = values[i], values[i + 1]
        if a is None or b is None:
            continue
        days = (dt.date.fromisoformat(samples[i + 1]["date"])
                - dt.date.fromisoformat(samples[i]["date"])).days
        if days <= 0:
            continue
        out.append({
            "fromDate": samples[i]["date"],
            "toDate": samples[i + 1]["date"],
            "days": days,
            "fromMgPerL": a,
            "toMgPerL": b,
            "changeMgPerL": round(b - a, 4),
            "changeMgPerLPerDay": round((b - a) / days, 5),
            "massInSolutionFromMg": round(a * SOLUTION_VOLUME_L, 2),
            "massInSolutionToMg": round(b * SOLUTION_VOLUME_L, 2),
        })
    return out


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not WORKBOOK.is_file():
        raise SystemExit(f"missing {WORKBOOK}; run ml/research/acquire_spectrum_light.py")
    book = openpyxl.load_workbook(WORKBOOK, data_only=True)

    parsed = {key: _parse_sheet(book[sheet]) for sheet, key in SHEETS.items()}

    tidy = []
    for regime, payload in parsed.items():
        for block in payload["systems"]:
            for i, sample in enumerate(block["samples"]):
                for ion, values in block["ions"].items():
                    if i < len(values) and values[i] is not None:
                        tidy.append({"regime": regime, "system": block["system"], "ion": ion,
                                     "date": sample["date"], "label": sample["label"],
                                     "mgPerL": values[i]})
                if i < len(block["ec"]) and block["ec"][i] is not None:
                    tidy.append({"regime": regime, "system": block["system"], "ion": "EC",
                                 "date": sample["date"], "label": sample["label"],
                                 "mgPerL": block["ec"][i]})
    _write_csv(PROCESSED / "solution_chemistry_long.csv", tidy,
               ["regime", "system", "ion", "date", "label", "mgPerL"])

    # ---------------------------------------------------------------- dose-level harvest
    # The harvest sheet stacks three systems side by side inside each treatment block, nine
    # columns per system, with the treatment name on the row above the block. Reading it as a
    # single six-column table loses two thirds of the plants, so each block is walked explicitly.
    harvest = {}
    sheet = book["Destructive harvest"]
    rows = list(sheet.iter_rows(values_only=True))
    system_columns = [0, 9, 18]
    current = None
    buckets: dict[str, list[tuple[float, float | None]]] = {}
    for index, row in enumerate(rows):
        first = row[0]
        if isinstance(first, str) and first.strip().startswith("Treatment"):
            current = first.strip()
            buckets.setdefault(current, [])
            continue
        if not (isinstance(first, str) and first.strip().startswith("System")):
            continue
        header = rows[index]
        for offset in system_columns:
            if offset >= len(header) or not isinstance(header[offset], str):
                continue
            # "Yield component" is the endpoint the deposit's own economic analysis reports,
            # so it is the one used here; reading "Overall fw" instead would make these numbers
            # incomparable with the paper they accompany.
            fw_col = next((offset + k for k in range(1, 9)
                           if isinstance(header[offset + k], str)
                           and "Yield component fw" in header[offset + k]), None)
            dw_col = next((offset + k for k in range(1, 9)
                           if isinstance(header[offset + k], str)
                           and "Yield component dw" in header[offset + k]), None)
            if fw_col is None:
                continue
            for data_row in rows[index + 1:]:
                if isinstance(data_row[0], str) and (data_row[0].strip().startswith("Treatment")
                                                     or data_row[0].strip().startswith("System")):
                    break
                if len(data_row) <= fw_col or not isinstance(data_row[fw_col], (int, float)):
                    continue
                if not isinstance(data_row[offset], str):
                    continue
                dry = data_row[dw_col] if dw_col is not None and len(data_row) > dw_col else None
                buckets[current].append((float(data_row[fw_col]),
                                         float(dry) if isinstance(dry, (int, float)) else None))
    for name, values in buckets.items():
        if not values:
            continue
        fw = [v[0] for v in values]
        dw = [v[1] for v in values if v[1] is not None]
        harvest[name] = {
            "label": "measured",
            "n": len(fw),
            "freshWeightG": {"mean": round(statistics.fmean(fw), 3),
                             "sd": round(statistics.stdev(fw), 3) if len(fw) > 1 else None},
            "dryWeightG": ({"mean": round(statistics.fmean(dw), 3),
                            "sd": round(statistics.stdev(dw), 3) if len(dw) > 1 else None}
                           if dw else None),
            "dryMatterFraction": (round(statistics.fmean(dw) / statistics.fmean(fw), 4)
                                  if dw and statistics.fmean(fw) else None),
        }

    # ---------------------------------------------------------------- trajectory summary
    trajectory = {}
    for ion in IONS + ("EC",):
        per_regime = {}
        for regime, payload in parsed.items():
            rates = []
            for block in payload["systems"]:
                if ion == "EC":
                    values = block["ec"]
                else:
                    values = block["ions"].get(ion) or []
                proxy = {"ions": {ion: values}, "samples": block["samples"]}
                rates.extend(_depletion_rates(proxy, ion))
            if not rates:
                continue
            daily = [r["changeMgPerLPerDay"] for r in rates]
            per_regime[regime] = {
                "intervalCount": len(rates),
                "medianChangeMgPerLPerDay": round(statistics.median(daily), 5),
                "totalChangeMgPerLAcrossCycle": round(sum(r["changeMgPerL"] for r in rates), 4),
                "depletingIntervals": sum(1 for r in rates if r["changeMgPerL"] < 0),
                "replenishingIntervals": sum(1 for r in rates if r["changeMgPerL"] > 0),
            }
            if ion == "Nitrate":
                per_regime[regime]["intervals"] = rates
        if per_regime:
            trajectory[ion] = per_regime

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/analyze_nutrient_balance.py",
        "source": {
            "doi": "10.5281/zenodo.17794636",
            "title": "Temporal variation of nutrient ratios within hydroponic nutrient solutions",
            "licence": "CC-BY-4.0",
            "workbook": str(WORKBOOK.relative_to(ROOT)),
            "duplicateDeposit": {
                "doi": "10.5281/zenodo.18804397",
                "status": "same study, not a second campaign",
                "evidence": "data/metadata/phase37_acquisition_manifest.json#duplicateCheck",
            },
        },
        "design": {
            "crop": "Red Batavia lettuce",
            "cycleDays": 28,
            "regimes": list(SHEETS.values()),
            "systemsPerRegime": {k: len(v["systems"]) for k, v in parsed.items()},
            "ionsMeasured": list(IONS),
            "ecMeasured": True,
            "phMeasured": False,
            "solutionVolumeL": SOLUTION_VOLUME_L,
            "solutionVolumeSource": "economic analysis sheet, 70 L per solution change",
        },
        "measuredConcentrations": {
            "label": "measured",
            "what": ("Eight ions in mg/L plus electrical conductivity, sampled repeatedly from each "
                     "of three independent nutrient systems under three management regimes."),
            "trajectory": trajectory,
            "tidyTable": str((PROCESSED / "solution_chemistry_long.csv").relative_to(ROOT)),
        },
        "harvest": {
            "label": "measured",
            "endpoint": "Yield component fw (g)",
            "endpointNote": (
                "The workbook carries both 'Overall fw' and 'Yield component fw' and they differ by "
                "roughly a quarter. The deposit's own economic analysis reports the yield "
                "component, so that is the column used here; quoting one while comparing against "
                "the other would manufacture a yield change the study does not report."),
            "byTreatment": harvest,
        },
        "whatIsNotDerivable": {
            "label": "unavailable",
            "uptakeRateMgPerPlantPerDay": None,
            "reason": (
                "An uptake rate needs a sample taken immediately before dosing and one immediately "
                "after, paired to a known volume. The deposit's Pre/Post labels are not "
                "self-consistent - the Treatment 1 sheet labels two samples on 3 March both "
                "'Pre dose', and places a 'Post dose' on a 10 March column followed by another "
                "'Pre dose' - so any pairing is an assumption this script declines to make. The "
                "volume and the concentrations are both present; the pairing is not."),
            "whatWouldCloseIt": (
                "The dosing log or the raw sample register that states which measurement preceded "
                "and which followed each nutrient addition."),
        },
        "plantCountDiscrepancy": {
            "plantsInWorkbook": {name: h["n"] for name, h in harvest.items()},
            "plantsInDepositEconomicAnalysis": 64,
            "note": ("The deposit's economic sheet reports totals and means that divide to 64 plants "
                     "per treatment (2996.37/46.82 and 3679.02/57.49), while the harvest sheet holds "
                     "191 and 194 plants across its three system blocks. The subset the published "
                     "analysis used is not identified in the deposit, so this report describes every "
                     "plant in the sheet and does not claim to reproduce the published means."),
        },
        "whatThisDoesNotShow": [
            "No pH measurement is present, so the pH half of the EC/pH requirement is unmet.",
            "No per-plant ion analysis, so uptake cannot be attributed to a specific tissue sink.",
            "One cultivar and one season: Red Batavia in a single facility.",
            "The three regimes are management strategies, not replicates of a single treatment, so "
            "differences between them include any system-level difference.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nutrient_solution.json").write_text(json.dumps(report, indent=2) + "\n",
                                                encoding="utf-8")

    print(f"regimes parsed: {list(parsed)}")
    for name, h in harvest.items():
        print(f"  harvest {name:14} n={h['n']:3} FW={h['freshWeightG']['mean']:6.2f} g  "
              f"DM={h['dryMatterFraction']}")
    nitrate = trajectory.get("Nitrate", {})
    for regime, block in nitrate.items():
        print(f"  NO3-N {regime:11} median {block['medianChangeMgPerLPerDay']:+.4f} mg/L/day over "
              f"{block['intervalCount']} intervals")
    print(f"\nreport -> {OUT / 'nutrient_solution.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
