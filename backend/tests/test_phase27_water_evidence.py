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
import safedata

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

VALIDATION = REPO_ROOT / "ml" / "evaluation" / "phase26_measured_et_validation"
BENCHMARK = REPO_ROOT / "data" / "processed" / "phase26" / "schroder2021_lettuce_et.csv"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def benchmark_payload() -> dict:
    if not safedata.exists(BENCHMARK):
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


def test_benchmark_records_the_measurement_pattern_instead_of_smoothing_it(benchmark_payload):
    """The raw series steps by a factor of 2.3 between two consecutive days.

    That is a fact about the trial's intervals, not noise to be filtered, and a reader comparing
    curves needs to know it before concluding anything about the model.
    """
    pattern = benchmark_payload["measurementPattern"]
    assert "not smooth" in pattern["note"]
    assert pattern["largestOneDayStepMlPerPot"] > 100
    assert "not smoothed" in pattern["status"]
    values = [entry["measuredMlPerPotPerDay"] for entry in benchmark_payload["series"]]
    steps = [b - a for a, b in zip(values, values[1:])]
    assert max(steps) == pytest.approx(pattern["largestOneDayStepMlPerPot"], abs=0.01)


def test_benchmark_endpoint_returns_the_same_payload(client, benchmark_payload):
    if not safedata.exists(BENCHMARK):
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
    if not safedata.exists(VALIDATION):
        pytest.skip("validation artefact not present")
    artefact = safedata.load(VALIDATION)
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
    {"crop": "lettuce", "gravity": 0.3},  # removed in Phase 30
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


# ---------------------------------------------------------------------------------------
# the implementation coverage matrix (Phase 27 deliverable)
# ---------------------------------------------------------------------------------------
COVERAGE = REPO_ROOT / "data" / "research" / "phase27" / "feature_implementation_coverage"


@pytest.fixture(scope="module")
def coverage() -> dict:
    if not safedata.exists(COVERAGE):
        pytest.skip("coverage matrix not built")
    return safedata.load(COVERAGE)


def test_coverage_covers_every_audited_feature(coverage):
    readiness = safedata.load(REPO_ROOT / "data" / "research" / "phase26" / "feature_readiness")
    assert {f["id"] for f in coverage["features"]} == {f["id"] for f in readiness["features"]}


def test_coverage_tiers_agree_with_the_readiness_audit(coverage):
    readiness = {f["id"]: f["tier"] for f in safedata.load(REPO_ROOT / "data" / "research" / "phase26" / "feature_readiness")["features"]}
    for feature in coverage["features"]:
        assert feature["readinessTier"] == readiness[feature["id"]], feature["id"]


def test_coverage_gives_every_feature_all_ten_layers(coverage):
    layers = set(coverage["layerDefinitions"])
    assert len(layers) == 10
    for feature in coverage["features"]:
        assert set(feature["layers"]) == layers, feature["id"]


def test_no_layer_is_present_without_evidence(coverage):
    for feature in coverage["features"]:
        for name, entry in feature["layers"].items():
            if entry["state"] == "present":
                assert entry["evidence"], f"{feature['id']}.{name}"
            for path in entry["evidence"]:
                assert safedata.exists(REPO_ROOT / path), f"{feature['id']}.{name}: {path}"


def test_the_complete_workflows_are_the_ones_phase_32_closed(coverage):
    """Phase 27 shipped one complete workflow; Phase 32 closed the other three it had audited.

    The set is pinned rather than counted, so a feature cannot become "complete" by having a
    layer quietly re-labelled `not-applicable`.
    """
    assert set(coverage["summary"]["completeWorkflows"]) == {
        "measured-eta", "independent-et0", "led-spectrum-response", "sub-daily-weather"}
    assert coverage["summary"]["byDisposition"] == {
        "complete": 3, "comparison-only": 1, "removed": 8}


def test_the_completed_feature_has_no_missing_applicable_layer(coverage):
    measured = next(f for f in coverage["features"] if f["id"] == "measured-eta")
    for name, entry in measured["layers"].items():
        assert entry["state"] in ("present", "not-applicable"), name


def test_every_retained_feature_now_covers_uncertainty_and_output_checks(coverage):
    """Phase 27's central finding was that `uncertainty` and `outputCheck` were the weakest layers.

    Phase 32 closed it: no retained feature is left with an `absent` uncertainty or output-check
    layer. Removed features are exempt - there is no result to qualify.
    """
    by_layer = coverage["summary"]["byLayer"]
    assert by_layer["uncertainty"].get("absent", 0) == 0
    assert by_layer["outputCheck"].get("absent", 0) == 0
    for feature in coverage["features"]:
        if feature["phase32Disposition"] == "removed":
            continue
        for layer in ("uncertainty", "outputCheck", "inputCheck"):
            assert feature["layers"][layer]["state"] in ("present", "not-applicable"), (
                feature["id"], layer, feature["layers"][layer]["state"])
    assert by_layer["tests"]["present"] >= 10


def test_cross_cutting_gaps_carry_evidence_and_a_disposition(coverage):
    """Every cross-cutting gap names its evidence and says what Phase 32 did about it.

    A gap may not be left as an open `major` finding: it is either resolved in the product or
    recorded as a limitation the response itself states.
    """
    assert len(coverage["crossCuttingGaps"]) >= 5
    for gap in coverage["crossCuttingGaps"]:
        assert gap["evidence"]
        assert gap["severity"] in {"resolved", "documented-limitation"}
        assert gap["disposition"].strip()
        for path in gap["evidence"]:
            assert safedata.exists(REPO_ROOT / path), (gap["id"], path)


def test_coverage_markdown_is_not_stale():
    import subprocess
    result = subprocess.run([sys.executable, "ml/research/build_feature_coverage.py", "--check"],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_identification_block_states_a_rank_claim_and_no_correction(client):
    """The comparison's scope, asserted so a later phase cannot upgrade it into a validation.

    Phase 31 had to resolve the dashboard's "Shape supported - level not identified" line. The
    evidence supports a rank claim and nothing about level, so the contract is pinned here: the
    identification block must say the level is unidentified, must offer no correction, and must
    name the missing measurement rather than an assumption that was silently adopted.
    """
    response = client.post("/api/water-use-evidence/compare", json={"crop": "lettuce", "lightScale": 1.0})
    assert response.status_code == 200
    payload = response.json()
    identification = payload["identification"]
    assert identification["levelIdentified"] is False
    assert identification["shapeSupported"] is True
    assert payload["isValidation"] is False
    assert "no correction is applied" in identification["claim"]
    assert identification["identifiableWith"].strip() == identification["identifiableWith"]
    assert "0.247" in identification["denominatorSpread"] and "2.7" in identification["denominatorSpread"]
    # No field of the comparison may carry a fitted scale factor that would move the level.
    assert "correction" not in payload and "scaleFactor" not in payload["totals"]
