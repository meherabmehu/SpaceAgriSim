"""Scenario persistence through the HTTP API: create, read, update, delete, ownership.

These run on whatever database the suite is configured with (a scratch SQLite file by default), so
they cover the routes and the ownership rules on every CI run. The PostgreSQL-specific guarantees -
that a configured URL really is used, and that rows survive disposing the engine - live in
`test_postgresql_persistence.py`, which needs a server.

Before this file the API could only create and list scenarios. A saved configuration could not be
fetched by id, renamed, re-configured or deleted, so "the data is persisted" was not observable
through the product at all.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "CorrectHorseBattery9!"

CONFIGURATION = {
    "crop": "lettuce", "simulationDays": 35, "gravity": 1.0, "radiation": 0.01,
    "waterAvailability": 100.0, "lightHours": 16.0, "co2Level": 420.0, "growingArea": 10.0,
    "earthComparisonMode": "matched", "lightIntensity": 400.0, "temperature": 22.0,
    "humidity": 65.0, "waterRecyclingEfficiency": 90.0, "lightSpectrum": "balanced",
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _account(client: TestClient, label: str = "scenario") -> dict:
    """A fresh authenticated account, as headers."""
    email = f"{label}-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _create(client: TestClient, headers: dict, name: str = "audit scenario", **config) -> dict:
    body = {"name": name, "configuration": {**CONFIGURATION, **config}}
    response = client.post("/api/scenarios", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def test_create_then_retrieve_by_id(client):
    headers = _account(client)
    created = _create(client, headers, growingArea=12.5)
    assert created["id"]
    assert created["owner_id"] is None or isinstance(created["owner_id"], str)

    fetched = client.get(f"/api/scenarios/{created['id']}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == created["id"]
    assert body["name"] == "audit scenario"
    assert body["configuration"]["growingArea"] == 12.5
    assert body["created_at"]  # the existing scenario contract is the raw row shape


def test_update_changes_the_name_and_the_configuration(client):
    headers = _account(client)
    created = _create(client, headers)

    renamed = client.patch(f"/api/scenarios/{created['id']}", json={"name": "renamed"},
                           headers=headers)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "renamed"
    # A partial update keeps the field it was not given.
    assert renamed.json()["configuration"]["growingArea"] == 10.0

    reconfigured = client.patch(f"/api/scenarios/{created['id']}",
                                json={"configuration": {**CONFIGURATION, "simulationDays": 60}},
                                headers=headers)
    assert reconfigured.status_code == 200
    assert reconfigured.json()["name"] == "renamed"
    assert reconfigured.json()["configuration"]["simulationDays"] == 60

    # And the change is what a later read returns, not just what the writer was told.
    assert client.get(f"/api/scenarios/{created['id']}", headers=headers).json()[
        "configuration"]["simulationDays"] == 60


def test_delete_removes_the_scenario_from_every_read(client):
    headers = _account(client)
    created = _create(client, headers)

    assert client.delete(f"/api/scenarios/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/scenarios/{created['id']}", headers=headers).status_code == 404
    listed = client.get("/api/scenarios", headers=headers).json()["scenarios"]
    assert all(row["id"] != created["id"] for row in listed)
    # Deleting twice is a 404, not a silent success.
    assert client.delete(f"/api/scenarios/{created['id']}", headers=headers).status_code == 404


def test_listing_shows_only_the_callers_scenarios(client):
    alice, bob = _account(client, "alice"), _account(client, "bob")
    mine = _create(client, alice, name="alice only")
    theirs = _create(client, bob, name="bob only")
    listed = {row["id"] for row in client.get("/api/scenarios", headers=alice).json()["scenarios"]}
    assert mine["id"] in listed
    assert theirs["id"] not in listed


# ---------------------------------------------------------------------------
# Ownership and access control
# ---------------------------------------------------------------------------
def test_another_account_cannot_read_update_or_delete(client):
    owner, stranger = _account(client, "owner"), _account(client, "stranger")
    created = _create(client, owner, name="private")

    # 404 rather than 403 in every case: a distinguishable answer would confirm the id exists.
    assert client.get(f"/api/scenarios/{created['id']}", headers=stranger).status_code == 404
    assert client.patch(f"/api/scenarios/{created['id']}", json={"name": "hijacked"},
                        headers=stranger).status_code == 404
    assert client.delete(f"/api/scenarios/{created['id']}", headers=stranger).status_code == 404

    # The owner's row is unchanged by all three attempts.
    still = client.get(f"/api/scenarios/{created['id']}", headers=owner).json()
    assert still["name"] == "private"


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_scenario_routes_require_authentication(client, method):
    created = _create(client, _account(client, "auth"))
    kwargs = {"json": {"name": "x"}} if method == "patch" else {}
    response = getattr(client, method)(f"/api/scenarios/{created['id']}", **kwargs)
    assert response.status_code in {401, 403}, response.text


def test_unknown_scenario_id_is_not_found(client):
    headers = _account(client, "unknown")
    missing = "00000000-0000-4000-8000-000000000000"
    assert client.get(f"/api/scenarios/{missing}", headers=headers).status_code == 404
    assert client.patch(f"/api/scenarios/{missing}", json={"name": "x"},
                        headers=headers).status_code == 404
    assert client.delete(f"/api/scenarios/{missing}", headers=headers).status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_an_empty_update_is_rejected(client):
    headers = _account(client, "empty-update")
    created = _create(client, headers)
    assert client.patch(f"/api/scenarios/{created['id']}", json={},
                        headers=headers).status_code == 422


def test_an_invalid_configuration_is_rejected_and_nothing_is_stored(client):
    headers = _account(client, "invalid")
    before = len(client.get("/api/scenarios", headers=headers).json()["scenarios"])
    created = _create(client, headers)
    rejected = client.patch(f"/api/scenarios/{created['id']}",
                            json={"configuration": {**CONFIGURATION, "gravity": 9.0}},
                            headers=headers)
    assert rejected.status_code == 422
    after = client.get(f"/api/scenarios/{created['id']}", headers=headers).json()
    assert after["configuration"]["gravity"] == 1.0
    assert len(client.get("/api/scenarios", headers=headers).json()["scenarios"]) == before + 1


# ---------------------------------------------------------------------------
# Saved analyses are simulation results, and they persist too
# ---------------------------------------------------------------------------
def test_a_saved_analysis_can_be_retrieved_after_being_written(client):
    headers = _account(client, "analysis")
    run = client.post("/api/workflow/run-and-save", headers=headers, json={
        "modelId": "lettuce-earth-growth-v3",
        "inputs": {"daysAfterTransplant": 28.0, "airTemperature": 27.5,
                   "rootTemperature": 27.5, "dailyLightIntegral": 16.9},
    })
    assert run.status_code == 200, run.text
    saved = run.json()["saved"]
    assert saved and saved["id"]

    fetched = client.get(f"/api/analyses/{saved['id']}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["modelId"] == "lettuce-earth-growth-v3"
    # The stored payload is the model output, not a re-run of it.
    assert body["analysis"]["output"]["kind"] == "regression"
    assert body["analysis"]["output"]["isMeasurement"] is False

    listed = client.get("/api/analyses", headers=headers).json()
    assert any(row["id"] == saved["id"] for row in listed["analyses"])
    assert listed["usage"]["count"] >= 1

    assert client.delete(f"/api/analyses/{saved['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/analyses/{saved['id']}", headers=headers).status_code == 404


def test_an_analysis_belongs_only_to_its_owner(client):
    owner, stranger = _account(client, "an-owner"), _account(client, "an-stranger")
    run = client.post("/api/workflow/run-and-save", headers=owner, json={
        "modelId": "lettuce-earth-growth-v3",
        "inputs": {"daysAfterTransplant": 28.0, "airTemperature": 27.5,
                   "rootTemperature": 27.5, "dailyLightIntegral": 16.9},
    })
    analysis_id = run.json()["saved"]["id"]
    assert client.get(f"/api/analyses/{analysis_id}", headers=stranger).status_code == 404
    assert client.delete(f"/api/analyses/{analysis_id}", headers=stranger).status_code == 404
    assert client.get(f"/api/analyses/{analysis_id}", headers=owner).status_code == 200


# ---------------------------------------------------------------------------
# Share links are rows too
# ---------------------------------------------------------------------------
def test_a_share_link_survives_and_dies_with_its_scenario(client):
    headers = _account(client, "share")
    created = _create(client, headers, name="shared config")
    minted = client.post(f"/api/scenarios/{created['id']}/share", headers=headers)
    assert minted.status_code == 201, minted.text
    token = minted.json()["token"]

    public = client.get(f"/api/shared/{token}")
    assert public.status_code == 200
    assert public.json()["name"] == "shared config"
    # The public view carries no account data.
    assert "owner" not in json.dumps(public.json())

    assert client.delete(f"/api/scenarios/{created['id']}", headers=headers).status_code == 204
    # A link that outlived its scenario would be a dangling reference.
    assert client.get(f"/api/shared/{token}").status_code == 404


# ---------------------------------------------------------------------------
# Readiness reflects the database, not a hard-coded string
# ---------------------------------------------------------------------------
def test_readiness_reports_the_schema_state_not_only_connectivity(client):
    body = client.get("/api/ready")
    assert body.status_code == 200, body.text
    payload = body.json()
    assert payload["status"] == "ready"
    assert payload["database"] == "available"
    # A reachable server with missing tables is reported by databaseSchema, and /ready refuses.
    assert payload["databaseSchema"] == "present"
    assert payload["storage"]["durable"] is True
