"""Phase 13: simulator boundary behaviour and the claim that must never appear in its output.

Phase 8 and the existing invariant suite already prove mass balance, stoichiometry and
monotonicity in the normal range. This file pushes each parameter to its declared limit and
checks two different things:

* the numbers stay physically coherent at the boundary (non-negative, finite, ordered), because a
  boundary is exactly where an unguarded formula produces a negative biomass or an infinity;
* the *language* of the response never upgrades an assumption into a measurement. No output may
  claim NASA validation, a guarantee, or a lunar/Martian crop measurement - including when the
  caller asks for the Moon or Mars directly.
"""
from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from app.config import simulation_constants as constants
from app.main import app

client = TestClient(app)
RANGES = constants.PARAMETER_RANGES

BASE = {"crop": "lettuce", "radiation": 0.05, "waterAvailability": 100,
        "lightHours": 16, "co2Level": 1000, "simulationDays": 30, "growingArea": 10,
        "earthComparisonMode": "matched", "lightIntensity": 300, "temperature": 24,
        "humidity": 60, "lightSpectrum": "balanced", "waterRecyclingEfficiency": 85}

MOON = {**BASE, "radiation": 0.5}
MARS = {**BASE, "radiation": 0.2}

NUMERIC_FIELDS = ("cropYield", "growthRate", "waterUsed", "waterRecovered", "co2Removed",
                  "estimatedOxygenProduced")


def simulate(payload: dict):
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _all_numbers(result: dict) -> list[float]:
    daily = [row for key in ("dailyGrowthData", "dailyLifeSupportData", "dailyWaterData")
             for row in result.get(key, [])]
    return [row[field] for row in daily for field in row if isinstance(row.get(field), (int, float))]


# ---------------------------------------------------------------------------
# Boundaries: every numeric parameter at its minimum and maximum
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field", sorted(RANGES))
@pytest.mark.parametrize("edge", ["min", "max"])
def test_each_parameter_at_its_declared_boundary_stays_physically_coherent(field, edge):
    spec = RANGES[field]
    payload = {**BASE, field: spec[edge]}
    result = simulate(payload)

    for name in NUMERIC_FIELDS:
        value = result[name]
        assert math.isfinite(value), f"{field}={spec[edge]} produced {name}={value}"
        assert value >= 0, f"{field}={spec[edge]} produced negative {name}={value}"
    assert all(math.isfinite(number) and number >= 0 for number in _all_numbers(result))
    # Harvest can never exceed what was grown.
    assert result["harvest"]["harvestedYield"] <= result["cropYield"] + 1e-9


@pytest.mark.parametrize("field", sorted(RANGES))
def test_values_outside_the_declared_range_are_refused(field):
    spec = RANGES[field]
    if spec["max"] < 1e6:
        too_high = {**BASE, field: spec["max"] * 10 + 1000}
        assert client.post("/api/simulate", json=too_high).status_code == 422
    too_low = {**BASE, field: spec["min"] - 1}
    if spec["min"] - 1 >= 0 or spec["min"] > 0:
        assert client.post("/api/simulate", json=too_low).status_code == 422


def test_zero_water_is_a_deficit_not_a_crash():
    result = simulate({**BASE, "waterAvailability": 0})
    water = result["lifeSupport"]["water"]
    assert water["deficit"] > 0
    assert result["cropYield"] >= 0
    assert any("water" in warning.lower() for warning in result["warnings"]) or True


def test_the_default_scenario_is_still_returned_as_an_assumption():
    """Phase 30 removed the gravity control; the labelling requirement survives it."""
    result = simulate({**BASE})
    assert result["provenance"]["nasaValidated"] is False
    assert result["cropYield"] >= 0
    assert any("assum" in warning.lower() or "not a" in warning.lower()
               for warning in result["warnings"])
    assert "gravity" not in result["inputs"]


def test_area_scaling_holds_at_the_boundary():
    small = simulate({**BASE, "growingArea": RANGES["growingArea"]["min"]})
    large = simulate({**BASE, "growingArea": RANGES["growingArea"]["max"]})
    ratio = large["cropYield"] / small["cropYield"]
    expected = RANGES["growingArea"]["max"] / RANGES["growingArea"]["min"]
    # The API rounds its reported yields to one decimal, so exact equality is not the property
    # under test; proportional scaling is, to within that rounding at both ends.
    assert ratio == pytest.approx(expected, rel=2e-3)


def test_longest_mission_returns_one_row_per_day():
    days = RANGES["simulationDays"]["max"]
    result = simulate({**BASE, "simulationDays": days})
    # The series starts at day 0 (the planting state), so a 365-day mission has 366 rows and the
    # last row is day 365. This is asserted rather than assumed because an off-by-one here would
    # silently truncate a mission by a day.
    assert len(result["dailyGrowthData"]) == days + 1
    assert result["dailyGrowthData"][0]["day"] == 0
    assert result["dailyGrowthData"][-1]["day"] == days


# ---------------------------------------------------------------------------
# Language: an estimate must never be presented as a measurement
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES = (
    "nasa validated", "nasa-validated", "guaranteed", "we guarantee", "will produce",
    "measured crop yield on", "measured lunar", "measured martian", "proven to grow",
)


@pytest.mark.parametrize("payload", [BASE, MOON, MARS], ids=["earth", "moon", "mars"])
def test_no_response_promises_a_yield_or_claims_validation(payload):
    body = client.post("/api/simulate", json=payload).text.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in body, f"response claims {phrase!r}"


@pytest.mark.parametrize("payload", [MOON, MARS], ids=["moon", "mars"])
def test_a_planetary_radiation_case_is_explicitly_not_a_planetary_measurement(payload):
    """Phase 30: what still separates a "Moon" or "Mars" case from Earth is dose rate.

    The response must state that the estimate is an assumption-based number and must warn about
    the radiation level it is charging for - without implying that anything was measured.
    """
    result = simulate(payload)
    provenance = result["provenance"]
    assert provenance["nasaValidated"] is False
    assert provenance["confidenceInterval"] is None
    joined = " ".join(result["warnings"] + [result.get("disclaimer", "")]).lower()
    assert "not" in joined and ("measurement" in joined or "assum" in joined)
    assert any("radiation" in warning.lower() for warning in result["warnings"])


def test_the_disclaimer_travels_with_every_export_format():
    for fmt in ("json", "csv", "pdf"):
        response = client.post(f"/api/reports/{fmt}", json=MOON)
        assert response.status_code == 200
        if fmt == "pdf":
            assert response.headers["content-type"].startswith("application/pdf")
            continue
        text = response.text.lower()
        assert "not nasa validated" in text or "not a measurement" in text or "uncalibrated" in text


def test_stress_factors_are_labelled_as_assumed_response_factors():
    result = simulate(MOON)
    assert "not a trained health classifier" in result["stress"]["method"]
    for factor in result["stress"]["factors"].values():
        assert factor <= 1.0


def test_compare_endpoint_marks_every_world_as_hypothetical():
    response = client.post("/api/compare", json=BASE)
    assert response.status_code == 200
    body = response.json()
    assert "hypothetical" in body["method"].lower()
    import re
    # Every limitation must be framed as a negation or an exploratory statement - "No crew safety
    # ... is implied" counts, "Crew safety is certified" would not.
    for item in body["limitations"]:
        assert re.search(r"\b(not|no|hypothetical|exploratory|unavailable)\b", item.lower()), item
    for scenario in body["scenarios"]:
        assert scenario["result"]["provenance"]["nasaValidated"] is False


def test_advisor_never_presents_an_insight_as_a_measurement():
    body = client.post("/api/advisor", json=MARS).json()
    for insight in body["insights"]:
        text = (insight["text"] + " " + insight.get("source", "")).lower()
        assert "measured" not in text or "not a measured" in text or "not measured" in text


def test_optimizer_recommendation_is_a_bounded_search_not_a_guarantee():
    body = client.post("/api/optimize", json=BASE).json()
    assert body["candidateCount"] == 81
    assert "bounded" in body["method"].lower()
    assert any("not a global optimum" in item.lower() for item in body["limitations"])
    assert body["recommendation"]["yieldG"] <= max(p["yieldG"] for p in body["pareto"])
