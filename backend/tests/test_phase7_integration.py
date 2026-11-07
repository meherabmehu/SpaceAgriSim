"""Phase 7 integration: versioned endpoints, registry, checksums, evidence.

The Phase 7 additions are additive by design: no Phase 6 field moved, no Phase 4
security rule was relaxed, and the model registry grew by exactly one entry whose
predecessor is still present and still verified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.research import router

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client_scientific():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_v2_prediction_is_relative_and_refuses_absolute_without_a_campaign(client_scientific):
    response = client_scientific.post("/api/predict/mizuna-microbial-relative-load-v2", json={
        "environment": "flight", "spectrum": "red", "sanitised": True,
        "freshWeightG": 3.0, "harvestIndex": 2,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["unit"].startswith("standard deviations")
    # The estimand must be visible in the response, not only in the docs.
    assert payload["estimandChange"]["to"] == "within-campaign standardised log10 load"
    assert payload["absoluteScale"]["supplied"] is False
    assert "log10CfuPerG" not in payload["absoluteScale"]
    assert payload["absoluteScale"]["note"]
    assert payload["supersedes"]


def test_v2_prediction_offers_absolute_scale_only_with_a_reference(client_scientific):
    baseline = client_scientific.post(
        "/api/predict/mizuna-microbial-relative-load-v2", json={
            "environment": "ground", "spectrum": "red", "sanitised": False,
            "freshWeightG": 2.5, "harvestIndex": 1}).json()
    referenced = client_scientific.post(
        "/api/predict/mizuna-microbial-relative-load-v2", json={
            "environment": "ground", "spectrum": "red", "sanitised": False,
            "freshWeightG": 2.5, "harvestIndex": 1,
            "campaignReference": "VEG04B"}).json()

    # The relative prediction cannot depend on whether a reference was supplied.
    assert baseline["prediction"] == pytest.approx(referenced["prediction"])
    absolute = referenced["absoluteScale"]
    assert absolute["supplied"] is True
    assert absolute["campaign"] == "VEG04B"
    expected = absolute["campaignMean"] + referenced["prediction"] * absolute["campaignSd"]
    assert absolute["log10CfuPerG"] == pytest.approx(expected)
    assert absolute["caveat"]


def test_v2_rejects_experiment_identity_as_an_input(client_scientific):
    # v1 accepted `experiment`; v2 must not, because the campaign offset is the
    # quantity it deliberately refuses to model.
    response = client_scientific.post(
        "/api/predict/mizuna-microbial-relative-load-v2", json={
            "environment": "flight", "spectrum": "red", "sanitised": True,
            "freshWeightG": 3.0, "harvestIndex": 2, "experiment": "VEG04B"})
    assert response.status_code == 422


def test_v2_prediction_is_bounded_by_its_domain(client_scientific):
    response = client_scientific.post(
        "/api/predict/mizuna-microbial-relative-load-v2", json={
            "environment": "flight", "spectrum": "blue", "sanitised": False,
            "freshWeightG": 49.0, "harvestIndex": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["outOfDistribution"] is True  # far outside the measured subsample range
    assert payload["warnings"]


def test_measurements_endpoint_exposes_absence_as_clearly_as_presence(client_scientific):
    response = client_scientific.get("/api/science/measurements")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert len(payload["catalogSha256"]) == 64
    targets = payload["targets"]
    assert len(targets) == 12
    not_measured = [t for t in targets if t["status"] == "not-measured"]
    # O2 evolution, gravity-dependent growth and radiation dose-response.
    assert len(not_measured) == 3
    assert all(t["eligibility"] == "insufficient" for t in not_measured)
    assert all(t["searchRecord"] for t in not_measured)
    # Nothing is rated ready for predictive training.
    assert payload["summary"]["byEligibility"].get("ready", 0) == 0
    assert payload["trainingEligibility"]["summary"]["readyForPredictiveTraining"] == []


def test_measurement_catalog_checksum_matches_the_file_on_disk(client_scientific):
    served = client_scientific.get("/api/science/measurements").json()["catalogSha256"]
    on_disk = hashlib.sha256(
        (ROOT / "data/metadata/phase7_measurement_catalog.json").read_bytes()).hexdigest()
    assert served == on_disk


def test_checksums_endpoint_verifies_every_model_artifact(client_scientific):
    payload = client_scientific.get("/api/science/checksums").json()
    assert payload["algorithm"] == "SHA-256"
    documents = payload["sourceDocuments"]
    assert len(documents) == 6
    assert all(len(d["sha256"]) == 64 for d in documents)
    assert all(d["ntrsId"] and d["url"].startswith("https://ntrs.nasa.gov") for d in documents)
    models = payload["modelArtifacts"]
    # Six artifacts since Phase 8 added the versioned lettuce-earth-growth-v2.
    assert len(models) == 6
    assert all(m["verified"] for m in models), [m for m in models if not m["verified"]]


def test_evidence_summary_replaces_the_phase6_blanket_blocked_claim(client_scientific):
    payload = client_scientific.get("/api/science/evidence").json()
    assert payload["schemaVersion"] == 2
    measured_but_not_trainable = {item["target"].lower()
                                  for item in payload["measuredNotTrainable"]}
    blocked = " ".join(payload["blockedTargets"]).lower()

    # Phase 7 recovered these as real measurements; claiming they are blocked
    # would now be false.
    for recovered in ("transpiration", "water recovery", "co2 assimilation",
                      "biomass time series"):
        assert recovered in measured_but_not_trainable
        assert recovered not in blocked

    # And these remain genuinely absent - the one part of the Phase 6 claim that
    # survives intact.
    for still_missing in ("o2 evolution", "gravity response", "radiation"):
        assert still_missing in blocked

    record = payload["negativeFindingRecord"]
    assert record["queries"] == 39 and record["downloadablePdfs"] == 110


def test_calibration_endpoint_is_additive_and_reports_zero_applied_changes(client_scientific):
    payload = client_scientific.get("/api/science/calibration").json()
    # Phase 6 fields must still be present and unchanged in shape.
    assert payload["status"] == "available"
    assert payload["invariants"]["allPassed"] is True
    assert "calibration" in payload
    # Phase 7 block is additive.
    phase7 = payload["phase7"]
    assert phase7["appliedChanges"] == []
    assert phase7["massBalance"]["allPassed"] is True
    assert len(phase7["outputFingerprint"]["sha256"]) == 64
    declined = phase7["declinedChanges"][0]["detail"]["crops"]
    assert declined["tomato"]["applied"] is False
    assert declined["radish"]["applied"] is False


def test_phase7_model_does_not_leak_coefficients(client_scientific):
    models = client_scientific.get("/api/models").json()["models"]
    v2 = next(m for m in models if m["id"] == "mizuna-microbial-relative-load-v2")
    # Same rule as every other model: no executable arrays over the wire.
    assert "forest" not in v2 and "linear" not in v2
    assert v2["artifactExists"] is True
    assert v2["artifactSha256"]


def test_superseded_model_remains_served_so_phase6_stays_reproducible(client_scientific):
    models = {m["id"]: m for m in client_scientific.get("/api/models").json()["models"]}
    assert "mizuna-microbial-load-v1" in models
    assert models["mizuna-microbial-load-v1"]["artifactExists"] is True
    assert models["mizuna-microbial-relative-load-v2"]["supersedes"].startswith(
        "mizuna-microbial-load-v1")
