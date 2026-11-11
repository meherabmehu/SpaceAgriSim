"""FAO-56 soil water balance, for irrigation scheduling rather than for a single demand number.

Why this module exists
----------------------
A daily demand figure answers "how much water does this canopy want today". It does not answer the
question an irrigator actually has: *if I deliver this much, this often, how many days does the crop
spend short of water, and how much water do I put on over the cycle?* That question needs a water
balance with a storage term, and a stress coefficient that reduces transpiration as the root zone
dries out.

Everything here is FAO-56 (Allen et al. 1998) closed form:

    TAW = total available water in the root zone [mm]        (supplied by the caller)
    RAW = p * TAW                                            (p = depletion fraction for no stress)
    Ks  = 1                        if Dr <= RAW
        = (TAW - Dr) / (TAW - RAW) if Dr >  RAW              (eq. 84)
    ETa = Ks * ETc                                           (eq. 80)
    Dr(t+1) = Dr(t) + ETc(t) - I(t) - DP(t)   (no rain in a controlled environment)   (eq. 85)

with deep percolation DP occurring only when the irrigation would push the depletion below zero.

What this module does not do, and will not
------------------------------------------
* It does not convert a transpiration deficit into a yield loss. FAO-33 publishes `Ky` crop
  response factors, but a Ky value for this crop and this environment is not in this repository,
  and inventing one would turn a water-balance calculation into a yield forecast nobody measured.
  The output is the **relative transpiration deficit**, which is what the balance actually computes.
* It does not assume rain, runoff, capillary rise or a water table. A controlled environment has
  none of them, and silently modelling them would be a different study.
* It does not invent the depletion fraction. FAO-56 tabulates `p` per crop group; the value used is
  returned with its source and can be overridden.

Units: water depths in millimetres, areas in square metres, volumes in litres. 1 mm over 1 m2 is 1 L.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# FAO-56 Table 22, "depletion fraction (p) for no stress" grouped by crop type.
# Leafy vegetables sit in the 0.30-0.40 band for ETc near 5 mm/day; the standard also gives the
# ETc adjustment p_adj = p + 0.04 * (5 - ETc). Both are applied and reported, never silently.
DEPLETION_FRACTION_BY_CROP = {
    "lettuce": {"p": 0.35, "source": "FAO-56 Table 22, leafy vegetables (0.30-0.40 band)"},
    "tomato": {"p": 0.40, "source": "FAO-56 Table 22, solanum/garden fruit (0.35-0.45 band)"},
    "radish": {"p": 0.35, "source": "FAO-56 Table 22, root and tuber vegetables"},
}
ETC_REFERENCE_FOR_P_ADJUSTMENT = 5.0  # mm/day, FAO-56 eq. 83


@dataclass
class IrrigationResult:
    daily: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)


def adjusted_depletion_fraction(crop_key: str, etc_mm: float) -> dict[str, Any]:
    """`p` and the ETc adjustment FAO-56 specifies, so a dry day is not judged by a wet-day rule."""
    entry = DEPLETION_FRACTION_BY_CROP.get(crop_key, DEPLETION_FRACTION_BY_CROP["lettuce"])
    adjusted = entry["p"] + 0.04 * (ETC_REFERENCE_FOR_P_ADJUSTMENT - etc_mm)
    return {
        "baseP": entry["p"],
        "adjustedP": round(max(0.1, min(0.8, adjusted)), 4),
        "source": entry["source"],
        "adjustment": ("FAO-56 eq. 83: p_adj = p + 0.04 x (5 - ETc); clamped to 0.10-0.80 so an "
                       "extreme ETc cannot make the raw zone meaningless"),
    }


def simulate(
    *,
    crop_key: str,
    daily_et0_mm: list[float],
    canopy_fractions: list[float],
    crop_coefficient: float,
    growing_area_m2: float,
    total_available_water_mm: float,
    initial_depletion_mm: float,
    irrigation_amount_mm: float,
    irrigation_interval_days: int,
    first_irrigation_day: int = 1,
) -> IrrigationResult:
    """Run the balance over the days supplied and return the schedule and the stress record."""
    if total_available_water_mm <= 0:
        raise ValueError("totalAvailableWaterMm must be positive")
    if irrigation_interval_days < 1:
        raise ValueError("irrigationIntervalDays must be at least 1")
    if not 0 <= initial_depletion_mm <= total_available_water_mm:
        raise ValueError("initialDepletionMm must lie between 0 and totalAvailableWaterMm")

    result = IrrigationResult()
    depletion = float(initial_depletion_mm)
    totals = {"etcMm": 0.0, "etaMm": 0.0, "irrigationMm": 0.0, "deepPercolationMm": 0.0,
              "stressDays": 0, "days": 0, "irrigations": 0}

    for index, (et0_mm, canopy) in enumerate(zip(daily_et0_mm, canopy_fractions)):
        day = index + 1
        etc_mm = et0_mm * crop_coefficient * canopy
        p = adjusted_depletion_fraction(crop_key, etc_mm)
        raw_mm = p["adjustedP"] * total_available_water_mm

        irrigation_mm = 0.0
        if irrigation_amount_mm > 0 and (day - first_irrigation_day) % irrigation_interval_days == 0:
            irrigation_mm = float(irrigation_amount_mm)

        # Ks is evaluated on the depletion *before* this day's stress, which is what the crop
        # experiences as it transpires.
        if depletion <= raw_mm:
            ks = 1.0
        else:
            ks = max(0.0, (total_available_water_mm - depletion)
                     / (total_available_water_mm - raw_mm))
        eta_mm = ks * etc_mm

        depletion += etc_mm - irrigation_mm
        deep_percolation = 0.0
        if depletion < 0:
            deep_percolation = -depletion
            depletion = 0.0

        totals["etcMm"] += etc_mm
        totals["etaMm"] += eta_mm
        totals["irrigationMm"] += irrigation_mm
        totals["deepPercolationMm"] += deep_percolation
        totals["days"] += 1
        if irrigation_mm:
            totals["irrigations"] += 1
        if ks < 0.999:
            totals["stressDays"] += 1

        result.daily.append({
            "day": day,
            "et0Mm": round(et0_mm, 3),
            "cropCoefficient": round(crop_coefficient, 3),
            "canopyScale": round(canopy, 4),
            "etcMm": round(etc_mm, 3),
            "stressCoefficientKs": round(ks, 4),
            "etaMm": round(eta_mm, 3),
            "irrigationMm": round(irrigation_mm, 2),
            "deepPercolationMm": round(deep_percolation, 3),
            "depletionEndMm": round(depletion, 2),
            "rawMm": round(raw_mm, 2),
            "tawMm": round(total_available_water_mm, 2),
        })

    etc_total = totals["etcMm"]
    eta_total = totals["etaMm"]
    result.totals = {
        "daysSimulated": totals["days"],
        "cropEtcMm": round(etc_total, 2),
        "actualEtaMm": round(eta_total, 2),
        "relativeTranspirationDeficit": (round(1 - eta_total / etc_total, 4)
                                         if etc_total else None),
        "irrigationMm": round(totals["irrigationMm"], 2),
        "irrigationLitres": round(totals["irrigationMm"] * growing_area_m2, 2),
        "deepPercolationMm": round(totals["deepPercolationMm"], 2),
        "deepPercolationLitres": round(totals["deepPercolationMm"] * growing_area_m2, 2),
        "irrigations": totals["irrigations"],
        "stressDays": totals["stressDays"],
        "waterUseEfficiencyNote": ("irrigationLitres is net water delivered at the root zone; pump "
                                   "and distribution losses are not modelled"),
    }
    return result


def irrigation_requirement_mm(daily_et0_mm: list[float], canopy_fractions: list[float],
                              crop_coefficient: float) -> float:
    """Net irrigation depth that would keep the crop unstressed (the summed crop ET)."""
    return sum(et0 * crop_coefficient * canopy
               for et0, canopy in zip(daily_et0_mm, canopy_fractions))


def stress_free_check(result: IrrigationResult) -> dict[str, Any]:
    """What the same climate requires if the grower simply replaces what the crop uses."""
    deficit = result.totals.get("relativeTranspirationDeficit")
    return {
        "stressDays": result.totals.get("stressDays"),
        "relativeTranspirationDeficit": deficit,
        "interpretation": ("zero stress days means the schedule kept depletion below the no-stress "
                           "threshold on every day; a positive deficit means the crop transpired "
                           "less than its potential on at least one day" ),
        "isYieldClaim": False,
        "whyNoYieldClaim": ("a transpiration deficit is not a yield loss; converting one into the "
                            "other needs a crop yield-response factor that this repository does not "
                            "hold for this crop and environment"),
    }
