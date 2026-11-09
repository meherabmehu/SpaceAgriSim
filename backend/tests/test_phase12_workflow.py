"""Phase 12: scientific AI workflow and saved-analysis tests.

These assert the things that would make the workflow scientifically dishonest if they
broke: a retired model quietly answering, a molecular classifier accepting weather
inputs, an impossible value passing, another account reading a saved analysis, or an
export disagreeing with the API it was exported from.
"""
from __future__ import annotations

import csv
import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import research
from app import workflow
from app.main import app

PASSWORD = "CorrectHorseBattery1!"
LETTUCE = {"daysAfterTransplant": 20, "airTemperature": 24,
           "rootTemperature": 22, "ppfd": 400}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, label: str) -> dict[str, str]:
    email = f"wf-{label}-{uuid.uuid4().hex[:8]}@example.test"
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code in (200, 201), response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _run(client: TestClient, model_id: str, inputs: dict, **extra):
    return client.post("/api/workflow/run",
                       json={"modelId": model_id, "inputs": inputs, **extra})


# --------------------------------------------------------------------------- catalogue

def test_catalogue_lists_every_served_model_with_its_family(client):
    payload = client.get("/api/workflow/models").json()
    ids = {row["modelId"] for row in payload["models"]}
    assert len(ids) == len(research.MODEL_IDS)
    assert "mizuna-microbial-load-v1" in ids  # retired but kept reproducible

    families = {row["modelId"]: row["inputFamily"] for row in payload["models"]}
    assert families["radiation-quality-osd46-v1"] == "gene-expression"
    assert families["tomato-flight-response-v1"] == "gene-expression"
    assert families["lettuce-earth-growth-v2"] == "environment"
    assert families["mizuna-microbial-relative-load-v2"] == "microbial"


def test_catalogue_never_marks_a_retired_model_runnable(client):
    rows = client.get("/api/workflow/models").json()["models"]
    retired = [row for row in rows if row["runStatus"] == "retired"]
    assert [row["modelId"] for row in retired] == ["mizuna-microbial-load-v1"]
    assert retired[0]["runStatus"] == "retired"
    assert all(row["runStatus"] == "runnable"
               for row in rows if row["modelId"] != "mizuna-microbial-load-v1")


def test_catalogue_carries_classification_and_calibration_status(client):
    """A model must not be advertised as calibrated when Phase 11 declined to calibrate."""
    for row in client.get("/api/workflow/models").json()["models"]:
        assert row["category"] in range(1, 7)
        assert row["categoryName"]
        assert (row["calibration"] or {}).get("calibrated") is False
        assert row["featureCount"] > 0


def test_compatible_endpoint_matches_by_feature_set_not_by_name(client):
    feature_names = [feature["name"] for feature in
                     workflow.model_features("tomato-flight-response-v1")]
    response = client.post("/api/workflow/compatible", json={"features": feature_names})
    assert response.status_code == 200
    matched = {row["modelId"] for row in response.json()["compatible"]}
    assert matched == {"tomato-flight-response-v1"}


def test_compatible_endpoint_reports_nothing_for_an_unrelated_feature_set(client):
    response = client.post("/api/workflow/compatible",
                           json={"features": ["foo", "bar", "baz"]})
    assert response.json()["compatible"] == []


# ------------------------------------------------------------------------ validation

def test_environmental_input_cannot_drive_a_gene_expression_classifier(client):
    """The headline safety property: weather cannot be fed to a molecular model."""
    response = _run(client, "radiation-quality-osd46-v1", LETTUCE)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "family-mismatch"
    assert detail["expectedFamily"] == "gene-expression"
    assert detail["providedFamily"] == "environment"
    assert detail["missing"], "the response must say which features are missing"


def test_gene_expression_input_cannot_drive_an_environmental_model(client):
    feature_names = [feature["name"] for feature in
                     workflow.model_features("tomato-flight-response-v1")]
    response = _run(client, "lettuce-earth-growth-v2",
                    {name: 1.0 for name in feature_names})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "family-mismatch"
    assert detail["expectedFamily"] == "environment"
    assert detail["providedFamily"] == "gene-expression"


def test_physically_impossible_temperature_is_rejected(client):
    response = _run(client, "lettuce-earth-growth-v2",
                    {**LETTUCE, "airTemperature": 900})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "physically-impossible"
    assert detail["feature"] == "airTemperature"


def test_negative_light_is_rejected(client):
    response = _run(client, "lettuce-earth-growth-v2", {**LETTUCE, "ppfd": -50})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "physically-impossible"


def test_non_finite_value_is_rejected_by_the_schema(client):
    response = client.post("/api/workflow/run", content=json.dumps(
        {"modelId": "lettuce-earth-growth-v2",
         "inputs": {**LETTUCE, "ppfd": float("nan")}}),
        headers={"Content-Type": "application/json"})
    assert response.status_code in (400, 422)


def test_partial_input_list_is_reported_rather_than_guessed(client):
    response = _run(client, "lettuce-earth-growth-v2", {"airTemperature": 24})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "missing-features"
    assert len(detail["missing"]) == 3


def test_extra_unexpected_feature_is_rejected_not_ignored(client):
    response = _run(client, "lettuce-earth-growth-v2",
                    {**LETTUCE, "cropYieldTonnes": 12.0})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] in ("unexpected-features", "missing-features")


def test_validate_endpoint_does_not_return_a_prediction(client):
    response = client.post("/api/workflow/validate",
                           json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert "output" not in body
    assert body["classification"]["category"] == 3
    assert "schema-exact-feature-set" in body["checks"]["checksApplied"]


def test_unknown_model_is_not_found(client):
    response = _run(client, "definitely-not-a-model", LETTUCE)
    assert response.status_code == 404


def test_retired_model_returns_gone_with_its_reasoning(client):
    response = _run(client, "mizuna-microbial-load-v1", {"experiment": 1})
    assert response.status_code == 410
    detail = response.json()["detail"]
    assert detail["error"] == "retired-model"
    assert detail["message"]


# ----------------------------------------------------------------------------- run

def test_run_returns_a_number_with_its_domain_and_provenance(client):
    response = _run(client, "lettuce-earth-growth-v2", LETTUCE)
    assert response.status_code == 200
    body = response.json()

    prediction = body["output"]["prediction"]
    assert isinstance(prediction, float) and prediction > 0
    assert body["output"]["unit"]
    assert body["output"]["calibrated"] is False
    assert body["output"]["kind"] == "regression"

    validation = body["validation"]
    assert validation["schemaExact"] is True
    assert validation["missing"] == [] and validation["unexpected"] == []
    assert validation["insideTrainingDomain"] is True

    provenance = body["provenance"]
    assert provenance["sourceStudy"]
    assert len(provenance["artifactSha256"]) == 64


def test_every_run_carries_citations_and_limitations(client):
    body = _run(client, "lettuce-earth-growth-v2", LETTUCE).json()
    assert body["evidence"]["claims"], "an answer without claims is not acceptable"
    assert body["evidence"]["citations"]
    for claim in body["evidence"]["claims"]:
        assert claim["citation"] in range(1, len(body["evidence"]["citations"]) + 1)
    assert len(body["limitations"]) >= 2
    text = " ".join(body["limitations"]).lower()
    assert "not " in text or "no " in text


def test_run_labels_the_number_as_interpretation_not_measurement(client):
    body = _run(client, "lettuce-earth-growth-v2", LETTUCE).json()
    assert body["output"]["isMeasurement"] is False
    assert "not a measurement" in body["output"].get("note", "").lower() or \
           "not a measurement" in body["interpretation"].lower()


def test_extrapolation_beyond_the_training_domain_is_flagged_not_hidden(client):
    body = _run(client, "lettuce-earth-growth-v2",
                {**LETTUCE, "ppfd": 1600, "airTemperature": 31}).json()
    if not body["validation"]["insideTrainingDomain"]:
        assert any("domain" in item.lower() or "extrapolat" in item.lower()
                   for item in body["limitations"])


def test_anonymous_caller_cannot_persist_an_analysis(client):
    response = _run(client, "lettuce-earth-growth-v2", LETTUCE, save=True)
    assert response.status_code == 401


def test_anonymous_caller_can_still_run_a_model(client):
    response = _run(client, "lettuce-earth-growth-v2", LETTUCE)
    assert response.status_code == 200
    assert response.json()["saved"] is None


def test_authentication_may_be_present_without_saving(client):
    headers = _headers(client, "nosave")
    response = _run(client, "lettuce-earth-growth-v2", LETTUCE, save=False)
    assert response.status_code == 200
    body = client.post("/api/workflow/run", headers=headers,
                       json={"modelId": "lettuce-earth-growth-v2",
                             "inputs": LETTUCE, "save": False}).json()
    assert body["saved"] is None
    assert client.get("/api/analyses", headers=headers).json()["analyses"] == []


# ------------------------------------------------------------------------- analyses

def test_saved_analysis_is_listed_and_retrievable_by_its_owner(client):
    headers = _headers(client, "owner")
    created = client.post("/api/workflow/run", headers=headers,
                          json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE,
                                "save": True, "title": "Lettuce at 20 days"}).json()
    analysis_id = created["saved"]["id"]
    assert created["saved"]["title"] == "Lettuce at 20 days"

    listing = client.get("/api/analyses", headers=headers).json()["analyses"]
    assert [row["id"] for row in listing] == [analysis_id]

    fetched = client.get(f"/api/analyses/{analysis_id}", headers=headers).json()
    assert fetched["analysis"]["output"]["prediction"] == created["output"]["prediction"]


def test_saved_analysis_is_invisible_to_another_account(client):
    alice = _headers(client, "alice")
    bob = _headers(client, "bob")
    created = client.post("/api/workflow/run", headers=alice,
                          json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE,
                                "save": True}).json()
    analysis_id = created["saved"]["id"]

    assert client.get("/api/analyses", headers=bob).json()["analyses"] == []
    # 404, not 403: the API must not confirm that another user's id exists.
    assert client.get(f"/api/analyses/{analysis_id}", headers=bob).status_code == 404
    assert client.delete(f"/api/analyses/{analysis_id}", headers=bob).status_code == 404
    assert client.get(f"/api/analyses/{analysis_id}/export/json",
                      headers=bob).status_code == 404


def test_analyses_require_authentication(client):
    assert client.get("/api/analyses").status_code == 401
    assert client.get("/api/analyses/anything").status_code == 401
    assert client.get("/api/analyses/anything/export/json").status_code == 401


def test_owner_can_delete_their_analysis_and_only_once(client):
    headers = _headers(client, "deleter")
    created = client.post("/api/workflow/run", headers=headers,
                          json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE,
                                "save": True}).json()
    analysis_id = created["saved"]["id"]
    assert client.delete(f"/api/analyses/{analysis_id}", headers=headers).status_code == 204
    assert client.get(f"/api/analyses/{analysis_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/analyses/{analysis_id}", headers=headers).status_code == 404


def test_retired_or_invalid_run_is_never_saved(client):
    headers = _headers(client, "invalidrun")
    for model_id, inputs in (("mizuna-microbial-load-v1", {"experiment": 1}),
                             ("lettuce-earth-growth-v2", {**LETTUCE, "airTemperature": 900})):
        assert client.post("/api/workflow/run", headers=headers,
                           json={"modelId": model_id, "inputs": inputs,
                                 "save": True}).status_code in (410, 422)
    assert client.get("/api/analyses", headers=headers).json()["analyses"] == []


# -------------------------------------------------------------------------- exports

def _saved(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = {"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE,
               "save": True, "title": "Export fixture", **overrides}
    response = client.post("/api/workflow/run", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_json_export_round_trips_the_same_numbers_as_the_api(client):
    headers = _headers(client, "exportjson")
    created = _saved(client, headers)
    analysis_id = created["saved"]["id"]

    response = client.get(f"/api/analyses/{analysis_id}/export/json", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "no-store" in response.headers.get("cache-control", "")
    exported = response.json()

    assert exported["output"]["prediction"] == created["output"]["prediction"]
    assert exported["inputs"] == created["inputs"]
    assert exported["output"]["calibrated"] is False


def test_csv_export_states_the_prediction_and_its_status(client):
    headers = _headers(client, "exportcsv")
    created = _saved(client, headers)
    analysis_id = created["saved"]["id"]

    response = client.get(f"/api/analyses/{analysis_id}/export/csv", headers=headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    rows = list(csv.reader(io.StringIO(response.text)))
    fields = {row[0]: row[1] for row in rows if len(row) == 2 and not row[0].startswith("#")}

    assert float(fields["prediction"]) == created["output"]["prediction"]
    assert fields["calibrated"] == "False"
    assert fields["model_id"] == "lettuce-earth-growth-v2"
    assert fields["output_kind"] == "regression"
    # The disclaimer must travel with the numbers, not only live in the UI.
    assert any("not a measurement" in " ".join(row).lower() for row in rows)


def test_markdown_export_carries_citations_and_limitations(client):
    headers = _headers(client, "exportmd")
    created = _saved(client, headers)
    analysis_id = created["saved"]["id"]

    response = client.get(f"/api/analyses/{analysis_id}/export/md", headers=headers)
    assert response.status_code == 200
    text = response.text
    for citation in created["evidence"]["citations"]:
        assert citation["sourceId"] in text
    assert "## Limitations" in text
    assert "not a measured plant observation" in text


def test_export_rejects_an_unknown_format(client):
    headers = _headers(client, "exportfmt")
    created = _saved(client, headers)
    response = client.get(f"/api/analyses/{created['saved']['id']}/export/pdf",
                          headers=headers)
    assert response.status_code == 422


def test_run_and_save_requires_authentication_and_always_persists(client):
    assert client.post("/api/workflow/run-and-save",
                       json={"modelId": "lettuce-earth-growth-v2",
                             "inputs": LETTUCE}).status_code == 401
    headers = _headers(client, "runandsave")
    response = client.post("/api/workflow/run-and-save", headers=headers,
                           json={"modelId": "lettuce-earth-growth-v2", "inputs": LETTUCE})
    assert response.status_code == 200
    assert response.json()["saved"]["id"]
    assert len(client.get("/api/analyses", headers=headers).json()["analyses"]) == 1
