"""Measured closed-loop numbers: ethylene production and dose response, and water recovery.

The simulator models growth from light, temperature, CO2 and water. It has never modelled the
atmosphere of a sealed chamber or the engineering loop that keeps water moving, and that gap was
previously only disclosed in prose. This module serves what NASA actually measured for those two
questions, so the simulator can be read against a number instead of a caveat.

Nothing here is folded into the growth equations. The ethylene figures are a hazard screen beside
the simulation, and the water figures bound a control the simulator already exposes.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.research import DATA

PATH = DATA / "literature" / "nasa_air_and_water.json"


@lru_cache(maxsize=1)
def _source() -> dict | None:
    if not PATH.is_file():
        return None
    return json.loads(PATH.read_text())


def ethylene_accumulation(area_m2: float, days: float, volume_m3: float,
                          rate_ml_per_m2_day: float = 0.05) -> dict:
    """Arithmetic from the measured production rate, with every assumption named.

    This is not a kinetics model: it assumes no scrubbing, no leakage and no plant uptake, so it
    gives the fastest a chamber of that volume could reach the concentration where lettuce yield
    loss has been measured. It exists so an operator can see whether scrubbing matters at their
    scale, and it says plainly that the answer is a lower bound.
    """
    # 1 mL ethylene = 1e-3 L; at 25 C and 1 atm one mole occupies 24.45 L, so volume -> moles -> mass.
    molar_mass_g = 28.05
    molar_volume_l = 24.45
    produced_ml = rate_ml_per_m2_day * area_m2 * days
    moles = (produced_ml / 1000.0) / molar_volume_l
    mass_g = moles * molar_mass_g
    # Express as a volumetric mixing ratio: ppb = (volume of ethylene / volume of air) x 1e9.
    ppb = (produced_ml / 1000.0) / volume_m3 / 1000.0 * 1e9
    return {
        "inputs": {"areaM2": area_m2, "days": days, "volumeM3": volume_m3,
                   "rateMlPerM2Day": rate_ml_per_m2_day},
        "ethyleneMassG": round(mass_g, 3),
        "mixingRatioPpb": round(ppb, 1),
        "assumptions": [
            "no scrubbing, no leakage and no plant uptake of ethylene",
            "rate held at the measured peak rather than the whole growth curve",
            "ideal gas at 25 C and 1 atm",
        ],
        "means": ("A lower bound on the concentration a closed volume reaches: real chambers leak, "
                  "and NASA's own measured chamber concentrations are the check on how far off this is."),
    }


def payload() -> dict:
    source = _source()
    if source is None:
        return {"available": False,
                "reason": "data/literature/nasa_air_and_water.json is not in this deployment"}
    ethylene = source["ethylene"]
    water = source["water"]
    peak = ethylene["production"]["peakProduction"]
    return {
        "available": True,
        "ethylene": {
            "production": ethylene["production"],
            "doseResponse": ethylene["lettuceDoseResponse"],
            "relatedReport": ethylene.get("relatedNasaReport"),
            "whyItMatters": ethylene["whyItMatters"],
            "notClaimed": ethylene["notClaimed"],
            # Both ends of the measured range, so the reader sees the spread rather than one pick.
            "workedExamples": [
                ethylene_accumulation(area_m2=1.0, days=28, volume_m3=10.0, rate_ml_per_m2_day=0.04),
                ethylene_accumulation(area_m2=20.0, days=28, volume_m3=113.0, rate_ml_per_m2_day=0.06),
            ],
            # NASA measured 40-120 ppb in that same 20 m2 / 113 m3 chamber, so the no-leak bound can
            # be checked against a real measurement instead of standing on its own.
            "chamberCheck": {
                "chamber": "NASA CELSS Biomass Production Chamber, 20 m2 growing area, 113 m3 volume",
                "measuredPpb": "40-120 (lettuce and wheat, per Wheeler et al. 1996)",
                "boundedPpb": 297.3,
                "ratioToUpperMeasured": round(297.3 / 120, 1),
                "explanation": ("The no-leak, peak-rate bound lands 2.5x above the highest concentration "
                                "NASA measured in that chamber, which is the right direction: the real "
                                "chamber leaked about 10 % of its volume per day and wheat leaf rolling "
                                "was removed by scrubbing. The bound is an upper limit, not a prediction."),
            },
            "workedExampleNote": (
                f"Peak production is {peak['value']} {peak['unit']} ({peak['equivalent']}), "
                "unadjusted for chamber leakage. The second example uses the Biomass Production "
                "Chamber's own 20 m2 area over its 113 m3 volume, which is why its predicted "
                "concentration can be compared with the 40-120 ppb NASA measured there."
            ),
        },
        "water": {
            "source": water["source"],
            "issRecovery": water["issRecovery"],
            "implication": water["implication"],
            "useInSimulator": water["useInSimulator"],
        },
        "sourcesAudited": source["sourcesAudited"],
        "scopeNote": ("Measured closed-loop numbers served beside the simulator. Ethylene is a "
                      "hazard screen, not a growth term; water recovery bounds a control the "
                      "simulator exposes."),
    }
