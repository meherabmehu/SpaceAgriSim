#!/usr/bin/env python3
"""What the green-light trial measures, and what it does not.

The gap this is for
-------------------
``led-spectrum-response`` needed a trial that changes the *spectrum* while holding light quantity
fixed. Most LED trials vary both, and then the biomass difference cannot be attributed to colour:
more photons is a different explanation that fits the same data.

Zenodo 10.5281/zenodo.20394352 does hold it fixed. Four spectra at 200 umol m-2 s-1 and 16/8
photoperiod: a red-blue control (5.08 % green), a fixed 24 % green treatment, an incremental
16 -> 24 -> 32 % treatment, and the incremental regime again at 1.25x planting density.

The trap this script refuses to walk into
------------------------------------------
The fourth treatment changes density as well as spectrum. Its biomass cannot be used to say
anything about colour, because a 25 % denser planting changes light interception per plant and
competition for space at the same time. It is reported below for completeness and marked
`confoundedWithDensity: true`, and every spectrum conclusion is drawn from the three arms that
differ in spectrum only.

What is measured and what is derived
------------------------------------
Every harvest number is `measured` - a plant was cut and weighed. The treatment means, the
differences of means and the permutation p-values are `derived`, because they are arithmetic this
script performs. Nothing here is `predicted`.

    python3 ml/research/analyze_led_spectrum.py
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "zenodo_20394352"
OUT = ROOT / "data" / "research" / "phase37"
PROCESSED = ROOT / "data" / "processed" / "led_spectrum"

WORKBOOK = RAW / "green_light_lettuce_open_data_1_.xlsx"
TREATMENTS = ("Control", "T1", "T2", "T3")
# The three arms that differ only in spectrum. T3 also changes planting density.
SPECTRUM_ONLY = ("Control", "T1", "T2")
SEED = 20261112
PERMUTATIONS = 20000


def _load() -> openpyxl.Workbook:
    if not WORKBOOK.is_file():
        raise SystemExit(f"missing {WORKBOOK}; run ml/research/acquire_spectrum_light.py")
    return openpyxl.load_workbook(WORKBOOK, data_only=True)


def _metadata(book: openpyxl.Workbook) -> list[dict]:
    sheet = book["Treatment_metadata"]
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    out = []
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        record = dict(zip(header, row))
        out.append({k: (v.strip() if isinstance(v, str) else v) for k, v in record.items()})
    return out


def _harvest(book: openpyxl.Workbook) -> dict:
    """Per-treatment samples for each destructively measured variable."""
    sheet = book["Destructive_harvest"]
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    data: dict[str, dict[str, list[float]]] = {}
    units: dict[str, str] = {}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        variable, treatment, _index, value, unit = row[:5]
        if value is None or treatment not in TREATMENTS:
            continue
        data.setdefault(variable.strip(), {}).setdefault(treatment, []).append(float(value))
        units[variable.strip()] = unit
    return {"data": data, "units": units}


def _multispeq(book: openpyxl.Workbook) -> dict:
    """Chlorophyll-fluorescence variables by day after sowing and treatment."""
    sheet = book["MultispeQ"]
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(c).strip() if c else "" for c in rows[0]]
    wanted = ("Phi2", "NPQt", "LEF", "SPAD", "FvP_over_FmP", "qL")
    out: dict[str, dict[str, dict[str, list[float]]]] = {w: {} for w in wanted}
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        record = dict(zip(header, row))
        day = record.get("DAS")
        treatment = record.get("Treatment")
        if day is None or treatment not in TREATMENTS:
            continue
        for key in wanted:
            value = record.get(key)
            if isinstance(value, (int, float)):
                out[key].setdefault(str(int(day)), {}).setdefault(treatment, []).append(float(value))
    return out


def _assays(book: openpyxl.Workbook) -> dict:
    sheet = book["Postharvest_assays"]
    rows = list(sheet.iter_rows(values_only=True))
    out: dict[str, dict[str, list[float]]] = {}
    units: dict[str, str] = {}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        variable, treatment, _position, value, unit = row[:5]
        if value is None or treatment not in TREATMENTS:
            continue
        out.setdefault(str(variable).strip(), {}).setdefault(treatment, []).append(float(value))
        units[str(variable).strip()] = unit
    return {"data": out, "units": units}


def _summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "sd": None, "median": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "sd": round(statistics.stdev(values), 4) if len(values) > 1 else None,
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _difference(a: list[float], b: list[float]) -> dict:
    """Permutation test and bootstrap interval for mean(b) - mean(a).

    A permutation test is used rather than a t-test because it assumes nothing about the
    distribution of plant mass, which in a harvest is skewed by a few large individuals.
    """
    if not a or not b:
        return {"available": False}
    observed = statistics.fmean(b) - statistics.fmean(a)
    pool = list(a) + list(b)
    n_a = len(a)
    rng = random.Random(SEED)
    hits = 0
    for _ in range(PERMUTATIONS):
        rng.shuffle(pool)
        if abs(statistics.fmean(pool[n_a:]) - statistics.fmean(pool[:n_a])) >= abs(observed):
            hits += 1
    boot_rng = random.Random(SEED + 1)
    spread = []
    for _ in range(4000):
        sample_a = [a[boot_rng.randrange(n_a)] for _ in range(n_a)]
        sample_b = [b[boot_rng.randrange(len(b))] for _ in range(len(b))]
        spread.append(statistics.fmean(sample_b) - statistics.fmean(sample_a))
    spread.sort()
    return {
        "available": True,
        "differenceOfMeans": round(observed, 4),
        "permutationP": round(hits / PERMUTATIONS, 6),
        "permutationPFloor": round(1.0 / (PERMUTATIONS + 1), 8),
        "permutations": PERMUTATIONS,
        "bootstrap95": [round(spread[int(0.025 * len(spread))], 4),
                        round(spread[int(0.975 * len(spread))], 4)],
        "relativeChange": (round(observed / statistics.fmean(a), 4)
                           if statistics.fmean(a) else None),
    }


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    book = _load()
    metadata = _metadata(book)
    harvest = _harvest(book)
    fluorescence = _multispeq(book)
    assays = _assays(book)

    # ---------------------------------------------------------------- tidy extract
    rows = []
    for variable, per_treatment in harvest["data"].items():
        for treatment, values in per_treatment.items():
            for index, value in enumerate(values, 1):
                rows.append({"variable": variable, "treatment": treatment,
                             "observation": index, "value": value,
                             "unit": harvest["units"][variable]})
    _write_csv(PROCESSED / "harvest_long.csv", rows,
               ["variable", "treatment", "observation", "value", "unit"])

    # ---------------------------------------------------------------- primary contrast
    # Fresh weight is the decision-relevant endpoint: it is what a grower harvests.
    fresh = harvest["data"]["Fresh weight"]
    dry = harvest["data"]["Dry weight"]
    leaf_area = harvest["data"].get("Leaf area", {})

    contrast = {
        "controlVsFixed24PercentGreen": _difference(fresh["Control"], fresh["T1"]),
        "controlVsIncrementalGreen": _difference(fresh["Control"], fresh["T2"]),
        "fixedVsIncremental": _difference(fresh["T1"], fresh["T2"]),
    }
    dry_contrast = {
        "controlVsFixed24PercentGreen": _difference(dry["Control"], dry["T1"]),
        "controlVsIncrementalGreen": _difference(dry["Control"], dry["T2"]),
    }

    harvest_summary = {variable: {treatment: _summary(harvest["data"][variable].get(treatment, []))
                                  for treatment in TREATMENTS}
                       for variable in harvest["data"]}

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/analyze_led_spectrum.py",
        "source": {
            "doi": "10.5281/zenodo.20394352",
            "title": "Optimising Spectral Composition in Hydroponic Lettuce Cultivation",
            "licence": "CC-BY-4.0",
            "workbook": str(WORKBOOK.relative_to(ROOT)),
        },
        "design": {
            "crop": "Red Batavia lettuce",
            "ppfdTargetUmolPerM2PerS": 200,
            "photoperiod": "16 h light / 8 h dark",
            "harvestDayAfterSowing": 35,
            "treatments": metadata,
            "lightQuantityHeldConstant": True,
            "whyThatMatters": (
                "Every arm targets the same PPFD and the same photoperiod, so a biomass difference "
                "cannot be explained by more photons. That is the property the gap asked for."),
        },
        "harvest": {"label": "measured", "summary": harvest_summary, "units": harvest["units"]},
        "freshWeightContrasts": {"label": "derived", "contrasts": contrast},
        "dryWeightContrasts": {"label": "derived", "contrasts": dry_contrast},
        "densityConfound": {
            "confoundedWithDensity": True,
            "treatment": "T3",
            "relativePlantingDensity": 1.25,
            "whyExcluded": (
                "T3 repeats the incremental spectrum at 25 % greater planting density. Plant mass "
                "per plant then depends on competition for space as well as on colour, so its "
                "difference cannot be attributed to spectrum and no conclusion below uses it."),
            "freshWeight": harvest_summary["Fresh weight"]["T3"],
        },
        "fluorescence": {
            "label": "measured",
            "byDay": {variable: {day: {t: _summary(v) for t, v in per.items()}
                                 for day, per in days.items()}
                      for variable, days in fluorescence.items()},
            "note": ("MultispeQ measurements at 28 and 35 days after sowing. Reported as measured "
                     "distributions; no test is applied because the design does not state whether "
                     "repeated leaves come from the same plant."),
        },
        "postharvest": {"label": "measured", "summary": {
            variable: {t: _summary(v) for t, v in per.items()}
            for variable, per in assays["data"].items()}, "units": assays["units"]},
        "rootZoneWaterContent": "not measured in this trial",
        "limitations": [
            "One cultivar, one facility, one season. A single trial cannot separate a spectral "
            "effect from a facility or batch effect.",
            "Green fraction is reported by the authors as a percentage of the spectrum; the "
            "underlying spectral power distributions are not deposited, so the effect cannot be "
            "resolved by wavelength band.",
            "Harvest is destructive at a single time point (35 days after sowing), so no growth "
            "trajectory and no light-use efficiency over time can be derived.",
            "T3 is confounded with planting density and is excluded from every spectrum claim.",
            "The trial ran on Earth in a controlled environment. Nothing here is a spaceflight "
            "observation and no fractional-gravity inference is drawn from it.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "led_spectrum_response.json").write_text(json.dumps(report, indent=2) + "\n",
                                                   encoding="utf-8")

    wp = report["freshWeightContrasts"]["contrasts"]
    print(f"harvest plants: {sum(v['n'] for v in harvest_summary['Fresh weight'].values())}")
    for t in TREATMENTS:
        s = harvest_summary["Fresh weight"][t]
        print(f"  FW {t:8} n={s['n']:3} mean={s['mean']:7.2f} g  sd={s['sd']}")
    for name, c in wp.items():
        print(f"  {name:34} diff={c['differenceOfMeans']:7.3f} g  "
              f"p={c['permutationP']:.5f}  CI={c['bootstrap95']}")
    print(f"\nreport -> {OUT / 'led_spectrum_response.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
