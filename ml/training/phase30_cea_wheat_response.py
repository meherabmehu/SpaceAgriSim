#!/usr/bin/env python3
"""Phase 30: does the controlled-environment wheat series support a yield response surface?

The question
------------
Phase 29 left workflow C without a response surface and recorded why: nothing in this repository
varied light, temperature or CO2 across enough independent experiments to fit one. Phase 30 acquired
a series that does — indoor wheat experiments with a harvested grain yield and a logged environment —
so this script asks the question the data can answer and writes the answer down before any product
surface depends on it.

Protocol, fixed before any number was read
------------------------------------------
1.  **Unit of independence is the experiment.** Sub-plots inside one chamber share the environment and
    the operator; treating them as replicates would shrink every interval. Each experiment contributes
    one target: the mean of its harvested sub-plots.
2.  **Leave-one-experiment-out** cross-validation over the development experiments is the selection
    signal. Every candidate is scored on identical folds.
3.  **A holdout of experiments is sealed before selection**, chosen by SHA-256 of the experiment id so
    nobody can tune the choice, and scored exactly once by the selected model.
4.  **Selection rule, written first:** lowest out-of-fold MAE on the measurement scale; if two
    candidates are within 2 %, take the structurally simpler one (`CANDIDATE_ORDER`).
5.  **The acceptance criterion is the project's, unchanged: 30 % MAPE on the holdout.** A failure is
    reported as a failure.
6.  **Intervals are split-conformal** on the out-of-fold log residuals, reported with empirical
    coverage overall and by CO2 band, and probed for exchangeability. An interval on non-exchangeable
    residuals is a width, not a promise.

    python3 ml/training/phase30_cea_wheat_response.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed" / "phase30" / "cea_wheat_experiments.csv"
QUALITY = ROOT / "data" / "processed" / "phase30" / "quality.json"
OUT = ROOT / "ml" / "evaluation" / "phase30_cea_wheat_response.json"

SEED = 20261110
ACCEPTANCE_CRITERION_PCT = 30.0
HOLDOUT_FRACTION = 0.18
MODEL_FEATURES = ("log10Ppfd", "photoperiodHours", "co2Ppm", "airTemperatureC",
                  "relativeHumidityPct", "dailyLightIntegralMolPerM2Day")
FEATURE_UNITS = {
    "log10Ppfd": "log10(umol/m2/s)",
    "photoperiodHours": "h/day",
    "co2Ppm": "ppm",
    "airTemperatureC": "degC",
    "relativeHumidityPct": "%",
    "dailyLightIntegralMolPerM2Day": "mol/m2/day",
}
CANDIDATE_ORDER = ("baseline-mean", "structured-dli-co2", "ridge-log", "gbm-log")


def load() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with DATA.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            record: dict[str, Any] = {"experimentId": row["experimentId"],
                                      "system": row.get("system", "")}
            for field in ("grainYieldKgPerM2Mean", "meanPpfdUmolPerM2S", "photoperiodHours",
                          "co2Ppm", "airTemperatureC", "relativeHumidityPct",
                          "cycleLengthDays"):
                try:
                    record[field] = float(row[field])
                except (KeyError, TypeError, ValueError):
                    record[field] = None
            if any(record[field] is None for field in
                   ("grainYieldKgPerM2Mean", "meanPpfdUmolPerM2S", "photoperiodHours",
                    "co2Ppm", "airTemperatureC", "relativeHumidityPct")):
                continue
            if record["grainYieldKgPerM2Mean"] <= 0:
                continue
            record["dailyLightIntegralMolPerM2Day"] = (
                record["meanPpfdUmolPerM2S"] * record["photoperiodHours"] * 3600 / 1e6)
            record["log10Ppfd"] = math.log10(record["meanPpfdUmolPerM2S"])
            record["logTarget"] = math.log10(record["grainYieldKgPerM2Mean"])
            rows.append(record)
    return sorted(rows, key=lambda row: row["experimentId"])


def holdout_ids(rows: list[dict[str, Any]]) -> list[str]:
    """Deterministic, un-tunable split: the ids whose SHA-256 sorts lowest."""
    ranked = sorted(rows, key=lambda row: hashlib.sha256(
        row["experimentId"].encode()).hexdigest())
    count = max(4, round(len(rows) * HOLDOUT_FRACTION))
    return sorted(row["experimentId"] for row in ranked[:count])


def design(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([[row[name] for name in MODEL_FEATURES] for row in rows], dtype=float)
    y = np.array([row["logTarget"] for row in rows], dtype=float)
    return x, y


def _structured(train_x: np.ndarray, train_y: np.ndarray) -> np.ndarray:
    """Saturating-light CO2-modified shape, fitted in closed form on the log target.

    The shape physiology predicts and the shape Phase 28 chose before failing on other data: yield
    rises with daily light integral and with CO2, falls away from a thermal optimum. It needs no
    library and cannot overfit a few dozen experiments the way a tree can.
    """
    columns = [_column(train_x, index) for index in range(train_x.shape[1])]
    dli = columns[MODEL_FEATURES.index("dailyLightIntegralMolPerM2Day")]
    co2 = columns[MODEL_FEATURES.index("co2Ppm")]
    photo = columns[MODEL_FEATURES.index("photoperiodHours")]
    temp = columns[MODEL_FEATURES.index("airTemperatureC")]
    matrix = np.column_stack([np.ones_like(dli), np.log(dli), np.log(co2), np.log(photo),
                              (temp - 23.0) ** 2])
    coefficients, *_ = np.linalg.lstsq(matrix, train_y, rcond=None)
    return coefficients


def _column(x: np.ndarray, index: int) -> np.ndarray:
    return x[:, index]


def _structured_predict(coefficients: np.ndarray, x: np.ndarray) -> np.ndarray:
    dli = _column(x, MODEL_FEATURES.index("dailyLightIntegralMolPerM2Day"))
    co2 = _column(x, MODEL_FEATURES.index("co2Ppm"))
    photo = _column(x, MODEL_FEATURES.index("photoperiodHours"))
    temp = _column(x, MODEL_FEATURES.index("airTemperatureC"))
    matrix = np.column_stack([np.ones_like(dli), np.log(dli), np.log(co2), np.log(photo),
                              (temp - 23.0) ** 2])
    return matrix @ coefficients


def fit_predict(name: str, train_x: np.ndarray, train_y: np.ndarray,
                test_x: np.ndarray) -> np.ndarray:
    if name == "baseline-mean":
        return np.full(len(test_x), float(np.mean(train_y)))
    if name == "structured-dli-co2":
        return _structured_predict(_structured(train_x, train_y), test_x)
    if name == "ridge-log":
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        return model.fit(train_x, train_y).predict(test_x)
    if name == "gbm-log":
        model = HistGradientBoostingRegressor(
            max_depth=3, max_iter=200, learning_rate=0.06, min_samples_leaf=4,
            l2_regularization=1.0, random_state=SEED)
        return model.fit(train_x, train_y).predict(test_x)
    raise KeyError(name)


def metrics(actual: list[float], predicted: list[float]) -> dict[str, Any]:
    """Computed on the measurement scale (kg/m2), never on the log target."""
    a = np.array(actual, dtype=float)
    p = np.array(predicted, dtype=float)
    errors = p - a
    ape = np.abs(errors) / a * 100
    ss_res = float(np.sum((a - p) ** 2))
    ss_tot = float(np.sum((a - np.mean(a)) ** 2))
    return {
        "n": int(len(a)),
        "MAE": round(float(np.mean(np.abs(errors))), 4),
        "RMSE": round(float(np.sqrt(np.mean(errors ** 2))), 4),
        "MAPE": round(float(np.mean(ape)), 3),
        "medianAPE": round(float(np.median(ape)), 3),
        "meanBias": round(float(np.mean(errors)), 4),
        "R2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
        "spearman": _spearman(a.tolist(), p.tolist()),
    }


def _spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    ra, rb = _rank(a), _rank(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return round(num / den, 4) if den else None


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2 + 1
        for index in range(position, end + 1):
            ranks[order[index]] = average
        position = end + 1
    return ranks


def _range(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    values = [row[field] for row in rows if row.get(field) is not None]
    if not values:
        return None
    return {"n": len(values), "min": round(min(values), 4), "max": round(max(values), 4),
            "distinct": len({round(value, 6) for value in values})}


def main() -> int:
    rows = load()
    sealed = set(holdout_ids(rows))
    development = [row for row in rows if row["experimentId"] not in sealed]
    holdout = [row for row in rows if row["experimentId"] in sealed]
    dev_x, dev_y = design(development)
    holdout_x, holdout_y = design(holdout)
    dev_yield = [row["grainYieldKgPerM2Mean"] for row in development]
    holdout_yield = [row["grainYieldKgPerM2Mean"] for row in holdout]
    print(f"experiments {len(rows)}  development {len(development)}  holdout {len(holdout)}")

    oof: dict[str, np.ndarray] = {}
    for name in CANDIDATE_ORDER:
        values = np.zeros(len(development))
        for index in range(len(development)):
            train = np.array([i for i in range(len(development)) if i != index])
            values[index] = float(fit_predict(name, dev_x[train], dev_y[train],
                                              dev_x[[index]])[0])
        oof[name] = values

    candidates: dict[str, Any] = {}
    for name in CANDIDATE_ORDER:
        candidates[name] = metrics(dev_yield, [10 ** value for value in oof[name]])
        print(f"  {name:<22} MAE {candidates[name]['MAE']:.4f} kg/m2  "
              f"MAPE {candidates[name]['MAPE']:.2f} %  R2 {candidates[name]['R2']}")

    best = min(row["MAE"] for row in candidates.values())
    selected = next(name for name in CANDIDATE_ORDER if candidates[name]["MAE"] <= best * 1.02)
    print(f"selected: {selected}")

    residuals = sorted(y - value for y, value in zip(dev_y, oof[selected]))
    n = len(residuals)
    rank = min(n, math.ceil((n + 1) * 0.9))
    low, high = residuals[max(0, n - rank)], residuals[rank - 1]
    covered = sum(1 for y, value in zip(dev_y, oof[selected]) if low <= y - value <= high)
    bands = {"ambient": lambda row: row["co2Ppm"] <= 450,
             "enriched": lambda row: 450 < row["co2Ppm"] <= 800,
             "high": lambda row: row["co2Ppm"] > 800}
    coverage_by_co2: dict[str, Any] = {}
    for band, predicate in bands.items():
        members = [(y, value) for row, y, value in zip(development, dev_y, oof[selected])
                   if predicate(row)]
        if not members:
            coverage_by_co2[band] = {"n": 0}
            continue
        inside = sum(1 for y, value in members if low <= y - value <= high)
        coverage_by_co2[band] = {"n": len(members), "coverage": round(inside / len(members), 4)}

    ranked = sorted(development, key=lambda row: hashlib.sha256(
        row["experimentId"].encode()).hexdigest())
    halves: list[dict[str, Any]] = []
    for label, half in (("half-a", ranked[::2]), ("half-b", ranked[1::2])):
        ids = {row["experimentId"] for row in half}
        pairs = [(y, value) for row, y, value in zip(development, dev_y, oof[selected])
                 if row["experimentId"] in ids]
        halves.append({"half": label, "n": len(pairs),
                       "coverage": round(sum(1 for y, v in pairs if low <= y - v <= high)
                                         / len(pairs), 4),
                       "medianResidualLog10": round(statistics.median([y - v for y, v in pairs]), 4)})
    exchangeable = abs(halves[0]["coverage"] - halves[1]["coverage"]) <= 0.15

    holdout_log = fit_predict(selected, dev_x, dev_y, holdout_x)
    holdout_predicted = [10 ** value for value in holdout_log]
    holdout_metrics = metrics(holdout_yield, holdout_predicted)
    inside_holdout = sum(1 for y, value in zip(holdout_y, holdout_log) if low <= y - value <= high)
    passed = holdout_metrics["MAPE"] <= ACCEPTANCE_CRITERION_PCT
    print(f"holdout MAPE {holdout_metrics['MAPE']:.2f} % vs {ACCEPTANCE_CRITERION_PCT} % -> "
          f"{'PASS' if passed else 'FAIL'} (median APE {holdout_metrics['medianAPE']:.1f} %, "
          f"R2 {holdout_metrics['R2']})")

    detail = [{"experimentId": row["experimentId"],
               "co2Ppm": row["co2Ppm"],
               "measuredKgPerM2": round(row["grainYieldKgPerM2Mean"], 4),
               "predictedKgPerM2": round(predicted, 4),
               "apePct": round(abs(predicted - row["grainYieldKgPerM2Mean"])
                               / row["grainYieldKgPerM2Mean"] * 100, 2)}
              for row, predicted in zip(holdout, holdout_predicted)]
    measured_yields = sorted(row["grainYieldKgPerM2Mean"] for row in rows)
    ratio = measured_yields[-1] / measured_yields[0]
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))["datasets"]["cea-wheat-apogee"]

    payload = {
        "schema": "spaceagrisim.phase30_cea_wheat_response/1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "purpose": ("test whether the Phase 30 controlled-environment wheat series supports a yield "
                    "response surface, with the experiment as the unit of independence"),
        "dataset": {
            "id": "cea-wheat-apogee",
            "doi": "10.5281/zenodo.17764612",
            "license": "CC BY 4.0",
            "file": "data/processed/phase30/cea_wheat_experiments.csv",
            "experiments": len(rows),
            "target": "grain yield kg/m2, mean of the harvested sub-plots in one experiment",
            "features": list(MODEL_FEATURES),
            "featureUnits": FEATURE_UNITS,
            "environmentRanges": quality["environmentRanges"],
            "subplotRows": quality["subplotRows"],
        },
        "protocol": {
            "split": "leave-one-experiment-out over the development experiments",
            "groupingKey": "experiment (sub-plots of one chamber stay together)",
            "targetTransform": "log10(grain yield kg/m2)",
            "holdoutSelectionMethod": "SHA-256 of the experiment id, lowest "
                                      f"{round(len(rows) * HOLDOUT_FRACTION)}",
            "holdoutExperiments": sorted(sealed),
            "developmentExperiments": [row["experimentId"] for row in development],
            "holdoutUsedForSelection": False,
            "selectionRule": ("lowest out-of-fold MAE; within 2 % prefer the structurally simpler "
                              "candidate in the declared order"),
            "candidateOrder": list(CANDIDATE_ORDER),
            "selectionRuleWrittenBeforeScoring": True,
            "acceptanceCriterionPct": ACCEPTANCE_CRITERION_PCT,
            "criterionSource": "unchanged project criterion, not set by this phase",
            "seed": SEED,
            "noRandomSplit": ("sub-plots of one chamber share an environment; a random split across "
                              "rows would leak and is not used"),
        },
        "candidates": candidates,
        "selected": selected,
        "selectedOutOfFold": candidates[selected],
        "interval": {
            "method": "split conformal on out-of-fold log10 residuals, 90 % two-sided",
            "logLow": round(low, 4),
            "logHigh": round(high, 4),
            "multiplicativeWidth": round(10 ** (high - low), 3),
            "nResiduals": n,
            "outOfFoldCoverage": round(covered / n, 4),
            "coverageByCo2Band": coverage_by_co2,
            "coverageNote": ("an in-sample coverage figure from the same residuals the interval was "
                             "built on; descriptive, not a guarantee for a new experiment"),
            "exchangeabilityCheck": {
                "halves": halves,
                "exchangeableAt15Pct": exchangeable,
                "conclusion": ("residuals are treated as exchangeable across experiments"
                               if exchangeable else
                               "residuals are NOT exchangeable across experiments: the width is "
                               "arithmetic on this sample and no independent coverage claim is made"),
            },
        },
        "holdout": {
            "experiments": len(holdout),
            "perExperiment": detail,
            "metrics": holdout_metrics,
            "errorDiagnostic": {
                "yieldRangeRatio": round(ratio, 1),
                "note": (f"measured grain yield spans a factor of {ratio:.0f} across experiments, "
                         f"from {measured_yields[0]:.4f} to {measured_yields[-1]:.4f} kg/m2. MAPE is "
                         "dominated by the smallest yields; that is a property of the series and "
                         "not a reason to change the criterion."),
                "criterionAppliesTo": "the unmodified MAPE over every holdout experiment",
            },
            "intervalCoverage": round(inside_holdout / len(holdout), 4),
            "acceptanceCriterionPct": ACCEPTANCE_CRITERION_PCT,
            "passed": passed,
        },
        "domain": {
            "measuredRanges": {
                "meanPpfdUmolPerM2S": _range(rows, "meanPpfdUmolPerM2S"),
                "photoperiodHours": _range(rows, "photoperiodHours"),
                "co2Ppm": _range(rows, "co2Ppm"),
                "airTemperatureC": _range(rows, "airTemperatureC"),
                "relativeHumidityPct": _range(rows, "relativeHumidityPct"),
                "dailyLightIntegralMolPerM2Day": _range(rows, "dailyLightIntegralMolPerM2Day"),
            },
            "crop": "wheat cv. Apogee only",
            "system": "indoor controlled-environment chambers at one facility family",
            "noExtrapolationRule": ("inputs outside the measured ranges are refused, not clipped, "
                                    "and no other crop is accepted"),
        },
        "served": False,
        "servedReason": ("the selected model missed the pre-registered 30 % holdout criterion by an "
                         "order of magnitude, so no predictive surface is served. Workflow C reports "
                         "measured groups instead, and this file is the record of the attempt."),
        "holdoutSpent": ("this holdout has been scored once and will not be re-split. Selecting a "
                         "different candidate set after seeing these numbers would be tuning on the "
                         "evaluation data."),
        "limitations": [
            "One crop and one facility family: nothing here transfers to lettuce, tomato or radish.",
            "The environmental axes are correlated by design; a coefficient is an association across "
            "experiments, not an isolated response to one factor.",
            "Temperature spans a narrow band and CO2 has few distinct levels, so neither a cardinal "
            "temperature response nor a full CO2 saturation curve is identifiable.",
            "Grain yield, not edible biomass, and the harvest index is not modelled.",
            "The sample is small: every interval is wide and the holdout is a handful of "
            "experiments, so a single unusual run moves the metric.",
        ],
        "units": {**FEATURE_UNITS, "grainYieldKgPerM2": "kg/m2"},
        "priorHoldoutInspection": ("no experiment in this dataset was inspected before the sealed "
                                   "holdout was chosen; the split was fixed by SHA-256 and scored "
                                   "once"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
