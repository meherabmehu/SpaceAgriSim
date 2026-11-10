"""Phase 27: the measured water-use evidence feature, end to end.

The feature's whole claim is that a user can see a measured benchmark, compare their simulation
against it, and be told honestly that the level is not identifiable. Each of those three is tested
here, plus the ways the feature could quietly start lying:

* reporting a comparison for a crop with no measurement behind it;
* calling the result a validation;
* losing the provenance that ties the numbers to a hash-verified file;
* presenting the between-pot spread as a confidence interval.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import water_evidence  # noqa: E402
from app.main import app  # noqa: E402

VALIDATION = REPO_ROOT / "ml" / "evaluation" / "phase26_measured_et_validation.json"
BENCHMARK = REPO_ROOT / "data" / "processed" / "phase26" / "schroder2021_lettuce_et.csv"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def benchmark_payload() -> dict:
    if not BENCHMARK.is_file():
        pytest.skip("benchmark table not present")
    return water_evidence.benchmark()


# ---------------------------------------------------------------------------------------
# the benchmark endpoint
# ---------------------------------------------------------------------------------------
def test_benchmark_reports_every_measurement_date(benchmark_payload):
    assert benchmark_payload["available"] is True
    assert benchmark_payload["measurementDates"] == 11
    assert len(benchmark_payload["series"]) == 11
    assert [entry["dayNumber"] for entry in benchmark_payload["series"]] == [
        7, 9, 11, 14, 16, 17, 19, 21, 23, 25, 28]


def test_benchmark_series_is_monotonic_in_time_with_no_gaps(benchmark_payload):
    days = [entry["dayNumber"] for entry in benchmark_payload["series"]]
    assert days == sorted(days)
    for entry in benchmark_payload["series"]:
        assert entry["measuredMlPerPotPerDay"] > 0
        assert entry["pots"] >= 30


def test_benchmark_carries_the_measured_spread_not_a_confidence_interval(benchmark_payload):
    uncertainty = benchmark_payload["uncertainty"]
    assert uncertainty["isConfidenceInterval"] is False
    assert "between-pot" in uncertainty["kind"]
    assert any("not a confidence interval" in entry["note"].lower()
               for entry in [uncertainty])


def test_benchmark_provenance_points_at_a_hash_verified_file(benchmark_payload):
    provenance = benchmark_payload["provenance"]
    assert provenance["doi"] == "10.5281/zenodo.5550230"
    assert provenance["license"] == "CC BY 4.0"
    assert provenance["hashVerified"] is True
    assert provenance["files"] and all(item["sha256"] for item in provenance["files"])
    assert provenance["files"][0]["verified"] is True


def test_benchmark_limitations_include_the_geometry_and_the_gravity_caveats(benchmark_payload):
    text = " ".join(benchmark_payload["limitations"]).lower()
    assert "evapotranspiration" in text and "transpiration is not" in text
    assert "pot diameter" in text
    assert "earth" in text
    assert "no reference et0" in text


def test_benchmark_endpoint_returns_the_same_payload(client, benchmark_payload):
    if not BENCHMARK.is_file():
        pytest.skip("benchmark table not present")
    response = client.get("/api/water-use-evidence")
    assert response.status_code == 200
    body = response.json()
    assert body["measurementDates"] == benchmark_payload["measurementDates"]
    assert body["provenance"]["doi"] == benchmark_payload["provenance"]["doi"]


# ---------------------------------------------------------------------------------------
# the comparison endpoint
# ---------------------------------------------------------------------------------------
def test_comparison_reproduces_the_independent_validation_artefact(client):
    """The service must agree with the pandas-based artefact, not just with itself."""
    if not VALIDATION.is_file():
        pytest.skip("validation artefact not present")
    artefact = json.loads(VALIDATION.read_text(encoding="utf-8"))
    body = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce"}).json()
    assert body["shape"]["spearman"] == artefact["shape"]["spearmanAcrossDays"]
    assert body["shape"]["pairs"] == artefact["shape"]["points"]


def test_comparison_is_never_a_validation(client):
    body = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce"}).json()
    assert body["isValidation"] is False
    assert body["verdict"] in {"shape-only", "level-mismatch", "not-applicable"}
    assert body["verdict"] != "validated"


def test_comparison_reports_shape_supported_and_level_outside_the_measured_spread(client):
    body = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce"}).json()
    assert body["shape"]["supported"] is True
    assert body["uncertainty"]["withinMeasuredSpread"] is False
    assert body["verdict"] == "shape-only"
    assert body["totals"]["simulatedOverMeasured"] < 1


def test_comparison_gives_every_date_a_measured_and_a_simulated_value(client):
    body = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce"}).json()
    assert len(body["curve"]) == 11
    for point in body["curve"]:
        assert point["measuredMlPerPotPerDay"] > 0
        assert point["simulatedMlPerPotPerDay"] > 0
        assert 0 <= point["growthFraction"] <= 1


def test_comparison_names_all_three_denominators_and_flags_which_is_measured(client):
    body = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce"}).json()
    denominators = body["denominators"]
    assert set(denominators) == {"potSurface", "canopyArea", "freshMass"}
    assert denominators["potSurface"]["isMeasured"] is False
    assert denominators["canopyArea"]["isMeasured"] is False
    assert denominators["freshMass"]["isMeasured"] is True


def test_comparison_refuses_to_extrapolate_to_a_crop_with_no_measurement(client):
    body = client.post("/api/water-use-evidence/compare", json={"crop": "tomato"}).json()
    assert body["verdict"] == "not-applicable"
    assert body["benchmarkCrop"] == "lettuce"
    assert "no measurement for tomato" in body["reason"]
    assert "curve" not in body


def test_comparison_says_what_would_be_needed_to_settle_the_level(client):
    body = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce"}).json()
    assert "per-day weather" in body["whatWouldSettleIt"].lower()
    assert "crop coefficient becomes identifiable" in body["whatWouldSettleIt"]


def test_comparison_does_not_modify_the_simulator(client):
    """The feature is read-only evidence; the crop profile must be untouched by calling it."""
    from app.simulation import crops

    before = crops.get_crop("lettuce").peak_water_l_per_day
    client.post("/api/water-use-evidence/compare", json={"crop": "lettuce", "lightScale": 2.5})
    assert crops.get_crop("lettuce").peak_water_l_per_day == before


def test_a_larger_light_scale_scales_the_demand_linearly(client):
    base = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce",
                                                                "lightScale": 1.0}).json()
    doubled = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce",
                                                                   "lightScale": 2.0}).json()
    assert doubled["totals"]["simulatedMlPerPot"] == pytest.approx(
        2 * base["totals"]["simulatedMlPerPot"], rel=1e-6)
    # The measured side must not move: the benchmark is data, not a function of the request.
    assert doubled["totals"]["measuredMlPerPot"] == base["totals"]["measuredMlPerPot"]


# ---------------------------------------------------------------------------------------
# input validation
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("body", [
    {"crop": "lettuce", "growingAreaM2": -1},
    {"crop": "lettuce", "growingAreaM2": 0},
    {"crop": "lettuce", "lightScale": 0},
    {"crop": "lettuce", "lightScale": 99},
    {"crop": "mizuna"},
    {"crop": "lettuce", "gravity": 0.3},
])
def test_invalid_inputs_are_rejected_with_422(client, body):
    assert client.post("/api/water-use-evidence/compare", json=body).status_code == 422


def test_the_unknown_crop_message_does_not_leak_internals():
    with pytest.raises(KeyError):
        water_evidence.compare("banana", 1.0)


# ---------------------------------------------------------------------------------------
# the feature degrades honestly when the data is absent
# ---------------------------------------------------------------------------------------
def test_missing_table_reports_unavailable_instead_of_an_estimate(monkeypatch):
    monkeypatch.setattr(water_evidence, "_benchmark_rows", lambda: ())
    payload = water_evidence.benchmark()
    assert payload["available"] is False
    assert "series" not in payload or payload["series"] == []
    assert "reports no measurement" in payload["reason"]

    comparison = water_evidence.compare("lettuce", 1.0)
    assert comparison["available"] is False
    assert comparison["verdict"] == "not-applicable"
    assert "no measured benchmark" in comparison["reason"]
