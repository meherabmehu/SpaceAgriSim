"""Phase 32: the features that were removed must be absent, not merely undocumented.

Phase 26 listed twelve candidate features and Phase 27 measured how complete each one was. Phase 32
closed the list: four are complete at the level they claim (one of them served as a measured
comparison only), and eight are removed from the product because the data needed to support them
does not exist in an obtainable, reproducible form.

A removal that only exists in a document is not a removal, so each test below checks a *surface*:
routes, request schemas, response fields, the catalogue, the assistant corpus and the coverage
matrix. Anything that could resurrect one of these features quietly fails here.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import evidence, workflow
from app.main import app
from app.research import ROOT

client = TestClient(app)
PATHS = set(app.openapi()["paths"])

REMOVED = ["nutrient-balance", "cultivar-metadata", "mission-energy", "fractional-gravity",
           "substrate-water", "imagery", "long-run-climate", "yield-labels"]


def _response_text(payload) -> str:
    return json.dumps(payload).lower()


# ------------------------------------------------------------------ routes

def test_no_removed_feature_has_a_route():
    """A capability with a route has not been removed, whatever the docs say."""
    fragments = ["nutrient", "cultivar", "mission-energy", "energy-budget", "substrate",
                 "rootzone", "root-zone", "water-potential", "image", "imagery", "climate",
                 "harvest", "gravity"]
    for path in PATHS:
        lowered = path.lower()
        for fragment in fragments:
            assert fragment not in lowered, f"{path} re-introduces the {fragment} capability"


def test_the_simulation_response_has_no_removed_feature_field():
    body = client.post("/api/simulate", json={"crop": "lettuce", "simulationDays": 35}).json()
    keys = set(body) | set(body.get("environment", {})) | set(body.get("space", {}))
    for key in keys:
        for fragment in ("nutrient", "cultivar", "energy", "gravity", "imagery", "substrate"):
            assert fragment not in key.lower(), key
    text = _response_text(body)
    for marker in ("kwh", "rootzone", "waterpotential", "cmip", "dosegy"):
        assert marker not in text


def test_a_gravity_input_is_refused_by_schema():
    response = client.post("/api/simulate",
                           json={"crop": "lettuce", "simulationDays": 20, "gravityLevel": 0.38})
    assert response.status_code == 422


# ------------------------------------------------------------------ catalogue and schemas

def test_no_model_takes_a_cultivar_nutrient_or_gravity_input():
    for row in workflow.model_catalogue()["models"]:
        features = [str(feature).lower() for feature in row.get("features") or []]
        for fragment in ("cultivar", "nutrient", "gravity"):
            assert not any(fragment in feature for feature in features), row["modelId"]
        assert not any(fragment in str(row.get("task", "")).lower()
                       for fragment in ("mission energy", "imagery", "climate projection"))


def test_no_request_schema_accepts_a_removed_capability():
    """A schema is a promise that the platform will compute something with the input."""
    document = app.openapi()
    schemas = document.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        properties = set(((schema or {}).get("properties") or {}))
        for fragment in ("nutrient", "cultivar", "gravity", "imagery", "missionEnergy",
                         "climateScenario", "rootZoneWaterPotential"):
            assert not any(fragment.lower() in prop.lower() for prop in properties), (name, fragment)


# ------------------------------------------------------------------ assistant corpus

@pytest.mark.parametrize("phrase", [
    "predict nutrient", "nutrient recommendation", "estimate mission energy",
    "mission energy budget", "classify plant health", "healthy leaf image",
    "future climate siting", "recommend a cultivar", "cultivar-specific parameter",
    "root-zone water status", "predict root zone",
])
def test_the_assistant_never_offers_a_removed_capability(phrase):
    """Topical mentions are allowed - the corpus explains *why* these are unavailable.

    An *offer* is not: no passage the retriever can quote may promise to compute one of them.
    """
    for passage in evidence.corpus()["passages"]:
        assert phrase not in passage.text.lower(), (phrase, passage.id)


# ------------------------------------------------------------------ the matrices

def test_the_coverage_matrix_agrees_the_features_are_gone():
    coverage = json.loads((ROOT / "data" / "research" / "phase27" /
                           "feature_implementation_coverage.json").read_text(encoding="utf-8"))
    assert {feature["id"] for feature in coverage["features"]} == {
        "measured-eta", "independent-et0", "yield-labels", "led-spectrum-response",
        "nutrient-balance", "cultivar-metadata", "mission-energy", "fractional-gravity",
        "substrate-water", "sub-daily-weather", "imagery", "long-run-climate"}
    for feature in coverage["features"]:
        disposition = feature["phase32Disposition"]
        assert disposition in {"complete", "comparison-only", "removed"}, feature["id"]
        if disposition != "removed":
            continue
        for layer, entry in feature["layers"].items():
            if layer in ("provenance", "tests"):
                # the record of the removal and the test that keeps it gone are the point
                assert entry["state"] == "present", (feature["id"], layer)
                continue
            assert entry["state"] in {"retired", "not-applicable"}, (feature["id"], layer,
                                                                    entry["state"])


def test_the_readiness_audit_records_a_reason_and_a_search_for_each_removal():
    readiness = json.loads((ROOT / "data" / "research" / "phase26" /
                            "feature_readiness.json").read_text(encoding="utf-8"))
    removed = [feature for feature in readiness["features"] if feature["tier"] == "removed"]
    assert len(removed) == 8
    assert {feature["id"] for feature in removed} == set(REMOVED)
    for feature in removed:
        assert feature["phase32"]["reason"].strip()
        assert feature["phase32"]["searched"].strip()
        # Nothing a removed feature "supports" may read as a capability still on offer.
        for supported in feature["whatItSupports"]:
            assert any(word in supported.lower()
                       for word in ("record", "parity", "archival", "nothing")), (
                feature["id"], supported)


def test_no_feature_is_left_in_a_blocked_state():
    """The point of Phase 32: 'blocked' is a plan, and this phase does not ship plans."""
    readiness = json.loads((ROOT / "data" / "research" / "phase26" /
                            "feature_readiness.json").read_text(encoding="utf-8"))
    assert readiness["counts"]["byTier"].get("data-blocked", 0) == 0
    assert readiness["counts"]["byTier"].get("unsupported", 0) == 0
    for feature in readiness["features"]:
        assert feature["tier"] in {"removed", "research-ready", "production-ready"}, feature["id"]
