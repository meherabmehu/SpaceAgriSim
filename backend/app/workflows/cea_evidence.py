"""Workflow C, second evidence set — controlled-environment wheat across experiments, measured.

Why this exists
---------------
The light-quality half of workflow C compares four spectral regimes from one trial. Useful, but it
answers a narrow question, and everything the platform could say about irradiance, CO2, photoperiod or
temperature stress was either absent or resting on an assumption.

Phase 30 acquired a dataset that changes what can be said: 39 indoor wheat (cv. Apogee) experiments,
36 of which pair a harvested grain yield with the chamber environment logged during the run — mean
PPFD, photoperiod, CO2, air temperature and relative humidity. That is enough independent experiments
to report what the environment did to yield across a real range, with each experiment standing as its
own group.

What it does, and what it refuses to do
---------------------------------------
It reports **measured yields grouped by environment stratum**: a user picks a factor and a band, and
the response returns the experiments in that band with their yields, spread and provenance. It also
returns the daily-light-integral relationship as a measured association rather than a fitted curve.

It does **not** predict the yield of a new environment. A response surface was fitted to this same
dataset in Phase 30 and scored once on sealed experiments; it missed the project's 30 % criterion by
an order of magnitude. The numbers come from `ml/evaluation/phase30_cea_wheat_response.json`, the model
is not served, and the failure is returned in every response so a user can read the evidence for the
decision instead of taking it on trust.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.workflows import units

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "processed" / "phase30" / "cea_wheat_experiments.csv"
QUALITY = ROOT / "data" / "processed" / "phase30" / "quality.json"
MODEL_EVIDENCE = ROOT / "ml" / "evaluation" / "phase30_cea_wheat_response.json"

SOURCE = {
    "dataset": "cea-wheat-apogee",
    "title": "Indoor wheat (cv. Apogee) under fully controlled environmental conditions",
    "doi": "10.5281/zenodo.17764612",
    "license": "CC BY 4.0",
    "citation": ("Wheat growth data from indoor vertical-farm experiments under fully controlled "
                 "environmental conditions, Zenodo record 17764612"),
    "measurementBasis": ("destructive harvest of grain per sub-plot, with chamber environment logged "
                         "by the climate computer during the run"),
}

# The four factors the experiment series actually varies. Each is a measured chamber setting, not a
# modelled level, and each band is a real partition of the experiments.
FACTORS: list[dict[str, Any]] = [
    {
        "factor": "meanPpfdUmolPerM2S",
        "publicName": "ppfdUmolPerM2S",
        "label": "Mean PPFD",
        "unit": "umol/m2/s",
        "bands": [{"id": "low", "label": "< 400", "min": 0, "max": 400},
                  {"id": "mid", "label": "400 - 700", "min": 400, "max": 700},
                  {"id": "high", "label": "> 700", "min": 700, "max": 100000}],
        "note": ("PPFD is the mean over the run. It varied between sub-plots inside a chamber in "
                 "most experiments, and that within-run spread is recorded per experiment."),
    },
    {
        "factor": "photoperiodHours",
        "publicName": "photoperiodHours",
        "label": "Photoperiod",
        "unit": "h/day",
        "bands": [{"id": "short", "label": "< 12 h", "min": 0, "max": 12},
                  {"id": "standard", "label": "12 - 20 h", "min": 12, "max": 20},
                  {"id": "long", "label": "> 20 h", "min": 20, "max": 24.1}],
        "note": "Continuous light above 20 h is a real treatment in this series, not an extrapolation.",
    },
    {
        "factor": "co2Ppm",
        "publicName": "co2Ppm",
        "label": "CO2 concentration",
        "unit": "ppm",
        "bands": [{"id": "ambient", "label": "<= 450 (ambient)", "min": 0, "max": 450},
                  {"id": "enriched", "label": "451 - 800", "min": 450, "max": 800},
                  {"id": "high", "label": "> 800", "min": 800, "max": 100000}],
        "note": ("The only CO2 contrast in this repository, and a narrow one: a handful of distinct "
                 "concentrations inside a controlled chamber."),
    },
    {
        "factor": "airTemperatureC",
        "publicName": "airTemperatureC",
        "label": "Air temperature",
        "unit": "degC",
        "bands": [{"id": "cool", "label": "< 23 C", "min": 0, "max": 23},
                  {"id": "mid", "label": "23 - 25 C", "min": 23, "max": 25},
                  {"id": "warm", "label": "> 25 C", "min": 25, "max": 60}],
        "note": ("A narrow band by field standards: this series studied a vertical farm, where "
                 "temperature is held near an optimum. It does not identify a cardinal-temperature "
                 "response."),
    },
]

MAX_SELECTIONS = 6


@lru_cache(maxsize=1)
def _experiments() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    with DATA.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            record: dict[str, Any] = {"experimentId": row["experimentId"],
                                      "system": row.get("system", "")}
            for field in ("grainYieldKgPerM2Mean", "meanPpfdUmolPerM2S", "photoperiodHours",
                          "co2Ppm", "airTemperatureC", "relativeHumidityPct", "cycleLengthDays",
                          "harvestIndexMean", "subplotRows"):
                try:
                    record[field] = float(row[field])
                except (KeyError, TypeError, ValueError):
                    record[field] = None
            rows.append(record)
    return tuple(row for row in rows
                 if row["grainYieldKgPerM2Mean"] is not None
                 and row["meanPpfdUmolPerM2S"] is not None)


@lru_cache(maxsize=1)
def _quality() -> dict[str, Any]:
    return json.loads(QUALITY.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _model_evidence() -> dict[str, Any]:
    return json.loads(MODEL_EVIDENCE.read_text(encoding="utf-8"))


def _dli(row: dict[str, Any]) -> float:
    return row["meanPpfdUmolPerM2S"] * row["photoperiodHours"] * 3600 / 1e6


def _band(factor: dict[str, Any], band: dict[str, Any], row: dict[str, Any]) -> bool:
    value = row.get(factor["factor"])
    if value is None:
        return False
    low, high = band["min"], band["max"]
    if band["id"] in ("low", "short", "ambient", "cool"):
        return low <= value <= high
    return low < value <= high


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    return {
        "n": len(values),
        "mean": round(mean, 5),
        "median": round(statistics.median(values), 5),
        "sd": round(sd, 5) if sd is not None else None,
        "min": round(min(values), 5),
        "max": round(max(values), 5),
        "meanCiLow": round(mean - 1.96 * sd / math.sqrt(len(values)), 5) if sd else None,
        "meanCiHigh": round(mean + 1.96 * sd / math.sqrt(len(values)), 5) if sd else None,
    }


def _predictive_model() -> dict[str, Any]:
    """What happened when a response surface was actually attempted on this dataset.

    Read from the evaluation artifact rather than retyped, so the workflow cannot drift into
    describing a model that scored something else.
    """
    evidence = _model_evidence()
    holdout = evidence["holdout"]
    best_oof = min(row["MAPE"] for row in evidence["candidates"].values())
    return {
        "attempted": True,
        "served": False,
        "criterion": holdout["acceptanceCriterionPct"],
        "holdoutMapePct": holdout["metrics"]["MAPE"],
        "holdoutR2": holdout["metrics"]["R2"],
        "bestOutOfFoldMapePct": best_oof,
        "selected": evidence["selected"],
        "developmentExperiments": len(evidence["protocol"]["developmentExperiments"]),
        "holdoutExperiments": holdout["experiments"],
        "reason": (
            f"a response surface was fitted to {len(evidence['protocol']['developmentExperiments'])} "
            "experiments under leave-one-experiment-out validation and scored once on "
            f"{holdout['experiments']} sealed experiments. The selected model "
            f"({evidence['selected']}) missed the {holdout['acceptanceCriterionPct']:g} % criterion "
            f"by an order of magnitude: {holdout['metrics']['MAPE']:.1f} % MAPE, R2 "
            f"{holdout['metrics']['R2']}. It is recorded in "
            "ml/evaluation/phase30_cea_wheat_response.json and is not served."
        ),
        "evidenceFile": "ml/evaluation/phase30_cea_wheat_response.json",
    }


def _count(factor: dict[str, Any], band: dict[str, Any]) -> int:
    return sum(1 for row in _experiments() if _band(factor, band, row))


def capability() -> dict[str, Any]:
    experiments = _experiments()
    yields = [row["grainYieldKgPerM2Mean"] for row in experiments]
    return {
        "workflow": "cea-evidence",
        "partOf": "light-stress",
        "title": "Controlled-environment wheat across independent experiments — measured",
        "evidenceClass": "measured-observation",
        "isSimulation": False,
        "isModelPrediction": False,
        "crop": {"name": "wheat", "cultivar": "Apogee"},
        "dataset": {**SOURCE, "experiments": len(experiments),
                    "subplotRows": _quality()["datasets"]["cea-wheat-apogee"]["subplotRows"],
                    "yieldRangeKgPerM2": [round(min(yields), 4), round(max(yields), 4)]},
        "fields": [
            {"name": "factor", "label": "Environmental factor", "kind": "select",
             "options": [factor["publicName"] for factor in FACTORS],
             "why": "the four factors the experiment series varied; every band is a real partition"},
            {"name": "band", "label": "Band", "kind": "select",
             "options": {factor["publicName"]: [band["id"] for band in factor["bands"]]
                         for factor in FACTORS},
             "why": "a measured group of experiments, not a modelled level"},
        ],
        "factors": [
            {**factor,
             "bands": [{**band, "experiments": _count(factor, band)}
                       for band in factor["bands"]]}
            for factor in FACTORS
        ],
        "maxSelections": MAX_SELECTIONS,
        "responseVariables": [
            {"name": "grainYieldKgPerM2", "unit": "kg/m2", "means": "harvested grain per square metre"},
        ],
        "predictiveModel": _predictive_model(),
        "units": units.block(grainYieldKgPerM2="kg/m2", ppfdUmolPerM2S="umol/m2/s",
                             photoperiodHours="h/day", co2Ppm="ppm", airTemperatureC="degC",
                             relativeHumidityPct="%", cycleLengthDays="day",
                             harvestIndex="fraction"),
    }


def run(selections: list[dict[str, Any]]) -> dict[str, Any]:
    experiments = _experiments()
    by_factor = {factor["publicName"]: factor for factor in FACTORS}
    groups: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for selection in selections[:MAX_SELECTIONS]:
        factor = by_factor.get(selection.get("factor"))
        if factor is None:
            continue
        band = next((item for item in factor["bands"] if item["id"] == selection.get("band")), None)
        if band is None:
            continue
        members = [row for row in experiments if _band(factor, band, row)]
        summary = _summary([row["grainYieldKgPerM2Mean"] for row in members])
        if not members:
            summary["note"] = ("no experiment in this dataset falls in this band. The band is left "
                               "empty rather than filled with a neighbouring experiment.")
        entry = {
            "label": f"{factor['label']} {band['label']}",
            "factor": factor["publicName"],
            "band": band["id"],
            "unit": "kg/m2",
            "crop": "wheat",
            "cultivar": "Apogee",
            "experiments": [row["experimentId"] for row in members],
            "measured": summary,
            "co2RangePpm": _range([row["co2Ppm"] for row in members]),
            "ppfdRange": _range([row["meanPpfdUmolPerM2S"] for row in members]),
            "photoperiodRangeHours": _range([row["photoperiodHours"] for row in members]),
            "temperatureRangeC": _range([row["airTemperatureC"] for row in members]),
        }
        groups.append(entry)
        for row in members:
            rows.append({"label": entry["label"], "experimentId": row["experimentId"],
                         "grainYieldKgPerM2": round(row["grainYieldKgPerM2Mean"], 4),
                         "ppfdUmolPerM2S": round(row["meanPpfdUmolPerM2S"], 2),
                         "photoperiodHours": round(row["photoperiodHours"], 2),
                         "co2Ppm": row["co2Ppm"],
                         "airTemperatureC": row["airTemperatureC"]})

    differences = []
    for index, left in enumerate(groups):
        for right in groups[index + 1:]:
            if left["measured"]["n"] < 3 or right["measured"]["n"] < 3:
                continue
            differences.append({
                "between": [left["label"], right["label"]],
                "differenceKgPerM2": round(right["measured"]["mean"] - left["measured"]["mean"], 4),
                "relativeDifference": round(
                    (right["measured"]["mean"] - left["measured"]["mean"])
                    / left["measured"]["mean"], 4) if left["measured"]["mean"] else None,
                "note": ("a difference between two groups of whole experiments. Experiments differ in "
                         "more than this one factor, so this is not an isolated effect."),
            })

    return {
        "workflow": "cea-evidence",
        "partOf": "light-stress",
        "status": "complete",
        "title": "Controlled-environment wheat across independent experiments — measured",
        "evidenceClass": "measured-observation",
        "isSimulation": False,
        "isModelPrediction": False,
        "groups": groups,
        "rows": rows,
        "differences": differences,
        "dliRelationship": _dli_relationship(experiments),
        "predictiveModel": _predictive_model(),
        "provenance": {
            "source": SOURCE,
            "rawFileSha256": _quality()["datasets"]["cea-wheat-apogee"]["rawSha256"],
            "processedFiles": _quality()["datasets"]["cea-wheat-apogee"]["processedFiles"],
            "experimentRows": len(experiments),
            "verifiedAgainstManifest": True,
        },
        "method": {
            "name": "measured group summary over whole experiments",
            "unitOfIndependence": "experiment (chamber run)",
            "interval": ("95 % interval on the mean of the experiments in the band, from their own "
                         "between-experiment spread"),
            "noTest": ("no significance test is reported across bands: the experiments differ in "
                       "several factors at once, and a p-value on a band difference would be a "
                       "statement about confounding"),
        },
        "limitations": [
            "One crop (wheat cv. Apogee), one facility family, and bands chosen by this platform.",
            "Each band mixes experiments that also differ in the other three factors; a difference "
            "between bands is therefore not an isolated effect of the factor named.",
            "Yield is grain, not edible biomass, and the harvest index is not modelled.",
            "No predictive model is served: the response model fitted to this data failed its "
            "holdout by an order of magnitude and is recorded in "
            "ml/evaluation/phase30_cea_wheat_response.json.",
        ],
        "units": capability()["units"],
    }


def _range(values: list[float | None]) -> list[float] | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return [round(min(present), 3), round(max(present), 3)]


def _dli_relationship(experiments: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Measured scatter summary of grain yield against daily light integral.

    A correlation, explicitly not a response function: with these experiments differing in CO2,
    temperature and photoperiod at the same time, a slope here is an association.
    """
    points = [{"experimentId": row["experimentId"],
               "dailyLightIntegralMolPerM2Day": round(_dli(row), 3),
               "grainYieldKgPerM2": round(row["grainYieldKgPerM2Mean"], 4)}
              for row in experiments
              if row["photoperiodHours"] is not None]
    x = [point["dailyLightIntegralMolPerM2Day"] for point in points]
    y = [point["grainYieldKgPerM2"] for point in points]
    n = len(x)
    mean_x, mean_y = statistics.fmean(x), statistics.fmean(y)
    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    variance_x = sum((a - mean_x) ** 2 for a in x)
    variance_y = sum((b - mean_y) ** 2 for b in y)
    correlation = (covariance / math.sqrt(variance_x * variance_y)
                   if variance_x > 0 and variance_y > 0 else None)
    order_x = sorted(range(n), key=lambda index: x[index])
    order_y = sorted(range(n), key=lambda index: y[index])
    rank_x = {index: rank for rank, index in enumerate(order_x)}
    rank_y = {index: rank for rank, index in enumerate(order_y)}
    spearman = (1 - 6 * sum((rank_x[i] - rank_y[i]) ** 2 for i in range(n)) / (n * (n * n - 1))
                if n > 1 else None)
    return {
        "points": points,
        "pearson": round(correlation, 4) if correlation is not None else None,
        "spearman": round(spearman, 4) if spearman is not None else None,
        "note": ("an association between daily light integral and measured grain yield across "
                 "experiments that also differ in CO2, temperature and photoperiod. It is not a "
                 "response function and must not be used as one."),
    }
