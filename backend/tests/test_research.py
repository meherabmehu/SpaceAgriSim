import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import research
from app.routes.research import router


@pytest.fixture
def scientific_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_actual_dataset_inventory_and_no_cross_crop_claim(scientific_client):
    response = scientific_client.get("/api/datasets")
    assert response.status_code == 200
    studies = response.json()["datasets"]
    assert len(studies) == 13
    mizuna = next(d for d in studies if d["id"] == "OSD-655")
    assert mizuna["organisms"] == ["Brassica rapa"]
    assert mizuna["sampleCount"] == 37
    assert mizuna["downloadedFileCount"] > 0
    assert "files" not in mizuna
    assert len(response.json()["coverage"]) == 15


def test_dataset_search_detail_preview_and_unknown(scientific_client):
    assert len(scientific_client.get("/api/datasets?q=OSD-767").json()["datasets"]) == 1
    detail = scientific_client.get("/api/datasets/OSD-655").json()
    assert all(f["url"].startswith("https://osdr.nasa.gov/") for f in detail["files"])
    preview = scientific_client.get("/api/datasets/OSD-655/preview").json()
    harvest = next(t for t in preview["tables"] if t["name"] == "mizuna_harvest.csv")
    assert harvest["rowCount"] == 14
    assert all(r["crop"] == "mizuna" for r in harvest["rows"])
    assert scientific_client.get("/api/datasets/OSD-999999").status_code == 404


def test_model_registry_requires_actual_verified_artifacts(scientific_client):
    models = scientific_client.get("/api/models").json()["models"]
    assert len(models) == 3
    assert all(m["artifactExists"] for m in models)
    for model in models:
        assert model["status"] == "trained-exploratory"
        assert model["metrics"]
        assert model["limitations"]
        assert model["artifactSha256"] and len(model["artifactSha256"]) == 64
        assert model["domain"]
    regression = next(m for m in models if m["id"] == "mizuna-harvest-v1")
    assert regression["metrics"]["R2"] < 0  # Honest failed-to-beat-baseline evaluation.
    assert regression["predictionStatus"] == "baseline-only"
    assert regression["baselineComparison"]["outperformsBaselineMAE"] is False


def test_mizuna_prediction_units_interval_and_domain(scientific_client):
    inputs = {"crop": "mizuna", "waterSuppliedL": 1.5, "establishedPlants": 2, "environment": "flight", "spectrum": "red"}
    result = scientific_client.post("/api/predict/mizuna-harvest-v1", json=inputs)
    assert result.status_code == 200
    result = result.json()
    assert result["unit"] == "g fresh mass/pillow"
    assert result["interval"]["low"] <= result["prediction"] <= result["interval"]["high"]
    assert "uncalibrated" in result["interval"]["kind"]
    assert result["outOfDistribution"] is False
    assert scientific_client.post("/api/predict/mizuna-harvest-v1", json=inputs | {"waterSuppliedL": 8}).json()["outOfDistribution"] is True
    assert scientific_client.post("/api/predict/mizuna-harvest-v1", json=inputs | {"crop": "lettuce"}).status_code == 422
    assert scientific_client.post("/api/predict/mizuna-harvest-v1", json=inputs | {"waterSuppliedL": -1}).status_code == 422
    assert scientific_client.post("/api/predict/mizuna-harvest-v1", json=inputs | {"madeUpFeature": 1}).status_code == 422


def test_molecular_prediction_schema_is_not_environmental_sliders(scientific_client):
    example = scientific_client.get("/api/models/tomato-flight-response-v1/example").json()
    assert example["isTrainingSample"] is True
    assert len(example["expression"]) == 64
    result = scientific_client.post("/api/predict/tomato-flight-response-v1", json={"expression": example["expression"]})
    assert result.status_code == 200
    assert 0 <= result.json()["probabilityFlight"] <= 1
    assert result.json()["calibrated"] is False
    assert scientific_client.post("/api/predict/tomato-flight-response-v1", json={"expression": {"gravity": .38}}).status_code == 422
    changed = dict(example["expression"]); changed[next(iter(changed))] = -1
    assert scientific_client.post("/api/predict/tomato-flight-response-v1", json={"expression": changed}).status_code == 422


def test_model_checksum_corruption_rejected(tmp_path, monkeypatch):
    model_id = "mizuna-harvest-v1"
    original = research.ARTIFACTS
    (tmp_path / "registry.json").write_bytes((original / "registry.json").read_bytes())
    (tmp_path / f"{model_id}.json").write_text('{"tampered": true}')
    research.load_model.cache_clear()
    monkeypatch.setattr(research, "ARTIFACTS", tmp_path)
    with pytest.raises(ValueError, match="SHA256"):
        research.load_model(model_id)
    research.load_model.cache_clear()


def test_all_outer_validation_splits_keep_groups_disjoint():
    for filename, train_key, test_key in [("mizuna_splits.json", "trainGroups", "testGroups"), ("tomato_splits.json", "trainPlants", "testPlants")]:
        splits = json.loads((research.ROOT / "ml" / "evaluation" / filename).read_text())
        assert len(splits) == 4
        assert all(not set(f[train_key]) & set(f[test_key]) for f in splits)


def test_tracked_physiological_source_files_have_valid_hashes():
    checks = research.read_json(research.DATA / "metadata" / "download_checksums.json")
    assert len(checks) == 28
    for item in checks:
        if item["studyId"] != "OSD-767":
            assert hashlib.sha256((research.ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]


def test_lettuce_external_model_scope_and_experiment_splits(scientific_client):
    inputs={'crop':'lettuce','daysAfterTransplant':20,'airTemperature':24,'rootTemperature':28,'ppfd':400}
    response=scientific_client.post('/api/predict/lettuce-earth-growth-v1',json=inputs)
    assert response.status_code==200
    result=response.json()
    assert result['sourceStudy']=='WUR-lettuce' and 'External' in result['method']
    assert 0 < result['prediction'] < 1000 and result['outOfDistribution'] is False
    assert result['interval']['low'] <= result['prediction'] <= result['interval']['high']
    unsupported=scientific_client.post('/api/predict/lettuce-earth-growth-v1',json=inputs|{'daysAfterTransplant':45})
    assert unsupported.json()['outOfDistribution'] is True
    tipburn=scientific_client.post('/api/predict/lettuce-earth-growth-v1',json=inputs|{'airTemperature':32,'rootTemperature':20})
    assert tipburn.json()['outOfDistribution'] is True
    assert scientific_client.post('/api/predict/lettuce-earth-growth-v1',json=inputs|{'gravity':.38}).status_code==422
    splits=json.loads((research.ROOT/'ml/evaluation/lettuce_splits.json').read_text())
    assert len(splits)==4 and all(not set(s['trainExperiments'])&set(s['testExperiments']) for s in splits)
