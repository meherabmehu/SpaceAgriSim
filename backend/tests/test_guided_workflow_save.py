"""Saving a guided-workflow reading: persistence, ownership, duplicates and retrieval.

What was broken and what these tests hold down
----------------------------------------------
The save button on the mission workspace sent a configuration and reported "Scenario saved to
mission history." - in a notice rendered at the top of a page the button sits at the bottom of, with
no identifier, no way to reopen the row, and no guard against the double press that a slow save
invites. A guided-workflow save had a second problem: a scenario that records a habitat configuration
and *nothing about the measured band the user was reading* cannot reproduce the reading.

These tests drive the real HTTP API against the suite's database. They assert that a save is a row
the server can read back by id, that the workflow context survives the round trip intact, that a
second identical press returns the first row's id instead of writing a twin, that a different name is
a different scenario, and that one account can neither read nor collide with another's rows.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workflows import cea_evidence

PASSWORD = "CorrectHorseBattery9!"

CONFIGURATION = {
    "crop": "lettuce", "simulationDays": 30, "radiation": 0.3,
    "waterAvailability": 100.0, "lightHours": 16.0, "co2Level": 1000.0, "growingArea": 10.0,
    "earthComparisonMode": "matched", "lightIntensity": 300.0, "temperature": 22.0,
    "humidity": 60.0, "waterRecyclingEfficiency": 90.0, "lightSpectrum": "balanced",
}

CONTEXT = {
    "workflow": "cea-evidence",
    "factor": "co2Ppm",
    "band": "ambient",
    "bandLabel": "CO2 concentration ≤ 450 ppm",
    "measured": {"n": 29, "mean": 0.671, "median": 0.699, "min": 0.062, "max": 1.442},
    "dataset": {"id": "cea-wheat-apogee", "doi": "10.5281/zenodo.17764612", "license": "CC BY 4.0"},
    "evidenceClass": "measured-observation",
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _account(client: TestClient, label: str = "save") -> dict:
    email = f"{label}-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _body(name: str = "CEA wheat · co2Ppm · ≤ 450 ppm", context: dict | None = CONTEXT,
          configuration: dict | None = None) -> dict:
    return {"name": name, "configuration": {**CONFIGURATION, **(configuration or {})},
            "context": CONTEXT if context is None else context}


# ---------------------------------------------------------------------------
# A save is a row the server can read back
# ---------------------------------------------------------------------------
def test_a_save_returns_the_identifier_the_database_stored(client):
    headers = _account(client, "save-id")
    response = client.post("/api/scenarios", json=_body(), headers=headers)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["id"] and len(saved["id"]) == 36
    assert saved["created_at"]

    fetched = client.get(f"/api/scenarios/{saved['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == saved["id"]


def test_the_workflow_context_survives_the_round_trip(client):
    """Reopening the scenario must reproduce the reading, not only the habitat configuration."""
    headers = _account(client, "save-context")
    saved = client.post("/api/scenarios", json=_body(), headers=headers).json()
    reopened = client.get(f"/api/scenarios/{saved['id']}", headers=headers).json()["context"]
    assert reopened == CONTEXT


def test_the_saved_scenario_is_listed_for_its_owner(client):
    headers = _account(client, "save-list")
    saved = client.post("/api/scenarios", json=_body(), headers=headers).json()
    listing = client.get("/api/scenarios", headers=headers).json()
    ids = [row["id"] for row in listing["scenarios"]]
    assert saved["id"] in ids
    row = next(item for item in listing["scenarios"] if item["id"] == saved["id"])
    assert row["context"]["bandLabel"] == CONTEXT["bandLabel"]


def test_a_scenario_without_context_is_still_a_complete_record(client):
    """A Mission Control save has no workflow, and that is a whole record, not a partial one."""
    headers = _account(client, "save-plain")
    saved = client.post("/api/scenarios",
                        json={"name": "plain", "configuration": CONFIGURATION},
                        headers=headers)
    assert saved.status_code == 201, saved.text
    assert saved.json()["context"] is None


# ---------------------------------------------------------------------------
# Duplicates: a second press is the same scenario, a second name is not
# ---------------------------------------------------------------------------
def test_the_same_save_twice_returns_the_first_identifier(client):
    headers = _account(client, "save-duplicate")
    first = client.post("/api/scenarios", json=_body(), headers=headers)
    assert first.status_code == 201
    second = client.post("/api/scenarios", json=_body(), headers=headers)
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert detail["duplicate"] is True
    assert detail["scenarioId"] == first.json()["id"]
    assert detail["message"]
    assert len(client.get("/api/scenarios", headers=headers).json()["scenarios"]) == 1


def test_a_different_name_over_the_same_configuration_is_a_second_scenario(client):
    headers = _account(client, "save-names")
    first = client.post("/api/scenarios", json=_body("baseline"), headers=headers)
    second = client.post("/api/scenarios", json=_body("with the CO2 raised"), headers=headers)
    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]
    assert len(client.get("/api/scenarios", headers=headers).json()["scenarios"]) == 2


def test_a_different_band_is_a_second_scenario(client):
    """Same mission, same name, another measured band: two readings, so two records."""
    headers = _account(client, "save-bands")
    other = {**CONTEXT, "band": "high", "bandLabel": "CO2 concentration > 800 ppm",
             "measured": {"n": 5, "mean": 1.468}}
    first = client.post("/api/scenarios", json=_body(), headers=headers)
    second = client.post("/api/scenarios", json=_body(context=other), headers=headers)
    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]


def test_a_different_configuration_is_a_second_scenario(client):
    headers = _account(client, "save-config")
    first = client.post("/api/scenarios", json=_body(), headers=headers)
    second = client.post("/api/scenarios", json=_body(configuration={"temperature": 26.0}),
                         headers=headers)
    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["configuration"]["temperature"] == 26.0


# ---------------------------------------------------------------------------
# Ownership and authentication
# ---------------------------------------------------------------------------
def test_saving_requires_an_account(client):
    response = client.post("/api/scenarios", json=_body("anonymous"))
    assert response.status_code == 401


def test_one_account_cannot_read_another_account_scenario(client):
    alice = _account(client, "save-alice")
    bob = _account(client, "save-bob")
    saved = client.post("/api/scenarios", json=_body(), headers=alice).json()
    assert client.get(f"/api/scenarios/{saved['id']}", headers=bob).status_code == 404


def test_another_account_can_save_the_same_body_without_colliding(client):
    alice = _account(client, "save-collide-a")
    bob = _account(client, "save-collide-b")
    first = client.post("/api/scenarios", json=_body(), headers=alice)
    second = client.post("/api/scenarios", json=_body(), headers=bob)
    # Same content, different owners: two rows, and neither account is told it already has one.
    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]
    assert len(client.get("/api/scenarios", headers=bob).json()["scenarios"]) == 1


def test_bob_does_not_see_alices_scenario_in_his_list(client):
    alice = _account(client, "save-private-a")
    bob = _account(client, "save-private-b")
    client.post("/api/scenarios", json=_body(), headers=alice)
    assert client.get("/api/scenarios", headers=bob).json()["scenarios"] == []


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("workflow", ["harvest", "", "cea"])
def test_an_unknown_workflow_is_rejected(client, workflow):
    headers = _account(client, "save-workflow")
    response = client.post("/api/scenarios",
                           json=_body(context={**CONTEXT, "workflow": workflow}),
                           headers=headers)
    assert response.status_code == 422


def test_an_unknown_context_field_is_rejected(client):
    headers = _account(client, "save-extra")
    response = client.post("/api/scenarios",
                           json=_body(context={**CONTEXT, "predicted": 1.2}), headers=headers)
    assert response.status_code == 422


def test_an_invalid_configuration_is_rejected_and_nothing_is_stored(client):
    headers = _account(client, "save-invalid")
    bad = {**CONFIGURATION, "waterAvailability": 500.0}
    response = client.post("/api/scenarios",
                           json={"name": "invalid", "configuration": bad, "context": CONTEXT},
                           headers=headers)
    assert response.status_code == 422
    assert client.get("/api/scenarios", headers=headers).json()["scenarios"] == []


def test_a_blank_name_is_rejected(client):
    headers = _account(client, "save-blank")
    response = client.post("/api/scenarios", json=_body("   "), headers=headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# The context a save records is the one the workflow reported
# ---------------------------------------------------------------------------
def test_the_stored_summary_matches_the_run_it_was_taken_from(client):
    headers = _account(client, "save-run")
    group = client.post("/api/workflows/light-stress/controlled-environment/run",
                        json={"selections": [{"factor": "co2Ppm", "band": "ambient"}]}
                        ).json()["groups"][0]
    context = {**CONTEXT, "bandLabel": group["bandLabel"], "measured": group["measured"]}
    saved = client.post("/api/scenarios",
                        json=_body(name="from the run", context=context), headers=headers).json()
    reopened = client.get(f"/api/scenarios/{saved['id']}", headers=headers).json()["context"]
    assert reopened["measured"] == group["measured"]
    assert reopened["bandLabel"] == group["bandLabel"]
    band = next(band for factor in cea_evidence.FACTORS
                if factor["publicName"] == "co2Ppm"
                for band in factor["bands"] if band["id"] == "ambient")
    expected = sum(1 for row in cea_evidence._experiments()
                   if cea_evidence._band(next(f for f in cea_evidence.FACTORS
                                              if f["publicName"] == "co2Ppm"), band, row))
    assert reopened["measured"]["n"] == expected >= 3


# ---------------------------------------------------------------------------
# The column is an additive migration, and adding it is idempotent
# ---------------------------------------------------------------------------
def test_the_context_column_is_added_to_an_existing_database(tmp_path):
    """A database created before this column keeps its rows and gains the column."""
    from sqlalchemy import create_engine, inspect, text

    from app import storage

    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE scenarios (id VARCHAR(36) PRIMARY KEY, name VARCHAR(120) NOT NULL, "
            "created_at VARCHAR(40) NOT NULL, configuration TEXT NOT NULL, "
            "model_version VARCHAR(40) NOT NULL, owner_id VARCHAR(36))"))
        connection.execute(text(
            "INSERT INTO scenarios (id, name, created_at, configuration, model_version, owner_id) "
            "VALUES ('legacy-id', 'kept', '2026-01-01T00:00:00+00:00', '{}', 'assumptions-2.0', "
            "'owner')"))

    assert "context" not in {column["name"] for column in inspect(engine).get_columns("scenarios")}
    storage._migrate_scenarios_context(engine)
    assert "context" in {column["name"] for column in inspect(engine).get_columns("scenarios")}

    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, context FROM scenarios")).one()
    assert row[0] == "kept" and row[1] is None, "the migration must not rewrite existing rows"

    # Running it again is a no-op, not an error: every start runs it.
    storage._migrate_scenarios_context(engine)
    assert "context" in {column["name"] for column in inspect(engine).get_columns("scenarios")}
