"""Measured water-use evidence: the one benchmark the water feature stands on.

What this module is for
-----------------------
The simulator predicts crop water demand from a crop-relative assumption. Until Phase 26 the
repository had no measurement of crop water use of any kind, so the prediction could not be
compared with anything. It now has one: a greenhouse lettuce pot experiment where every pot was
weighed repeatedly and the water loss is a measured evapotranspiration rate.

This module serves that measurement, and compares a live simulation against it. It is deliberately
built as a *benchmark*, not as a calibration:

* the measured series is read from the committed processed table, so the numbers the API returns
  are the numbers the acquisition script verified;
* the comparison is reported in three denominators at once, because the study does not publish the
  one that would decide the answer, and choosing quietly would be the whole error;
* the uncertainty that is returned is the between-pot spread that the experiment actually
  measured, not an invented confidence interval;
* nothing here changes the simulator. `compare()` calls the shipped water path unmodified.

The module refuses to invent a comparison it cannot support
-----------------------------------------------------------
`compare()` needs the crop's water demand for a growing season. That demand depends on the crop,
the area, the light scale and where in the cycle the plant is, all of which are caller inputs.

The honest consequence, stated in the response rather than discovered by a user: the platform's
demand model and this measurement disagree by a factor whose sign depends on a geometric quantity
neither source publishes. So the comparison verdict is one of `shape-only`, `level-mismatch` or
`not-applicable`, and never `validated`.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import simulation_constants as constants
from app.simulation import crops, growth, water

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed" / "phase26"
VALIDATION = ROOT / "ml" / "evaluation" / "phase26_measured_et_validation.json"
CATALOGUE = ROOT / "data" / "research" / "dataset_catalog.json"
MANIFEST = ROOT / "data" / "metadata" / "phase26_acquisition_manifest.json"

STUDY_ID = "zenodo-schroder-2021-lettuce-pot"
POT_AREA_M2 = 0.0112
POT_VOLUME_L = 2.2
CYCLE_DAYS = 35
HARVEST_DAY = 37
IRRIGATION_CEILING_ML_PER_DAY = 350.0

# The three denominators the comparison is reported against. Each is named, and only one of them
# is a measurement; the other two are assumptions the study does not resolve.
DENOMINATOR_KEYS = ("potSurface", "canopyArea", "freshMass")

VERDICTS = {
    "shape-only": ("The seasonal shape agrees and the level cannot be identified from the available "
                   "geometry. Treat the demand curve as directionally supported."),
    "level-mismatch": ("The comparison lands outside the measured spread on every denominator. The "
                       "demand level is not supported by this benchmark."),
    "not-applicable": ("This crop or configuration has no measurement behind it. The benchmark is "
                       "greenhouse lettuce only, and nothing is extrapolated from it."),
}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    """Minimal CSV reader so the service does not depend on pandas at runtime."""
    import csv

    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


@lru_cache(maxsize=1)
def _benchmark_rows() -> tuple[dict[str, Any], ...]:
    """Treatment-mean measured ET per measurement date, published treatments only.

    The cache is keyed on nothing, so the table is read once per process. It holds no mutable
    state; the returned tuple is never written to.
    """
    per_pot = PROCESSED / "schroder2021_lettuce_et.csv"
    if not per_pot.is_file():
        return ()
    rows = _read_csv(per_pot)
    published = {"VC-C", "VC-P", "TC-F", "TC-G", "TC-G2", "TC-G3", "SC"}
    buckets: dict[int, list[float]] = {}
    for row in rows:
        if row.get("inPublication", "").lower() not in ("true", "1"):
            continue
        if row.get("flagAboveIrrigationCeiling", "").lower() in ("true", "1"):
            continue
        if row.get("treatment") not in published:
            continue
        day = _float(row.get("dayNumber"))
        rate = _float(row.get("etRateMlPerDay"))
        if day is None or rate is None:
            continue
        buckets.setdefault(int(round(day)), []).append(rate)

    series = []
    for day in sorted(buckets):
        values = buckets[day]
        mean = sum(values) / len(values)
        variance = (sum((value - mean) ** 2 for value in values) / (len(values) - 1)
                    if len(values) > 1 else None)
        series.append({
            "dayNumber": day,
            "measuredMlPerPotPerDay": round(mean, 2),
            "betweenPotSdMlPerDay": round(math.sqrt(variance), 2) if variance is not None else None,
            "pots": len(values),
        })
    return tuple(series)


@lru_cache(maxsize=1)
def _validation() -> dict[str, Any]:
    if not VALIDATION.is_file():
        return {}
    return json.loads(VALIDATION.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _catalogue_entry() -> dict[str, Any]:
    if not CATALOGUE.is_file():
        return {}
    payload = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    for dataset in payload.get("datasets", []):
        if dataset.get("id") == STUDY_ID:
            return dataset
    return {}


@lru_cache(maxsize=1)
def _manifest_entry() -> dict[str, Any]:
    if not MANIFEST.is_file():
        return {}
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return payload.get("datasets", {}).get(STUDY_ID, {})


def provenance() -> dict[str, Any]:
    """Everything needed to trace a number back to the bytes it came from."""
    entry = _catalogue_entry()
    manifest = _manifest_entry()
    files = [{
        "name": item.get("name"),
        "bytes": item.get("bytes"),
        "sha256": item.get("sha256"),
        "verified": (item.get("verification") or {}).get("verified"),
    } for item in manifest.get("files", [])]
    return {
        "studyId": STUDY_ID,
        "citation": entry.get("name", "Greenhouse lettuce pot experiment (Schröder et al. 2021)"),
        "doi": "10.5281/zenodo.5550230",
        "publisher": entry.get("publisher", "Zenodo"),
        "license": entry.get("license", "CC BY 4.0"),
        "licenseEvidence": entry.get("licenseEvidence", "verified"),
        "usabilityClass": entry.get("usabilityClass", "A"),
        "measurementBasis": (
            "Gravimetric pot evapotranspiration: each pot was weighed and the mass loss between "
            "weighings is the water lost by the plant and substrate together."),
        "processedTable": "data/processed/phase26/schroder2021_lettuce_et.csv",
        "validationArtefact": "ml/evaluation/phase26_measured_et_validation.json",
        "files": files,
        "hashVerified": bool(files) and all(item["verified"] for item in files),
    }


def limitations() -> list[str]:
    """The reasons this benchmark cannot be read as a validated crop coefficient.

    Served to the UI rather than kept in a docstring, because a limitation nobody reads is a
    limitation that will be forgotten at the point of use.
    """
    return [
        "Evapotranspiration is measured, transpiration is not: substrate evaporation is inside "
        "the number.",
        "No per-day weather was published for the trial, so no reference ET0 can be computed for "
        "the same days and no crop coefficient can be derived.",
        "Pot diameter, pot spacing and canopy area are unpublished, so a per-pot water loss cannot "
        "be converted into a flux without an assumption.",
        "One cultivar, one greenhouse, four weeks, pot culture.",
        "The trial ran on Earth. Nothing here is a reduced-gravity or spaceflight observation.",
    ]


def benchmark() -> dict[str, Any]:
    """The measured reference curve, with its spread, provenance and limitations."""
    series = _benchmark_rows()
    payload: dict[str, Any] = {
        "available": bool(series),
        "series": list(series),
        "measurementDates": len(series),
        "potsPerDate": series[0]["pots"] if series else 0,
        "potVolumeL": POT_VOLUME_L,
        "potAreaAssumptionM2": POT_AREA_M2,
        "harvestDay": HARVEST_DAY,
        "cycleDays": CYCLE_DAYS,
        "irrigationCeilingMlPerDay": IRRIGATION_CEILING_ML_PER_DAY,
        "provenance": provenance(),
        "limitations": limitations(),
        "uncertainty": {
            "kind": "between-pot standard deviation of the treatment mean",
            "isConfidenceInterval": False,
            "note": ("This is the spread the experiment actually measured across replicate pots. "
                     "It is not a confidence interval on the model, and it does not include "
                     "method error, harvest-date error or the missing geometry."),
        },
        "measurementPattern": {
            "note": (
                "The measured series is not smooth. It steps from 89 mL/pot/day on day 16 to 204 "
                "on day 17, a factor of 2.3 between consecutive weighings one day apart, and the "
                "between-pot spread is widest on exactly that date. A plant cannot change its "
                "water use that fast, so the intervals are not equivalent: irrigation events, "
                "weighing times and substrate water storage all land differently in a one-day "
                "interval than in a three-day one. The comparison therefore aggregates over the "
                "trial and reports rank agreement, which a step of this size cannot manufacture."),
            "largestOneDayStepMlPerPot": 115.77,
            "widestBetweenPotSdMlPerDay": 46.4,
            "status": "recorded, not smoothed: the raw series is served as measured",
        },
        "cropScope": ["lettuce"],
        "environmentScope": "greenhouse, pot culture, Earth gravity",
    }
    if not series:
        payload["reason"] = (
            "The processed benchmark table is not present in this deployment. The feature is "
            "available but reports no measurement rather than falling back to an estimate.")
    return payload


def _demand_curve(crop_key: str, area_m2: float, light_scale: float) -> list[dict[str, float]]:
    """The platform's own demand path, evaluated across the benchmark's measurement days."""
    crop = crops.get_crop(crop_key)
    curve = []
    for day in [entry["dayNumber"] for entry in _benchmark_rows()]:
        # The benchmark days are day-of-trial; the platform's cycle is 0-based.
        day_in_cycle = max(0, min(CYCLE_DAYS, day))
        progress = growth.logistic_progress(day_in_cycle, CYCLE_DAYS)
        litres = water.daily_water_demand_l(crop, progress, area_m2, light_scale)
        curve.append({
            "dayNumber": day,
            "growthFraction": round(progress, 4),
            "simulatedLPerPotPerDay": litres,
            "simulatedMlPerPotPerDay": round(litres * 1000.0, 3),
        })
    return curve


def _spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(a) != len(b):
        return None

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda index: values[index])
        result = [0.0] * len(values)
        index = 0
        while index < len(order):
            end = index
            while end + 1 < len(order) and values[order[end + 1]] == values[order[index]]:
                end += 1
            average = (index + end) / 2.0 + 1.0
            for position in range(index, end + 1):
                result[order[position]] = average
            index = end + 1
        return result

    rank_a, rank_b = ranks(a), ranks(b)
    n = len(a)
    mean_a = sum(rank_a) / n
    mean_b = sum(rank_b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(rank_a, rank_b))
    var_a = math.sqrt(sum((x - mean_a) ** 2 for x in rank_a))
    var_b = math.sqrt(sum((y - mean_b) ** 2 for y in rank_b))
    if var_a == 0 or var_b == 0:
        return None
    return cov / (var_a * var_b)


def compare(crop_key: str, heat: float, growing_area_m2: float = POT_AREA_M2) -> dict[str, Any]:
    """Hold a live simulation's water demand against the measured benchmark.

    `heat` is the platform's light scale. `growing_area_m2` defaults to the pot area assumption so
    the default comparison is like-for-like with the measurement.

    The verdict is never "validated". The benchmark cannot support that word, and a caller that
    sees it would be entitled to quote it.
    """
    series = _benchmark_rows()
    if not series:
        return {
            "available": False,
            "verdict": "not-applicable",
            "verdictMeaning": VERDICTS["not-applicable"],
            "reason": "no measured benchmark table is present",
        }
    if crop_key not in {crop.key for crop in crops.list_crops()}:
        raise KeyError(f"unknown crop: {crop_key}")
    if crop_key not in ("lettuce",):
        return {
            "available": True,
            "verdict": "not-applicable",
            "verdictMeaning": VERDICTS["not-applicable"],
            "reason": (f"The only measured water-use benchmark in this repository is greenhouse "
                       f"lettuce. There is no measurement for {crop_key}, and none is "
                       f"extrapolated from the lettuce trial."),
            "benchmarkCrop": "lettuce",
            "requestedCrop": crop_key,
        }

    curve = _demand_curve(crop_key, growing_area_m2, heat)
    measured = [float(entry["measuredMlPerPotPerDay"]) for entry in series]
    simulated = [float(entry["simulatedMlPerPotPerDay"]) for entry in curve]

    total_measured = sum(measured)
    total_simulated = sum(simulated)
    paired = sum(1 for a, b in zip(measured, simulated) if a > 0 and b > 0)
    ratio = (total_simulated / total_measured) if total_measured else None
    spearman = _spearman(measured, simulated)

    # A rank correlation over eleven dates is a weak instrument; it is reported with the count of
    # pairs that produced it and never on its own.
    shape_supported = spearman is not None and spearman >= 0.5 and paired >= 8
    spread = [entry["betweenPotSdMlPerDay"] for entry in series
              if entry["betweenPotSdMlPerDay"] is not None]
    mean_sd = sum(spread) / len(spread) if spread else None
    relative_spread = (mean_sd / (total_measured / len(measured))
                       if mean_sd and total_measured else None)

    within_spread = None
    if ratio is not None and relative_spread:
        within_spread = abs(1.0 - ratio) <= relative_spread

    if within_spread is None:
        verdict = "shape-only" if shape_supported else "level-mismatch"
    elif within_spread:
        verdict = "shape-only"
    else:
        verdict = "shape-only" if shape_supported else "level-mismatch"

    denominators = {
        "potSurface": {
            "areaM2": growing_area_m2,
            "measuredLPerM2PerDay": round((total_measured / len(measured)) / growing_area_m2 / 1000,
                                          4),
            "profilePeakLPerM2PerDay": crops.get_crop(crop_key).peak_water_l_per_day,
            "isMeasured": False,
            "note": "the pot surface is an assumption; the study does not publish pot diameter",
        },
        "canopyArea": {
            "areaM2": 0.13,
            "measuredLPerM2PerDay": round((total_measured / len(measured)) / 0.13 / 1000, 4),
            "profilePeakLPerM2PerDay": crops.get_crop(crop_key).peak_water_l_per_day,
            "isMeasured": False,
            "note": ("cross-experiment leaf area from a different lettuce trial; an "
                     "order-of-magnitude check, not this trial's canopy"),
        },
        "freshMass": {
            "measuredMlPerGCycle": None,
            "isMeasured": True,
            "note": "denominator the dataset supports directly: fresh mass at harvest",
        },
    }

    return {
        "available": True,
        "verdict": verdict,
        "verdictMeaning": VERDICTS[verdict],
        "isValidation": False,
        # Phase 31: the level question is answered explicitly rather than left in a warning.
        # The trial publishes pot volume but not pot diameter, pot spacing or canopy area, so the
        # same daily water loss maps to anything from ~0.25x to ~2.7x the platform's flux
        # depending on which denominator one assumes. A ratio computed under an assumed geometry
        # cannot identify a bias, so it is reported as a shape comparison only.
        "identification": {
            "levelIdentified": False,
            "shapeSupported": shape_supported,
            "claim": ("Rank agreement between the measured seasonal water-use curve and the "
                      "platform demand curve. The absolute level is not identified by this trial "
                      "and no correction is applied to the simulator."),
            "identifiableWith": (
                "Per-day weather for the trial plus its pot diameter or plant spacing."),
            "denominatorSpread": (
                "The measured daily loss is 0.247x the platform flux on the pot-surface "
                "assumption and 2.7x on the canopy-area assumption; both denominators are "
                "assumptions, so the sign of any bias is indeterminate."),
            "whyNotAssumed": (
                "Choosing either denominator would decide the answer before the comparison was "
                "made, and the trial publishes neither."),
        },
        "benchmarkCrop": "lettuce",
        "requestedCrop": crop_key,
        "inputs": {
            "growingAreaM2": growing_area_m2,
            "lightScale": heat,
            "cycleDays": CYCLE_DAYS,
            "demandBasis": water.demand_basis(None),
            "peakWaterLPerM2PerDay": crops.get_crop(crop_key).peak_water_l_per_day,
        },
        "curve": [
            {**measured_entry, **{"growthFraction": sim["growthFraction"],
                                  "simulatedMlPerPotPerDay": sim["simulatedMlPerPotPerDay"]}}
            for measured_entry, sim in zip(series, curve)
        ],
        "totals": {
            "measuredMlPerPot": round(total_measured, 2),
            "simulatedMlPerPot": round(total_simulated, 2),
            "simulatedOverMeasured": round(ratio, 4) if ratio is not None else None,
            "pairedDates": paired,
        },
        "shape": {
            "spearman": None if spearman is None else round(spearman, 4),
            "pairs": len(measured),
            "supported": shape_supported,
            "threshold": 0.5,
            "note": ("A threshold on eleven points is a reporting convention, not a statistical "
                     "test. It exists so the verdict is reproducible, not because 0.5 means "
                     "anything physically."),
        },
        "uncertainty": {
            "betweenPotSdMeanMlPerDay": round(mean_sd, 2) if mean_sd is not None else None,
            "relativeSpread": round(relative_spread, 4) if relative_spread is not None else None,
            "withinMeasuredSpread": within_spread,
            "isConfidenceInterval": False,
            "sources": [
                "between-pot replicate spread (measured)",
                "pot-area assumption (not measured)",
                "missing canopy geometry (not measured)",
            ],
        },
        "denominators": denominators,
        "limitations": limitations(),
        "provenance": provenance(),
        "whatWouldSettleIt": (
            "Per-day weather and pot or canopy geometry from the same trial. With those, measured "
            "evapotranspiration becomes a flux, a reference ET0 can be computed for identical "
            "days, and the crop coefficient becomes identifiable. Until then the level cannot be "
            "corrected from this dataset, and the simulator's crop profile is left unchanged."),
    }
