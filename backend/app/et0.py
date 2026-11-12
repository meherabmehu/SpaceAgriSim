"""Reference-ET0 service: published physics, and nothing learned on top of it.

Two sources of a number, in order of authority:

    1. FAO-56 Penman-Monteith - published physics, no free parameters, checked against the worked
       examples in its own source document. Computed whenever radiation and wind are supplied.
    2. Hargreaves-Samani - published physics, temperature and latitude only. Used when the
       Penman-Monteith inputs are incomplete, because it is the published equation that the
       missing inputs do not affect.

Phase 31 removed the fitted ET0 surrogate (`et0-emulator-v1`) from the served pathway. It was a
regression model trained on FAO-56 ET0 derived from NASA POWER reanalysis - not on measured ET0 -
and on leave-one-site-out it was about 19 % worse than Hargreaves-Samani. Worse, when radiation
and wind were absent it became the *primary* number in preference to Hargreaves, i.e. the service
could return its least transferable estimate as the answer. A surrogate of an equation that is
already computable from the same inputs adds approximation error and no information, so it is no
longer served. Its artifact and evaluation remain in `ml/artifacts` and `ml/evaluation` as a
recorded negative result; `/api/reference-et0/model` documents the physics instead.

What is served here is a *computed standard* for a hypothetical reference grass surface. It is
never a measurement, and never a measurement of any crop's water use.

Note on the remaining inputs: the weather values a caller supplies are typically reanalysis
(NASA POWER) rather than station observations. The service labels that distinction in every
response instead of implying measured weather.
"""
from __future__ import annotations

import logging
import math

from app.simulation import et0_fao56

logger = logging.getLogger(__name__)

MAGNUS_A = 17.27
MAGNUS_B = 237.3

# Which inputs each method needs, published so a UI can say why a method was not available.
METHOD_REQUIREMENTS = {
    "penman-monteith": "daily tmax, tmin, dew point (or RH), solar radiation and wind speed",
    "hargreaves": "daily tmax, tmin, latitude and day of year",
}


def _dewpoint_from_rh(t_celsius: float, rh_percent: float) -> float:
    """Dew point from temperature and RH (Magnus inverse). Only used when Tdew is absent."""
    rh = min(max(rh_percent, 0.1), 100.0) / 100.0
    gamma = math.log(rh) + (MAGNUS_A * t_celsius) / (MAGNUS_B + t_celsius)
    return (MAGNUS_B * gamma) / (MAGNUS_A - gamma)


def physics_status() -> dict:
    """The model card for the served ET0 calculation.

    Everything here is a property of the published method or of this implementation of it, so the
    card cannot claim more than the code does. The worked-example results are recomputed on each
    call rather than stored, because a stored result is a claim about an older version of the code.
    """
    published = [
        {key: row[key] for key in ("example", "publishedMmPerDay", "computedMmPerDay",
                                   "ra", "rs")} | {
            "differenceMmPerDay": round(row["computedMmPerDay"] - row["publishedMmPerDay"], 4),
            "withinTolerance": bool(row.get("withinTolerance")),
        }
        for row in et0_fao56.run_published_examples()
    ]
    return {
        "id": "reference-et0",
        "name": "FAO-56 reference evapotranspiration (Penman-Monteith, with Hargreaves-Samani)",
        "kind": "calculation",
        "standard": "FAO-56 Penman-Monteith daily reference evapotranspiration (FAO-56 eq. 6)",
        "implementation": "app.simulation.et0_fao56",
        "servedAt": "/api/reference-et0/estimate",
        "deployed": True,
        "methods": dict(METHOD_REQUIREMENTS),
        "publishedExamples": published,
        "allExamplesWithinTolerance": all(row["withinTolerance"] for row in published),
        "evidenceClass": "computed standard, not a measurement",
        "measuredEt0Validation": {
            "available": False,
            "statement": (
                "No measured-ET0 station benchmark is bundled, so the implementation is validated "
                "against the FAO-56 manual's worked examples only. That validates the arithmetic, "
                "not the weather it is fed."
            ),
        },
        "removedSurrogate": {
            "modelId": "et0-emulator-v1",
            "removedIn": "Phase 31",
            "reason": (
                "Fitted on FAO-56 ET0 derived from NASA POWER reanalysis, about 19 % worse than "
                "Hargreaves-Samani on leave-one-site-out, and preferred as the primary number "
                "when radiation and wind were missing. A surrogate of an equation that is "
                "computable from the same inputs adds error and no information."
            ),
            "retainedFor": "ml/artifacts/et0-emulator-v1 and ml/evaluation, as a negative result.",
        },
        "limitations": [
            "ET0 is a computed flux for a reference grass surface, not a measurement of a crop's water use.",
            "Penman-Monteith needs radiation and wind; without them only Hargreaves-Samani is computed and the response says so.",
            "Reanalysis weather is not station weather; the response labels which inputs were supplied.",
            "Reference ET0 is the flux a water balance starts from; it is not crop water demand until a crop coefficient is applied.",
        ],
    }


# Phase 32: the audit found that no output layer checked whether a number was physically
# possible. Reference ET0 above this is not a dry day, it is a bad input - the highest daily
# total in the FAO-56 worked examples is under 8 mm and the world record class is ~15 mm. A
# value returned above the ceiling is *reported*, never clamped, because a clamp would turn a
# detectable input error into a plausible-looking number.
MAX_PLAUSIBLE_ET0_MM = 30.0


def estimate(
    *,
    tmax_c: float,
    tmin_c: float,
    day_of_year: int,
    latitude: float,
    elevation_m: float,
    tdew_c: float | None = None,
    relative_humidity_pct: float | None = None,
    solar_radiation_mj: float | None = None,
    wind_speed_ms: float | None = None,
    pressure_kpa: float | None = None,
) -> dict:
    """ET0 from whichever published method the inputs allow, with the method named."""
    tmean = (tmax_c + tmin_c) / 2.0

    if tdew_c is None:
        if relative_humidity_pct is None:
            raise ValueError("one of tdewC or relativeHumidityPct is required")
        tdew_c = _dewpoint_from_rh(tmean, relative_humidity_pct)
        dewpoint_derived = True
    else:
        dewpoint_derived = False
    # A dew point above the daily mean is possible in a saturated hour but not as a daily value;
    # clamping keeps VPD non-negative without silently changing the reported input.
    tdew_used = min(tdew_c, tmean)

    pressure = (pressure_kpa if pressure_kpa is not None
                else et0_fao56.atmospheric_pressure(elevation_m))
    ra_mj, daylight_hours = et0_fao56.extraterrestrial_radiation(latitude, day_of_year)
    ea = et0_fao56.actual_vapour_pressure_from_dewpoint(tdew_used)

    penman = None
    if solar_radiation_mj is not None and wind_speed_ms is not None:
        result = et0_fao56.reference_et0(
            tmax=tmax_c, tmin=tmin_c, ea=ea, rs=solar_radiation_mj, wind_2m=wind_speed_ms,
            pressure_kpa=pressure, day_of_year=day_of_year,
            latitude_deg=latitude, elevation_m=elevation_m)
        penman = {
            "et0MmPerDay": round(result["et0MmPerDay"], 3),
            "radiationTermMm": round(result["radiationTermMm"], 3),
            "aeroTermMm": round(result["aeroTermMm"], 3),
            "vpdKpa": round(result["vpdKpa"], 3),
            "netRadiationMJm2": round(result["netRadiationMJm2"], 3),
            "requires": METHOD_REQUIREMENTS["penman-monteith"],
        }

    hargreaves = et0_fao56.hargreaves_et0(tmax_c, tmin_c, ra_mj)
    hargreaves_block = {
        "et0MmPerDay": round(hargreaves["et0MmPerDay"], 3),
        "requires": METHOD_REQUIREMENTS["hargreaves"],
        "note": ("Published temperature-based estimate. Used when radiation or wind is missing; "
                 "it is less mechanistic than Penman-Monteith, not an alternative of equal "
                 "standing."),
    }

    if penman is not None:
        primary, value = "penman-monteith", penman["et0MmPerDay"]
    else:
        primary, value = "hargreaves", hargreaves_block["et0MmPerDay"]

    # ---- output plausibility -------------------------------------------------------------
    # Returned, not corrected. `plausible` is the verdict on the value above; the caller decides
    # whether to show it, and cannot do so without seeing this.
    implausibilities = []
    if tmax_c < tmin_c:
        implausibilities.append(
            f"tmaxC is below tminC ({tmax_c} < {tmin_c}); the daily temperature range is negative, "
            "which is not a physical day. The inputs are probably swapped.")
    if value < 0:
        implausibilities.append(
            f"ET0 {value} mm/day is negative; a reference surface cannot condense more water than "
            "it evaporates over a day at these inputs.")
    if value > MAX_PLAUSIBLE_ET0_MM:
        implausibilities.append(
            f"ET0 {value} mm/day exceeds the physical ceiling of {MAX_PLAUSIBLE_ET0_MM} mm/day "
            "used here; at this magnitude the inputs are wrong, not the weather exceptional.")

    missing = [name for name, present in (
        ("solarRadiationMJm2", solar_radiation_mj is not None),
        ("windSpeedMs", wind_speed_ms is not None),
    ) if not present]

    return {
        "primaryMethod": primary,
        "et0MmPerDay": value,
        "inputs": {
            "tmaxC": tmax_c, "tminC": tmin_c, "tdewC": round(tdew_used, 3),
            "dewpointDerivedFromRelativeHumidity": dewpoint_derived,
            "relativeHumidityPct": relative_humidity_pct,
            "dayOfYear": day_of_year, "latitude": latitude, "elevationM": elevation_m,
            "solarRadiationMJm2": solar_radiation_mj, "windSpeedMs": wind_speed_ms,
            "pressureKpa": round(pressure, 3),
            "extraterrestrialRadiationMJm2": round(ra_mj, 3),
            "daylightHours": round(daylight_hours, 3),
        },
        "methods": {"penmanMonteith": penman, "hargreaves": hargreaves_block},
        "methodSelection": {
            "primary": primary,
            "usedFallback": penman is None,
            "missingInputs": missing,
            "reason": ("Radiation and wind were supplied, so the full Penman-Monteith equation "
                       "was used." if penman is not None else
                       f"Penman-Monteith needs {' and '.join(missing)}; only Hargreaves-Samani "
                       "is computed."),
        },
        "outputCheck": {
            "plausible": not implausibilities,
            "failures": implausibilities,
            "rule": (f"0 <= ET0 <= {MAX_PLAUSIBLE_ET0_MM} mm/day and tmax >= tmin. A failed check "
                     "is returned rather than silently clamped, so a bad input cannot produce a "
                     "plausible-looking number."),
            "physicalCeilingMmPerDay": MAX_PLAUSIBLE_ET0_MM,
        },
        "light": (et0_fao56.daily_light_integral(solar_radiation_mj)
                  if solar_radiation_mj is not None else None),
        "evidenceClass": "computed standard, not a measurement",
        "weatherProvenance": {
            "suppliedBy": "caller",
            "isMeasured": False,
            "statement": ("These are the weather inputs the caller supplied (typically NASA POWER "
                          "reanalysis). The API does not verify them against a station and does "
                          "not describe the result as measured ET0."),
        },
        "limitations": [
            "Reference evapotranspiration is a computed standard, not a measurement of any crop's water use.",
            "The implementation is validated against the FAO-56 manual's worked examples; no measured-ET0 station benchmark is bundled.",
            "Not validated for microgravity, low pressure, or LED-lit interiors.",
            "A real crop's water demand needs a crop coefficient (Kc) and a water-balance model; ET0 is only the reference surface flux those steps start from.",
        ],
    }
