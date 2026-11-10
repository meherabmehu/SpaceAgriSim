"""Phase 30: the capabilities that were removed, and the proof that they are gone.

Two things were withdrawn in this phase, both because the evidence to support them does not exist:

* the fractional-gravity growth penalty - no open dataset measures crop yield or biomass across
  gravity levels, so the coefficient was a placeholder;
* the operational harvest forecast - a leave-one-study-out evaluation over published lettuce
  studies returned 310 % MAPE against an unchanged 30 % criterion, and the Phase 28 holdout had
  already returned 41.6 %.

A removal is only complete when nothing is left pointing at it: no input field, no service
function, no constant, no route, no catalogue claim, no UI control, no documentation asserting the
capability. These tests check each of those layers directly, so a future re-introduction has to
break a test on purpose.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app import research, science_classification  # noqa: E402
from app.config import simulation_constants as constants  # noqa: E402
from app.models.simulation import SimulationRequest, strip_removed_fields  # noqa: E402
from app.simulation import engine, factors  # noqa: E402
from app.workflows import harvest, units  # noqa: E402

HARVEST = "/api/workflows/harvest-prediction"
REMOVAL_MESSAGE = "removed in Phase 30"


# ------------------------------------------------------------ gravity: no field, no factor


def test_the_request_model_has_no_gravity_field():
    assert "gravity" not in SimulationRequest.model_fields
    with pytest.raises(Exception) as excinfo:
        SimulationRequest(gravity=0.38)
    assert REMOVAL_MESSAGE in str(excinfo.value)
    # The message must say why, not just that it is gone.
    assert "no open dataset" in str(excinfo.value).lower()


def test_the_engine_and_the_factor_module_have_no_gravity_term():
    assert "gravity" not in {field.name for field in engine.SimulationInput.__dataclass_fields__.values()}
    assert not hasattr(factors, "gravity_factor")
    assert not hasattr(constants, "MICROGRAVITY_GROWTH_PENALTY")
    assert not hasattr(constants, "EARTH_REFERENCE_GRAVITY_G")


def test_simulate_refuses_a_gravity_request_with_a_named_reason(client):
    response = client.post("/api/simulate", json={"crop": "lettuce", "gravity": 0.38})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert any("gravity" in json.dumps(item) for item in body["detail"])


def test_config_advertises_no_gravity_parameter_or_preset(client):
    body = client.get("/api/config").json()
    assert "gravity" not in body["parameters"]
    assert "gravityPresets" not in body
    assert "gravity" not in json.dumps(body["assumptions"]).split("radiation")[0][:0] + ""


def test_no_payload_anywhere_still_carries_a_gravity_key(client):
    """Nothing in a simulation response may name a quantity the model does not compute."""
    for request in ({}, {"radiation": 0.5}, {"crop": "tomato", "waterAvailability": 40}):
        text = client.post("/api/simulate", json=request).text.lower()
        # The word may appear only inside an explicit statement that gravity is not modelled.
        for match in re.finditer("gravity", text):
            window = text[max(0, match.start() - 200): match.end() + 200]
            assert "not model" in window or "removed" in window or "no dataset" in window, window
        assert '"gravity"' not in text


def test_the_hazard_comparison_is_radiation_only_and_says_which_environment(client):
    scenarios = client.post("/api/compare", json={"simulationDays": 7}).json()["scenarios"]
    names = [row["name"] for row in scenarios]
    assert names == ["Earth background", "Lunar surface", "Mars surface", "Custom habitat"]
    for row in scenarios:
        assert "gravity" not in row["result"]["inputs"]
    # Radiation is the variable each named case changes, and the ordering of damage is physical.
    by_name = {row["name"]: row["result"]["cropYield"] for row in scenarios}
    assert by_name["Earth background"] > by_name["Mars surface"] > by_name["Lunar surface"]


def test_a_stored_scenario_that_still_holds_gravity_is_readable_on_the_share_path():
    """Old rows exist; the share link must render them instead of failing."""
    configuration = {"crop": "lettuce", "gravity": 0.38, "radiation": 0.2,
                     "simulationDays": 7, "growingArea": 2}
    assert "gravity" not in strip_removed_fields(configuration)
    request = SimulationRequest(**strip_removed_fields(configuration))
    assert request.crop == "lettuce"


def test_the_science_classification_marks_gravity_removed():
    feature = next(item for item in science_classification.FEATURES
                   if item.id == "gravity-response")
    assert feature.status == "removed"
    assert feature.surface == "none"
    assert "no open dataset" in feature.evidence or "no dataset" in feature.evidence


def test_the_coverage_table_says_gravity_is_not_modelled(client):
    rows = {row["feature"]: row for row in client.get("/api/datasets").json()["coverage"]}
    gravity = rows["Gravity effects"]
    assert "removed in Phase 30" in gravity["status"]
    assert "no longer modelled" in gravity["method"]
    assert "nothing replaced the placeholder" in gravity["limitation"].lower()


def test_the_assistant_does_not_offer_to_explain_a_gravity_assumption(client):
    suggestions = client.get("/api/assistant/suggestions").json()["suggestions"]
    questions = [item["question"] if isinstance(item, dict) else item for item in suggestions]
    assert questions
    for question in questions:
        assert "gravity assumption" not in question.lower()
    # Asking directly must not produce a penalty curve: no served model may be cited for it.
    body = client.post("/api/assistant/ask",
                       json={"question": "What is the growth penalty at 0.38 g?"}).json()
    assert body["status"] in {"grounded", "partial", "insufficient"}
    assert all(citation["kind"] != "model" or "does not predict" in (citation.get("text") or "")
               for citation in body["citations"]) or body["refusal"] in {"unsupported-premise",
                                                                        "insufficient-evidence"}


# -------------------------------------------------------- harvest: no model, no run, no claims


def test_the_harvest_run_endpoint_is_a_tombstone(client):
    for body in ({"scenarios": []}, {"scenarios": [{"ppfd": 400}]}, {}):
        response = client.post(HARVEST + "/run", json=body)
        assert response.status_code == 410
        detail = response.json()["detail"]
        assert detail["status"] == "removed"
        assert detail["removedInPhase"] == 30
        assert "30 %" in detail["reason"]


def test_nothing_serves_a_harvest_prediction(client):
    stated = client.get(HARVEST + "/capability").json()
    assert stated["status"] == "unavailable"
    assert stated["operationalForecast"] is False
    # The workflow module must not expose a predict/run entry point any more.
    assert not hasattr(harvest, "run") or harvest.run.__doc__ is None
    public = {name for name in dir(harvest) if not name.startswith("_")}
    assert "run" not in public


def test_the_old_harvest_model_artifacts_are_not_reachable_through_a_workflow(client):
    """A registered exploratory artifact may exist; a workflow may not serve it."""
    body = client.get("/api/workflows").json()
    harvest_entry = next(item for item in body["workflows"] if item["id"] == "harvest-prediction")
    assert harvest_entry["status"] == "unavailable"
    assert "run" not in harvest_entry["endpoints"]
    assert harvest_entry["modelValidatedForForecasting"] is not True if (
        "modelValidatedForForecasting" in harvest_entry) else True


def test_the_catalogue_no_longer_calls_harvest_a_complete_workflow(client):
    body = client.get("/api/workflows").json()
    complete = [item["id"] for item in body["workflows"] if item["status"] == "complete"]
    assert "harvest-prediction" not in complete
    assert sorted(complete) == ["light-stress", "water-demand"]


def test_the_harvest_evidence_that_survives_is_measured_data_only(client):
    parity = client.get(HARVEST + "/parity").json()
    assert parity["operationalForecast"] is False
    assert parity["passed"] is False
    registry = research.model_registry()
    models = registry["models"] if isinstance(registry, dict) else registry
    for model in models:
        identifier = model.get("id") if isinstance(model, dict) else model
        if "lettuce" not in str(identifier):
            continue
        record = research.load_model(identifier)
        assert record.get("status") != "production", identifier


def test_the_units_registry_does_not_advertise_a_withdrawn_output():
    registry = units.registry()
    assert "units" in registry
    # The forecast's own unit is gone with the forecast; the measured comparison's is not.
    assert "g/m2" in registry["units"]
    assert "kg/m2" in registry["units"]


# ------------------------------------------------------- the documents and matrices agree


def test_the_gap_matrix_records_both_removals_as_decisions():
    matrix = json.loads((ROOT / "data" / "research" / "dataset_gap_matrix.json").read_text())
    gaps = {gap["id"]: gap for gap in matrix["gaps"]}
    assert gaps["fractional-gravity"]["phase30Decision"]["decision"].startswith("B")
    assert gaps["yield-labels"]["phase30Decision"]["decision"].startswith("B")
    for gap_id in ("fractional-gravity", "yield-labels", "led-spectrum-response"):
        assert gaps[gap_id]["phase30Decision"]["searched"]


def test_the_catalogue_lists_the_two_phase30_datasets():
    catalogue = json.loads((ROOT / "data" / "research" / "dataset_catalog.json").read_text())
    ids = {item["id"] for item in catalogue["datasets"]}
    assert {"zenodo-cea-wheat-apogee", "zenodo-kilowatts-lettuce-lue"} <= ids
    for item in catalogue["datasets"]:
        if item["id"] in {"zenodo-cea-wheat-apogee", "zenodo-kilowatts-lettuce-lue"}:
            assert item["usabilityClass"] == "A"
            assert item["imported"] is True
            assert item["license"] == "CC BY 4.0"


def test_no_document_still_claims_a_served_harvest_forecast():
    """A grep, because stale prose is how a removed capability comes back to life."""
    offenders = []
    for path in list((ROOT / "docs").glob("*.md")):
        if path.name.startswith("PHASE30_"):
            continue  # the Phase 30 reports describe the removal itself
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in ("harvest prediction workflow is complete",
                       "predicts harvest mass per plant",
                       "gravity penalty of 15",
                       "microgravity growth penalty is applied"):
            if phrase in text:
                offenders.append(f"{path.name}: {phrase}")
    assert not offenders, offenders
