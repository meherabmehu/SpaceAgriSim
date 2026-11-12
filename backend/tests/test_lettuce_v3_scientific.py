"""Scientific tests for the Phase 19 lettuce yield model (v3).

These are not shape tests. Each one pins a claim the audit made in prose, so that the prose cannot
quietly become false:

* the daily light integral the API reports is the number the model was actually fed;
* the per-area identity is exact, and doubling density halves per-plant mass;
* a density outside the supported band is flagged rather than extrapolated silently;
* the log target is inverted exactly once (the failure mode here is a number three orders of
  magnitude out that still looks like a plausible answer);
* the artifact's checksum, version and provenance still match what the registry records;
* the served predictions reproduce the numbers written in the validation report;
* the independent holdout stays a failure until a model actually passes it.

The last group is the important one. A retrained model that passes would be welcome; a retrained
model that passes by editing the criterion, the holdout, or the status label is the regression this
file exists to catch.
"""
from __future__ import annotations
import sys

import hashlib
import json
import math
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import research
from app.routes.research import router

MODEL_ID = "lettuce-earth-growth-v3"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
ARTIFACT = ROOT / "ml" / "artifacts" / f"{MODEL_ID}"
REGISTRY = ROOT / "ml" / "artifacts" / "registry"

# The PeerJ greenhouse conditions, used as a realistic call throughout.
PEERJ = {"daysAfterTransplant": 28.0, "airTemperature": 27.5, "rootTemperature": 27.5,
         "ppfd": 391.0, "photoperiodHours": 12.0, "plantDensityPerM2": 48.0}


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.fixture(scope="module")
def full_client() -> TestClient:
    """The real application: some behaviour only exists once the workflow router is mounted."""
    from app.main import app as application

    return TestClient(application)


def predict(client: TestClient, **overrides) -> dict:
    response = client.post(f"/api/predict/{MODEL_ID}", json={**PEERJ, **overrides})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Artifact integrity and provenance
# ---------------------------------------------------------------------------
def test_artifact_checksum_matches_registry():
    """A hand-edited artifact must not serve. This is the check that catches it."""
    registry = safedata.load(REGISTRY)
    entry = next(m for m in registry["models"] if m["id"] == MODEL_ID)
    assert hashlib.sha256(safedata.bytes(ARTIFACT)).hexdigest() == entry["sha256"]


def test_artifact_is_loadable_through_the_serving_path():
    model = research.load_model(MODEL_ID)
    assert model["id"] == MODEL_ID
    assert "boostedTrees" in model


def test_artifact_declares_provenance():
    model = safedata.load(ARTIFACT)
    assert model["sourceStudy"] and model["sourceUrl"]
    # The training rows are pinned, so "same script, different data" cannot pass as the same model.
    assert len(model["trainingDataSha256"]) == 64
    int(model["trainingDataSha256"], 16)


def test_feature_order_matches_the_domain_block():
    """predict_values feeds features positionally; a reordered list would be silently accepted."""
    model = safedata.load(ARTIFACT)
    assert model["features"] == ["daysAfterTransplant", "airTemperature", "rootTemperature",
                                "dailyLightIntegral"]
    assert set(model["domain"]) == set(model["features"])


def test_target_transform_is_declared_and_invertible():
    model = safedata.load(ARTIFACT)
    assert model["targetTransform"]["name"] == "log"
    assert research.inverse_target_transform(model, 0.0) == pytest.approx(1.0)
    assert research.inverse_target_transform(model, math.log(250.0)) == pytest.approx(250.0)
    with pytest.raises(ValueError):
        research.inverse_target_transform({"targetTransform": {"name": "sqrt"}}, 1.0)


# ---------------------------------------------------------------------------
# Dimensional consistency: the daily light integral
# ---------------------------------------------------------------------------
def test_daily_light_integral_derivation(client):
    """DLI [mol m-2 d-1] = PPFD [umol m-2 s-1] x photoperiod [h] x 3600 [s/h] / 1e6 [umol/mol]."""
    body = predict(client, ppfd=400.0, photoperiodHours=16.0)
    expected = 400.0 * 16.0 * 3600.0 / 1e6
    assert body["derived"]["dailyLightIntegral"] == pytest.approx(expected, abs=0.01)
    assert body["derived"]["unit"] == "mol m-2 d-1"
    # 400 umol/m2/s for 16 h is 23.04 mol/m2/d, a standard plant-factory setpoint.
    assert expected == pytest.approx(23.04)


def test_photoperiod_changes_the_prediction_at_fixed_ppfd(client):
    """Two runs at the same instantaneous flux but different day length are not the same plant.

    This is the whole reason v2 failed: it saw only PPFD, so a 12 h greenhouse and a 16 h plant
    factory were identical inputs.
    """
    short = predict(client, ppfd=400.0, photoperiodHours=12.0)
    long = predict(client, ppfd=400.0, photoperiodHours=16.0)
    assert short["derived"]["dailyLightIntegral"] < long["derived"]["dailyLightIntegral"]
    assert short["prediction"] != long["prediction"]


def test_feature_values_are_inside_the_declared_domain_when_not_flagged(client):
    model = safedata.load(ARTIFACT)
    body = predict(client)
    values = {"daysAfterTransplant": body["inputs"]["daysAfterTransplant"],
              "airTemperature": body["inputs"]["airTemperature"],
              "rootTemperature": body["inputs"]["rootTemperature"],
              "dailyLightIntegral": body["derived"]["dailyLightIntegral"]}
    in_domain = all(model["domain"][k]["min"] <= v <= model["domain"][k]["max"]
                    for k, v in values.items())
    assert in_domain == (not body["outOfDistribution"]) or body["warnings"]


@pytest.mark.parametrize("ppfd,photoperiod", [(200.0, 16.0), (750.0, 16.0), (400.0, 12.0)])
def test_predictions_stay_positive_within_the_trained_range(client, ppfd, photoperiod):
    body = predict(client, ppfd=ppfd, photoperiodHours=photoperiod)
    assert body["prediction"] > 0
    assert math.isfinite(body["prediction"])
    assert body["perAreaYieldGPerM2"] > 0


# ---------------------------------------------------------------------------
# The density identity
# ---------------------------------------------------------------------------
def test_density_identity_is_exact(client):
    body = predict(client)
    assert body["prediction"] * body["densityUsedPlantsPerM2"] == pytest.approx(
        body["perAreaYieldGPerM2"], rel=1e-3)


def test_doubling_density_halves_per_plant_mass(client):
    """Mass conservation across the identity: the same square metre, split between more plants."""
    sparse = predict(client, plantDensityPerM2=25.0)
    dense = predict(client, plantDensityPerM2=50.0)
    assert dense["perAreaYieldGPerM2"] == pytest.approx(sparse["perAreaYieldGPerM2"], rel=1e-9)
    assert dense["prediction"] == pytest.approx(sparse["prediction"] / 2.0, rel=1e-2)


def test_density_outside_the_supported_band_is_flagged(client):
    """Touliatos measured 1000 plants/m2, where the per-area identity itself breaks."""
    body = predict(client, plantDensityPerM2=1000.0)
    assert body["outOfDistribution"] is True
    assert any("plantDensityPerM2" in warning for warning in body["warnings"])


def test_the_supported_density_band_is_wide_enough_for_the_source_studies(client):
    model = safedata.load(ARTIFACT)
    band = model["densityDomain"]["plantsPerM2"]
    assert band["min"] <= 25.0 <= band["max"]      # WUR plant factory
    assert band["min"] <= 48.0 <= band["max"]      # PeerJ greenhouse
    assert band["min"] <= 50.0 <= band["max"]      # Touliatos horizontal hydroponics
    assert 1000.0 > band["max"]                    # Touliatos stacked VFS: refused


# ---------------------------------------------------------------------------
# Uncertainty
# ---------------------------------------------------------------------------
def test_interval_brackets_the_prediction_and_stays_physical(client):
    body = predict(client)
    low, high = body["interval"]["low"], body["interval"]["high"]
    assert 0.0 <= low <= body["prediction"] <= high
    # The interval is a ratio on the log target, so it must be multiplicative and non-degenerate.
    assert high / low > 1.5
    assert body["interval"]["calibrated"] is False


def test_interval_scales_with_density_like_the_point_estimate(client):
    sparse = predict(client, plantDensityPerM2=25.0)
    dense = predict(client, plantDensityPerM2=50.0)
    assert dense["interval"]["low"] == pytest.approx(sparse["interval"]["low"] / 2.0, rel=1e-2)
    assert dense["interval"]["high"] == pytest.approx(sparse["interval"]["high"] / 2.0, rel=1e-2)


def test_uncertainty_is_declared_as_out_of_fold_conformal():
    model = safedata.load(ARTIFACT)
    assert "conformal" in model["interval"]["kind"].lower()
    assert 0.85 <= model["interval"]["outOfFoldCoverage"] <= 0.95
    # The artifact must say the coverage is descriptive, not independent evidence.
    assert "not independent evidence" in model["interval"]["coverageNote"]


# ---------------------------------------------------------------------------
# Reproducibility: the API must return the numbers the report published
# ---------------------------------------------------------------------------
def test_predictions_reproduce_the_reported_development_values(client):
    """These are the figures written into MODEL_VALIDATION_REPORT.md for the PeerJ rows."""
    expected = {697.0: 157.4, 391.0: 123.4, 322.0: 123.4}
    for ppfd, value in expected.items():
        body = predict(client, ppfd=ppfd, airTemperature=27.5, rootTemperature=27.5)
        assert body["prediction"] == pytest.approx(value, abs=0.5), ppfd


def test_repeated_calls_are_identical(client):
    first = predict(client)
    second = predict(client)
    assert first["prediction"] == second["prediction"]
    assert first["interval"] == second["interval"]


# ---------------------------------------------------------------------------
# Evidence status: the failure must stay visible
# ---------------------------------------------------------------------------
def test_model_is_labelled_trained_exploratory(client):
    body = predict(client)
    assert body["validationStatus"]["status"] == "trained-exploratory"


def test_independent_holdout_failure_is_served_not_hidden(client):
    check = predict(client)["validationStatus"]["independentCheck"]
    assert check["passed"] is False
    assert check["metrics"]["MAPE"] > check["acceptanceCriterionPct"]
    assert check["study"].startswith("Touliatos")
    assert check["verdict"]


def test_acceptance_criterion_was_not_relaxed():
    """The criterion is a pre-registered constant of the audit, not a tunable."""
    model = safedata.load(ARTIFACT)
    assert model["validation"]["independent"]["acceptanceCriterionPct"] == 30.0


def test_development_set_is_not_presented_as_validation(client):
    body = predict(client)
    development = body["validationStatus"]["developmentCheck"]
    assert development["countsAsValidation"] is False
    # The artifact has to say why it does not count, not merely that it does not.
    assert development["usedForModelSelection"] is True
    assert "development" in development["study"].lower() or "peerj" in development["study"].lower()


def test_improvement_over_v2_is_reported_on_the_same_rows(client):
    comparison = predict(client)["validationStatus"]["comparedWithV2"]
    assert comparison["v2DevelopmentMAPEPct"] == pytest.approx(232.2)
    assert comparison["v3DevelopmentMAPEPct"] < comparison["v2DevelopmentMAPEPct"]


def test_registry_and_artifact_agree_on_the_verdict():
    registry = safedata.load(REGISTRY)
    entry = next(m for m in registry["models"] if m["id"] == MODEL_ID)
    model = safedata.load(ARTIFACT)
    independent = model["validation"]["independent"]
    declared = entry["independentValidation"]
    assert declared["passed"] is independent["passed"]
    assert declared["value"] == pytest.approx(independent["metrics"]["MAPE"], abs=0.05)
    assert entry["status"] == model["status"] == "trained-exploratory"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("payload", [
    {**PEERJ, "photoperiodHours": 0},
    {**PEERJ, "photoperiodHours": 25},
    {**PEERJ, "plantDensityPerM2": 0},
    {**PEERJ, "plantDensityPerM2": -5},
    {**PEERJ, "ppfd": 5000},
    {**PEERJ, "daysAfterTransplant": 61},
    {**PEERJ, "cultivar": "Batavia"},  # extra fields are refused, not silently ignored
])
def test_invalid_inputs_are_rejected(client, payload):
    assert client.post(f"/api/predict/{MODEL_ID}", json=payload).status_code == 422


def test_photoperiod_defaults_match_the_training_system(client):
    """The WUR source ran 16 h and 25 plants/m2; the defaults say so instead of guessing."""
    body = client.post(f"/api/predict/{MODEL_ID}",
                       json={"daysAfterTransplant": 28, "airTemperature": 22,
                             "rootTemperature": 22, "ppfd": 400}).json()
    assert body["inputs"]["photoperiodHours"] == 16.0
    assert body["inputs"]["plantDensityPerM2"] == 25.0


def test_v2_route_still_serves_its_original_behaviour(client):
    """The failing model is kept, not deleted: its 232 % result has to stay reproducible."""
    response = client.post("/api/predict/lettuce-earth-growth-v2",
                           json={"daysAfterTransplant": 28, "airTemperature": 27.5,
                                 "rootTemperature": 27.5, "ppfd": 391})
    assert response.status_code == 200
    assert response.json()["modelId"] == "lettuce-earth-growth-v2"


# ---------------------------------------------------------------------------
# The external-validation screen must report both models
# ---------------------------------------------------------------------------
def test_external_validation_reports_v3_development_and_holdout():
    from app import external_validation

    payload = external_validation.payload()
    assert payload["externalCheck"]["modelId"] == "lettuce-earth-growth-v2"
    v3 = payload["v3Check"]
    assert v3["available"] is True
    assert v3["modelId"] == MODEL_ID
    assert v3["developmentMetrics"]["countsAsValidation"] is False
    assert v3["developmentMetrics"]["mapeV3Pct"] < v3["developmentMetrics"]["mapeV2Pct"]
    assert v3["independentHoldout"]["passed"] is False
    assert v3["verdict"]["passed"] is False


# ---------------------------------------------------------------------------
# The generic workflow path must not report a log value as a yield
# ---------------------------------------------------------------------------
def test_workflow_run_inverts_the_target_and_labels_the_unit(full_client):
    """Regression: the workflow shared the log value 4.8 where the answer is 5924 g/m2.

    Every other model in the registry is served from the same generic path, so a target
    transform that only the dedicated route understood was a defect waiting to surface on the
    next log-target artifact - and it surfaced silently, with a plausible-looking number.
    """
    body = {"modelId": MODEL_ID,
            "inputs": {"daysAfterTransplant": 28.0, "airTemperature": 27.5,
                       "rootTemperature": 27.5, "dailyLightIntegral": 16.9}}
    response = full_client.post("/api/workflow/run", json=body)
    assert response.status_code == 200, response.text
    output = response.json()["output"]
    assert output["prediction"] > 1000          # a yield per square metre, not a logarithm
    assert output["unit"] == "g fresh mass per m2"
    assert output["interval"]["low"] < output["prediction"] < output["interval"]["high"]
    # The workflow cannot know the caller's density, so it must say what it did and did not return.
    assert "plantDensityPerM2" in output["scopeNote"]


def test_workflow_rejects_a_physically_impossible_dli(full_client):
    body = {"modelId": MODEL_ID,
            "inputs": {"daysAfterTransplant": 28.0, "airTemperature": 27.5,
                       "rootTemperature": 27.5, "dailyLightIntegral": 250.0}}
    response = full_client.post("/api/workflow/run", json=body)
    assert response.status_code in {400, 422}
