"""Phase 6 scientific invariant tests for the simulation engine.

These assert dimensional consistency and mass balance directly, so a future
change to the growth or water maths cannot silently break the physics.
"""
from __future__ import annotations

import math

import pytest

from app.config import simulation_constants as constants
from app.simulation import engine, growth, water
from app.simulation.crops import get_crop, list_crops

CROPS = list_crops()


def run(crop, days, area=1.0, radiation=0.3, water_availability=70.0):
    return engine.run_simulation(engine.SimulationInput(
        crop=crop.key, radiation=radiation,
        water_availability=water_availability, light_hours=16.0, co2_level=1000.0,
        simulation_days=days, growing_area=area,
    ))


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
@pytest.mark.parametrize("days", [1, 7, 30, 35, 60, 90])
def test_mass_balance_identity_holds_every_day(crop, days):
    """cumulative = harvested-through-previous-day + standing, on every day.

    This is the always-true production identity. It is deliberately NOT
    `cumulative == harvested + standing`, which double-counts by one cycle on a
    harvest day (see DailyGrowthPoint's docstring).
    """
    result = run(crop, days)
    for scenario in (result.space, result.earth):
        for point in scenario.daily_growth:
            assert abs(point.mass_balance_residual_g) < 1e-6, (
                f"{crop.key} day {point.day}: residual {point.mass_balance_residual_g}")


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_harvest_day_removes_standing_biomass(crop):
    """On a harvest day the crop is cut, so post-harvest standing is zero."""
    result = run(crop, crop.growth_duration_days * 2)
    harvest_days = [p for p in result.space.daily_growth if p.is_harvest_day]
    assert harvest_days, "a two-cycle run must contain a harvest day"
    for point in harvest_days:
        assert point.post_harvest_standing_g == 0.0
        assert point.biomass_g > 0.0, "the peak must still be visible before cutting"
        assert point.harvested_g >= point.biomass_g - 1e-6


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_post_harvest_standing_equals_standing_off_harvest_days(crop):
    result = run(crop, 60)
    for point in result.space.daily_growth:
        if not point.is_harvest_day:
            assert point.post_harvest_standing_g == pytest.approx(point.biomass_g)


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_growth_is_monotone_within_a_cycle(crop):
    result = run(crop, 90)
    points = result.space.daily_growth
    for a, b in zip(points, points[1:]):
        if a.cycle == b.cycle:
            assert b.biomass_g >= a.biomass_g - 1e-6


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_biomass_is_never_negative(crop):
    for scenario in (run(crop, 90).space, run(crop, 90).earth):
        assert all(p.biomass_g >= -1e-9 for p in scenario.daily_growth)
        assert all(p.cumulative_biomass_g >= -1e-9 for p in scenario.daily_growth)


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_water_conservation(crop):
    """supplied <= demand, deficit = demand - supplied, recovered <= supplied."""
    scenario = run(crop, 60, water_availability=70.0).space
    for point in scenario.daily_water:
        assert point.water_used_l <= point.water_demand_l + 1e-9
        assert point.water_deficit_l >= -1e-9
        assert (point.water_demand_l - point.water_deficit_l) == pytest.approx(point.water_used_l)
        assert point.water_recovered_l <= point.water_used_l + 1e-9


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_no_transpiration_demand_at_planting(crop):
    scenario = run(crop, 10).space
    assert scenario.daily_water[0].water_demand_l == 0.0


def test_water_supply_is_bounded_by_availability():
    crop = get_crop("lettuce")
    full = run(crop, 40, water_availability=100.0).space
    half = run(crop, 40, water_availability=50.0).space
    assert half.water_used_l < full.water_used_l
    assert half.water_deficit_l > 0.0
    assert full.water_deficit_l == pytest.approx(0.0)


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_oxygen_carbon_stoichiometry(crop):
    """O2 released per CO2 fixed must equal the 32/44 molar mass ratio."""
    scenario = run(crop, 90).space
    if scenario.co2_removed_g > 0:
        assert scenario.o2_produced_g / scenario.co2_removed_g == pytest.approx(
            constants.O2_PER_CO2_MASS_RATIO, rel=1e-9)


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_carbon_mass_balance_from_dry_matter(crop):
    """CO2 fixed must reconcile with WHOLE-PLANT dry mass.

    Roots, stems and inedible leaves also fix carbon, so the life-support balance
    uses total biomass (edible / harvest index), not the edible yield. Using the
    edible yield here would under-count CO2 uptake by 1/harvest_index.
    """
    scenario = run(crop, 90, area=1.0).space
    total_biomass_g = scenario.crop_yield_g / crop.harvest_index
    dry_mass_g = total_biomass_g * crop.dry_matter_fraction
    expected_co2 = dry_mass_g * constants.CARBON_FRACTION_OF_DRY_MASS * constants.CO2_PER_CARBON_MASS_RATIO
    assert scenario.co2_removed_g == pytest.approx(expected_co2, rel=1e-6)


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_harvest_index_consistency(crop):
    """Edible biomass per m^2 equals total biomass times the harvest index."""
    assert crop.total_biomass_g == pytest.approx(
        crop.harvest_biomass_g / crop.harvest_index, rel=1e-12)
    assert 0.0 < crop.harvest_index <= 1.0


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_area_scaling_is_linear(crop):
    """Yield must scale linearly with growing area (no hidden area constants)."""
    one = run(crop, 60, area=1.0).space.crop_yield_g
    ten = run(crop, 60, area=10.0).space.crop_yield_g
    assert ten == pytest.approx(one * 10.0, rel=1e-9)


@pytest.mark.parametrize("crop", CROPS, ids=lambda c: c.key)
def test_earth_reference_never_worse_than_space(crop):
    """Under equal resources, the Earth reference must not yield less."""
    result = run(crop, 90, radiation=0.3)
    assert result.earth.crop_yield_g >= result.space.crop_yield_g - 1e-6


def test_growth_factor_bounds():
    crop = get_crop("lettuce")
    earth = run(crop, 30, radiation=0.01, water_availability=100.0)
    for key, value in earth.space.factors.items():
        if key == "combined":
            continue
        assert 0.0 <= value <= 1.5, f"{key} outside a plausible bounded range: {value}"


def test_relative_humidity_affects_water_demand():
    """Higher VPD (drier air) must increase demand, not decrease it."""
    dry = engine.run_simulation(engine.SimulationInput(
        crop="lettuce", radiation=0.01, water_availability=100.0,
        light_hours=16.0, co2_level=1000.0, simulation_days=35, growing_area=1.0,
        temperature=28.0, humidity=30.0,
    )).space
    humid = engine.run_simulation(engine.SimulationInput(
        crop="lettuce", radiation=0.01, water_availability=100.0,
        light_hours=16.0, co2_level=1000.0, simulation_days=35, growing_area=1.0,
        temperature=28.0, humidity=85.0,
    )).space
    assert dry.water_demand_l >= humid.water_demand_l


def test_all_reported_quantities_are_finite():
    for crop in CROPS:
        result = run(crop, 90, area=2.5)
        for scenario in (result.space, result.earth):
            for value in (scenario.crop_yield_g, scenario.water_used_l,
                          scenario.co2_removed_g, scenario.o2_produced_g,
                          scenario.harvested_yield_g, scenario.standing_biomass_g,
                          scenario.water_demand_l, scenario.water_deficit_l):
                assert math.isfinite(value)
