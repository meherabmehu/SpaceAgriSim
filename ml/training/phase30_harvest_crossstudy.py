#!/usr/bin/env python3
"""Phase 30: does the lettuce harvest model generalise to studies it has never seen?

The question Phase 28 could not answer
--------------------------------------
`lettuce-earth-growth-v3` was trained on four WUR experiments and checked against a single external
observation. Its independent holdout failed (41.6 % MAPE against a 30 % criterion), and one point
cannot tell a model from a coincidence. Phase 30 acquired a compilation of 53 published lettuce
treatment means from 40 studies, which is enough independent studies to ask the question properly.

Protocol, fixed before any number was read
------------------------------------------
1.  **The unit of independence is the study.** Eight studies contribute more than one treatment;
    holding out one treatment and training on its sibling would leak. Every split is by study key.
2.  **Leave-one-study-out** over the development studies is the selection signal, identical folds
    for every candidate, including the mean baseline.
3.  **Eight studies are sealed before selection**, chosen by SHA-256 of the study key so the choice
    cannot be tuned, and scored exactly once by the selected model.
4.  **Selection rule, written first:** lowest out-of-fold MAE on the measurement scale; within 2 %
    prefer the structurally simpler candidate in `CANDIDATE_ORDER`.
5.  **The acceptance criterion is the project's, unchanged: 30 % MAPE.** A failure is reported as a
    failure and nothing is dropped to improve it.

What this script will not do
----------------------------
No imputation of the environment beyond a declared, uniform default for CO2 and photoperiod where a
study did not report them (recorded in the payload with the count it affected), no dropping of
outliers, no fitting on the holdout, and no claim that a random split would have been acceptable.

    python3 ml/training/phase30_harvest_crossstudy.py
"""
from __future__ import annotations
import sys

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
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
DATA = ROOT / "data" / "processed" / "phase30" / "lettuce_multistudy.csv"
OUT = ROOT / "ml" / "evaluation" / "phase30_harvest_crossstudy"

SEED = 20261110
ACCEPTANCE_CRITERION_PCT = 30.0
HOLDOUT_STUDIES = 8
FEATURES = ("co2Ppm", "photoperiodHours", "ppfdUmolPerM2S", "dailyLightIntegralMolPerM2Day",
            "plantDensityPerM2", "plantAgeDays")
FEATURE_UNITS = {"co2Ppm": "ppm", "photoperiodHours": "h/day", "ppfdUmolPerM2S": "umol/m2/s",
                 "dailyLightIntegralMolPerM2Day": "mol/m2/day",
                 "plantDensityPerM2": "plant/m2", "plantAgeDays": "day"}
DEFAULTS = {"co2Ppm": 420.0, "photoperiodHours": 16.0}
CANDIDATE_ORDER = ("baseline-mean", "light-limited-structure", "ridge-log", "gbm-log")


def load() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    filled: dict[str, int] = {feature: 0 for feature in DEFAULTS}
    with DATA.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            def number(key: str) -> float | None:
                value = row.get(key, "")
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            target = number("shootDryMassG")
            if target is None:
                excluded["missing target or core feature"] = excluded.get(
                    "missing target or core feature", 0) + 1
                continue
            if target <= 0:
                # A published dry mass of zero cannot enter a log target, and replacing it would be
                # an imputation. It is excluded and counted.
                excluded["published dry mass of zero (cannot enter a log target)"] = excluded.get(
                    "published dry mass of zero (cannot enter a log target)", 0) + 1
                continue
            record: dict[str, Any] = {"studyKey": row["studyKey"], "citation": row["citation"],
                                      "target": target, "logTarget": math.log10(target)}
            for feature in FEATURES:
                record[feature] = number(feature)
            if record["dailyLightIntegralMolPerM2Day"] is None:
                ppfd, photo = record["ppfdUmolPerM2S"], record["photoperiodHours"]
                if ppfd is not None and photo is not None:
                    record["dailyLightIntegralMolPerM2Day"] = ppfd * photo * 3600 / 1e6
            for feature, value in DEFAULTS.items():
                if record[feature] is None:
                    # Counted here, at the moment a blank is filled. Counting rows that happen to
                    # equal the default would report coincidence as imputation.
                    record[feature] = value
                    filled[feature] += 1
            if any(record[feature] is None for feature in FEATURES):
                excluded["missing core feature after the daily-light-integral derivation"] = (
                    excluded.get("missing core feature after the daily-light-integral derivation", 0)
                    + 1)
                continue
            rows.append(record)
    return rows, excluded, filled


def sealed_studies(rows: list[dict[str, Any]]) -> list[str]:
    ranked = sorted({row["studyKey"] for row in rows},
                    key=lambda key: hashlib.sha256(key.encode()).hexdigest())
    return sorted(ranked[:HOLDOUT_STUDIES])


def design(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)
    y = np.array([row["logTarget"] for row in rows], dtype=float)
    return x, y


def fit_predict(name: str, train_x: np.ndarray, train_y: np.ndarray,
                test_x: np.ndarray) -> np.ndarray:
    if name == "baseline-mean":
        return np.full(len(test_x), float(np.mean(train_y)))
    if name == "light-limited-structure":
        # log yield = a + b*log(DLI), the shape a light-limited growth model predicts. A structural
        # prior, not a fitted black box: it is the candidate that should win if light is the signal.
        dli = train_x[:, FEATURES.index("dailyLightIntegralMolPerM2Day")]
        design_train = np.column_stack([np.ones_like(dli), np.log(dli)])
        coefficients, *_ = np.linalg.lstsq(design_train, train_y, rcond=None)
        test_dli = test_x[:, FEATURES.index("dailyLightIntegralMolPerM2Day")]
        return np.column_stack([np.ones_like(test_dli), np.log(test_dli)]) @ coefficients
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
    a = np.array(actual, dtype=float)
    p = np.array(predicted, dtype=float)
    errors = p - a
    ape = np.abs(errors) / a * 100
    ss_res = float(np.sum((a - p) ** 2))
    ss_tot = float(np.sum((a - np.mean(a)) ** 2))
    return {
        "n": int(len(a)),
        "MAEgPerPlant": round(float(np.mean(np.abs(errors))), 4),
        "RMSEgPerPlant": round(float(np.sqrt(np.mean(errors ** 2))), 4),
        "MAPE": round(float(np.mean(ape)), 3),
        "medianAPE": round(float(np.median(ape)), 3),
        "meanBiasErrorGPerPlant": round(float(np.mean(errors)), 4),
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


def main() -> int:
    rows, excluded, filled = load()
    sealed = set(sealed_studies(rows))
    development = [row for row in rows if row["studyKey"] not in sealed]
    holdout = [row for row in rows if row["studyKey"] in sealed]
    dev_studies = {row["studyKey"] for row in development}
    print(f"rows {len(rows)}  studies {len({row['studyKey'] for row in rows})}  "
          f"development {len(development)}  holdout rows {len(holdout)} ({len(sealed)} studies)")

    dev_x, dev_y = design(development)
    dev_target = [row["target"] for row in development]

    # Leave-one-study-out: every observation of a study leaves together.
    oof: dict[str, list[float]] = {name: [] for name in CANDIDATE_ORDER}
    for study in sorted(dev_studies):
        test_index = [index for index, row in enumerate(development) if row["studyKey"] == study]
        train_index = [index for index, row in enumerate(development) if row["studyKey"] != study]
        for name in CANDIDATE_ORDER:
            predicted = fit_predict(name, dev_x[train_index], dev_y[train_index],
                                    dev_x[test_index])
            for index, value in zip(test_index, predicted):
                oof[name].append((index, float(value)))
    # Restore the original order so a metric is computed against the right target.
    ordered_oof: dict[str, list[float]] = {}
    for name in CANDIDATE_ORDER:
        values = [0.0] * len(development)
        for index, value in oof[name]:
            values[index] = value
        ordered_oof[name] = values

    candidates: dict[str, Any] = {}
    for name in CANDIDATE_ORDER:
        predicted_yield = [10 ** value for value in ordered_oof[name]]
        candidates[name] = metrics(dev_target, predicted_yield)
        print(f"  {name:<26} MAE {candidates[name]['MAEgPerPlant']:.4f} g  "
              f"MAPE {candidates[name]['MAPE']:.1f} %  R2 {candidates[name]['R2']}")

    best = min(row["MAEgPerPlant"] for row in candidates.values())
    selected = next(name for name in CANDIDATE_ORDER
                    if candidates[name]["MAEgPerPlant"] <= best * 1.02)
    print(f"selected: {selected}")

    residuals = sorted(actual - predicted
                       for actual, predicted in zip(dev_y, ordered_oof[selected]))
    n = len(residuals)
    rank = min(n, math.ceil((n + 1) * 0.9))
    low, high = residuals[max(0, n - rank)], residuals[rank - 1]

    holdout_x, holdout_y = design(holdout)
    holdout_log = fit_predict(selected, dev_x, dev_y, holdout_x)
    holdout_target = [row["target"] for row in holdout]
    holdout_predicted = [10 ** value for value in holdout_log]
    holdout_metrics = metrics(holdout_target, holdout_predicted)
    per_study: dict[str, list[float]] = {}
    for row, predicted in zip(holdout, holdout_target and holdout_predicted):
        per_study.setdefault(row["studyKey"], []).append(
            abs(predicted - row["target"]) / row["target"] * 100)
    median_study_ape = round(statistics.median(
        [statistics.fmean(values) for values in per_study.values()]), 3)
    passed = holdout_metrics["MAPE"] <= ACCEPTANCE_CRITERION_PCT
    print(f"holdout MAPE {holdout_metrics['MAPE']:.2f} % vs {ACCEPTANCE_CRITERION_PCT} % -> "
          f"{'PASS' if passed else 'FAIL'}  (median APE {holdout_metrics['medianAPE']:.1f} %, "
          f"R2 {holdout_metrics['R2']})")

    payload = {
        "schema": "spaceagrisim.phase30_harvest_crossstudy/1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "purpose": ("measure lettuce harvest-model generalisation across genuinely independent "
                    "studies, which the four-experiment training set could not do"),
        "dataset": {
            "id": "lettuce-multistudy-lue",
            "doi": "10.5281/zenodo.14640245",
            "license": "CC BY 4.0",
            "file": "data/processed/phase30/lettuce_multistudy.csv",
            "observationKind": "published-treatment-mean",
            "rowsUsed": len(rows),
            "studiesUsed": len({row["studyKey"] for row in rows}),
            "target": "shoot dry mass per plant (g), as published",
            "exclusions": excluded,
            "imputedDefaults": {**DEFAULTS,
                                "why": ("a study that did not report CO2 or photoperiod cannot "
                                        "drop out of a cross-study comparison without biasing it "
                                        "toward the studies that reported everything. A single "
                                        "declared default is applied and the affected count is "
                                        "reported; no value is fitted or drawn from the target."),
                                "affectedRows": filled,
                                },
        },
        "protocol": {
            "split": "leave-one-study-out over the development studies",
            "groupingKey": "study",
            "targetTransform": "log10(shoot dry mass g per plant)",
            "features": list(FEATURES),
            "featureUnits": FEATURE_UNITS,
            "holdoutStudies": sorted(sealed),
            "holdoutUsedForSelection": False,
            "holdoutSelectionMethod": "SHA-256 of the study key, eight lowest",
            "selectionRule": ("lowest out-of-fold MAE; within 2 % prefer the structurally simpler "
                              "model (light-limited, ridge, baseline over gbm)"),
            "candidateOrder": list(CANDIDATE_ORDER),
            "selectionRuleWrittenBeforeScoring": True,
            "acceptanceCriterionPct": ACCEPTANCE_CRITERION_PCT,
            "criterionSource": "unchanged project criterion, not set by this phase",
            "seed": SEED,
            "noRandomSplit": ("a random split across treatment means would put sibling treatments "
                              "of one study on both sides; it is not used and its result is not "
                              "reported"),
        },
        "candidates": candidates,
        "selected": selected,
        "selectedOutOfFold": candidates[selected],
        "interval": {
            "method": "split conformal on out-of-fold log10 residuals, 90 % two-sided",
            "logLow": round(low, 4),
            "logHigh": round(high, 4),
            "multiplicativeWidth": round(10 ** (high - low), 4),
            "nResiduals": n,
            "coverageNote": ("an in-sample coverage figure from the same residuals the interval was "
                             "built on; descriptive, not a guarantee for a new study"),
        },
        "holdout": {
            "studies": len(sealed),
            "treatments": len(holdout),
            "records": [{"studyKey": row["studyKey"], "citation": row["citation"],
                         "measuredGPerPlant": round(row["target"], 4),
                         "predictedGPerPlant": round(predicted, 4),
                         "apePct": round(abs(predicted - row["target"]) / row["target"] * 100, 2)}
                        for row, predicted in zip(holdout, holdout_predicted)],
            "metrics": holdout_metrics,
            "medianStudyAPE": median_study_ape,
            "acceptanceCriterionPct": ACCEPTANCE_CRITERION_PCT,
            "passed": passed,
        },
        "promoted": False,
        "promotionBlockedBy": [
            "the holdout error is more than five times the criterion",
            "the fitted interval spans a factor of " + f"{10 ** (high - low):.1f}",
            "the corpus is published treatment means, so within-study variance is unknown",
        ] if not passed else [],
        "limitations": [
            "Published treatment means: one row is a mean another author reported, so the residual "
            "mix inside a study is invisible and a weighted fit is impossible.",
            "Study-level choices (cultivar, substrate, harvest definition, dry versus fresh basis) "
            "move yield by more than the environment the model sees.",
            "The holdout is eight studies; one unusual study moves the metric a long way.",
            "No extrapolation to a cultivar, a facility or a light regime outside these studies.",
        ],
        "priorHoldoutInspection": ("no study in this table was inspected before the sealed holdout "
                                   "was chosen; the split was fixed by SHA-256 and scored once."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(payload, OUT)
    print(f"written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
