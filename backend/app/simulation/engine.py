"""
Simulation engine - the single entry point the API calls.

    run_simulation(SimulationInput) -> SimulationResult

The engine orchestrates the individual modules:

    factors.py       environment multipliers (light, water, radiation, CO2)
    growth.py        daily biomass curve
    water.py         daily water use / recovery
    gas_exchange.py  daily CO2 removal / O2 production

and runs the whole pipeline twice: once for the user's space scenario and
once for an Earth reference scenario, so the caller gets the comparison for
free. No formulas live in this file - only wiring and bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import simulation_constants as constants
from app.simulation import factors, gas_exchange, growth, impact, water
from app.simulation.crops import CropProfile, get_crop


# ---------------------------------------------------------------------------
# Input / output containers (plain dataclasses; the API layer maps them to
# Pydantic models so the engine stays framework-free)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SimulationInput:
    crop: str
    radiation: float
    water_availability: float
    light_hours: float
    co2_level: float
    simulation_days: int
    growing_area: float = constants.PARAMETER_RANGES["growingArea"]["default"]
    # "matched": Earth run keeps the user's water/light/CO2 (isolates radiation)
    # "baseline": Earth run also resets water/light/CO2 to the crop's reference values
    earth_comparison_mode: str = "matched"
    light_intensity: float = 300.0
    temperature: float = 22.0
    humidity: float = 60.0
    water_recycling_efficiency: float = 0.90
    light_spectrum: str = "balanced"
    # Optional reference-flux demand. `None` keeps the crop-relative equation every saved
    # scenario was produced with; a value switches the water module to
    # demand = ET0 x Kc x area x canopy, which is a different basis and is labelled as such
    # in the response rather than silently replacing the old numbers.
    et0_mm_per_day: float | None = None
    crop_coefficient: float | None = None


@dataclass(frozen=True)
class ScenarioResult:
    """Everything the pipeline produced for one environment."""

    label: str
    factors: dict[str, float]
    crop_yield_g: float  # harvested + standing biomass at the end of the run
    growth_rate_g_per_day: float
    water_used_l: float
    water_recovered_l: float
    co2_removed_g: float
    o2_produced_g: float
    harvested_yield_g: float = 0.0  # whole cycles actually harvested
    standing_biomass_g: float = 0.0  # still growing, not yet harvested
    potential_harvest_g: float = 0.0  # what one full cycle yields under these conditions
    water_demand_l: float = 0.0  # what a healthy canopy would have wanted
    water_deficit_l: float = 0.0  # unmet demand (demand - supplied)
    # Which equation produced the water numbers, and the inputs it used. Defaults describe the
    # crop-relative path, so every existing caller reads the same values it did before.
    demand_basis: str = "crop-relative"
    et0_mm_per_day: float | None = None
    crop_coefficient: float | None = None
    daily_growth: list[growth.DailyGrowthPoint] = field(default_factory=list, repr=False)
    daily_water: list[water.DailyWaterPoint] = field(default_factory=list, repr=False)
    daily_gas: list[gas_exchange.DailyGasPoint] = field(default_factory=list, repr=False)


@dataclass(frozen=True)
class SimulationResult:
    crop: CropProfile
    inputs: SimulationInput
    space: ScenarioResult
    earth: ScenarioResult

    # -- comparison helpers --------------------------------------------------
    @property
    def comparison_defined(self) -> bool:
        """False when the Earth reference produced nothing (e.g. no water or no light)."""
        return self.earth.crop_yield_g > 0

    @property
    def space_growth_percentage(self) -> float:
        """
        Space yield as a percentage of the Earth yield (100 = identical).

        When the Earth reference is zero the ratio is undefined; both runs
        producing nothing is reported as "identical" (100) so the UI does not
        show a meaningless -100 %.
        """
        if not self.comparison_defined:
            return 100.0 if self.space.crop_yield_g <= 0 else 0.0
        return 100.0 * self.space.crop_yield_g / self.earth.crop_yield_g

    @property
    def yield_difference_percent(self) -> float:
        """Signed difference, e.g. -16.0 means space yields 16 % less than Earth."""
        return self.space_growth_percentage - 100.0

    @property
    def yield_difference_g(self) -> float:
        return self.space.crop_yield_g - self.earth.crop_yield_g

    @property
    def cycles_completed(self) -> int:
        return self.inputs.simulation_days // self.crop.growth_duration_days

    @property
    def harvest_days(self) -> list[int]:
        """Days inside the window on which the crop is harvested (may be empty)."""
        return growth.harvest_days(self.inputs.simulation_days, self.crop.growth_duration_days)

    @property
    def next_harvest_day(self) -> int:
        """First harvest day after the window ends (the crop still growing at the end)."""
        return growth.next_harvest_day(self.inputs.simulation_days, self.crop.growth_duration_days)

    @property
    def harvest_within_window(self) -> bool:
        return self.cycles_completed > 0

    @property
    def impact(self) -> impact.ImpactBreakdown:
        """Per-driver decomposition of the Earth-vs-space yield difference."""
        return impact.decompose_impact(self.space.factors, self.earth.factors)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def _run_scenario(
    label: str,
    crop: CropProfile,
    radiation: float,
    water_availability: float,
    light_hours: float,
    co2_level: float,
    simulation_days: int,
    growing_area: float,
    light_intensity: float = 300.0,
    temperature: float = 22.0,
    humidity: float = 60.0,
    water_recycling_efficiency: float = 0.90,
    et0_mm_per_day: float | None = None,
    crop_coefficient: float | None = None,
) -> ScenarioResult:
    env = factors.combined_growth_factor(
        crop,
        radiation_mgy_per_day=radiation,
        water_availability_percent=water_availability,
        light_hours=light_hours,
        co2_ppm=co2_level,
        light_intensity=light_intensity,
        temperature=temperature,
        humidity=humidity,
    )

    daily_growth = growth.simulate_growth(crop, env["combined"], simulation_days, growing_area)
    daily_water = water.simulate_water(
        crop,
        daily_growth,
        water_availability_percent=water_availability,
        light_scale=env["light"],
        growing_area_m2=growing_area,
        recovery_efficiency=water_recycling_efficiency,
        demand_scale=(factors.vapor_pressure_deficit(temperature, humidity) /
                      factors.vapor_pressure_deficit(22.0, 60.0)),
        et0_mm_per_day=et0_mm_per_day,
        crop_coefficient=crop_coefficient,
    )
    daily_gas = gas_exchange.simulate_gas_exchange(crop, daily_growth)

    return ScenarioResult(
        label=label,
        factors=env,
        crop_yield_g=growth.total_yield_g(daily_growth),
        harvested_yield_g=growth.harvested_yield_g(daily_growth),
        standing_biomass_g=growth.standing_biomass_g(daily_growth),
        potential_harvest_g=growth.potential_harvest_g(crop, env["combined"], growing_area),
        growth_rate_g_per_day=growth.average_growth_rate_g_per_day(daily_growth),
        water_used_l=water.total_water_used_l(daily_water),
        water_recovered_l=water.total_water_recovered_l(daily_water),
        water_demand_l=water.total_water_demand_l(daily_water),
        water_deficit_l=water.total_water_deficit_l(daily_water),
        co2_removed_g=gas_exchange.total_co2_removed_g(daily_gas),
        o2_produced_g=gas_exchange.total_o2_produced_g(daily_gas),
        demand_basis=water.demand_basis(et0_mm_per_day),
        et0_mm_per_day=et0_mm_per_day,
        crop_coefficient=(crop_coefficient if et0_mm_per_day is not None
                          else None),
        daily_growth=daily_growth,
        daily_water=daily_water,
        daily_gas=daily_gas,
    )


def earth_reference_conditions(params: SimulationInput, crop: CropProfile) -> dict[str, float]:
    """
    Conditions for the Earth comparison run.

    matched  -> background radiation, user's resources kept
    baseline -> background radiation + reference resources
                (100 % water, crop's optimal photoperiod, ambient CO2)

    Gravity is deliberately absent: Phase 30 removed the fractional-gravity response rather than keep
    an invented coefficient, so this comparison isolates radiation and the resource settings and
    nothing else.
    """
    conditions = {
        "radiation": constants.EARTH_BACKGROUND_RADIATION_MGY_PER_DAY,
        "water_availability": params.water_availability,
        "light_hours": params.light_hours,
        "co2_level": params.co2_level,
        "light_intensity": params.light_intensity,
        "temperature": params.temperature,
        "humidity": params.humidity,
        "water_recycling_efficiency": params.water_recycling_efficiency,
        # ET0 describes the site's weather, not the scenario, so both runs use it. The Earth
        # reference answers "same site, background radiation".
        "et0_mm_per_day": params.et0_mm_per_day,
        "crop_coefficient": params.crop_coefficient,
    }
    if params.earth_comparison_mode == "baseline":
        conditions.update(
            water_availability=constants.EARTH_REFERENCE_WATER_AVAILABILITY,
            light_hours=crop.optimal_light_hours,
            co2_level=constants.EARTH_AMBIENT_CO2_PPM,
            light_intensity=300.0,
            temperature=22.0,
            humidity=60.0,
        )
    return conditions


def run_simulation(params: SimulationInput) -> SimulationResult:
    """Run the space scenario and its Earth reference and bundle the results."""
    crop = get_crop(params.crop)

    space = _run_scenario(
        "space",
        crop,
        radiation=params.radiation,
        water_availability=params.water_availability,
        light_hours=params.light_hours,
        co2_level=params.co2_level,
        simulation_days=params.simulation_days,
        growing_area=params.growing_area,
        light_intensity=params.light_intensity,
        temperature=params.temperature,
        humidity=params.humidity,
        water_recycling_efficiency=params.water_recycling_efficiency,
        et0_mm_per_day=params.et0_mm_per_day,
        crop_coefficient=params.crop_coefficient,
    )

    earth_conditions = earth_reference_conditions(params, crop)
    earth = _run_scenario(
        "earth",
        crop,
        simulation_days=params.simulation_days,
        growing_area=params.growing_area,
        **earth_conditions,
    )

    return SimulationResult(crop=crop, inputs=params, space=space, earth=earth)
