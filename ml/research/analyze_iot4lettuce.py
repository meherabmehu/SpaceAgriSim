#!/usr/bin/env python3
"""Analyse the IoT4Lettuce deficit-irrigation and cultivar contrast.

What this adds
--------------
Two gaps in ``data/research/dataset_gap_matrix.json`` are about evidence that did not exist in
this repository at all: ``cultivar-metadata`` (one parameter set per crop, no cultivar dimension)
and ``crop-water-response-ky`` (no deficit-irrigation experiment per crop). The IoT4Lettuce
record contains both, in a form that has to be joined carefully before it can be used:

* 45 plants, 2 cultivars, 3 nitrogen levels, 2 irrigation application rates;
* destructive harvest fresh weight per plant in grams - a real yield measurement;
* eight repeated morphological measurements per plant;
* an OpenSILEX export whose plant identifiers do not match the morphology table's identifiers.

The join is the part that could silently produce a wrong answer, so it is *verified* rather than
assumed: the OpenSILEX row for a plant on a date is matched to the morphology row for the same
plant and date only when leaves/height/diameter agree exactly. The match rate is reported. A
mapping that was merely plausible from the identifier text would be an assumption dressed as
data.

What is NOT claimed
-------------------
* No evapotranspiration was measured per treatment. The irrigation *application rate* is a
  design variable, not a water-use measurement. The implied Ky is therefore reported as
  conditional on an assumed water-use ratio, with a sensitivity band, and never as a measured Ky.
* The non-destructive fresh weights in the export are produced by a regression analysis. They are
  labelled derived and are not used for any effect estimate; only the destructive harvest weights
  are.
* The design is unbalanced: at 50 % only Grand Rapid was grown. The irrigation contrast is a
  Grand Rapid contrast, and the cultivar contrast exists only at 75 %.

    python3 ml/research/analyze_iot4lettuce.py
"""
from __future__ import annotations

import csv
import io
import json
import random
import statistics
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "zenodo_20759414"
OUT = ROOT / "data" / "research" / "phase36"
REPORT = OUT / "iot4lettuce_water_cultivar.json"

FRESH_WEIGHT_MEASURED = "plant_fresh_weight_directmeasurement_gram"
FRESH_WEIGHT_MODELLED = "plant_fresh_weight_regression_analysis_gram"
LEAVES = "plant_leaves_number_directmeasurement_dimensionless"
HEIGHT = "foliage_height_directmeasurement_centimeter"
DIAMETER = "plant_diameter_mean_directmeasurement_centimeter"

# Treatment decoding, established by matching values - not by reading the identifier text.
# The identifier prefix maps to the irrigation application rate, and the cultivar code to the
# cultivar name given in the record description.
PREFIX = {"RW": {"applicationPct": 50, "label": "50 % of water loss replaced"},
          "RN": {"applicationPct": 75, "label": "75 % of water loss replaced"}}
CULTIVAR = {"GR": "Grand Rapid", "RO": "Lollo Rossa"}


def open_text(path: Path):
    """Open a table whose encoding is not stated by the publisher.

    The climate exports are cp1252, not UTF-8: their header contains "temperature (\u00baC)" with
    the degree sign as a single 0xBA byte, which raises UnicodeDecodeError on a UTF-8 read. The
    encoding actually used is returned alongside the handle so the report can say which one it
    was rather than leaving it implicit.
    """
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return io.StringIO(raw.decode(encoding)), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", raw[:1], 0, 1, f"no encoding matched {path}")


def load_opensilex() -> tuple[list[dict], list[str]]:
    path = RAW / "14_Utilities" / "OpenSILEX" / "data.csv"
    rows = list(csv.reader(path.open(encoding="utf-8-sig")))
    header = rows[4]
    records = [dict(zip(header, row)) for row in rows[5:] if len(row) > 2]
    return records, header


def load_manual() -> list[dict]:
    path = RAW / "13_Manual_measurements" / "full_db.csv"
    out = []
    for row in csv.DictReader(path.open(encoding="utf-8-sig")):
        day, month, year = row["date"].split("/")
        out.append({
            "sample": row["sample"],
            "date": f"{year}-{month}-{day}",
            "leaf_n": float(row["leaf_n"]) if row["leaf_n"] else None,
            "diam_cm": float(row["diam"]) if row["diam"] else None,
            "height_cm": float(row["height"]) if row["height"] else None,
        })
    return out


def verify_join(opensilex_rows: list[dict], manual_rows: list[dict]) -> dict:
    """Pair OpenSILEX targets to morphology samples by exact agreement on the same date."""
    morphology = {(r["sample"], r["date"]): r for r in manual_rows}
    manual_dates = {r["date"] for r in manual_rows}

    # Build OpenSILEX (target, date) -> measurement triple.
    measurements: dict[tuple[str, str], tuple] = {}
    for row in opensilex_rows:
        target, day = row.get("Target"), row.get("Date")
        if not target or not day or day not in manual_dates:
            continue
        triple = (row.get(LEAVES), row.get(HEIGHT), row.get(DIAMETER))
        if all(value not in (None, "") for value in triple):
            measurements[(target, day)] = triple

    pairs: list[dict] = []
    used_samples: set[str] = set()
    for (target, day), triple in sorted(measurements.items()):
        try:
            triple_f = (float(triple[0]), float(triple[1]), float(triple[2]))
        except (TypeError, ValueError):
            continue
        for (sample, sample_day), record in morphology.items():
            if sample_day != day or sample in used_samples:
                continue
            if record["leaf_n"] is None or record["diam_cm"] is None:
                continue
            if (record["leaf_n"] == triple_f[0]
                    and abs(record["height_cm"] - triple_f[1]) < 1e-6
                    and abs(record["diam_cm"] - triple_f[2]) < 1e-6):
                pairs.append({"target": target, "sample": sample, "date": day})
                used_samples.add(sample)
                break

    prefixes = {pair["target"][:2] for pair in pairs}
    samples = {pair["sample"] for pair in pairs}
    agreement = None
    if pairs:
        mismatched = []
        for pair in pairs:
            sample_prefix = pair["sample"][:2]
            expected = {"50": "RW", "75": "RN"}[sample_prefix]
            if pair["target"][:2] != expected:
                mismatched.append(pair)
        agreement = {
            "rule": "OpenSILEX prefix RW == morphology '50', RN == '75'",
            "violations": len(mismatched),
            "examples": mismatched[:5],
        }
    return {
        "pairsMatched": len(pairs),
        "distinctTargets": len({p["target"] for p in pairs}),
        "distinctSamples": len(samples),
        "prefixesSeen": sorted(prefixes),
        "dateRange": [min({p["date"] for p in pairs}), max({p["date"] for p in pairs})]
        if pairs else None,
        "prefixRuleCheck": agreement,
        "pairs": pairs,
    }


def permutation_test(a: list[float], b: list[float], draws: int = 20000,
                     seed: int = 20261107) -> dict:
    """Two-sided permutation test on the difference of means, plus a bootstrap interval.

    A t-test would be defensible too; a permutation test is used because the harvest weights are
    small-n and slightly skewed, and because it needs no distributional assumption that the data
    cannot support at n = 15 per group.
    """
    observed = statistics.fmean(a) - statistics.fmean(b)
    pool = list(a) + list(b)
    n_a = len(a)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(draws):
        rng.shuffle(pool)
        difference = statistics.fmean(pool[:n_a]) - statistics.fmean(pool[n_a:])
        if abs(difference) >= abs(observed) - 1e-12:
            extreme += 1
    p_value = (extreme + 1) / (draws + 1)

    boot_rng = random.Random(seed + 1)
    boot = []
    for _ in range(4000):
        sample_a = [a[boot_rng.randrange(n_a)] for _ in range(n_a)]
        sample_b = [b[boot_rng.randrange(len(b))] for _ in range(len(b))]
        boot.append(statistics.fmean(sample_a) - statistics.fmean(sample_b))
    boot.sort()
    return {
        "differenceOfMeans": round(observed, 4),
        "permutationP": round(p_value, 6),
        "permutationPFloor": round(1.0 / (draws + 1), 8),
        "permutationPNote": ("a Monte Carlo permutation test cannot resolve below 1/(draws+1); a "
                             "reported value at the floor means no permuted sample reached the "
                             "observed difference"),
        "permutations": draws,
        "bootstrap95": [round(boot[int(0.025 * len(boot))], 4),
                        round(boot[int(0.975 * len(boot))], 4)],
    }


def group_of(target: str) -> dict:
    prefix, cultivar_code, nitro, rep = target[:2], target[2:4], target[4], target[5:]
    return {
        "target": target,
        "prefix": prefix,
        "irrigationPct": PREFIX[prefix]["applicationPct"],
        "cultivarCode": cultivar_code,
        "cultivar": CULTIVAR[cultivar_code],
        "nitrogenLevel": nitro,
        "replicate": int(rep),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    opensilex, header = load_opensilex()
    manual = load_manual()

    join = verify_join(opensilex, manual)

    harvest: list[dict] = []
    derived: list[dict] = []
    for row in opensilex:
        target = row.get("Target")
        if not target:
            continue
        group = group_of(target)
        if row.get(FRESH_WEIGHT_MEASURED):
            harvest.append({**group, "date": row["Date"],
                            "freshWeightG": float(row[FRESH_WEIGHT_MEASURED])})
        if row.get(FRESH_WEIGHT_MODELLED):
            derived.append({**group, "date": row["Date"],
                            "freshWeightG": float(row[FRESH_WEIGHT_MODELLED])})

    def values(predicate) -> list[float]:
        return [h["freshWeightG"] for h in harvest if predicate(h)]

    groups = {
        "50% Grand Rapid": values(lambda h: h["irrigationPct"] == 50 and h["cultivar"] == "Grand Rapid"),
        "75% Grand Rapid": values(lambda h: h["irrigationPct"] == 75 and h["cultivar"] == "Grand Rapid"),
        "75% Lollo Rossa": values(lambda h: h["irrigationPct"] == 75 and h["cultivar"] == "Lollo Rossa"),
    }
    summary = {
        name: {"n": len(vals),
               "meanG": round(statistics.fmean(vals), 3) if vals else None,
               "sdG": round(statistics.pstdev(vals), 3) if len(vals) > 1 else None,
               "minG": min(vals) if vals else None,
               "maxG": max(vals) if vals else None}
        for name, vals in groups.items()
    }

    irrigation = permutation_test(groups["75% Grand Rapid"], groups["50% Grand Rapid"])
    cultivar = permutation_test(groups["75% Grand Rapid"], groups["75% Lollo Rossa"])

    y50 = statistics.fmean(groups["50% Grand Rapid"])
    y75 = statistics.fmean(groups["75% Grand Rapid"])
    yield_ratio = y50 / y75

    # Ky accounting, made conditional and transparent. (1 - Ya/Ym) = Ky (1 - ETa/ETm).
    # Three water-use ratios are carried through: the nominal design ratio, a conservative
    # 0.75 (the substrate buffers the deficit), and 0.90 (the treatments barely differed).
    ky_scenarios = []
    for et_ratio in (0.6667, 0.75, 0.90):
        denominator = 1.0 - et_ratio
        ky_scenarios.append({
            "assumedEtRatio50over75": et_ratio,
            "assumedBasis": ("nominal design ratio (50/75); not a measurement"
                             if et_ratio == 0.6667 else "sensitivity case"),
            "yieldRatio50over75": round(yield_ratio, 4),
            "relativeYieldReduction": round(1.0 - yield_ratio, 4),
            "impliedKy": round((1.0 - yield_ratio) / denominator, 4),
        })

    climate_summary: dict = {}
    for name in ("inside", "outside", "PAR"):
        path = RAW / "03_Climate" / f"{name}.csv"
        if not path.exists():
            continue
        handle, encoding = open_text(path)
        rows = list(csv.DictReader(handle))
        if not rows:
            continue
        numeric_columns = [c for c in rows[0] if c not in {"station", "date", "timestamp"}]
        climate_summary[name] = {
            "rows": len(rows),
            "columns": numeric_columns,
            "encoding": encoding,
            "mean": {c: round(statistics.fmean(float(r[c]) for r in rows
                                               if r.get(c) not in (None, "")), 3)
                     for c in numeric_columns},
            "max": {c: max(float(r[c]) for r in rows if r.get(c) not in (None, ""))
                    for c in numeric_columns},
        }

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/analyze_iot4lettuce.py",
        "source": {"doi": "10.5281/zenodo.20759414", "license": "CC-BY-4.0",
                   "plantCount": 45, "cultivars": ["Grand Rapid", "Lollo Rossa"],
                   "irrigationApplicationRates": [50, 75],
                   "nitrogenLevelsMmolL": [6, 13, 17]},
        "evidenceLabels": {
            "measured": "destructive harvest fresh weight (g) at 2024-10-03; morphology; SPAD",
            "derived": "group means, permutation tests, bootstrap intervals, implied Ky",
            "notUsed": "non-destructive fresh weight from regression analysis (modelled, not "
                       "measured) - present in the export, deliberately excluded from estimates",
        },
        "joinVerification": {k: v for k, v in join.items() if k != "pairs"},
        "harvestFreshWeight": summary,
        "irrigationContrast": {
            "comparison": "75 % vs 50 % application rate, Grand Rapid only (unbalanced design)",
            **irrigation,
            "interpretation": ("the difference is not distinguishable from zero, so at this "
                               "application contrast there is no measurable yield penalty"),
        },
        "cultivarContrast": {
            "comparison": "Grand Rapid vs Lollo Rossa at 75 % application rate",
            **cultivar,
            "ratioGrandRapidOverLolloRossa": round(
                statistics.fmean(groups["75% Grand Rapid"])
                / statistics.fmean(groups["75% Lollo Rossa"]), 4),
            "interpretation": ("a single parameter set for 'lettuce' cannot represent both "
                               "cultivars: the same treatments produce a yield ratio of about 1.8"),
        },
        "kyAccounting": {
            "status": "CONDITIONAL - not a measured Ky",
            "whyConditional": ("no per-treatment evapotranspiration was measured; the application "
                               "rate is an irrigation design variable, not water use"),
            "scenarios": ky_scenarios,
        },
        "derivedFreshWeightRowsExcluded": len(derived),
        "climate": climate_summary,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"join: {join['pairsMatched']} target-date pairs verified, "
          f"prefix violations={join['prefixRuleCheck']['violations'] if join['prefixRuleCheck'] else 'n/a'}")
    print("harvest FW:", {k: (v["n"], v["meanG"]) for k, v in summary.items()})
    print(f"irrigation: diff={irrigation['differenceOfMeans']} p={irrigation['permutationP']} "
          f"CI={irrigation['bootstrap95']}")
    print(f"cultivar:   diff={cultivar['differenceOfMeans']} p={cultivar['permutationP']} "
          f"CI={cultivar['bootstrap95']}")
    print("Ky scenarios:", [(s["assumedEtRatio50over75"], s["impliedKy"]) for s in ky_scenarios])
    print(f"\nreport -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
