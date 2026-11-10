"""Phase 27: simulation engine integrity, checked mechanically rather than by reading the code.

The brief asks whether inputs affect actual calculations, whether units are consistent, whether
reference ET0 is ever presented as measured crop consumption, and whether water, nutrient,
radiation and growth outputs stay distinct. Each of those is a property that can be tested, so it
is tested here instead of being asserted in a document.

The single most valuable test in this file is `test_every_input_changes_at_least_one_output`: a
control that silently does nothing is the most common way a simulation UI lies, and it is invisible
to every other kind of test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import simulation_constants as constants  # noqa: E402
from app.models.simulation import SimulationRequest  # noqa: E402
from app.simulation import crops, growth, water  # noqa: E402
from app.simulation.engine import SimulationInput, run_simulation  # noqa: E402
from app.simulation.serializers import to_response  # noqa: E402

BASE = {
    "crop": "lettuce", "radiation": 0.3, "waterAvailability": 100,
    "lightHours": 16, "co2Level": 1000, "simulationDays": 30, "growingArea": 10,
    "earthComparisonMode": "matched", "lightIntensity": 300, "temperature": 22,
    "humidity": 60, "lightSpectrum": "balanced", "waterRecyclingEfficiency": 90,
}

WATCHED = (
    "cropYield", "growthRate", "waterUsed", "waterRecovered", "co2Removed",
    "estimatedOxygenProduced", "spaceGrowthPercentage", "space", "earth", "comparison",
    "harvest", "lifeSupport", "dailyGrowthData", "dailyWaterData", "stress", "environment",
    "warnings", "demandBasis",
)


def simulate(**overrides):
    request = SimulationRequest(**{**BASE, **overrides})
    params = SimulationInput(
        crop=request.crop, radiation=request.radiation,
        water_availability=request.waterAvailability, light_hours=request.lightHours,
        co2_level=request.co2Level, simulation_days=request.simulationDays,
        growing_area=request.growingArea, earth_comparison_mode=request.earthComparisonMode,
        light_intensity=request.lightIntensity, temperature=request.temperature,
        humidity=request.humidity, light_spectrum=request.lightSpectrum,
        water_recycling_efficiency=request.waterRecyclingEfficiency / 100.0,
        et0_mm_per_day=request.et0MmPerDay, crop_coefficient=request.cropCoefficient,
    )
    return to_response(run_simulation(params), request).model_dump()


# ---------------------------------------------------------------------------------------
# 1. every input must reach a calculation
# ---------------------------------------------------------------------------------------
ALTERNATIVES = {
    "crop": "tomato", "radiation": 1.5, "waterAvailability": 40,
    "lightHours": 12, "co2Level": 2000, "simulationDays": 45, "growingArea": 25,
    "earthComparisonMode": "baseline", "lightIntensity": 600, "temperature": 30,
    "humidity": 85, "waterRecyclingEfficiency": 60, "lightSpectrum": "red-blue",
    "et0MmPerDay": 4.5,
}

# The only input permitted to change nothing but the warnings. It is permitted because no
# validated spectrum response exists, and the warning says exactly that.
ANNOTATION_ONLY = {"lightSpectrum": {"warnings"}}


@pytest.fixture(scope="module")
def baseline() -> dict:
    return simulate()


@pytest.mark.parametrize("field", sorted(ALTERNATIVES))
def test_every_input_changes_at_least_one_output(field, baseline):
    changed = simulate(**{field: ALTERNATIVES[field]})
    differing = {
        name for name in WATCHED
        if json.dumps(baseline.get(name), sort_keys=True, default=str)
        != json.dumps(changed.get(name), sort_keys=True, default=str)
    }
    assert differing, f"{field} changed nothing: the control is decorative"
    if field in ANNOTATION_ONLY:
        assert differing == ANNOTATION_ONLY[field], (
            f"{field} now affects {sorted(differing)}; it is documented as an annotation only, "
            "so either the documentation or the code is wrong")


def test_the_spectrum_warning_says_no_response_is_inferred():
    payload = simulate(lightSpectrum="red-blue")
    assert any("no validated spectrum response" in warning for warning in payload["warnings"])


# ---------------------------------------------------------------------------------------
# 2. units
# ---------------------------------------------------------------------------------------
def test_one_millimetre_over_one_square_metre_is_one_litre():
    """The conversion every water number depends on."""
    assert constants.ET0_MM_PER_M2_TO_LITRES == 1.0
    one_litre = water.et0_reference_demand_l(1.0, 1.0, 1.0, 1.0)
    # canopy scale is 1.0 at full cover; seedling fraction applies only below it
    assert one_litre == pytest.approx(1.0)


def test_demand_scales_linearly_with_area_and_reference_flux():
    # Signature is (et0_mm_per_day, crop_coefficient, growth_fraction, growing_area_m2). An earlier
    # version of this test passed them in a different order and "passed" a comparison that meant
    # nothing, which is why the signature is written out here.
    for area in (1.0, 10.0, 100.0):
        assert water.et0_reference_demand_l(4.0, 1.0, 1.0, area) == pytest.approx(4.0 * area)
    assert water.et0_reference_demand_l(8.0, 1.0, 1.0, 10.0) == pytest.approx(
        2 * water.et0_reference_demand_l(4.0, 1.0, 1.0, 10.0))


def test_full_canopy_demand_equals_flux_times_area():
    """At growth fraction 1.0 the canopy scale is exactly 1.0, so the identity must be exact."""
    assert water.et0_reference_demand_l(4.0, 1.0, 1.0, 10.0) == pytest.approx(40.0)


def test_a_seedling_uses_the_documented_seedling_fraction():
    """At growth fraction 0.0 the demand must be the seedling activity fraction of full cover."""
    seedling = constants.SEEDLING_ACTIVITY_FRACTION
    assert water.et0_reference_demand_l(4.0, 1.0, 0.0, 10.0) == pytest.approx(40.0 * seedling)


def test_canopy_scale_never_leaves_the_unit_interval():
    lettuce = crops.get_crop("lettuce")
    for day in range(0, 36):
        progress = growth.logistic_progress(day, 35)
        assert 0.0 <= progress <= 1.0
        demand = water.daily_water_demand_l(lettuce, progress, 1.0, 1.0)
        assert 0.0 < demand <= lettuce.peak_water_l_per_day


def test_the_two_demand_paths_are_labelled_and_never_confused():
    assert water.demand_basis(None) == "crop-relative"
    assert water.demand_basis(4.0) == "et0-reference"
    crop_relative = simulate()
    reference = simulate(et0MmPerDay=6.0)
    assert crop_relative["demandBasis"]["basis"] == "crop-relative"
    assert reference["demandBasis"]["basis"] == "et0-reference"
    assert crop_relative["demandBasis"]["evidence"] != reference["demandBasis"]["evidence"]


# ---------------------------------------------------------------------------------------
# 3. reference ET0 is not presented as measured crop consumption
# ---------------------------------------------------------------------------------------
def test_the_et0_path_warns_that_it_is_not_a_measurement():
    payload = simulate(et0MmPerDay=5.0)
    joined = " ".join(payload["warnings"])
    assert "not a measurement of this crop's water use" in joined
    assert "reference grass surface" in joined


def test_the_default_crop_coefficient_is_described_as_a_reference_surface():
    payload = simulate(et0MmPerDay=5.0)
    assert payload["demandBasis"]["cropCoefficientSource"].startswith("default")
    assert "not a crop" in payload["demandBasis"]["cropCoefficientSource"]


def test_a_caller_supplied_coefficient_is_labelled_as_such():
    payload = simulate(et0MmPerDay=5.0, cropCoefficient=0.9)
    assert payload["demandBasis"]["cropCoefficientSource"] == "caller-supplied"
    assert payload["demandBasis"]["cropCoefficient"] == pytest.approx(0.9)


def test_no_response_field_calls_reference_et0_a_measurement():
    payload = simulate(et0MmPerDay=5.0)
    text = json.dumps(payload).lower()
    assert "measured crop water use" not in text
    assert payload["provenance"]["nasaValidated"] is False


# ---------------------------------------------------------------------------------------
# 4. water, growth, radiation and nutrient stay distinct
# ---------------------------------------------------------------------------------------
def test_changing_the_water_basis_does_not_change_the_growth_output():
    """Two calculations, two meanings: water demand must not feed back into biomass here."""
    crop_relative = simulate()
    reference = simulate(et0MmPerDay=6.0)
    assert crop_relative["cropYield"] == reference["cropYield"]
    assert crop_relative["waterUsed"] != reference["waterUsed"]


def test_water_and_gas_outputs_are_separate_fields_with_separate_units():
    payload = simulate()
    assert {"waterUsed", "waterRecovered", "co2Removed", "estimatedOxygenProduced",
            "cropYield"} <= set(payload)
    for name in ("waterUsed", "waterRecovered", "co2Removed", "estimatedOxygenProduced",
                 "cropYield"):
        assert isinstance(payload[name], (int, float))


def test_gravity_is_no_longer_an_input_at_all():
    """Phase 30 removed the fractional-gravity response; this is the anti-regression test.

    The old placeholder penalty (15 % growth lost at 0 g) had no measurement behind it. If a
    future change reintroduces a gravity term it must fail here rather than reappear silently.
    """
    with pytest.raises(Exception) as excinfo:
        SimulationRequest(**{**BASE, "gravity": 0.38})
    assert "gravity was removed in Phase 30" in str(excinfo.value)
    earth = simulate(radiation=0.01)
    mars_radiation = simulate(radiation=0.2)
    assert mars_radiation["cropYield"] < earth["cropYield"]
    assert "gravity" not in earth and "gravity" not in earth["inputs"]


def test_radiation_alone_does_not_move_the_water_numbers():
    low = simulate()
    high = simulate(radiation=1.5)
    assert low["waterUsed"] == pytest.approx(high["waterUsed"])
    assert low["cropYield"] != high["cropYield"]


# ---------------------------------------------------------------------------------------
# 5. unsupported conditions are exposed, and incoherent input is refused
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("overrides,expected", [
    ({"co2Level": 3000}, "supraoptimal"),
    ({"lightSpectrum": "red-blue"}, "annotation"),
])
def test_unsupported_conditions_raise_a_specific_warning(overrides, expected):
    payload = simulate(**overrides)
    assert any(expected.lower() in warning.lower() for warning in payload["warnings"])


def test_biomass_output_carries_a_no_confidence_interval_statement():
    payload = simulate()
    assert payload["provenance"]["confidenceInterval"] is None
    assert "not quantified" in payload["provenance"]["uncertainty"].lower()


@pytest.mark.parametrize("overrides", [
    {"temperature": 42}, {"temperature": -5}, {"humidity": 101}, {"growingArea": 0},
    {"simulationDays": 0}, {"lightIntensity": -1}, {"waterRecyclingEfficiency": 120},
])
def test_impossible_inputs_are_refused_before_they_reach_the_engine(overrides):
    with pytest.raises(Exception):
        simulate(**overrides)


def test_zero_water_produces_no_yield_rather_than_an_error():
    payload = simulate(waterAvailability=0)
    assert payload["cropYield"] == 0.0


# ---------------------------------------------------------------------------------------
# 6. one definition per formula
# ---------------------------------------------------------------------------------------
def test_the_vapour_pressure_deficit_has_a_single_definition():
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "def vapor_pressure_deficit", "backend/app"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert len([line for line in result.stdout.splitlines() if line.strip()]) == 1


def test_the_harvest_formula_has_a_single_definition():
    """Found duplicated in Phase 27: simulate_growth repeated potential_harvest_g() inline."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "harvest_biomass_g \\* growth_factor \\* growing_area_m2", "backend/app"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    assert len([line for line in result.stdout.splitlines() if line.strip()]) == 1


def test_simulate_growth_and_the_helper_agree_exactly():
    lettuce = crops.get_crop("lettuce")
    expected = growth.potential_harvest_g(lettuce, 0.8, 10.0)
    points = growth.simulate_growth(lettuce, 0.8, 70, 10.0)
    harvested = {point.harvested_g for point in points}
    assert expected in harvested


def test_the_canopy_scale_is_defined_once_in_the_water_module():
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "SEEDLING_ACTIVITY_FRACTION", "backend/app"],
        cwd=REPO_ROOT, capture_output=True, text=True).stdout
    users = [line for line in result.splitlines() if "water.py" in line]
    assert len(users) == 2, "the two water paths should share the one constant"
