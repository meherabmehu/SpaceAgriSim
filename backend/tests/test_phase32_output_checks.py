"""Phase 32: output plausibility, the layer the Phase 27 audit found systematically missing.

The audit's finding was that `uncertainty` and `outputCheck` were the weakest layers across the
product - "the two that stand between a number and a defensible number". These tests cover the
output checks added in Phase 32:

* reference ET0 returns a plausibility verdict with its value, and never a clamped one;
* the VPD and light numbers the simulator emits carry an explicit statement of what they are;
* /api/simulate returns machine-readable units for every headline scalar.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import et0
from app.main import app

client = TestClient(app)

DAY = {"latitude": 23.8, "dayOfYear": 60, "relativeHumidityPct": 60}


# ------------------------------------------------------------------ reference ET0


def test_a_normal_day_is_plausible():
    body = client.get("/api/reference-et0/validate", params={"tmaxC": 30, "tminC": 18, **DAY}).json()
    assert body["outputCheck"]["plausible"] is True
    assert body["outputCheck"]["failures"] == []
    assert 0 <= body["et0MmPerDay"] <= body["outputCheck"]["physicalCeilingMmPerDay"]


def test_inverted_temperatures_fail_the_check_instead_of_being_quietly_used():
    body = client.get("/api/reference-et0/validate", params={"tmaxC": 18, "tminC": 30, **DAY}).json()
    assert body["outputCheck"]["plausible"] is False
    assert any("tmaxC is below tminC" in failure for failure in body["outputCheck"]["failures"])


def test_an_impossible_flux_is_reported_not_clamped():
    """A 40 mm/day reference ET0 means the inputs are wrong; the value must say so."""
    body = client.get("/api/reference-et0/validate", params={
        "tmaxC": 45, "tminC": 10, "latitude": 0, "dayOfYear": 80,
        "relativeHumidityPct": 5, "solarRadiationMJm2": 50, "windSpeedMs": 70}).json()
    assert body["outputCheck"]["plausible"] is False
    assert body["et0MmPerDay"] > body["outputCheck"]["physicalCeilingMmPerDay"]
    assert "physical ceiling" in body["outputCheck"]["failures"][0]


def test_the_ceiling_is_a_declared_constant_not_a_magic_number():
    assert et0.MAX_PLAUSIBLE_ET0_MM == 30.0
    body = client.get("/api/reference-et0/validate", params={"tmaxC": 30, "tminC": 18, **DAY}).json()
    assert str(et0.MAX_PLAUSIBLE_ET0_MM) in body["outputCheck"]["rule"]
    assert "clamped" in body["outputCheck"]["rule"]


def test_the_estimate_endpoint_carries_the_same_gate():
    body = client.get("/api/reference-et0/estimate",
                      params={"tmaxC": 30, "tminC": 18, **DAY}).json()
    assert body["outputCheck"]["plausible"] is True
    assert body["primaryMethod"] == "hargreaves"  # no radiation or wind supplied


def test_the_whole_day_can_be_validated_as_a_payload_too():
    """A day read from a file is a payload, and a batch of days needs a post route."""
    good = client.post("/api/reference-et0/validate", json={
        "tmaxC": 30, "tminC": 18, "latitude": 23.8, "dayOfYear": 60,
        "relativeHumidityPct": 60})
    assert good.status_code == 200
    assert good.json()["outputCheck"]["plausible"] is True
    bad = client.post("/api/reference-et0/validate", json={
        "tmaxC": 18, "tminC": 30, "latitude": 23.8, "dayOfYear": 60,
        "relativeHumidityPct": 60})
    assert bad.json()["outputCheck"]["plausible"] is False


def test_an_extra_field_is_rejected_rather_than_ignored():
    response = client.post("/api/reference-et0/validate", json={
        "tmaxC": 30, "tminC": 18, "latitude": 23.8, "dayOfYear": 60,
        "relativeHumidityPct": 60, "cropCoefficient": 0.9})
    assert response.status_code == 422


def test_vapour_pressure_must_be_defined():
    response = client.get("/api/reference-et0/validate",
                          params={"tmaxC": 30, "tminC": 18, "latitude": 23.8, "dayOfYear": 60})
    assert response.status_code == 422
    assert "tdewC" in str(response.json())


# ------------------------------------------------------------------ simulator outputs


def test_vpd_is_accompanied_by_its_method_and_its_limits():
    body = client.post("/api/simulate", json={"crop": "lettuce", "simulationDays": 35}).json()
    vpd = body["environment"]["vaporPressureDeficit"]
    assert vpd["method"].startswith("Tetens")
    assert vpd["inputsAreAssumptions"] is True
    assert vpd["propagatedError"] is None
    assert "scenario" in vpd["statement"]
    assert body["environment"]["vaporPressureDeficitKpa"] >= 0


def test_the_light_integral_says_it_is_a_setting_not_a_measurement():
    body = client.post("/api/simulate", json={"crop": "lettuce", "simulationDays": 20}).json()
    integral = body["environment"]["dailyLightIntegral"]
    assert integral["inputsAreAssumptions"] is True
    assert "setting" in integral["statement"]


def test_every_headline_scalar_has_a_machine_readable_unit():
    body = client.post("/api/simulate", json={"crop": "lettuce", "simulationDays": 35}).json()
    units = body["units"]
    for scalar in ("cropYield", "growthRate", "waterUsed", "waterRecovered", "co2Removed",
                   "estimatedOxygenProduced", "spaceGrowthPercentage"):
        assert scalar in units, scalar
        assert isinstance(units[scalar], str) and units[scalar].strip()
        assert body[scalar] is not None
    assert units["environment.vaporPressureDeficitKpa"] == "kPa"


def test_the_units_map_does_not_rename_existing_fields():
    """Additive by design: a client written before Phase 32 keeps working unchanged."""
    body = client.post("/api/simulate", json={"crop": "lettuce", "simulationDays": 35}).json()
    for legacy in ("cropYield", "waterUsed", "dailyGrowthData", "demandBasis", "disclaimer",
                   "provenance", "warnings", "stress", "lifeSupport", "harvest"):
        assert legacy in body


@pytest.mark.parametrize("crop", ["lettuce", "tomato", "radish"])
def test_the_units_map_is_present_for_every_supported_crop(crop):
    body = client.post("/api/simulate", json={"crop": crop, "simulationDays": 20}).json()
    assert body["units"]["waterUsed"]


def test_an_unsupported_crop_is_rejected_rather_than_approximated():
    response = client.post("/api/simulate", json={"crop": "mizuna", "simulationDays": 20})
    assert response.status_code == 422
    assert "lettuce, tomato, radish" in response.json()["message"]


# ------------------------------------------------------------------ water path stays rank-only


def test_the_measured_comparison_still_refuses_a_level_claim():
    """The rank claim lives in the comparison payload; this surface publishes the measurement.

    Whichever surface is read, the prohibition is the same: no absolute-agreement claim, no
    "calibrated against the measurement", and no invented pot geometry to make a per-area number
    look comparable.
    """
    body = client.get("/api/water-use-evidence").json()
    text = str(body).lower()
    for forbidden in ("agreement within", "calibrated against the measurement",
                      "validated the level", "level correction applied"):
        assert forbidden not in text
    comparison = client.post("/api/water-use-evidence/compare",
                             json={"crop": "lettuce"}).json()
    comparison_text = str(comparison).lower()
    assert "shape" in comparison_text or "rank" in comparison_text
    for forbidden in ("agreement within", "calibrated against the measurement"):
        assert forbidden not in comparison_text
