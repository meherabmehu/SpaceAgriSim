"""Workflow A — water demand and irrigation intelligence, end to end.

What a user can do here
-----------------------
Supply a crop, a growing area, a growth stage and a set of climate observations, and get:

  * a reference ET0 computed by FAO-56 Penman-Monteith (or Hargreaves when radiation or wind is
    missing), with the method named and the terms broken out;
  * the crop's daily water demand under **both** of the platform's equations, side by side,
    because they disagree and the disagreement is a finding rather than a bug to hide;
  * the same demand normalised per unit area, per plant and over the whole cycle;
  * the measured greenhouse lettuce trial held against it, with its three candidate denominators;
  * a scenario comparison when more than one climate/growth-stage set is supplied;
  * a `units` map so a chart can label itself without parsing prose.

What it refuses
---------------
  * It never calls an ET0 a measurement of a crop's water use. ET0 is a computed standard for a
    reference grass surface; the crop coefficient turns it into a crop estimate; the measured bench
    is separate and is labelled as measured.
  * It never returns a single demand number without saying which equation produced it.
  * It never extrapolates the measurement. The lettuce trial is greenhouse lettuce only; a tomato
    or radish request gets the computed demand and an explicit "no measurement for this crop".
  * It never invents an uncertainty it cannot estimate. Where nothing is known, the field says so.

The two equations, and why both are returned
--------------------------------------------
`crop-relative` is the simulator's own assumption: peak litres per m2 at full canopy, scaled by
canopy cover and a light multiplier. `et0-reference` is the FAO-56 route: a physical reference flux
multiplied by a crop coefficient. They answer the same question from different evidence and differ
by a large factor. Returning only the one the caller happened to request would hide the platform's
largest unexplained internal difference, so both are computed on every call and the response states
that they are unarbitrated.
"""

from __future__ import annotations

import math
from typing import Any

from app import et0 as et0_service
from app.config import simulation_constants as constants
from app.simulation import crops, growth, irrigation, water
from app.workflows import units

SUPPORTED_CROPS = ("lettuce", "tomato", "radish")

# The measured bench is greenhouse lettuce only. Named once, used everywhere, so the day a second
# measured dataset arrives there is one place to change rather than a search for the string.
MEASURED_CROP = "lettuce"
MEASURED_STUDY = {
    "studyId": "zenodo-schroder-2021-lettuce-pot",
    "citation": ("Schröder C, Häfner F, Larsen OC, Krause A (2021). Urban Organic Waste for Urban "
                 "Farming: Growing Lettuce Using Vermicompost and Thermophilic Compost. Agronomy "
                 "11(6):1175"),
    "doi": "10.5281/zenodo.5550230",
    "license": "CC BY 4.0",
    "measurementBasis": ("gravimetric pot evapotranspiration: pots weighed repeatedly, mass loss "
                         "is plant plus substrate water loss"),
    "environment": "greenhouse, pot culture, Earth gravity",
    "measurementDates": 11,
}

# FAO-56 Table 11/12 style crop coefficients. These are NOT fitted here and NOT derived from the
# repository's own data: they are the standard's tabulated values for the leafy/garden-fruit groups,
# and the response says so. Kc = 1.0 remains the reference-surface default.
KC_SOURCES = {
    "lettuce": {"kc": 1.00, "source": "FAO-56 tabulated leafy-vegetable mid-season range 0.95-1.05",
                "note": "the platform's default of 1.0 is the reference surface, not this crop"},
    "tomato": {"kc": 1.05, "source": "FAO-56 tabulated garden-fruit mid-season range 1.00-1.15",
               "note": "field tomato; no controlled-environment coefficient is published"},
    "radish": {"kc": 0.90, "source": "FAO-56 tabulated root-vegetable mid-season range 0.85-0.95",
               "note": "field radish; no controlled-environment coefficient is published"},
}

LIMITATIONS = [
    ("Reference ET0 is a computed standard for a hypothetical reference grass surface, not a "
     "measurement of any crop's water use."),
    ("The crop coefficient converts that reference into a crop estimate. The one shipped default "
     "(1.0) describes the reference surface, not a crop; the per-crop values returned here are "
     "FAO-56 tabulated field values, not controlled-environment measurements."),
    ("The crop-relative and ET0-reference equations differ substantially and nothing in this "
     "repository arbitrates between them. Both are returned; neither is presented as correct."),
    ("The only measured water use in this repository is greenhouse lettuce in 2.2 L pots on Earth. "
     "No tomato or radish measurement exists, and none is extrapolated."),
    ("Daily demand is reported for the growth stage supplied. The platform's growth curve is a "
     "logistic assumption, so the stage itself is a modelled quantity unless the user supplies "
     "a measured canopy cover."),
    ("The irrigation schedule repeats the supplied single-day climate across the remaining cycle "
     "and models no rain, runoff, capillary rise or pump losses. It is a reference calculation "
     "with a storage term, not a weather forecast."),
    ("A transpiration deficit is reported as a deficit. It is not converted into a yield loss, "
     "because that conversion needs a crop yield-response factor this repository does not hold."),
]


def _growth_fraction(days_after_transplant: float, crop_key: str) -> float:
    """Canopy cover on the platform's own logistic curve, clamped to the cycle."""
    cycle = crops.get_crop(crop_key).growth_duration_days
    day = max(0.0, min(float(cycle), days_after_transplant))
    return growth.logistic_progress(int(round(day)), cycle)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def scenario(scenario_input: dict[str, Any]) -> dict[str, Any]:
    """Run one scenario. Pure function of its inputs plus the shipped code."""
    crop_key = scenario_input["crop"]
    if crop_key not in SUPPORTED_CROPS:
        raise KeyError(f"unsupported crop: {crop_key}")
    crop = crops.get_crop(crop_key)

    area_m2 = float(scenario_input["growingAreaM2"])
    day = float(scenario_input["daysAfterTransplant"])
    cycle = crop.growth_duration_days
    cover = _growth_fraction(day, crop_key)

    # ---- reference ET0 ----------------------------------------------------------------
    et0_result = et0_service.estimate(
        tmax_c=float(scenario_input["tmaxC"]),
        tmin_c=float(scenario_input["tminC"]),
        day_of_year=int(scenario_input["dayOfYear"]),
        latitude=float(scenario_input["latitude"]),
        elevation_m=float(scenario_input["elevationM"]),
        relative_humidity_pct=float(scenario_input["relativeHumidityPct"]),
        solar_radiation_mj=scenario_input.get("solarRadiationMJm2"),
        wind_speed_ms=scenario_input.get("windSpeedMs"),
    )
    et0_mm = float(et0_result["et0MmPerDay"])

    # ---- the two demand equations ------------------------------------------------------
    kc = float(scenario_input.get("cropCoefficient") or KC_SOURCES[crop_key]["kc"])
    reference_l = water.et0_reference_demand_l(et0_mm, kc, cover, area_m2)
    relative_l = water.daily_water_demand_l(crop, cover, area_m2, 1.0)

    # ---- normalisations ----------------------------------------------------------------
    per_m2_mm = (reference_l / area_m2) if area_m2 else 0.0  # L per m2 == mm
    # Plants per m2 is not published for any crop profile, so per-plant figures are opt-in.
    density = scenario_input.get("plantsPerM2")
    per_plant_l = (reference_l / (density * area_m2)) if density else None

    days_remaining = max(0, int(math.ceil(cycle - day)))
    cycle_reference_l = sum(
        water.et0_reference_demand_l(
            et0_mm, kc, _growth_fraction(d + 1, crop_key), area_m2)
        for d in range(int(day), int(cycle)))

    return {
        "label": scenario_input.get("label") or f"{crop_key} day {day:g}",
        "inputs": {
            "crop": crop_key,
            "cropName": crop.name,
            "daysAfterTransplant": day,
            "daysRemainingInCycle": days_remaining,
            "cycleLengthDays": cycle,
            "growthFraction": round(cover, 4),
            "growingAreaM2": area_m2,
            "tmaxC": float(scenario_input["tmaxC"]),
            "tminC": float(scenario_input["tminC"]),
            "relativeHumidityPct": float(scenario_input["relativeHumidityPct"]),
            "solarRadiationMJm2": scenario_input.get("solarRadiationMJm2"),
            "windSpeedMs": scenario_input.get("windSpeedMs"),
            "dayOfYear": int(scenario_input["dayOfYear"]),
            "latitude": float(scenario_input["latitude"]),
            "elevationM": float(scenario_input["elevationM"]),
            "plantsPerM2": density,
            "cropCoefficient": kc,
        },
        "et0": {
            "valueMmPerDay": et0_mm,
            "primaryMethod": et0_result["primaryMethod"],
            "methods": et0_result["methods"],
            "terms": {
                "radiationMm": (et0_result["methods"]["penmanMonteith"] or {}).get(
                    "radiationTermMm"),
                "aerodynamicMm": (et0_result["methods"]["penmanMonteith"] or {}).get("aeroTermMm"),
                "vpdKpa": (et0_result["methods"]["penmanMonteith"] or {}).get("vpdKpa"),
            },
            "evidenceClass": et0_result["evidenceClass"],
            "limitations": et0_result["limitations"],
        },
        "demand": {
            "et0Reference": {
                "litresPerDay": round(reference_l, 3),
                "mmPerDay": round(per_m2_mm, 3),
                "litresPerPlantPerDay": (round(per_plant_l, 4)
                                         if per_plant_l is not None else None),
                "litresRemainingCycle": round(cycle_reference_l, 2),
                "equation": "et0_mm_per_day x kc x area_m2 x canopyScale",
                "canopyScale": round(water.canopy_scale(cover), 4),
                "canopyScaleFormula": ("SEEDLING_ACTIVITY_FRACTION + (1 - SEEDLING_ACTIVITY_FRACTION) "
                                       "x growthFraction"),
                "cropCoefficient": kc,
                "cropCoefficientSource": KC_SOURCES[crop_key]["source"],
            },
            "cropRelative": {
                "litresPerDay": round(relative_l, 3),
                "mmPerDay": round((relative_l / area_m2) if area_m2 else 0.0, 3),
                "equation": "peak_water_l_per_m2 x area_m2 x lightScale x canopyScale",
                "peakWaterLPerM2PerDay": crop.peak_water_l_per_day,
                "lightScale": 1.0,
            },
            "agreement": {
                "cropRelativeOverEt0Reference": (round(relative_l / reference_l, 4)
                                                 if reference_l else None),
                "arbitrated": False,
                "note": ("The two equations disagree and nothing arbitrates between them. The "
                         "measured lettuce bench cannot settle it either: see measuredBench."),
            },
            "basis": water.demand_basis(et0_mm),
            "climateSensitivity": {
                "et0ReferenceRespondsToClimate": True,
                "cropRelativeRespondsToClimate": False,
                "note": ("Worth seeing before comparing scenarios: the crop-relative equation takes "
                         "no climate input at all. It is the crop profile scaled by canopy cover "
                         "and a light multiplier, so two scenarios that differ only in temperature, "
                         "humidity, radiation or wind produce an identical crop-relative number. "
                         "Only the ET0-reference path responds to the weather you supply."),
            },
        },
        "irrigationSchedule": _irrigation_block(scenario_input, crop_key, cover, kc, et0_mm,
                                                area_m2, day),
        "measuredBench": _measured_bench(crop_key, et0_mm, cover, area_m2, reference_l),
    }


def _measured_bench(crop_key: str, et0_mm: float, cover: float, area_m2: float,
                    reference_l: float) -> dict[str, Any]:
    """The measured trial, held against this scenario where the comparison is meaningful."""
    from app import water_evidence  # local import keeps module import order simple

    payload: dict[str, Any] = {
        "available": True,
        "applies": crop_key == MEASURED_CROP,
        "study": MEASURED_STUDY,
    }
    if crop_key != MEASURED_CROP:
        payload.update({
            "applies": False,
            "reason": (f"The only measured water-use dataset in this repository is greenhouse "
                       f"lettuce. There is no measurement for {crop_key}, and none is "
                       f"extrapolated from the lettuce trial."),
            "measuredMlPerPotPerDay": None,
        })
        return payload

    bench = water_evidence.benchmark()
    if not bench.get("available"):
        payload.update({"available": False,
                        "reason": "the measured benchmark table is not present in this deployment"})
        return payload

    series = bench["series"]
    measured_mean = sum(entry["measuredMlPerPotPerDay"] for entry in series) / len(series)
    measured_peak = max(entry["measuredMlPerPotPerDay"] for entry in series)
    pot_area = bench["potAreaAssumptionM2"]

    payload.update({
        "measuredMlPerPotPerDay": round(measured_mean, 2),
        "measuredPeakMlPerPotPerDay": round(measured_peak, 2),
        "measuredDates": bench["measurementDates"],
        "measuredLPerM2PerDay": round(measured_mean / pot_area / 1000.0, 3),
        "scenarioLPerM2PerDay": round((reference_l / area_m2) if area_m2 else 0.0, 3),
        "potAreaAssumptionM2": pot_area,
        "comparisonCaveat": (
            "The trial's pot surface area is not published, so its flux rests on an assumption. "
            "On a pot-surface denominator the measured water use is far above this scenario's "
            "reference flux; on a canopy-area denominator it is far below. The sign of the "
            "discrepancy depends on geometry the study does not report, which is why this "
            "benchmark cannot calibrate the model and is shown as a bound on interpretation "
            "rather than a correction."),
        "measurementPattern": bench.get("measurementPattern"),
        "limitations": bench.get("limitations"),
        "provenance": bench.get("provenance"),
        "hashVerified": (bench.get("provenance") or {}).get("hashVerified"),
    })
    return payload


def _irrigation_block(scenario_input: dict[str, Any], crop_key: str, cover: float,
                      kc: float, et0_mm: float, area_m2: float, day: float) -> dict[str, Any]:
    """The FAO-56 soil water balance, when the caller supplies the soil it needs.

    This is the improvement Phase 29 makes to this workflow: a daily demand figure answers "how much
    does the canopy want today", and this answers "how often, how much, and how many days short".
    It is a reference calculation, not a measurement, and it says so.
    """
    taw = scenario_input.get("totalAvailableWaterMm")
    if taw is None:
        return {
            "available": False,
            "reason": ("supply totalAvailableWaterMm to run the FAO-56 soil water balance; without "
                       "a root-zone storage term an irrigation schedule cannot be computed"),
            "isReferenceCalculation": True,
        }
    crop = crops.get_crop(crop_key)
    cycle = crop.growth_duration_days
    days = int(max(0, math.ceil(cycle - day)))
    if days == 0:
        return {"available": False, "reason": "the crop is at the end of its cycle",
                "isReferenceCalculation": True}

    daily_et0 = [et0_mm] * days
    canopy = [water.canopy_scale(_growth_fraction(day + offset, crop_key))
              for offset in range(days)]
    result = irrigation.simulate(
        crop_key=crop_key,
        daily_et0_mm=daily_et0,
        canopy_fractions=canopy,
        crop_coefficient=kc,
        growing_area_m2=area_m2,
        total_available_water_mm=float(taw),
        initial_depletion_mm=float(scenario_input.get("initialDepletionMm") or 0.0),
        irrigation_amount_mm=float(scenario_input.get("irrigationAmountMm") or 0.0),
        irrigation_interval_days=int(scenario_input.get("irrigationIntervalDays") or 1),
    )
    requirement = irrigation.irrigation_requirement_mm(daily_et0, canopy, kc)
    first = result.daily[0] if result.daily else {}
    return {
        "available": True,
        "isReferenceCalculation": True,
        "isMeasurement": False,
        "method": "FAO-56 soil water balance (eq. 84-85) with a tabulated depletion fraction",
        "assumptions": {
            "climateHeldConstant": ("the supplied single-day climate is repeated over the remaining "
                                    "cycle; supplying a daily weather series is a Phase 30 "
                                    "candidate, and this response does not pretend to have one"),
            "noRain": "controlled environment: no rain, runoff, capillary rise or water table",
            "rootZone": "the caller supplies total available water in mm, which already integrates "
                        "rooting depth and soil texture",
        },
        "parameters": {
            "totalAvailableWaterMm": round(float(taw), 2),
            "initialDepletionMm": round(float(scenario_input.get("initialDepletionMm") or 0.0), 2),
            "irrigationAmountMm": round(float(scenario_input.get("irrigationAmountMm") or 0.0), 2),
            "irrigationIntervalDays": int(scenario_input.get("irrigationIntervalDays") or 1),
            "cropCoefficient": round(kc, 3),
            "depletionFraction": irrigation.adjusted_depletion_fraction(crop_key, first.get("etcMm", 0)),
        },
        "totals": result.totals,
        "requirementIfReplacedDaily": {"netIrrigationMm": round(requirement, 2),
                                       "litres": round(requirement * area_m2, 2),
                                       "note": ("the depth that would exactly replace crop ET over "
                                                "the remaining cycle, i.e. the zero-deficit case")},
        "stress": irrigation.stress_free_check(result),
        "daily": result.daily[:120],
        "dailyTruncated": days > 120,
        "units": units.block(cropEtcMm="mm/day", actualEtaMm="mm/day", irrigationMm="mm",
                             deepPercolationMm="mm", depletionEndMm="mm", tawMm="mm",
                             stressCoefficientKs="dimensionless"),
    }


def compare(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Run every scenario and align them for comparison."""
    results = [scenario(item) for item in scenarios]
    labels = [item["label"] for item in results]

    rows = []
    for item in results:
        rows.append({
            "label": item["label"],
            "crop": item["inputs"]["crop"],
            "daysAfterTransplant": item["inputs"]["daysAfterTransplant"],
            "growthFraction": item["inputs"]["growthFraction"],
            "growingAreaM2": item["inputs"]["growingAreaM2"],
            "et0MmPerDay": item["et0"]["valueMmPerDay"],
            "et0PrimaryMethod": item["et0"]["primaryMethod"],
            "demandEt0ReferenceLPerDay": item["demand"]["et0Reference"]["litresPerDay"],
            "demandCropRelativeLPerDay": item["demand"]["cropRelative"]["litresPerDay"],
            "mmPerDay": item["demand"]["et0Reference"]["mmPerDay"],
            "litresRemainingCycle": item["demand"]["et0Reference"]["litresRemainingCycle"],
            "irrigationLitres": (item["irrigationSchedule"].get("totals") or {}).get("irrigationLitres"),
            "stressDays": (item["irrigationSchedule"].get("totals") or {}).get("stressDays"),
            "relativeTranspirationDeficit": (item["irrigationSchedule"].get("totals") or {})
            .get("relativeTranspirationDeficit"),
        })

    deltas: list[dict[str, Any]] = []
    baseline = results[0] if results else None
    for item, row in zip(results[1:], rows[1:]):
        deltas.append({
            "vs": baseline["label"] if baseline else None,
            "label": item["label"],
            "et0MmPerDayDelta": round(row["et0MmPerDay"] - rows[0]["et0MmPerDay"], 3),
            "demandLPerDayDelta": round(
                row["demandEt0ReferenceLPerDay"] - rows[0]["demandEt0ReferenceLPerDay"], 3),
            "demandPctDelta": (
                round(100.0 * (row["demandEt0ReferenceLPerDay"]
                               - rows[0]["demandEt0ReferenceLPerDay"])
                      / rows[0]["demandEt0ReferenceLPerDay"], 2)
                if rows[0]["demandEt0ReferenceLPerDay"] else None),
        })

    return {
        "workflow": "water-demand",
        "status": "complete",
        "scenarios": results,
        "comparison": {
            "rows": rows,
            "deltas": deltas,
            "baseline": baseline["label"] if baseline else None,
            "note": ("Deltas are computed against the first scenario. Negative demand deltas mean "
                     "the later scenario needs less water, not that it is better. Ambient "
                     "temperature, humidity, radiation and wind move only the ET0-reference column; "
                     "a change in the crop-relative column can only come from crop, area or "
                     "growth stage."),
        },
        "units": units.block(
            et0MmPerDay="mm/day",
            demandEt0ReferenceLPerDay="L/day",
            demandCropRelativeLPerDay="L/day",
            mmPerDay="mm/day",
            litresPerDay="L/day",
            litresRemainingCycle="L",
            measuredMlPerPotPerDay="mL/pot/day",
            measuredLPerM2PerDay="L/m2/day",
            growingAreaM2="m2",
            growthFraction="fraction",
            daysAfterTransplant="day",
            tmaxC="degC",
            tminC="degC",
            relativeHumidityPct="%",
            solarRadiationMJm2="MJ/m2/day",
            windSpeedMs="m/s",
            latitude="degree",
            elevationM="m",
            cropCoefficient="dimensionless",
            litresPerPlantPerDay="L/day",
        ),
        "evidence": {
            "layers": [
                {"kind": "reference-calculation",
                 "what": "FAO-56 Penman-Monteith reference ET0 from the supplied climate",
                 "isMeasurement": False,
                 "provenance": "published standard, implemented in backend/app/simulation/"
                               "et0_fao56.py and checked against its own worked examples"},
                {"kind": "model-prediction",
                 "what": "crop water demand from the reference flux and a crop coefficient",
                 "isMeasurement": False,
                 "provenance": "coefficients are FAO-56 tabulated field values (see kcSource)"},
                {"kind": "exploratory-simulation",
                 "what": "crop-relative demand from the platform's own crop profile",
                 "isMeasurement": False,
                 "provenance": "assumed peak water per m2 in backend/app/simulation/crops.py"},
                {"kind": "measured-observation",
                 "what": "greenhouse lettuce pot evapotranspiration (lettuce only)",
                 "isMeasurement": True,
                 "provenance": f"{MEASURED_STUDY['citation']} · {MEASURED_STUDY['doi']} · "
                               f"{MEASURED_STUDY['license']}"},
            ],
            "distinction": ("Reference calculations, model predictions, exploratory simulations and "
                            "measured observations are four different things. Each layer above "
                            "says which one it is."),
        },
        "limitations": LIMITATIONS,
        "method": {
            "name": "reference-ET0 crop demand with a measured bench",
            "referenceEquation": "FAO-56 Penman-Monteith (Hargreaves when radiation or wind absent)",
            "cropEquation": "E = ET0 x Kc x canopy cover x area",
            "canopyCurve": f"logistic_progress(day, cycle), steepness {constants.LOGISTIC_STEEPNESS}",
            "seedlingActivityFraction": constants.SEEDLING_ACTIVITY_FRACTION,
            "litresPerMmPerM2": constants.ET0_MM_PER_M2_TO_LITRES,
            "constantsChanged": [],
        },
        "kcSources": KC_SOURCES,
    }


def capability() -> dict[str, Any]:
    """What this workflow can be asked for, for a form builder or a client validator."""
    fields = [
        {"name": "growingAreaM2", "label": "Growing area", "unit": "m2", "min": 0.1,
         "max": 10_000, "step": 0.5, "kind": "number",
         "why": "Water demand is an area-scaled flux, so the area decides the litres."},
        {"name": "daysAfterTransplant", "label": "Days after transplant", "unit": "day",
         "min": 0, "max": 365, "step": 1, "kind": "number",
         "why": "Sets the canopy cover on the growth curve, which scales both demand equations."},
        {"name": "tmaxC", "label": "Daily maximum air temperature", "unit": "degC",
         "min": -40, "max": 60, "step": 0.5, "kind": "number",
         "why": "Drives the aerodynamic and radiation terms of the reference ET0."},
        {"name": "tminC", "label": "Daily minimum air temperature", "unit": "degC",
         "min": -50, "max": 55, "step": 0.5, "kind": "number",
         "why": "With the maximum, sets the mean temperature and the dew point."},
        {"name": "relativeHumidityPct", "label": "Relative humidity", "unit": "%",
         "min": 1, "max": 100, "step": 1, "kind": "number",
         "why": "Converted to a dew point and hence to vapour-pressure deficit: dry air pulls "
                "more water out of the canopy."},
        {"name": "solarRadiationMJm2", "label": "Solar radiation", "unit": "MJ/m2/day",
         "min": 0, "max": 60, "step": 0.5, "kind": "number", "required": False,
         "why": "The dominant term of Penman-Monteith. Without it the workflow falls back to the "
                "trained emulator or to Hargreaves and names whichever it used."},
        {"name": "windSpeedMs", "label": "Wind speed at 2 m", "unit": "m/s",
         "min": 0, "max": 40, "step": 0.1, "kind": "number", "required": False,
         "why": "The aerodynamic term. Without it the workflow falls back to the emulator or to "
                "Hargreaves and names whichever it used."},
        {"name": "dayOfYear", "label": "Day of year", "unit": "day",
         "min": 1, "max": 366, "step": 1, "kind": "integer",
         "why": "Sets extraterrestrial radiation, which depends on the Earth's orbit."},
        {"name": "latitude", "label": "Latitude", "unit": "degree",
         "min": -90, "max": 90, "step": 0.1, "kind": "number",
         "why": "With day of year, sets the incoming radiation a clear sky allows."},
        {"name": "elevationM", "label": "Elevation", "unit": "m",
         "min": -500, "max": 9000, "step": 1, "kind": "number",
         "why": "Sets atmospheric pressure, which scales both radiation and aerodynamic terms."},
        {"name": "plantsPerM2", "label": "Planting density", "unit": "plant/m2",
         "min": 0.5, "max": 2000, "step": 1, "kind": "number", "required": False,
         "why": "Optional. Without it the response reports no per-plant figure rather than "
                "assuming a density the studies do not publish."},
        {"name": "cropCoefficient", "label": "Crop coefficient (Kc)", "unit": "dimensionless",
         "min": 0.05, "max": 2.0, "step": 0.05, "kind": "number", "required": False,
         "why": "Optional override. The default is the FAO-56 tabulated value for the crop; 1.0 "
                "describes the reference surface, not a crop."},
        # ---- irrigation scheduling (Phase 29) ----
        {"name": "totalAvailableWaterMm", "label": "Root-zone available water (TAW)", "unit": "mm",
         "min": 1, "max": 400, "step": 1, "kind": "number", "required": False,
         "requiredFor": "irrigationSchedule",
         "why": "The storage term of the FAO-56 water balance: how much water the root zone holds "
                "between field capacity and wilting point. Without it no schedule can be computed."},
        {"name": "initialDepletionMm", "label": "Depletion at the start", "unit": "mm",
         "min": 0, "max": 400, "step": 1, "kind": "number", "required": False,
         "why": "How dry the root zone already is on day one. Sets whether the crop starts stressed."},
        {"name": "irrigationAmountMm", "label": "Irrigation depth per event", "unit": "mm",
         "min": 0, "max": 200, "step": 0.5, "kind": "number", "required": False,
         "why": "Net depth delivered at the root zone per irrigation. Zero means no irrigation and "
                "the schedule reports the deficit that results."},
        {"name": "irrigationIntervalDays", "label": "Irrigation interval", "unit": "day",
         "min": 1, "max": 30, "step": 1, "kind": "number", "required": False,
         "why": "How often the event above is delivered. This is the control an irrigator actually "
                "changes, and the schedule shows what it costs in stress days."},
    ]
    return {
        "workflow": "water-demand",
        "fields": fields,
        "fieldsNote": ("Every field carries its own unit and range so a form can be built from this "
                       "document instead of from the prose."),
        "capabilities": {
            "referenceEt0": True,
            "twoDemandEquations": True,
            "measuredBenchLettuceOnly": True,
            "irrigationSchedule": {
                "available": True,
                "requiresFields": ["totalAvailableWaterMm"],
                "method": "FAO-56 soil water balance (eq. 84-85)",
                "returnsYieldClaim": False,
                "note": ("an optional layer. The workflow is complete without it, and it adds a "
                         "daily water balance and a stress-day count when a storage term is "
                         "supplied."),
            },
            "dailyWeatherSeries": {
                "available": False,
                "reason": ("a per-day weather series would make the schedule a real forecast rather "
                           "than a repeated single day; the endpoint accepts one climate per "
                           "scenario, and this is stated as a limitation rather than approximated."),
            },
        },
        "crops": [
            {"key": key, "name": crops.get_crop(key).name,
             "cycleDays": crops.get_crop(key).growth_duration_days,
             "kc": KC_SOURCES[key]["kc"], "kcSource": KC_SOURCES[key]["source"],
             "hasMeasuredBench": key == MEASURED_CROP}
            for key in SUPPORTED_CROPS
        ],
        "measuredCrop": MEASURED_CROP,
        "maxScenarios": 4,
        "units": units.block(et0MmPerDay="mm/day", demandEt0ReferenceLPerDay="L/day"),
    }
