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
    high=estimate(client,waterRecyclingEfficiency=100)
    assert low["cropYield"] == high["cropYield"]
    assert low["waterRecovered"] == 0
    assert high["lifeSupport"]["water"]["netConsumed"] == 0
    assert high["waterRecovered"] == high["waterUsed"]
    assert high["lifeSupport"]["waterRecoveryEfficiency"] == 1


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
