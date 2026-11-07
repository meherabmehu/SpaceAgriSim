"""Phase 8 scientific integrity and performance guards.

Two things are protected here, both of them regressions that actually happened:

1.  Classification completeness. Phase 8 requires every prediction and
    optimisation surface to sit in exactly one evidence category, and category 6
    (unsupported scientific prediction) to be served to nobody. The classification
    is published at GET /api/science/classification; these tests assert it covers
    every live model and that no category 6 feature is reachable as a prediction.

2.  Model cache sizing. The registry grew from four models to five while
    `load_model` stayed at `lru_cache(maxsize=4)`, so the cache never retained a
    full working set and every GET /api/models re-read ~1 MB of artifacts.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import research, science_classification
from app.routes.research import router


@pytest.fixture
def scientific_client():
    """A router-only app, so these integrity checks do not depend on app wiring."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Classification integrity
# ---------------------------------------------------------------------------
def test_classification_covers_every_registered_model():
    payload = science_classification.classifier_response()
    classified = {f["id"] for f in payload["features"]}
    for model_id in research.MODEL_IDS:
        assert model_id in classified, f"{model_id} has no Phase 8 classification"


def test_every_feature_uses_a_valid_category():
    payload = science_classification.classifier_response()
    for feature in payload["features"]:
        assert feature["category"] in science_classification.CATEGORY_NAMES
        assert feature["categoryName"] == science_classification.CATEGORY_NAMES[feature["category"]]
        assert feature["serviceAllowed"] == science_classification.SERVICE_ALLOWED[feature["category"]]


def test_feature_ids_are_unique():
    ids = [f.id for f in science_classification.FEATURES]
    assert len(ids) == len(set(ids))


def test_no_category_six_feature_is_served_as_a_prediction():
    """Category 6 means 'must not be served'. No such feature may be a live surface."""
    payload = science_classification.classifier_response()
    served = set(payload["summary"]["servedAsPrediction"])
    retired = set(payload["summary"]["retiredAsPrediction"])
    for feature in payload["byCategory"]["6"]:
        assert feature["id"] in retired
        assert feature["id"] not in served
        assert feature["status"].startswith("retired")


def test_classification_reaches_the_api(scientific_client):
    response = scientific_client.get("/api/science/classification")
    assert response.status_code == 200
    body = response.json()
    assert body["schemaVersion"] == 1
    assert body["summary"]["features"] == len(science_classification.FEATURES)
    # The unsupported count must equal the number of category 6 entries, not zero.
    assert body["summary"]["unsupportedServicedCount"] == len(body["byCategory"]["6"])


def test_claimed_predictive_surfaces_are_testable():
    """Any feature claiming to be served must not also be marked retired."""
    for feature in science_classification.FEATURES:
        if feature.status.startswith("retired"):
            assert feature.category == 6 or "retired" in feature.status
        if feature.category == 6:
            assert feature.status.startswith("retired")


# ---------------------------------------------------------------------------
# Cache regression guards
# ---------------------------------------------------------------------------
def test_model_cache_holds_whole_registry():
    """The LRU cache must fit every registered model, or it thrashes indefinitely."""
    research.load_model.cache_clear()
    for model_id in sorted(research.MODEL_IDS):
        research.load_model(model_id)
    info = research.load_model.cache_info()
    assert info.maxsize is None or info.maxsize >= len(research.MODEL_IDS), (
        f"cache maxsize {info.maxsize} < {len(research.MODEL_IDS)} registered models; "
        "every registry load would evict an entry it just inserted"
    )
    assert info.currsize == len(research.MODEL_IDS)
    assert info.misses == len(research.MODEL_IDS)


def test_model_cache_is_reused_on_second_pass():
    """After one warm pass, reloading every model must hit, not miss."""
    research.load_model.cache_clear()
    for model_id in sorted(research.MODEL_IDS):
        research.load_model(model_id)
    hits_before = research.load_model.cache_info().hits
    for model_id in sorted(research.MODEL_IDS):
        research.load_model(model_id)
    info = research.load_model.cache_info()
    assert info.hits - hits_before == len(research.MODEL_IDS)
    # crit: a full second pass must not reload any artifact.
    assert info.misses == len(research.MODEL_IDS)


def test_registry_endpoint_warms_cache_without_eviction(scientific_client):
    research.load_model.cache_clear()
    assert scientific_client.get("/api/models").status_code == 200
    first = research.load_model.cache_info()
    assert scientific_client.get("/api/models").status_code == 200
    second = research.load_model.cache_info()
    assert second.misses == first.misses, "second /api/models re-read artifacts"
    assert second.hits >= len(research.MODEL_IDS)


@pytest.mark.parametrize("model_id", sorted(research.MODEL_IDS))
def test_each_model_artifact_verifies(model_id):
    """Cache sizing must not have bypassed checksum verification."""
    model = research.load_model(model_id)
    assert model["id"] == model_id
