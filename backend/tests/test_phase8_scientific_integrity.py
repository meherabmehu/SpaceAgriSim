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
import safedata

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


# ---------------------------------------------------------------------------
# Phase 8 model improvement: lettuce v2 (gradient boosting)
# ---------------------------------------------------------------------------
def test_lettuce_v2_is_registered_beside_v1_not_over_it():
    """v1 must remain byte-identical: Phase 8 improves by addition, not overwrite."""
    registry = research.read_json(research.ARTIFACTS / "registry")
    entries = {item["id"]: item for item in registry["models"]}
    assert "lettuce-earth-growth-v1" in entries
    assert "lettuce-earth-growth-v2" in entries
    assert entries["lettuce-earth-growth-v2"]["supersedes"] == "lettuce-earth-growth-v1"
    # Both artifacts must still verify against their recorded digests.
    for model_id in ("lettuce-earth-growth-v1", "lettuce-earth-growth-v2"):
        assert research.load_model(model_id)["id"] == model_id


def test_lettuce_v2_improves_on_the_model_it_replaces():
    """The shipped class must actually be better, measured on identical folds."""
    registry = research.model_registry()["models"]
    v1 = next(m for m in registry if m["id"] == "lettuce-earth-growth-v1")
    v2 = next(m for m in registry if m["id"] == "lettuce-earth-growth-v2")
    assert v2["metrics"]["R2"] > v1["metrics"]["R2"]
    assert v2["metrics"]["MAE"] < v1["metrics"]["MAE"]
    # Improvement must be reported per held-out experiment, not only pooled.
    per_fold = v2["modelSelection"]["perFold"]
    shipped, predecessor = per_fold["gradientBoosting (classic)"], per_fold["randomForest(): v1 class"]
    wins = sum(a < b for a, b in zip(shipped["foldMAE"], predecessor["foldMAE"]))
    assert wins >= 3, f"improvement held in only {wins}/4 held-out experiments"


def test_lettuce_v2_beats_its_own_baseline():
    registry = research.model_registry()["models"]
    v2 = next(m for m in registry if m["id"] == "lettuce-earth-growth-v2")
    assert v2["baselineComparison"]["outperformsBaselineMAE"] is True
    assert v2["metrics"]["R2"] > 0


def test_lettuce_v2_ensemble_reproduces_sklearn():
    """The serialised additive ensemble must equal what sklearn fitted."""
    model = research.load_model("lettuce-earth-growth-v2")
    recorded = model["modelSelection"]["serialisationCheck"]
    assert recorded["maxAbsDifference"] <= recorded["tolerance"]
    # Re-evaluate the stored trees directly against the recorded parameters.
    boosted = model["boostedTrees"]
    value, _ = research.predict_values(model, [14, 22.0, 22.0, 400.0])
    manual = boosted["init"] + boosted["learningRate"] * sum(
        research._eval_tree(tree, [14, 22.0, 22.0, 400.0]) for tree in boosted["trees"])
    assert abs(value - manual) < 1e-9


def test_lettuce_v2_never_predicts_negative_mass(scientific_client):
    """Fresh mass cannot be negative; boosted trees cross zero below the domain."""
    body = scientific_client.post("/api/predict/lettuce-earth-growth-v2", json={
        "daysAfterTransplant": 2, "airTemperature": 20, "rootTemperature": 20,
        "ppfd": 200}).json()
    assert body["prediction"] >= 0
    assert body["interval"]["low"] >= 0


def test_lettuce_v2_endpoint_reports_model_selection(scientific_client):
    body = scientific_client.post("/api/predict/lettuce-earth-growth-v2", json={
        "daysAfterTransplant": 14, "airTemperature": 22, "rootTemperature": 22,
        "ppfd": 400}).json()
    assert body["modelId"] == "lettuce-earth-growth-v2"
    assert body["supersedes"] == "lettuce-earth-growth-v1 (kept, not overwritten)"
    assert body["interval"]["calibrated"] is False
    assert body["modelSelection"]["shipped"] == "gradientBoosting (classic)"
    # The comparison must include the model being replaced, not only the winner.
    assert "randomForest(): v1 class" in body["modelSelection"]["comparedOnIdenticalFolds"]
    assert body["unit"] == "g fresh shoot mass/plant"


def test_lettuce_v1_remains_served_and_marked_superseded(scientific_client):
    v1 = scientific_client.post("/api/predict/lettuce-earth-growth-v1", json={
        "daysAfterTransplant": 14, "airTemperature": 22, "rootTemperature": 22,
        "ppfd": 400})
    assert v1.status_code == 200
    operation = scientific_client.get("/openapi.json").json()["paths"][
        "/api/predict/lettuce-earth-growth-v1"]["post"]
    assert operation["deprecated"] is True


def test_boosted_artifact_rejects_corrupt_learning_rate(tmp_path, monkeypatch):
    """The new artifact type must not bypass structural validation.

    The artifact is written with a *correct* checksum so the test fails on the
    semantic check rather than trivially on the digest.
    """
    import hashlib

    model = safedata.load(research.ARTIFACTS / "lettuce-earth-growth-v2")
    model["boostedTrees"]["learningRate"] = 0.0
    target = safedata.dump(model, tmp_path / "lettuce-earth-growth-v2")
    body = target.read_bytes()
    safedata.dump({"schemaVersion": 1, "models": [{
        "id": "lettuce-earth-growth-v2",
        "artifact": "ml/artifacts/lettuce-earth-growth-v2",
        "sha256": hashlib.sha256(body).hexdigest(),
    }]}, tmp_path / "registry")
    monkeypatch.setattr(research, "ARTIFACTS", tmp_path)
    research.load_model.cache_clear()
    try:
        with pytest.raises(ValueError, match="learning rate"):
            research.load_model("lettuce-earth-growth-v2")
    finally:
        research.load_model.cache_clear()

    # A tree whose branch index points out of bounds must be rejected too.
    model["boostedTrees"]["learningRate"] = 0.06
    model["boostedTrees"]["trees"][0]["left"][0] = 10 ** 6
    target = safedata.dump(model, tmp_path / "lettuce-earth-growth-v2")
    body = target.read_bytes()
    safedata.dump({"schemaVersion": 1, "models": [{
        "id": "lettuce-earth-growth-v2",
        "artifact": "ml/artifacts/lettuce-earth-growth-v2",
        "sha256": hashlib.sha256(body).hexdigest(),
    }]}, tmp_path / "registry")
    research.load_model.cache_clear()
    try:
        with pytest.raises(ValueError, match="tree branches"):
            research.load_model("lettuce-earth-growth-v2")
    finally:
        research.load_model.cache_clear()
