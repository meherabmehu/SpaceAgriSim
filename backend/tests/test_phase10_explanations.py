"""Phase 10: an explanation must be of the model that answered the request.

The cheapest way to fake explainable AI is to fit a surrogate, show its feature
importances, and let the reader assume they describe the served model. These tests
exist so that cannot happen here by accident: the served evaluator is linear, so
the attribution must reconstruct its logits exactly, and anything that does not is
an error rather than a table.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import research
from app.routes.research import router

ROOT = Path(__file__).resolve().parents[2]
EXPLAINED = ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1")


@pytest.fixture
def scientific_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize("model_id", EXPLAINED)
def test_attribution_reconstructs_the_served_logits(model_id):
    """The identity is the whole claim: intercept + sum(contributions) == logit."""
    import sys

    sys.path.insert(0, str(ROOT / "ml" / "training"))
    from explain import linear_contributions

    artifact = json.loads((ROOT / "ml" / "artifacts" / f"{model_id}.json").read_text())
    evaluator = artifact["evaluator"]
    expression = dict(zip(evaluator["features"], artifact["referenceProfiles"]["control"]))

    attribution = linear_contributions(evaluator, expression)
    assert attribution["identityResidual"] < 1e-9

    for label, block in attribution["perClass"].items():
        weights = np.asarray(evaluator["coefficients"][label], dtype=float)
        values = np.asarray([expression[gene] for gene in evaluator["features"]], dtype=float)
        standardised = (values - np.asarray(evaluator["mean"])) / np.asarray(evaluator["scale"])
        expected = float(evaluator["intercept"][evaluator["classes"].index(label)]
                         + np.dot(weights, standardised))
        assert block["logit"] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("model_id", EXPLAINED)
def test_explanation_endpoint_serves_evidence_and_its_limits(scientific_client, model_id):
    response = scientific_client.get(f"/api/models/{model_id}/explanation")
    assert response.status_code == 200
    body = response.json()

    assert body["modelId"] == model_id
    assert body["identityResidual"] < 1e-9
    assert body["notASurrogate"].strip()
    assert body["explainedInput"].strip()
    assert body["interpretationLimits"], "an explanation without limits is an advertisement"

    stability = body["selectionStability"]
    assert stability["folds"] == 22
    assert stability["genesSelectedInEveryFold"] > 0
    assert stability["deployedGeneCount"] == 150
    assert len(stability["deployed"]) == 150
    # The instability count is surfaced, not buried: a coefficient from a gene chosen
    # in 3 of 22 folds is the weakest part of the explanation and says so.
    assert stability["deployedGenesChosenInFewerThanHalfTheFolds"] >= 0

    importance = body["permutationImportance"]
    assert importance["inSample"] is False
    assert importance["baselineBalancedAccuracy"] < 1.0, "an in-sample baseline of 1.0 means leakage"
    assert body["selectionLeakageNote"].strip()


def test_binary_model_is_explained_as_a_decision_function(scientific_client):
    """The binary evaluator stores an all-zero row for class 0.

    Reporting "control contributes nothing" would be an artefact of that encoding,
    not a finding, so the endpoint must explain the single decision function and say
    why.
    """
    body = scientific_client.get(
        "/api/models/radiation-exposure-osd46-v1/explanation").json()
    assert body["binaryEncodingNote"]
    assert body["perClass"]["controlIsReference"] is True
    assert body["perClass"]["classZeroRowIsAllZero"] is True
    assert "decisionFunction" in body["perClass"]

    artifact = json.loads(
        (ROOT / "ml" / "artifacts" / "radiation-exposure-osd46-v1.json").read_text())
    zero_row = artifact["evaluator"]["coefficients"]["control"]
    assert all(value == 0.0 for value in zero_row), "the zero-row premise no longer holds"


def test_models_without_a_valid_method_return_404_not_a_stub(scientific_client):
    """A tree ensemble gets no explanation rather than a surrogate's guess."""
    for model_id in ("lettuce-earth-growth-v2", "mizuna-microbial-load-v1",
                     "mizuna-harvest-v1"):
        response = scientific_client.get(f"/api/models/{model_id}/explanation")
        assert response.status_code == 404, f"{model_id} returned {response.status_code}"

    assert scientific_client.get("/api/models/not-a-model/explanation").status_code == 404


def test_explanation_cannot_be_served_for_a_different_model(tmp_path, monkeypatch):
    """A mislabelled explanation is worse than none, so the id is cross-checked."""
    original = json.loads(
        (ROOT / "ml" / "artifacts" / "radiation-quality-osd46-v1-explanation.json").read_text())
    mislabelled = dict(original, modelId="radiation-exposure-osd46-v1")
    (tmp_path / "radiation-quality-osd46-v1-explanation.json").write_text(
        json.dumps(mislabelled))
    monkeypatch.setattr(research, "ARTIFACTS", tmp_path)

    with pytest.raises(ValueError, match="different model"):
        research.explanation("radiation-quality-osd46-v1")


def test_explanation_with_a_broken_identity_is_refused(tmp_path, monkeypatch):
    """Read-time check: an explanation that does not reconstruct the logits is not one."""
    original = json.loads(
        (ROOT / "ml" / "artifacts" / "radiation-quality-osd46-v1-explanation.json").read_text())
    broken = dict(original, identityResidual=0.5)
    (tmp_path / "radiation-quality-osd46-v1-explanation.json").write_text(json.dumps(broken))
    monkeypatch.setattr(research, "ARTIFACTS", tmp_path)

    with pytest.raises(ValueError, match="reconstruction identity"):
        research.explanation("radiation-quality-osd46-v1")


def test_stability_counts_are_consistent_with_the_artifact_metrics():
    """Selection stability must agree with the figure the model card already shows."""
    for model_id in EXPLAINED:
        artifact = json.loads((ROOT / "ml" / "artifacts" / f"{model_id}.json").read_text())
        explanation = json.loads(
            (ROOT / "ml" / "artifacts" / f"{model_id}-explanation.json").read_text())
        assert (explanation["selectionStability"]["genesSelectedInEveryFold"]
                == artifact["metrics"]["genesSharedAcrossFolds"]), model_id
