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
an order of magnitude. The numbers come from `ml/evaluation/phase30_cea_wheat_response`, the model
is not served, and the failure is returned in every response so a user can read the evidence for the
decision instead of taking it on trust.
"""
from __future__ import annotations
import sys

import csv
import math
import statistics
from functools import lru_cache
from pathlib import Path
from typing import Any

from scipy import stats

from app.workflows import units

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
DATA = ROOT / "data" / "processed" / "phase30" / "cea_wheat_experiments.csv"
QUALITY = ROOT / "data" / "processed" / "phase30" / "quality"
MODEL_EVIDENCE = ROOT / "ml" / "evaluation" / "phase30_cea_wheat_response"

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
#
# Every band carries explicit bounds — a lower and an upper value, and whether each end is included —
# and its label is *generated* from those bounds by `band_label()`. Before that, the two were written
# by hand and had drifted apart: the air-temperature band labelled "< 23 C" admitted experiments
# measured at exactly 23.0 C (five of them), so the table said one thing about a group and the
# predicate had done another. A label that is a function of the predicate cannot drift again, and
# `backend/tests/test_guided_cea_workflow.py` checks every band against the file.
#
# The inclusivity below is exactly the inclusivity the previous hard-coded predicate used, so no
# experiment changes band and no reported mean moves. Only the wording becomes true.
FACTORS: list[dict[str, Any]] = [
    {
        "factor": "meanPpfdUmolPerM2S",
        "publicName": "ppfdUmolPerM2S",
        "label": "Mean PPFD",
        "unit": "umol/m2/s",
        "unitSymbol": "",
        "bands": [{"id": "low", "min": 0, "minInclusive": True, "max": 400, "maxInclusive": True},
                  {"id": "mid", "min": 400, "minInclusive": False, "max": 700, "maxInclusive": True},
                  {"id": "high", "min": 700, "minInclusive": False, "max": 100000, "maxInclusive": True,
                   "openUpper": True}],
        "note": ("PPFD is the mean over the run. It varied between sub-plots inside a chamber in "
                 "most experiments, and that within-run spread is recorded per experiment."),
    },
    {
        "factor": "photoperiodHours",
        "publicName": "photoperiodHours",
        "label": "Photoperiod",
        "unit": "h/day",
        "unitSymbol": " h",
        "bands": [{"id": "short", "min": 0, "minInclusive": True, "max": 12, "maxInclusive": True},
                  {"id": "standard", "min": 12, "minInclusive": False, "max": 20, "maxInclusive": True},
                  {"id": "long", "min": 20, "minInclusive": False, "max": 24.1, "maxInclusive": True,
                   "openUpper": True}],
        "note": "Continuous light above 20 h is a real treatment in this series, not an extrapolation.",
    },
    {
        "factor": "co2Ppm",
        "publicName": "co2Ppm",
        "label": "CO2 concentration",
        "unit": "ppm",
        "unitSymbol": " ppm",
        "bands": [{"id": "ambient", "min": 0, "minInclusive": True, "max": 450, "maxInclusive": True},
                  {"id": "enriched", "min": 450, "minInclusive": False, "max": 800, "maxInclusive": True},
                  {"id": "high", "min": 800, "minInclusive": False, "max": 100000, "maxInclusive": True,
                   "openUpper": True}],
        "note": ("The only CO2 contrast in this repository, and a narrow one: a handful of distinct "
                 "concentrations inside a controlled chamber."),
    },
    {
        "factor": "airTemperatureC",
        "publicName": "airTemperatureC",
        "label": "Air temperature",
        "unit": "degC",
        "unitSymbol": " C",
        "bands": [{"id": "cool", "min": 0, "minInclusive": True, "max": 23, "maxInclusive": True},
                  {"id": "mid", "min": 23, "minInclusive": False, "max": 25, "maxInclusive": True},
                  {"id": "warm", "min": 25, "minInclusive": False, "max": 60, "maxInclusive": True,
                   "openUpper": True}],
        "note": ("A narrow band by field standards: this series studied a vertical farm, where "
                 "temperature is held near an optimum. It does not identify a cardinal-temperature "
                 "response."),
    },
]

MAX_SELECTIONS = 6


@lru_cache(maxsize=1)
def _all_experiment_ids() -> tuple[str, ...]:
    """Every experiment the published series names, including those with no environment row."""
    with DATA.open(newline="", encoding="utf-8") as handle:
        return tuple(row["experimentId"] for row in csv.DictReader(handle) if row.get("experimentId"))


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
    return safedata.load(QUALITY)


@lru_cache(maxsize=1)
def _model_evidence() -> dict[str, Any]:
    return safedata.load(MODEL_EVIDENCE)


def _dli(row: dict[str, Any]) -> float:
    return row["meanPpfdUmolPerM2S"] * row["photoperiodHours"] * 3600 / 1e6


def band_label(band: dict[str, Any], unit_symbol: str) -> str:
    """The band's bounds, written out. The label is derived, never typed in beside the predicate.

    A closed lower end renders as "≥ 400"; an open one as "> 400". The top band of each factor is
    open-ended and prints only its lower bound, because its ceiling is a sentinel used to keep the
    predicate total, not a measurement. `test_every_band_label_matches_its_predicate` compares this
    text with the values `in_band` actually accepts, so the two cannot drift apart again.
    """
    low, high = band["min"], band["max"]
    low_text = "" if low == 0 else ("≥ " if band["minInclusive"] else "> ") + f"{low:g}"
    high_prefix = "≤ " if band["maxInclusive"] else "< "
    if band.get("openUpper"):
        body = low_text or "all measured values"
    elif low_text:
        body = f"{low_text} to {high_prefix}{high:g}"
    else:
        body = f"{high_prefix}{high:g}"
    return f"{body}{unit_symbol}"


def in_band(band: dict[str, Any], value: float | None) -> bool:
    if value is None:
        return False
    lower_ok = value >= band["min"] if band["minInclusive"] else value > band["min"]
    upper_ok = value <= band["max"] if band["maxInclusive"] else value < band["max"]
    return lower_ok and upper_ok


def _band(factor: dict[str, Any], band: dict[str, Any], row: dict[str, Any]) -> bool:
    return in_band(band, row.get(factor["factor"]))


#: Below this many experiments no interval on the mean is reported at all. With n = 2 a 95 %
#: Student-t interval is 12.7 standard errors wide and, on this dataset, ran from -0.13 kg/m2:
#: an interval on a yield that cannot be negative, produced by an approximation that assumes the
#: data can be. Reporting "n = 2" is honest; reporting that interval is not.
MIN_INTERVAL_N = 3

#: Two-sided 95 %, the same coverage the previous 1.96 figure claimed - but as a Student-t quantile
#: with n-1 degrees of freedom, which is what a standard error estimated from n observations means.
CI_CONFIDENCE = 0.95


def _summary(values: list[float]) -> dict[str, Any]:
    """Mean, median, spread and - when the sample supports it - a 95 % interval on the mean.

    The interval changed in this pass. It used to be `mean ± 1.96 · sd / sqrt(n)` for any n with an
    sd, which is the large-sample form: at n = 2 it produced a negative lower bound on a non-negative
    yield, and it was printed for every band regardless. It is now a Student-t interval, and it is
    withheld below `MIN_INTERVAL_N` with a stated reason instead of being shown anyway.
    """
    if not values:
        return {"n": 0, "ciStatus": "no-observations",
                "ciNote": "no experiment in this dataset falls in this band"}
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else None
    summary: dict[str, Any] = {
        "n": n,
        "mean": round(mean, 5),
        "median": round(statistics.median(values), 5),
        "sd": round(sd, 5) if sd is not None else None,
        "min": round(min(values), 5),
        "max": round(max(values), 5),
        "meanCiLow": None,
        "meanCiHigh": None,
    }
    if n < MIN_INTERVAL_N or sd is None:
        summary["ciStatus"] = "insufficient-observations"
        summary["ciNote"] = (
            f"{n} experiment{'s' if n != 1 else ''} in this band. A 95 % interval on the mean needs "
            f"at least {MIN_INTERVAL_N}; with fewer the interval is wider than the quantity it "
            "describes, so the count and the individual experiments are reported instead."
        )
        return summary
    half_width = stats.t.ppf(0.5 + CI_CONFIDENCE / 2, n - 1) * sd / math.sqrt(n)
    low, high = mean - half_width, mean + half_width
    summary.update({
        "meanCiLow": float(round(low, 5)),
        "meanCiHigh": float(round(high, 5)),
        "ciStatus": "reported",
        "ciMethod": "student-t, two-sided 95 %, df = n - 1",
        "ciDf": n - 1,
    })
    if low < min(values):
        # Not clamped: an interval that runs past the observed range is a property of the sample
        # size, and silently narrowing it to the data would hide exactly that.
        summary["ciCaveat"] = (
            "the interval extends below the lowest observed yield in this band; that is the "
            "small-sample width, not a negative measurement."
        )
    return summary


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
            "ml/evaluation/phase30_cea_wheat_response and is not served."
        ),
        "evidenceFile": "ml/evaluation/phase30_cea_wheat_response",
    }


def band_ids(public_name: str) -> list[str]:
    """The band ids that exist for one factor, in declared order. Empty for an unknown factor."""
    factor = next((item for item in FACTORS if item["publicName"] == public_name), None)
    return [band["id"] for band in factor["bands"]] if factor else []


def _count(factor: dict[str, Any], band: dict[str, Any]) -> int:
    return sum(1 for row in _experiments() if _band(factor, band, row))


def _public_factor(factor: dict[str, Any]) -> dict[str, Any]:
    """One factor as the API publishes it: derived label, explicit bounds, measured count."""
    return {
        **factor,
        "bands": [
            {
                "id": band["id"],
                "label": band_label(band, factor["unitSymbol"]),
                "bounds": {"min": band["min"], "minInclusive": band["minInclusive"],
                           "max": band["max"], "maxInclusive": band["maxInclusive"],
                           "openUpper": bool(band.get("openUpper"))},
                "experiments": _count(factor, band),
            }
            for band in factor["bands"]
        ],
    }


def resolve_selection(selection: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The (factor, band) a selection names, or a ValueError listing what is allowed.

    It used to `continue` past an unknown factor or band, so a client that guessed a band name got
    `200` and an empty group list - indistinguishable from a supported band that happens to hold no
    experiments. Those are different answers and the API now says which is which.
    """
    by_factor = {factor["publicName"]: factor for factor in FACTORS}
    factor = by_factor.get(str(selection.get("factor", "")))
    if factor is None:
        allowed = ", ".join(sorted(by_factor))
        raise ValueError(f"unknown factor {selection.get('factor')!r}; supported factors: {allowed}")
    band = next((item for item in factor["bands"] if item["id"] == selection.get("band")), None)
    if band is None:
        allowed = ", ".join(item["id"] for item in factor["bands"])
        raise ValueError(f"unknown band {selection.get('band')!r} for {factor['publicName']}; "
                         f"supported bands: {allowed}")
    return factor, band


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
                    # The published series holds experiments that carry no environment row, so they
                    # cannot be placed in any band. Saying both numbers keeps a reader from finding
                    # three experiments missing from a partition that adds up to fewer than the
                    # series claims.
                    "classifiableExperiments": len(experiments),
                    "unclassifiableExperiments": len(_all_experiment_ids()) - len(experiments),
                    "unclassifiableNote": (
                        f"{len(_all_experiment_ids()) - len(experiments)} experiments in the "
                        "published series carry no usable environment or yield row; they are "
                        "excluded from every band rather than assigned to one by guess"),
                    "subplotRows": _quality()["datasets"]["cea-wheat-apogee"]["subplotRows"],
                    "yieldRangeKgPerM2": [round(min(yields), 4), round(max(yields), 4)]},
        "fields": [
            {"name": "factor", "label": "Environmental factor", "kind": "select",
             "options": [factor["publicName"] for factor in FACTORS],
             "why": "the four factors the experiment series varied; every band is a real partition"},
            {"name": "band", "label": "Band", "kind": "select",
             "options": {factor["publicName"]: [band["id"] for band in factor["bands"]]
                         for factor in FACTORS},
             "labels": {factor["publicName"]: {band["id"]: band_label(band, factor["unitSymbol"])
                                               for band in factor["bands"]}
                        for factor in FACTORS},
             "why": "a measured group of experiments, not a modelled level"},
        ],
        "factors": [_public_factor(factor) for factor in FACTORS],
        "maxSelections": MAX_SELECTIONS,
        "statistics": {
            "confidenceLevel": CI_CONFIDENCE,
            "interval": "student-t on the between-experiment spread, two-sided, df = n - 1",
            "minExperimentsForInterval": MIN_INTERVAL_N,
            "belowMinimum": (f"with fewer than {MIN_INTERVAL_N} experiments the count, mean, median "
                             "and range are reported and no interval is, because an interval that "
                             "wide is not informative about the mean"),
        },
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
    """Measured groups for the requested factor/band pairs.

    Raises `ValueError` for a factor or band the dataset does not define; the route turns that into
    a 422 that names the supported values. A band that is defined but holds no experiment is *not*
    an error: it comes back as an empty group with `empty: true` and the reason, because a real
    band with no members is a fact about the data and the caller has to be able to tell it apart
    from a request the server did not understand.
    """
    experiments = _experiments()
    groups: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    if not selections:
        raise ValueError("at least one {factor, band} selection is required")
    for selection in selections[:MAX_SELECTIONS]:
        factor, band = resolve_selection(selection)
        label = band_label(band, factor["unitSymbol"])
        members = [row for row in experiments if _band(factor, band, row)]
        summary = _summary([row["grainYieldKgPerM2Mean"] for row in members])
        if not members:
            summary["note"] = ("no experiment in this dataset falls in this band. The band is left "
                               "empty rather than filled with a neighbouring experiment.")
        entry = {
            "label": f"{factor['label']} {label}",
            "bandLabel": label,
            "bandBounds": {"min": band["min"], "minInclusive": band["minInclusive"],
                           "max": band["max"], "maxInclusive": band["maxInclusive"],
                           "openUpper": bool(band.get("openUpper"))},
            "empty": not members,
            "factor": factor["publicName"],
            "band": band["id"],
            "unit": "kg/m2",
            # The factor's own unit, so an export can print bounds as "> 450 ppm" instead of a bare
            # number, and so a client does not have to know which factor carries which unit.
            "unitSymbol": factor["unitSymbol"],
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
            # factor and band travel with each row so an export (or a client) can tell which
            # selection an experiment belongs to without matching on the label string.
            rows.append({"label": entry["label"], "factor": factor["publicName"],
                         "band": band["id"], "experimentId": row["experimentId"],
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
            "ml/evaluation/phase30_cea_wheat_response.",
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
