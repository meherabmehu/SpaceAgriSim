"""
Turns engine dataclasses into API response models.

Keeping this separate means the engine stays free of Pydantic and the API
shape can evolve without touching the maths.
"""

from __future__ import annotations

from app.config import simulation_constants as constants
from app.models.simulation import (
    ComparisonSummary,
    CropSummary,
    DailyGrowthEntry,
    DailyLifeSupportEntry,
    DailyWaterEntry,
    GrowthFactors,
    HarvestSummary,
    ImpactFactor,
    ImpactSummary,
    LifeSupportContext,
    ScenarioSummary,
    SimulationRequest,
    SimulationResponse,
    WaterBalance,
)
from app.simulation import gas_exchange
from app.simulation.engine import ScenarioResult, SimulationResult

PHASE_1_DISCLAIMER = (
    "Phase 1 mathematical prototype. Outputs are based on documented simulation "
    "assumptions, not on validated NASA data or predictions."
)


def _r(value: float, digits: int = 2) -> float:
    return round(value, digits)


def _scenario_summary(scenario: ScenarioResult) -> ScenarioSummary:
    return ScenarioSummary(
        cropYield=_r(scenario.crop_yield_g, 1),
        harvestedYield=_r(scenario.harvested_yield_g, 1),
        standingBiomass=_r(scenario.standing_biomass_g, 1),
        potentialHarvest=_r(scenario.potential_harvest_g, 1),
        growthRate=_r(scenario.growth_rate_g_per_day, 2),
        waterUsed=_r(scenario.water_used_l, 2),
        waterRecovered=_r(scenario.water_recovered_l, 2),
        waterDemand=_r(scenario.water_demand_l, 2),
        waterDeficit=_r(scenario.water_deficit_l, 2),
        co2Removed=_r(scenario.co2_removed_g, 1),
        estimatedOxygenProduced=_r(scenario.o2_produced_g, 1),
        factors=GrowthFactors(**{k: _r(v, 4) for k, v in scenario.factors.items()}),
    )


def _daily_growth(result: SimulationResult) -> list[DailyGrowthEntry]:
    entries = []
    for earth, space in zip(result.earth.daily_growth, result.space.daily_growth):
        entries.append(
            DailyGrowthEntry(
                day=space.day,
                cycle=space.cycle,
                earthBiomass=_r(earth.biomass_g, 1),
                spaceBiomass=_r(space.biomass_g, 1),
                earthCumulative=_r(earth.cumulative_biomass_g, 1),
                spaceCumulative=_r(space.cumulative_biomass_g, 1),
                earthHarvested=_r(earth.harvested_g, 1),
                spaceHarvested=_r(space.harvested_g, 1),
                isHarvestDay=space.is_harvest_day,
                dayInCycle=space.day_in_cycle,
                growthFraction=_r(space.growth_fraction, 4),
            )
        )
    return entries


def _impact_summary(result: SimulationResult) -> ImpactSummary:
    breakdown = result.impact
    return ImpactSummary(
        factors=[
            ImpactFactor(
                key=step.key,
                label=step.label,
                spaceFactor=_r(step.space_factor, 4),
                earthFactor=_r(step.earth_factor, 4),
                percent=_r(step.percent, 1),
                responsePercent=_r(step.response_percent, 1),
                contributionPoints=_r(step.contribution_points, 1),
                runningPercent=_r(step.running_percent, 1),
            )
            for step in breakdown.steps
        ],
        combinedPercent=_r(breakdown.combined_percent, 1),
        limitingFactor=breakdown.limiting_factor,
        boostingFactor=breakdown.boosting_factor,
    )


def _harvest_summary(result: SimulationResult) -> HarvestSummary:
    space = result.space
    days = result.inputs.simulation_days
    harvest_days = result.harvest_days
    # every cycle runs under the same conditions, so each harvest equals the potential harvest
    last_harvest = space.potential_harvest_g if harvest_days else 0.0
    return HarvestSummary(
        standingBiomass=_r(space.standing_biomass_g, 1),
        harvestedYield=_r(space.harvested_yield_g, 1),
        lastHarvestYield=_r(last_harvest, 1),
        lastHarvestDay=harvest_days[-1] if harvest_days else None,
        cumulativeBiomass=_r(space.crop_yield_g, 1),
        potentialHarvest=_r(space.potential_harvest_g, 1),
        cycleLengthDays=result.crop.growth_duration_days,
        cyclesCompleted=result.cycles_completed,
        harvestDays=harvest_days,
        nextHarvestDay=result.next_harvest_day,
        daysUntilNextHarvest=result.next_harvest_day - days,
        harvestWithinWindow=result.harvest_within_window,
        simulationDays=days,
    )


def _daily_water(scenario: ScenarioResult) -> list[DailyWaterEntry]:
    return [
        DailyWaterEntry(
            day=p.day,
            waterUsed=_r(p.water_used_l, 3),
            waterRecovered=_r(p.water_recovered_l, 3),
            cumulativeWaterUsed=_r(p.cumulative_water_used_l, 2),
            cumulativeWaterRecovered=_r(p.cumulative_water_recovered_l, 2),
            waterDemand=_r(p.water_demand_l, 3),
            waterDeficit=_r(p.water_deficit_l, 3),
            cumulativeWaterDemand=_r(p.cumulative_water_demand_l, 2),
            cumulativeWaterDeficit=_r(p.cumulative_water_deficit_l, 2),
        )
        for p in scenario.daily_water
    ]


def _water_balance(scenario: ScenarioResult, efficiency: float = 0.9) -> WaterBalance:
    demand = scenario.water_demand_l
    return WaterBalance(
        demand=_r(demand, 2),
        supplied=_r(scenario.water_used_l, 2),
        deficit=_r(scenario.water_deficit_l, 2),
        recovered=_r(scenario.water_recovered_l, 2),
        netConsumed=_r(scenario.water_used_l - scenario.water_recovered_l, 2),
        recoveryEfficiency=efficiency,
        deficitPercent=_r(100.0 * scenario.water_deficit_l / demand if demand > 0 else 0.0, 1),
    )


def _daily_life_support(scenario: ScenarioResult) -> list[DailyLifeSupportEntry]:
    entries = []
    for w, g in zip(scenario.daily_water, scenario.daily_gas):
        entries.append(
            DailyLifeSupportEntry(
                day=w.day,
                waterUsed=_r(w.water_used_l, 3),
                waterRecovered=_r(w.water_recovered_l, 3),
                co2Removed=_r(g.co2_removed_g, 2),
                o2Produced=_r(g.o2_produced_g, 2),
                cumulativeWaterUsed=_r(w.cumulative_water_used_l, 2),
                cumulativeWaterRecovered=_r(w.cumulative_water_recovered_l, 2),
                cumulativeCo2Removed=_r(g.cumulative_co2_removed_g, 1),
                cumulativeO2Produced=_r(g.cumulative_o2_produced_g, 1),
                waterDemand=_r(w.water_demand_l, 3),
                waterDeficit=_r(w.water_deficit_l, 3),
                cumulativeWaterDemand=_r(w.cumulative_water_demand_l, 2),
                cumulativeWaterDeficit=_r(w.cumulative_water_deficit_l, 2),
            )
        )
    return entries


def to_response(result: SimulationResult, request: SimulationRequest) -> SimulationResponse:
    space = result.space
    from app.simulation.factors import vapor_pressure_deficit
    warnings = ["Growth, water and gas outputs are uncalibrated mathematical estimates; no empirical confidence interval is available."]
    if request.gravity < 1:
        warnings.append("Reduced-gravity response is an assumed penalty, not a lunar or Martian crop measurement.")
    if request.lightSpectrum != "balanced":
        warnings.append("Spectrum is recorded as a scenario annotation; no validated spectrum response is available.")
    if request.et0MmPerDay is not None:
        kc = (request.cropCoefficient if request.cropCoefficient is not None
              else constants.DEFAULT_CROP_COEFFICIENT)
        warnings.append(
            f"Water demand was computed from a reference ET0 of {request.et0MmPerDay:.2f} mm/day "
            f"with Kc = {kc:.2f}. ET0 is a computed standard for a reference grass surface, not a "
            "measurement of this crop's water use, and Kc = 1.0 describes that reference surface "
            "rather than a crop-specific coefficient.")
    if request.co2Level > constants.CO2_MEASURED_OPTIMUM_PPM:
        warnings.append(
            f"Above {constants.CO2_MEASURED_OPTIMUM_PPM:.0f} ppm CO2 the model still predicts a small yield gain, but NASA "
            "closed-chamber soybean data show yield peaking near 1000 ppm and declining at 2000-5000 ppm (NTRS 20040090155). "
            "No supraoptimal penalty is modelled, so treat these settings as an upper bound, not a prediction.")
    return SimulationResponse(
        provenance={"mode": "physics-based estimate", "modelVersion": "assumptions-2.0",
                    "nasaValidated": False, "confidenceInterval": None,
                    "uncertainty": "Not quantified; parameter sensitivity is not a confidence interval.",
                    "sources": ["Documented simulator assumptions", "Biomass carbon stoichiometry"]},
        warnings=warnings,
        stress={"limitingFactor": min((k for k in space.factors if k != "combined"), key=lambda k: space.factors[k]),
                "factors": {k: round(max(0, 1-v),4) for k,v in space.factors.items() if k != "combined"},
                "method": "assumed response-factor deficits, not a trained health classifier"},
        environment={"vaporPressureDeficitKpa": round(vapor_pressure_deficit(request.temperature, request.humidity), 3),
                     "dailyLightIntegralMolM2": round(request.lightIntensity * request.lightHours * 0.0036, 3),
                     "spectrumMode": "annotation only"},
        cropYield=_r(space.crop_yield_g, 1),
        growthRate=_r(space.growth_rate_g_per_day, 2),
        waterUsed=_r(space.water_used_l, 2),
        waterRecovered=_r(space.water_recovered_l, 2),
        co2Removed=_r(space.co2_removed_g, 1),
        estimatedOxygenProduced=_r(space.o2_produced_g, 1),
        spaceGrowthPercentage=_r(result.space_growth_percentage, 1),
        crop=CropSummary(
            key=result.crop.key,
            name=result.crop.name,
            emoji=result.crop.emoji,
            growthDurationDays=result.crop.growth_duration_days,
            harvestBiomassG=result.crop.harvest_biomass_g,
            cyclesCompleted=result.cycles_completed,
        ),
        inputs=request,
        space=_scenario_summary(space),
        earth=_scenario_summary(result.earth),
        comparison=ComparisonSummary(
            earthYield=_r(result.earth.crop_yield_g, 1),
            spaceYield=_r(space.crop_yield_g, 1),
            differenceGrams=_r(result.yield_difference_g, 1),
            differencePercent=_r(result.yield_difference_percent, 1),
            spaceGrowthPercentage=_r(result.space_growth_percentage, 1),
            earthComparisonMode=request.earthComparisonMode,
            isDefined=result.comparison_defined,
            # no decomposition when the Earth reference produced nothing:
            # the percentages would describe a gap that does not exist
            impact=_impact_summary(result) if result.comparison_defined else None,
        ),
        harvest=_harvest_summary(result),
        lifeSupport=LifeSupportContext(
            crewO2DaysSupported=_r(gas_exchange.crew_o2_days_supported(space.o2_produced_g), 2),
            crewCo2DaysRemoved=_r(gas_exchange.crew_co2_days_removed(space.co2_removed_g), 2),
            waterRecoveryEfficiency=request.waterRecyclingEfficiency / 100.0,
            water=_water_balance(space, request.waterRecyclingEfficiency / 100.0),
        ),
        dailyGrowthData=_daily_growth(result),
        dailyWaterData=_daily_water(space),
        dailyLifeSupportData=_daily_life_support(space),
        demandBasis=_demand_basis(space, request),
        disclaimer=PHASE_1_DISCLAIMER,
    )


def _demand_basis(space: ScenarioResult, request: SimulationRequest) -> dict:
    """Name the equation behind the water numbers, with the inputs it used.

    Additive: callers that ignore this field see exactly the response they saw before, and
    `basis` is always present so the default path is never ambiguous.
    """
    if space.et0_mm_per_day is None:
        return {
            "basis": "crop-relative",
            "description": ("Daily demand = crop peak litres per m^2 x area x light factor x "
                            "canopy cover. The simulator's own assumption, unchanged."),
            "equation": "peak_water_l_per_day x area x lightScale x canopyScale",
            "et0MmPerDay": None,
            "cropCoefficient": None,
            "evidence": "assumed crop parameter, not a measurement",
        }
    return {
        "basis": "et0-reference",
        "description": ("Daily demand = ET0 x Kc x area x canopy cover. ET0 already contains "
                        "the site's radiation and humidity, so the light and VPD scales are not "
                        "applied again on this path."),
        "equation": "et0_mm_per_day x crop_coefficient x area_m2 x canopyScale",
        "et0MmPerDay": space.et0_mm_per_day,
        "cropCoefficient": (space.crop_coefficient
                            if space.crop_coefficient is not None
                            else constants.DEFAULT_CROP_COEFFICIENT),
        "cropCoefficientSource": ("caller-supplied" if space.crop_coefficient is not None
                                  else "default (1.0 = reference surface, not a crop)"),
        "litresPerMmPerM2": constants.ET0_MM_PER_M2_TO_LITRES,
        "evidence": ("ET0 is a computed standard (FAO-56) or a surrogate of one; the resulting "
                     "litre figure is a demand estimate, not a measurement"),
    }
