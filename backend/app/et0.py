"""Reference-ET0 service: physics, learned surrogate, and the honest answer between them.

Three sources of a number, in order of authority:

    1. FAO-56 Penman-Monteith - published physics, no free parameters, checked against the worked
       examples in its own source document. Served whenever radiation and wind are supplied.
    2. Hargreaves-Samani - published physics, temperature and latitude only. The fallback, and the
       value that generalises better across sites than anything learned here.
    3. et0-emulator-v1 - a fitted surrogate of (1). Beats Hargreaves on held-out days from the
       training sites and loses to it on unseen sites, so it is never returned alone.

The service degrades instead of failing: no artifact -> physics only; no scikit-learn -> physics
only; unreadable artifact -> physics only. It never raises because a model file is missing,
because ET0 has a correct answer without any model at all.
"""
from __future__ import annotations

import json
import logging
import math
import warnings
from functools import lru_cache
from pathlib import Path

from app.simulation import et0_fao56

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_JSON = ROOT / "ml" / "artifacts" / "et0-emulator-v1.json"
ARTIFACT_MODEL = ROOT / "ml" / "artifacts" / "et0-emulator-v1.joblib"

MAGNUS_A = 17.27
MAGNUS_B = 237.3


def _dewpoint_from_rh(t_celsius: float, rh_percent: float) -> float:
    """Dew point from temperature and RH (Magnus inverse). Only used when Tdew is absent."""
    rh = min(max(rh_percent, 0.1), 100.0) / 100.0
    gamma = math.log(rh) + (MAGNUS_A * t_celsius) / (MAGNUS_B + t_celsius)
    return (MAGNUS_B * gamma) / (MAGNUS_A - gamma)


@lru_cache(maxsize=1)
def load_artifact() -> tuple[dict, dict] | None:
    """Load the JSON card and the pickled model. Returns None when either is unusable.

    Cached because the artifact is immutable for the life of the process; `cache_clear()` is the
    documented way to force a reload (the tests use it).
    """
    if not ARTIFACT_JSON.is_file() or not ARTIFACT_MODEL.is_file():
        return None
    try:
        card = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
        import joblib
        bundle = joblib.load(ARTIFACT_MODEL)
        if not bundle.get("features") or bundle.get("model") is None:
            raise ValueError("bundle is missing its feature list or model")
        return card, bundle
    except Exception as error:  # noqa: BLE001 - any failure means "physics only"
        logger.warning("ET0 emulator artifact unusable, serving physics only: %s", error)
        return None


def artifact_status() -> dict:
    """Availability and the gate results that decide how the artifact may be used."""
    loaded = load_artifact()
    if loaded is None:
        return {
            "available": False,
            "modelId": "et0-emulator-v1",
            "reason": "artifact missing or unreadable; the service serves FAO-56 physics only",
            "fallback": ("FAO-56 Penman-Monteith when radiation and wind are supplied, else "
                         "Hargreaves-Samani"),
        }
    card, bundle = loaded
    return {
        "available": True,
        "fallback": ("FAO-56 Penman-Monteith is the primary number whenever radiation and wind "
                     "are supplied; the emulator is offered beside it. When they are missing the "
                     "physics is Hargreaves-Samani."),
        "modelId": card.get("modelId"),
        "status": card.get("status"),
        "deployed": card.get("deployed"),
        "deploymentDecision": card.get("deploymentDecision"),
        "features": bundle.get("features"),
        "variant": bundle.get("variant"),
        # The recorded training envelope; the service flags any input outside it, and the registry
        # row publishes it so a caller can see the domain before asking for a number.
        "domainBounds": bundle.get("oodBounds"),
        "intervalMm": bundle.get("halfWidthMm"),
        "validation": {
            "acceptanceGate": (card.get("validation") or {}).get("acceptanceGate"),
            "gatesPassed": (card.get("validation") or {}).get("gatesPassed"),
            "gatesTotal": (card.get("validation") or {}).get("gatesTotal"),
            "losoSitesBeatingHargreaves": (card.get("validation") or {}).get(
                "losoSitesBeatingHargreaves"),
            "improvementOverHargreaves": card.get("improvementOverHargreaves"),
            "evaluation": card.get("evaluation"),
        },
        "metrics": card.get("metrics"),
        "baselineMetrics": card.get("baselineMetrics"),
        "trainingData": card.get("trainingData"),
        "limitations": card.get("limitations"),
    }


def _emulator_estimate(card: dict, bundle: dict, features: dict) -> dict:
    import numpy as np

    bounds = bundle.get("oodBounds") or {}
    outside = [name for name, limit in bounds.items()
               if name in features
               and (features[name] < limit["min"] or features[name] > limit["max"])]
    vector = np.asarray([[features[name] for name in bundle["features"]]], dtype=float)
    # The model was fitted on a DataFrame, so predicting from a bare array emits a feature-name
    # warning. Column order is pinned by the artifact's own feature list.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        value = float(bundle["model"].predict(vector)[0])
    half_width = float(bundle.get("halfWidthMm") or 0.0)
    return {
        "et0MmPerDay": round(value, 3),
        "intervalMm": [round(max(value - half_width, 0.0), 3), round(value + half_width, 3)],
        "intervalCoveragePct": (card.get("uncertainty") or {}).get("coverageOnHoldoutPct"),
        "outOfDistribution": bool(outside),
        "outsideFeatures": outside,
        "modelId": card.get("modelId"),
    }


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
    """ET0 from whichever methods the inputs allow, with the primary method named."""
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
            "requires": "solar radiation and wind speed",
        }

    hargreaves = et0_fao56.hargreaves_et0(tmax_c, tmin_c, ra_mj)
    hargreaves_block = {
        "et0MmPerDay": round(hargreaves["et0MmPerDay"], 3),
        "requires": "temperature and latitude only",
        "note": "better than the emulator on an unseen site in this project's own study",
    }

    loaded = load_artifact()
    emulator = None
    if loaded is not None:
        card, bundle = loaded
        features = {
            "T2M_MAX": tmax_c, "T2M_MIN": tmin_c, "T2MDEW": tdew_used,
            "doySin": math.sin(2 * math.pi * day_of_year / 365.0),
            "doyCos": math.cos(2 * math.pi * day_of_year / 365.0),
            "latitude": latitude, "elevationM": elevation_m,
            "raMj": ra_mj, "daylightHours": daylight_hours,
        }
        try:
            emulator = _emulator_estimate(card, bundle, features)
        except Exception as error:  # noqa: BLE001 - never fail a physics question on a model
            logger.warning("ET0 emulator prediction failed, using physics only: %s", error)
            emulator = None

    if penman is not None:
        primary, value = "penman-monteith", penman["et0MmPerDay"]
    elif emulator is not None:
        primary, value = "emulator", emulator["et0MmPerDay"]
    else:
        primary, value = "hargreaves", hargreaves_block["et0MmPerDay"]

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
        "methods": {"penmanMonteith": penman, "emulator": emulator,
                    "hargreaves": hargreaves_block},
        "light": (et0_fao56.daily_light_integral(solar_radiation_mj)
                  if solar_radiation_mj is not None else None),
        "evidenceClass": "computed standard + trained emulator, not a measurement",
        "limitations": [
            ("Reference evapotranspiration is a computed standard, not a measurement of any "
             "crop's water use."),
            ("The emulator was validated against FAO-56 ET0 derived from NASA POWER reanalysis at "
             "six sites; it is not validated for microgravity, low pressure, or LED-lit interiors."),
            ("On an unseen site the emulator was about 19 % worse than Hargreaves-Samani, so both "
             "values are returned and the emulator is flagged when the input falls outside its "
             "training range."),
            ("A real crop's water demand needs a crop coefficient (Kc) and a water-balance model; "
             "ET0 is only the reference surface flux those steps start from."),
        ],
    }
