"""
Water usage and recovery.

Daily water demand follows the canopy: a seedling transpires only a small
fraction of what a full canopy does, so demand ramps up with the growth
fraction of the logistic curve.

    demand(day)    = peakWaterPerDay x area x lightScale
                     x (seedlingFraction + (1 - seedlingFraction) x growthFraction)
    supplied(day)  = demand(day) x waterAvailability / 100
    deficit(day)   = demand(day) - supplied(day)
    recovered(day) = supplied(day) x WATER_RECOVERY_EFFICIENCY

Four quantities, kept apart on purpose:

    demand     what a healthy canopy would want at this growth stage
    supplied   what the system actually delivers (= "used" by the plants)
    deficit    unmet demand - the shortage that is already reducing growth
               through the water factor in `factors.py`
    recovered  the share of the supplied water captured again as condensate

`lightScale` is the light factor: longer photoperiods mean more hours of
transpiration. Water that plants use does not disappear - most of it is
transpired into the cabin air and can be condensed back, which is what the
recovery efficiency represents (closed-loop assumption from the constants).

Two demand bases, never mixed
-----------------------------
`crop-relative` (the default, and what every stored scenario replays as) keeps
the equation above: a peak litre figure per m^2 taken from the crop table.

`et0-reference` is used instead when the caller supplies a reference
evapotranspiration for the site:

    demand(day) = ET0 [mm/day] x Kc x area [m^2] x canopy_scale(day)

1 mm over 1 m^2 is 1 litre, so the flux converts directly. Two details are
deliberate. The light and VPD scales are NOT applied on this path, because ET0
already contains the site's real radiation, humidity and wind - scaling it again
would count the weather twice. And canopy_scale still applies, because ET0 is
defined for a full reference grass surface while a seedling transpires a
fraction of that.

Kc defaults to 1.0, which means "the reference surface", not "your crop". A Kc
must come from a source that measured the crop; see
`docs/SCIENTIFIC_AI_UPGRADE_REPORT.md` for why none is pre-filled here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import simulation_constants as constants
from app.simulation.crops import CropProfile
from app.simulation.growth import DailyGrowthPoint


@dataclass(frozen=True)
class DailyWaterPoint:
    day: int
    water_used_l: float  # litres actually supplied to (and used by) the crop on this day
    water_recovered_l: float  # litres returned to the loop on this day
    cumulative_water_used_l: float
    cumulative_water_recovered_l: float
    water_demand_l: float = 0.0  # litres a healthy canopy would want on this day
    water_deficit_l: float = 0.0  # unmet demand on this day
    cumulative_water_demand_l: float = 0.0
    cumulative_water_deficit_l: float = 0.0


def daily_water_demand_l(
    crop: CropProfile,
    growth_fraction: float,
    growing_area_m2: float,
    light_scale: float,
) -> float:
    """Water a healthy canopy at this growth stage would want (before shortage)."""
    seedling = constants.SEEDLING_ACTIVITY_FRACTION
    canopy_scale = seedling + (1.0 - seedling) * growth_fraction
    return crop.peak_water_l_per_day * growing_area_m2 * light_scale * canopy_scale


def et0_reference_demand_l(
    et0_mm_per_day: float,
    crop_coefficient: float,
    growth_fraction: float,
    growing_area_m2: float,
) -> float:
    """Water demand of a canopy from a reference ET0 flux (litres per day)."""
    seedling = constants.SEEDLING_ACTIVITY_FRACTION
    canopy_scale = seedling + (1.0 - seedling) * growth_fraction
    return (et0_mm_per_day * crop_coefficient * growing_area_m2 * canopy_scale
            * constants.ET0_MM_PER_M2_TO_LITRES)


def demand_basis(et0_mm_per_day: float | None) -> str:
    """Which equation produced the daily demand numbers."""
    return "et0-reference" if et0_mm_per_day is not None else "crop-relative"


def simulate_water(
    crop: CropProfile,
    growth_points: list[DailyGrowthPoint],
    water_availability_percent: float,
    light_scale: float,
    growing_area_m2: float,
    recovery_efficiency: float = constants.WATER_RECOVERY_EFFICIENCY,
    demand_scale: float = 1.0,
    et0_mm_per_day: float | None = None,
    crop_coefficient: float | None = None,
) -> list[DailyWaterPoint]:
    """One point per day, aligned with `growth_points` (day 0 uses no water).

    `et0_mm_per_day=None` keeps the crop-relative equation byte-for-byte, which is
    what every saved scenario and every stored test expectation assumes.
    """
    availability = min(max(water_availability_percent, 0.0), 100.0) / 100.0
    efficiency = min(max(recovery_efficiency, 0.0), 1.0)
    coefficient = (constants.DEFAULT_CROP_COEFFICIENT if crop_coefficient is None
                   else crop_coefficient)
    if et0_mm_per_day is not None:
        low, high = constants.ET0_PLAUSIBLE_RANGE_MM_PER_DAY
        if not low <= et0_mm_per_day <= high:
            raise ValueError(
                f"et0MmPerDay {et0_mm_per_day} is outside the plausible daily range "
                f"{low}-{high} mm/day")
        if coefficient <= 0:
            raise ValueError("cropCoefficient must be greater than zero")

    points: list[DailyWaterPoint] = []
    demand_total = 0.0
    used_total = 0.0
    deficit_total = 0.0
    recovered_total = 0.0

    for point in growth_points:
        if point.day == 0:
            demand = 0.0
        elif et0_mm_per_day is not None:
            # The weather is already inside ET0, so neither light_scale nor demand_scale
            # (the VPD ratio) is applied here.
            demand = et0_reference_demand_l(
                et0_mm_per_day, coefficient, point.growth_fraction, growing_area_m2)
        else:
            demand = daily_water_demand_l(crop, point.growth_fraction, growing_area_m2, light_scale) * max(demand_scale, 0.0)
        supplied = demand * availability
        deficit = max(demand - supplied, 0.0)
        recovered = supplied * efficiency

        demand_total += demand
        used_total += supplied
        deficit_total += deficit
        recovered_total += recovered
        points.append(
            DailyWaterPoint(
                day=point.day,
                water_used_l=supplied,
                water_recovered_l=recovered,
                cumulative_water_used_l=used_total,
                cumulative_water_recovered_l=recovered_total,
                water_demand_l=demand,
                water_deficit_l=deficit,
                cumulative_water_demand_l=demand_total,
                cumulative_water_deficit_l=deficit_total,
            )
        )

    return points


def total_water_used_l(points: list[DailyWaterPoint]) -> float:
    return points[-1].cumulative_water_used_l if points else 0.0


def total_water_recovered_l(points: list[DailyWaterPoint]) -> float:
    return points[-1].cumulative_water_recovered_l if points else 0.0


def total_water_demand_l(points: list[DailyWaterPoint]) -> float:
    return points[-1].cumulative_water_demand_l if points else 0.0


def total_water_deficit_l(points: list[DailyWaterPoint]) -> float:
    return points[-1].cumulative_water_deficit_l if points else 0.0
