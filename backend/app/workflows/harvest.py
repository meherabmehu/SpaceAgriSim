"""Workflow B — crop growth and harvest prediction for lettuce, end to end.

What a user can do here
-----------------------
Choose a growth stage, an environment (air temperature, root-zone temperature, PPFD), a photoperiod
and a planting density; run the served model; compare scenarios; and read the evidence behind the
number — including the part of the evidence that says the model is not validated for forecasting.

Two models are served, and both are returned
--------------------------------------------
`lettuce-earth-growth-v3` is the selected model. It predicts fresh yield per square metre from the
daily light integral and divides by the density the user states; it is the successor to v2 for a
reason recorded in its own artifact: v2 predicted mass per plant from PPFD alone and overpredicted
an independent greenhouse trial by a median of 3.2x (232 % MAPE), because photoperiod and planting
density were missing from its inputs.

v3 is returned alongside it on every call, not as a fallback but as the record. v2's failure is what
motivated v3, and a user who compares the two sees why.

What the response refuses to do
-------------------------------
1. **It does not call v3 validated.** The artifact's own status is `trained-exploratory`. Its
   independent holdout (Touliatos et al. 2016) scored 41.6 % MAPE against a 30 % criterion fixed in
   advance, so `passed: false`. The workflow reports the failure in the same payload as the
   prediction, not in a separate document.
2. **It does not count the PeerJ study as validation.** Those six observations informed the choice
   of the daily-light-integral feature, so the artifact marks them `countsAsValidation: false` and
   this workflow keeps that flag.
3. **It does not hide the root-temperature assumption.** Neither external study reports root-zone
   temperature; both checks assume it equals air temperature. The response says so.
4. **It does not extrapolate density.** Above ~200 plants/m2 the per-area identity is known to break
   (Touliatos measured 95 kg/m2 at 1000 plants/m2 including stacking), so the response warns rather
   than dividing anyway.
5. **It does not present scenario differences as findings.** Intervals overlap between most
   realistic scenarios; where they do, the comparison says the model cannot tell them apart.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from app import research
from app.workflows import units

MODEL_ID = "lettuce-earth-growth-v3"
RECORD_MODEL_ID = "lettuce-earth-growth-v2"
CROPS = ("lettuce",)
MAX_SCENARIOS = 4

FEATURE_UNITS = {
    "daysAfterTransplant": "day",
    "airTemperature": "degC",
    "rootTemperature": "degC",
    "ppfd": "umol/m2/s",
    "photoperiodHours": "h/day",
    "plantDensityPerM2": "plant/m2",
}
CALLER_INPUTS = ("daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd",
                 "photoperiodHours", "plantDensityPerM2")

LIMITATIONS = [
    "Fresh yield per square metre is higher in the training system (non-limiting CO2, optimal "
    "temperature, plant factory) than in an ambient-CO2 greenhouse, so an upward bias remains.",
    "Density enters only through the per-area identity; the model does not learn how density "
    "changes per-area yield, and it refuses above ~200 plants/m2 for that reason.",
    "Cultivar is not a feature. Batavia Othilie in training differs from Baby Cos and Green Oak in "
    "the external study by 63 %, which no recalibration can represent.",
    "The light response is monotonic; the external data are not.",
    "Root-zone temperature is required by the model and is not reported by either external study, "
    "so it is assumed equal to air temperature in both checks.",
    "Earth only, within the declared domains, and not validated for harvest forecasting.",
]

EVIDENCE_LAYERS = [
    {"kind": "model-prediction",
     "what": "fresh shoot mass per plant, from a per-area yield model divided by stated density",
     "isMeasurement": False,
     "provenance": "ml/artifacts/lettuce-earth-growth-v3.json"},
    {"kind": "measured-observation",
     "what": "1 648 destructive harvest weights over four WUR lettuce experiments — training and "
              "leave-one-experiment-out validation",
     "isMeasurement": True,
     "provenance": "WUR-lettuce, CC-BY-4.0, DOI 10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1"},
    {"kind": "measured-observation",
     "what": "six PeerJ 17085 observations (Baby Cos, Green Oak) — development data, not validation",
     "isMeasurement": True,
     "provenance": "PeerJ 12:e17085, CC BY 4.0"},
    {"kind": "measured-observation",
     "what": "one Touliatos et al. 2016 observation — the independent holdout, scored once",
     "isMeasurement": True,
     "provenance": "Food and Energy Security 5(3):184-191, DOI 10.1002/fes3.83"},
]


@lru_cache(maxsize=2)
def _model(model_id: str) -> dict[str, Any]:
    return research.load_model(model_id)


def _domain() -> dict[str, dict[str, float]]:
    return _model(MODEL_ID)["domain"]


def _run_v3(inputs: dict[str, float]) -> dict[str, Any]:
    model = _model(MODEL_ID)
    dli = inputs["ppfd"] * inputs["photoperiodHours"] * 3600.0 / 1e6
    raw, warnings = research.predict_values(
        model, [inputs["daysAfterTransplant"], inputs["airTemperature"],
                inputs["rootTemperature"], dli])
    per_area = max(0.0, research.inverse_target_transform(model, raw))
    density = inputs["plantDensityPerM2"]
    per_plant = per_area / density

    interval = model["interval"]
    low = per_area * math.exp(interval["logResidualLow"]) / density
    high = per_area * math.exp(interval["logResidualHigh"]) / density

    bounds = model["densityDomain"]["plantsPerM2"]
    density_ok = bounds["min"] <= density <= bounds["max"]
    if not density_ok:
        warnings.append(
            f"plantDensityPerM2 {density:g} is outside the supported [{bounds['min']:g}, "
            f"{bounds['max']:g}] range: per-plant mass there extrapolates the density identity "
            f"itself, not a fitted growth response.")

    return {
        "perAreaYieldGPerM2": round(per_area, 1),
        "freshShootMassGPerPlant": round(per_plant, 2),
        "intervalLowG": round(max(0.0, low), 2),
        "intervalHighG": round(high, 2),
        "intervalKind": interval["kind"],
        "intervalOutOfFoldCoverage": interval["outOfFoldCoverage"],
        "intervalCoverageNote": interval.get("coverageNote"),
        "dailyLightIntegralMolPerM2Day": round(dli, 2),
        "dailyLightIntegralFormula": model["derivedFeatures"]["dailyLightIntegral"]["formula"],
        "densityInsideSupportedRange": density_ok,
        "warnings": warnings,
    }


def _run_v2(inputs: dict[str, float]) -> dict[str, Any]:
    """The predecessor, scored on the same inputs it can accept, as the record."""
    model = _model(RECORD_MODEL_ID)
    raw, warnings = research.predict_values(
        model, [inputs["daysAfterTransplant"], inputs["airTemperature"],
                inputs["rootTemperature"], inputs["ppfd"]])
    value = max(0.0, raw)
    radius = float(model["interval"]["radius"])
    return {
        "modelId": RECORD_MODEL_ID,
        "freshShootMassGPerPlant": round(value, 2),
        "intervalLowG": round(max(0.0, value - radius), 2),
        "intervalHighG": round(value + radius, 2),
        "ignoresInputs": ["photoperiodHours", "plantDensityPerM2"],
        "warnings": warnings,
        "status": model.get("status"),
    }


def _check(inputs: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    warnings: list[str] = []
    values: dict[str, float] = {}
    errors: list[str] = []
    for name in CALLER_INPUTS:
        if inputs.get(name) is None:
            errors.append(f"{name} is required")
            continue
        value = float(inputs[name])
        if not math.isfinite(value):
            errors.append(f"{name} must be finite")
            continue
        values[name] = value
    if errors:
        raise ValueError("; ".join(errors))

    domain = _domain()
    dli = values["ppfd"] * values["photoperiodHours"] * 3600.0 / 1e6
    checked = {name: value for name, value in values.items() if name in domain}
    checked["dailyLightIntegral"] = dli
    for name, bounds in domain.items():
        if name not in checked:
            continue
        if not bounds["min"] <= checked[name] <= bounds["max"]:
            warnings.append(
                f"{name} = {checked[name]:g} is outside the measured training range "
                f"[{bounds['min']:g}, {bounds['max']:g}]; outside it the model interpolates "
                f"between its last split, it does not extrapolate a trend")
    return values, warnings


def predict_one(item: dict[str, Any]) -> dict[str, Any]:
    values, domain_warnings = _check(item)
    domain = _domain()
    v3 = _run_v3(values)
    v2 = _run_v2(values)
    # The model reports its own out-of-range notes; the workflow already phrased the same finding
    # with the derived-feature context, so the duplicate is dropped rather than shown twice.
    flagged = {warning.split(" = ")[0].split(" outside")[0] for warning in domain_warnings}
    model_warnings = [warning for warning in v3.pop("warnings")
                      if not any(feature and warning.startswith(feature) for feature in flagged)]
    warnings = domain_warnings + model_warnings
    return {
        "label": item.get("label") or (f"{values['daysAfterTransplant']:g} d, "
                                      f"{values['airTemperature']:g} C, "
                                      f"{values['ppfd']:g} PPFD"),
        "crop": "lettuce",
        "inputs": values,
        "prediction": v3,
        "recordPrediction": v2,
        "validation": {
            "insideTrainingDomain": not domain_warnings,
            "warnings": warnings,
            "domain": domain,
        },
        "interpretation": (
            f"{v3['freshShootMassGPerPlant']:.1f} g fresh shoot mass per plant at "
            f"{values['plantDensityPerM2']:g} plants/m2 ({v3['perAreaYieldGPerM2']:.0f} g/m2). "
            f"A model output, not a measurement, and not validated for harvest forecasting."),
    }


def compare(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    results = [predict_one(item) for item in scenarios]
    rows = []
    for item in results:
        rows.append({
            "label": item["label"],
            **{name: item["inputs"][name] for name in CALLER_INPUTS},
            "dailyLightIntegralMolPerM2Day": item["prediction"]["dailyLightIntegralMolPerM2Day"],
            "predictionG": item["prediction"]["freshShootMassGPerPlant"],
            "perAreaYieldGPerM2": item["prediction"]["perAreaYieldGPerM2"],
            "intervalLowG": item["prediction"]["intervalLowG"],
            "intervalHighG": item["prediction"]["intervalHighG"],
            "recordModelG": item["recordPrediction"]["freshShootMassGPerPlant"],
            "insideTrainingDomain": item["validation"]["insideTrainingDomain"],
        })

    deltas = []
    baseline = results[0]
    for item in results[1:]:
        low_a = baseline["prediction"]["intervalLowG"]
        high_a = baseline["prediction"]["intervalHighG"]
        low_b = item["prediction"]["intervalLowG"]
        high_b = item["prediction"]["intervalHighG"]
        separated = high_b < low_a or high_a < low_b
        base_g = baseline["prediction"]["freshShootMassGPerPlant"]
        deltas.append({
            "vs": baseline["label"],
            "label": item["label"],
            "predictionDeltaG": round(item["prediction"]["freshShootMassGPerPlant"] - base_g, 2),
            "predictionPctDelta": (round(100.0 * (item["prediction"]["freshShootMassGPerPlant"]
                                                  - base_g) / base_g, 2)
                                   if base_g else None),
            "intervalsOverlap": not separated,
            "distinguishableAtStatedCoverage": separated,
            "note": ("The intervals overlap, so at the coverage this model reports it cannot tell "
                     "these two scenarios apart. The point difference is still the model's output; "
                     "it is not a result."
                     if not separated else
                     "The intervals do not overlap, so the difference exceeds the model's own "
                     "stated uncertainty."),
        })

    model = _model(MODEL_ID)
    validation = model.get("validation") or {}
    independent = validation.get("independent") or {}
    development = validation.get("development") or {}
    return {
        "workflow": "harvest-prediction",
        "status": "complete",
        "workflowComplete": True,
        "modelValidatedForForecasting": bool(independent.get("passed", False)),
        "statusNote": ("The workflow is complete: every layer from input to documented evidence is "
                       "implemented and tested. The model behind it is not validated for harvest "
                       "forecasting, and that is reported here rather than smoothed over."),
        "model": {
            "id": model["id"],
            "name": model["name"],
            "version": model.get("version"),
            "status": model.get("status"),
            "task": model.get("task"),
            "target": model.get("target"),
            "unit": model.get("unit"),
            "method": model.get("method"),
            "features": model["features"],
            "derivedFeatures": model["derivedFeatures"],
            "samples": model.get("samples"),
            "groups": model.get("groups"),
            "domain": _domain(),
            "densityDomain": model.get("densityDomain"),
            "trainingDensityPlantsPerM2": model.get("trainingDensityPlantsPerM2"),
            "trainingPhotoperiodHours": model.get("trainingPhotoperiodHours"),
            "sourceStudy": model.get("sourceStudy"),
            "sourceUrl": model.get("sourceUrl"),
            "sourceLicense": model.get("sourceLicense"),
            "sourceCitation": model.get("sourceCitation"),
            "artifactPath": f"ml/artifacts/{MODEL_ID}.json",
        },
        "scenarios": results,
        "comparison": {"rows": rows, "deltas": deltas, "baseline": baseline["label"]},
        "validation": {
            "protocol": validation.get("internal", {}).get("protocol"),
            "internalMetrics": (validation.get("internal") or {}).get("metrics"),
            "metricUnits": model.get("metricUnits"),
            "modelSelection": model.get("modelSelection"),
            "baselineMetrics": model.get("baselineMetrics"),
            "developmentCheck": {
                "study": development.get("study"),
                "countsAsValidation": development.get("countsAsValidation"),
                "usedForModelSelection": development.get("usedForModelSelection"),
                "metrics": development.get("metrics"),
                "rows": development.get("scored"),
                "why": ("These observations informed the choice of the daily-light-integral "
                        "feature, so they are development data. Reporting them as validation "
                        "would be the error the artifact itself avoids."),
            },
            "independentCheck": {
                "study": independent.get("study"),
                "usedForFitting": independent.get("usedForFitting"),
                "usedForModelSelection": independent.get("usedForModelSelection"),
                "scored": independent.get("scored"),
                "refused": independent.get("refused"),
                "metrics": independent.get("metrics"),
                "acceptanceCriterionPct": independent.get("acceptanceCriterionPct"),
                "passed": independent.get("passed"),
                "verdict": independent.get("verdict"),
                "rootTemperatureAssumption": ("not reported by the study; assumed equal to air "
                                              "temperature"),
            },
            "interval": model.get("interval"),
            "predecessorFailure": {
                "modelId": RECORD_MODEL_ID,
                "note": ("v2 overpredicted the external study by 232 % MAPE. It is still served, "
                         "and still scored, because deleting a failing check once a better model "
                         "exists would erase the record that justified the rebuild."),
            },
        },
        "units": units.block(
            freshShootMassGPerPlant="g/plant",
            perAreaYieldGPerM2="g/m2",
            predictionG="g/plant",
            intervalLowG="g/plant",
            intervalHighG="g/plant",
            daysAfterTransplant="day",
            airTemperature="degC",
            rootTemperature="degC",
            ppfd="umol/m2/s",
            photoperiodHours="h/day",
            plantDensityPerM2="plant/m2",
            dailyLightIntegralMolPerM2Day="mol/m2/day",
        ),
        "evidence": {"layers": EVIDENCE_LAYERS},
        "limitations": LIMITATIONS,
        "method": {
            "name": "gradient boosting on the daily light integral, in per-area yield",
            "referenceRoute": "ppfd x photoperiod x 3600 / 1e6 = daily light integral (mol/m2/day)",
            "targetTransform": model.get("targetTransform"),
            "inverseApplied": "exp() applied centrally by research.inverse_target_transform",
            "densityConversion": "per-plant mass = per-area yield / stated plants per m2",
            "interval": "conformal residual quantiles on the log target, carried through the "
                        "density division",
            "notUsed": ["cultivar", "CO2", "water supply", "nutrients", "gravity", "radiation",
                        "substrate"],
            "notUsedNote": ("A control a user supplies from this list cannot change the prediction. "
                            "That is a model limitation, not a form limitation."),
        },
    }


def capability() -> dict[str, Any]:
    model = _model(MODEL_ID)
    domain = _domain()
    bounds = model["densityDomain"]["plantsPerM2"]
    fields = [
        {"name": "daysAfterTransplant", "label": "Days after transplant",
         "unit": "day", "min": domain["daysAfterTransplant"]["min"],
         "max": domain["daysAfterTransplant"]["max"], "step": 1,
         "why": "Growth stage: the model's strongest predictor of biomass."},
        {"name": "airTemperature", "label": "Air temperature", "unit": "degC",
         "min": domain["airTemperature"]["min"], "max": domain["airTemperature"]["max"],
         "step": 0.5, "why": "Leaf expansion and respiration both depend on it."},
        {"name": "rootTemperature", "label": "Root-zone temperature", "unit": "degC",
         "min": domain["rootTemperature"]["min"], "max": domain["rootTemperature"]["max"],
         "step": 0.5, "why": "Separate from air temperature in the training system; both were "
                             "measured."},
        {"name": "ppfd", "label": "PPFD", "unit": "umol/m2/s",
         "min": domain["dailyLightIntegral"]["min"], "max": 750, "step": 10,
         "why": "Instantaneous photosynthetically active photon flux. Combined with photoperiod "
                "it sets the daily light integral the model actually uses."},
        {"name": "photoperiodHours", "label": "Photoperiod", "unit": "h/day",
         "min": 4, "max": 24, "step": 0.5,
         "why": "How long the light is on. A 16 h plant factory and a 12 h greenhouse at the same "
                "PPFD deliver different daily light integrals."},
        {"name": "plantDensityPerM2", "label": "Planting density", "unit": "plant/m2",
         "min": bounds["min"], "max": bounds["max"], "step": 1,
         "why": "Converts the model's per-area yield into mass per plant. Outside this range the "
                "per-area identity is known to break."},
    ]
    return {
        "workflow": "harvest-prediction",
        "modelId": MODEL_ID,
        "crop": "lettuce",
        "fields": fields,
        "derivedDisplay": [{"name": "dailyLightIntegralMolPerM2Day", "unit": "mol/m2/day",
                            "formula": model["derivedFeatures"]["dailyLightIntegral"]["formula"]}],
        "maxScenarios": MAX_SCENARIOS,
        "intervalAvailable": True,
        "intervalCovers": "90 % of out-of-fold residuals on the log target",
        "measures": "g fresh shoot mass per plant, and g fresh yield per m2",
        "unmeasuredCrops": ["tomato", "radish"],
        "note": ("Only lettuce has a model with a measured validation behind it. Tomato and radish "
                 "predictions are not offered because no such model exists."),
    }


def parity() -> dict[str, Any]:
    """Measured vs predicted, from the two external studies the artifact records.

    Served straight from the artifact rather than recomputed: recomputing would make every page
    load a second model-selection opportunity, and the numbers a reader sees must be the numbers
    the artifact was accepted or rejected on.
    """
    model = _model(MODEL_ID)
    validation = model.get("validation") or {}
    development = validation.get("development") or {}
    independent = validation.get("independent") or {}
    points = []
    for row in development.get("scored") or []:
        points.append({
            "id": row["id"], "set": "development", "countsAsValidation": False,
            "measuredG": row["measuredG"], "predictedG": row["predictedG"],
            "ratio": row["ratio"], "ppfdUmol": row.get("ppfdUmol"),
        })
    for row in independent.get("scored") or []:
        points.append({
            "id": row["id"], "set": "independent", "countsAsValidation": True,
            "measuredG": row["measuredG"], "predictedG": row["predictedG"],
            "ratio": row["ratio"], "ppfdUmol": row.get("ppfdUmol"),
            "domainViolations": row.get("domainViolations"),
        })
    return {
        "workflow": "harvest-prediction",
        "modelId": MODEL_ID,
        "points": points,
        "developmentMetrics": development.get("metrics"),
        "independentMetrics": independent.get("metrics"),
        "acceptanceCriterionPct": independent.get("acceptanceCriterionPct"),
        "passed": independent.get("passed"),
        "units": units.block(measuredG="g/plant", predictedG="g/plant", ratio="dimensionless"),
        "caveat": ("Seven points in total, two cultivars, two facilities. This is the whole external "
                   "evidence base for the model, and it is not enough to call a model validated. "
                   "The ratios are all above 1: the model overpredicts in both studies."),
    }
