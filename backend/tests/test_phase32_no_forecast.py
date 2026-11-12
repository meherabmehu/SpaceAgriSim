"""Phase 32: no unsupported harvest forecast is reachable through any surface.

Phase 29 trained a lettuce yield model v3 against a 30 % MAPE criterion fixed in advance. On its
independent holdout it returned 41.6 %. The mizuna harvest model had a held-out R2 of -0.333, i.e.
worse than predicting the mean. Both were withdrawn from serving in Phase 31.

A withdrawal is only real if it is absent everywhere: not a 410 with a friendly message, not a
card labelled "retired", not a workflow that still appears in navigation. These tests walk every
surface a user or an assistant can reach and assert that no harvest forecast is offered by any of
them:

    routes          no path mentions harvest prediction; the withdrawn route answers 404/410
    catalogue       no runnable row, and the withdrawn model is not listed as available
    request schema  no endpoint accepts a harvest-forecast-shaped request
    assistant       no passage the retriever can quote offers one
    workflows       the guided workflow is not listed and cannot be run
    openapi         the operation is absent from the published contract

The models themselves are kept, checksummed, with their failed evaluations; the point is that the
forecast is not served, not that the failure is forgotten.
"""
from __future__ import annotations

import json

import pytest

import safedata
from fastapi.testclient import TestClient

from app import evidence, research, workflow
from app.main import app

client = TestClient(app)

WITHDRAWN_HARVEST_MODELS = ("mizuna-harvest-v1",)


# ------------------------------------------------------------------ routes

def test_no_route_offers_a_harvest_forecast():
    offenders = [path for path in app.openapi()["paths"]
                 if any(word in path.lower() for word in
                        ("harvest", "yield-forecast", "harvest-forecast"))]
    assert offenders == []


def test_the_withdrawn_harvest_workflow_route_is_gone():
    capability = client.get("/api/workflows/harvest-prediction/capability")
    run = client.post("/api/workflows/harvest-prediction/run", json={})
    for response, label in ((capability, "capability"), (run, "run")):
        assert response.status_code in (404, 405), (label, response.status_code)


def test_the_withdrawn_model_predict_route_is_gone():
    response = client.post("/api/predict/mizuna-harvest-v1",
                           json={"crop": "mizuna", "daysAfterSowing": 28})
    assert response.status_code == 404


# ------------------------------------------------------------------ catalogue and registry

def test_no_catalogue_row_is_runnable_or_advertises_a_harvest_forecast():
    including = {row["modelId"]: row for row in workflow.model_catalogue()["models"]}
    for model_id in WITHDRAWN_HARVEST_MODELS:
        assert model_id not in including, f"{model_id} still has a workflow catalogue row"
    for row in including.values():
        text = json.dumps(row).lower()
        assert "harvest forecast" not in text, row["modelId"]
        assert row.get("runStatus") != "runnable" or "yield" not in str(row.get("task", "")).lower()


def test_the_withdrawn_model_is_retained_but_not_served():
    served = {row["id"] for row in research.model_registry()["models"]}
    for model_id in WITHDRAWN_HARVEST_MODELS:
        assert model_id not in served
        assert research.RETIRED_MODEL_IDS[model_id].strip()
        # the artifact and its evaluation still exist, so the withdrawal is auditable
        assert safedata.exists(research.ARTIFACTS / f"{model_id}")


def test_every_served_prediction_says_it_is_not_a_forecast():
    """The positive half of the invariant: what *is* served states its scope."""
    for row in research.model_registry()["models"]:
        assert row.get("operationalForecast") is False, row["id"]
        assert row.get("harvestForecastClaim") in (None, "", "none"), row["id"]
        assert str(row.get("servedScope") or "").strip(), row["id"]


# ------------------------------------------------------------------ request schemas

def test_no_request_schema_accepts_a_harvest_forecast():
    document = app.openapi()
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            body = (operation.get("requestBody") or {}).get("content", {})
            for media in body.values():
                reference = json.dumps(media.get("schema", {}))
                assert "Harvest" not in reference, (method, path)


# ------------------------------------------------------------------ assistant corpus

def test_no_assistant_passage_offers_a_harvest_forecast():
    """Topical mentions are fine; an offer is not.

    The corpus has to be able to explain *why* this was withdrawn, so the test looks for the
    offer rather than the word: a passage may not say it can predict, estimate or forecast
    harvest.
    """
    phrases = ("predict harvest", "estimate harvest", "forecast harvest",
               "predict mizuna harvest", "harvest forecast for", "predict your harvest")
    for passage in evidence.corpus()["passages"]:
        text = passage.text.lower()
        for phrase in phrases:
            assert phrase not in text, (phrase, passage.id)


def test_the_corpus_states_the_scope_of_every_model_it_describes():
    """Every model passage carries the served scope, so a retrieval hit cannot upgrade it."""
    model_passages = [p for p in evidence.corpus()["passages"] if p.kind == "model"]
    assert model_passages
    for passage in model_passages:
        assert "Served scope:" in passage.text, passage.id


# ------------------------------------------------------------------ documents

def test_the_removal_is_documented_rather_than_implied():
    register = (research.ROOT / "docs" / "PHASE31_REMOVED_MODELS.md")
    assert safedata.exists(register)
    text = register.read_text(encoding="utf-8").lower()
    assert "harvest" in text
    # the document must quote the number that failed, not just describe a withdrawal
    assert "41.7 %" in text or "41.6" in text or "41.7%" in text


@pytest.mark.parametrize("model_id", WITHDRAWN_HARVEST_MODELS)
def test_the_withdrawal_reason_quotes_its_metric(model_id):
    reason = research.RETIRED_MODEL_IDS[model_id]
    assert any(token in reason for token in ("-0.333", "-0.138", "R2")), reason
