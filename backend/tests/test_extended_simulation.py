import math
import pytest
from app.simulation.factors import vapor_pressure_deficit


def estimate(client, **values):
    response=client.post("/api/simulate",json=values)
    assert response.status_code == 200, response.text
    return response.json()


def test_light_temperature_and_humidity_have_real_effects(client):
    base=estimate(client)
    dark=estimate(client,lightIntensity=0)
    hot=estimate(client,temperature=40)
    dry=estimate(client,humidity=10)
    assert dark["cropYield"] == 0
    assert hot["cropYield"] < base["cropYield"]
    assert dry["waterUsed"] > base["waterUsed"]
    assert base["environment"]["dailyLightIntegralMolM2"] == pytest.approx(17.28)
    assert base["environment"]["vaporPressureDeficitKpa"] == pytest.approx(1.058,abs=.002)
    assert base["provenance"]["confidenceInterval"] is None
    assert base["provenance"]["nasaValidated"] is False


def test_recycling_changes_makeup_without_changing_growth(client):
    low=estimate(client,waterRecyclingEfficiency=0)
    # 98 % is the ceiling, not 100 %: it is what the ISS has actually demonstrated. The endpoint
    # refuses a higher value rather than letting a scenario claim a closure nobody has achieved.
    high=estimate(client,waterRecyclingEfficiency=98)
    assert low["cropYield"] == high["cropYield"]
    assert low["waterRecovered"] == 0
    # the endpoint rounds recovered water to 2 dp, so compare at that precision
    assert high["waterRecovered"] == pytest.approx(high["waterUsed"] * 0.98, abs=0.02)
    assert high["lifeSupport"]["waterRecoveryEfficiency"] == pytest.approx(0.98)
    assert high["lifeSupport"]["water"]["netConsumed"] > 0


def test_recovery_above_the_demonstrated_maximum_is_refused(client):
    response = client.post("/api/simulate", json={"waterRecyclingEfficiency": 100})
    assert response.status_code == 422
    assert "waterRecyclingEfficiency" in response.json()["fields"]


def test_spectrum_is_annotated_without_fabricated_response(client):
    balanced=estimate(client,lightSpectrum="balanced")
    red=estimate(client,lightSpectrum="red-blue")
    assert balanced["cropYield"] == red["cropYield"]
    assert any("annotation" in w for w in red["warnings"])


def test_extended_validation_rejects_unknown_inputs_and_bounds(client):
    for inputs in ({"lightIntensity":1001},{"temperature":41},{"humidity":101},
                   {"waterRecyclingEfficiency":101},{"lightSpectrum":"ultraviolet"},
                   {"madeUpFeature":1}):
        assert client.post("/api/simulate",json=inputs).status_code == 422


def test_baseline_comparison_decomposition_includes_extended_inputs(client):
    result=estimate(client,earthComparisonMode="baseline",temperature=32,humidity=30,lightIntensity=100)
    impact=result["comparison"]["impact"]
    keys={step["key"] for step in impact["factors"]}
    assert {"intensity","temperature","humidity"} <= keys
    assert impact["combinedPercent"] == pytest.approx(result["comparison"]["differencePercent"],abs=.2)


def test_vpd_is_zero_at_saturation_and_increases_with_temperature():
    assert vapor_pressure_deficit(22,100)==0
    assert vapor_pressure_deficit(30,60)>vapor_pressure_deficit(22,60)>0


def test_water_balance_is_bounded_and_conserved_in_accounting(client):
    result=estimate(client,waterAvailability=63,waterRecyclingEfficiency=81,simulationDays=30)
    water=result["lifeSupport"]["water"]
    assert water["demand"] == pytest.approx(water["supplied"] + water["deficit"], abs=1e-8)
    assert 0 <= water["recovered"] <= water["supplied"]
    assert water["netConsumed"] == pytest.approx(water["supplied"] - water["recovered"], abs=1e-8)


def test_all_public_life_support_outputs_are_finite_and_nonnegative(client):
    result=estimate(client,gravity=.38,radiation=1.2,waterAvailability=47,lightHours=18,co2Level=900,simulationDays=90)
    for value in [
        result["cropYield"], result["space"]["harvestedYield"], result["space"]["standingBiomass"],
        result["waterUsed"], result["waterRecovered"], result["co2Removed"], result["estimatedOxygenProduced"],
    ]:
        assert math.isfinite(value) and value >= 0
