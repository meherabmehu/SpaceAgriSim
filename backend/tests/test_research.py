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
    # 14 from the original inventory, plus the four studies Phase 9 catalogued
    # after finding that models cited studies the explorer did not list
    # (OSD-46, OSD-782, OSD-411, OSD-780).
    assert len(studies) == 18
    mizuna = next(d for d in studies if d["id"] == "OSD-655")
    assert mizuna["organisms"] == ["Brassica rapa"]
    assert mizuna["sampleCount"] == 37
    assert mizuna["downloadedFileCount"] > 0
    assert "files" not in mizuna
    assert len(response.json()["coverage"]) == 15
    eden = next(d for d in studies if d["id"] == "OSD-895")
    assert eden["classification"] == "useful for scientific calibration"
    assert eden["rowCount"] == 19


def test_dataset_search_detail_preview_and_unknown(scientific_client):
    assert len(scientific_client.get("/api/datasets?q=OSD-767").json()["datasets"]) == 1
    detail = scientific_client.get("/api/datasets/OSD-655").json()
    assert all(f["url"].startswith("https://osdr.nasa.gov/") for f in detail["files"])
    preview = scientific_client.get("/api/datasets/OSD-655/preview").json()
    harvest = next(t for t in preview["tables"] if t["name"] == "mizuna_harvest.csv")
    assert harvest["rowCount"] == 14
    assert all(r["crop"] == "mizuna" for r in harvest["rows"])
    assert scientific_client.get("/api/datasets/OSD-999999").status_code == 404
    eden = scientific_client.get("/api/datasets/OSD-895/preview").json()
    assert eden["tables"][0]["rowCount"] == 19
    assert eden["tables"][0]["units"]["meanEdibleFreshweightKgM2"] == "kg/m2"


def test_model_registry_requires_actual_verified_artifacts(scientific_client):
    models = scientific_client.get("/api/models").json()["models"]
    # Phase 6 added mizuna-microbial-load-v1 (NASA OSD-780 plate counts). Phase 7
    # added mizuna-microbial-relative-load-v2, which supersedes v1's estimand; v1
    # stays registered and on disk so the Phase 6 claim remains reproducible.
    # Phase 8 added lettuce-earth-growth-v2, a gradient-boosting successor that
    # beat the registered random forest on identical folds. v1 stays registered and
    # on disk so the Phase 7 result remains reproducible.
    # Phase 9 added two NASA OSD-46 radiation classifiers. The two Phase 9
    # candidates that failed their pre-specified evaluation (OSD-782 dose,
    # OSD-411 gravity) are deliberately absent: they were excluded from the
    # registry rather than tuned until they appeared to work.
    assert len(models) == 8
    assert {m["id"] for m in models} == {
        "mizuna-harvest-v1", "tomato-flight-response-v1",
        "lettuce-earth-growth-v1", "lettuce-earth-growth-v2",
        "mizuna-microbial-load-v1", "mizuna-microbial-relative-load-v2",
        "radiation-quality-osd46-v1", "radiation-exposure-osd46-v1",
    }
    assert "radiation-dose-osd782-v1" not in {m["id"] for m in models}
    assert "gravity-reorientation-osd411-v1" not in {m["id"] for m in models}
    assert all(m["artifactExists"] for m in models)
    for model in models:
        assert model["status"] == "trained-exploratory"
        assert model["metrics"]
        assert model["limitations"]
        assert model["artifactSha256"] and len(model["artifactSha256"]) == 64
        assert model["domain"]
    v2 = next(m for m in models if m["id"] == "mizuna-microbial-relative-load-v2")
    assert v2["supersedes"] == "mizuna-microbial-load-v1 (kept, not overwritten)"
    # The re-scoped estimand is what makes held-out-study transfer positive; the
    # artifact must carry both the old and the new held-out numbers.
    assert v2["estimandChange"]["v1HeldOutR2"]["VEG04B"] < 0
    assert all(v > 0 for v in v2["transferSummary"]["v2HeldOutR2"].values())
    # Absolute-scale predictions must not be offered without a campaign reference.
    assert v2["absoluteScaleProtocol"]["required"]
    assert v2["evidenceStatus"] == "experimental"  # coverage missed nominal
    assert v2["interval"]["empiricallyCalibrated"] is False

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


# ---------------------------------------------------------------------------
# Phase 6: NASA OSD-780 microbial load model and evidence surface
# ---------------------------------------------------------------------------
def test_microbial_model_is_registered_with_honest_evidence(scientific_client):
    models = {m["id"]: m for m in scientific_client.get("/api/models").json()["models"]}
    model = models["mizuna-microbial-load-v1"]
    assert model["sourceStudy"] == "OSD-780"
    assert model["samples"] == 123
    assert model["groups"] == 35
    assert model["target"].startswith("log10(1 + CFU per gram")
    # It beats the baseline in pooled data but does not transfer, so it must not
    # be advertised as validated.
    assert model["evidenceStatus"] == "experimental"
    assert model["evidenceBasis"]["beatsBaselineWithinPooledData"] is True
    assert model["evidenceBasis"]["transfersToHeldOutExperiment"] is False
    # Intervals under-cover and must be labelled uncalibrated.
    assert model["interval"]["empiricallyCalibrated"] is False
    assert "uncalibrated" in model["interval"]["kind"].lower()
    # Leave-one-experiment-out must be negative for both campaigns.
    for held_out in ("VEG04A", "VEG04B"):
        assert model["leaveOneExperimentOut"][held_out]["R2"] < 0
    # The biomass category error must be forbidden in the prose.
    assert any("not harvest biomass" in note.lower() for note in model["limitations"])


def test_absolute_microbial_prediction_is_retired(scientific_client):
    """Phase 8 retires the absolute-load prediction; the evidence must survive.

    The Phase 6 endpoint answered 200 with a number that its own leave-one-
    experiment-out evaluation showed to be worse than the training mean on both
    held-out campaigns. Phase 8 policy is that such a surface must not answer with
    a prediction, so it now returns 410 Gone and states why. The artifact itself
    stays registered so the Phase 6/7 result remains reproducible.
    """
    base = {
        "experiment": "VEG04B", "environment": "flight", "spectrum": "red",
        "sanitised": True, "freshWeightG": 5.4, "harvestIndex": 1,
    }
    result = scientific_client.post("/api/predict/mizuna-microbial-load-v1", json=base)
    assert result.status_code == 410
    detail = result.json()["detail"]
    assert detail["error"] == "retired-prediction"
    assert detail["modelId"] == "mizuna-microbial-load-v1"
    assert detail["evidence"]["transfersToHeldOutExperiment"] is False
    # Both held-out campaigns must still be reported as failing to transfer.
    r2 = detail["evidence"]["leaveOneExperimentOutR2"]
    assert set(r2) == {"VEG04A", "VEG04B"}
    assert all(value < 0 for value in r2.values())
    assert detail["replacement"] == "/api/predict/mizuna-microbial-relative-load-v2"
    # No predicted number may be present anywhere in the retired response.
    assert "prediction" not in result.json()["detail"]

    # The artifact is retained, not deleted.
    models = {m["id"]: m for m in scientific_client.get("/api/models").json()["models"]}
    assert models["mizuna-microbial-load-v1"]["artifactExists"] is True


def test_retired_endpoint_is_documented_as_deprecated(scientific_client):
    """A caller reading OpenAPI must be told the endpoint is withdrawn."""
    schema = scientific_client.get("/openapi.json").json()
    operation = schema["paths"]["/api/predict/mizuna-microbial-load-v1"]["post"]
    assert operation["deprecated"] is True
    assert "410" in operation["responses"]


def test_microbial_prediction_rejects_invalid_input(scientific_client):
    base = {
        "experiment": "VEG04A", "environment": "flight", "spectrum": "red",
        "sanitised": False, "freshWeightG": 5.0, "harvestIndex": 1,
    }
    # Unknown campaign, impossible harvest index, negative mass, extra fields.
    assert scientific_client.post(
        "/api/predict/mizuna-microbial-load-v1",
        json=base | {"experiment": "VEG04C"}).status_code == 422
    assert scientific_client.post(
        "/api/predict/mizuna-microbial-load-v1",
        json=base | {"harvestIndex": 0}).status_code == 422
    assert scientific_client.post(
        "/api/predict/mizuna-microbial-load-v1",
        json=base | {"freshWeightG": -1}).status_code == 422
    assert scientific_client.post(
        "/api/predict/mizuna-microbial-load-v1",
        json=base | {"gravity": 0.38}).status_code == 422


def test_relative_microbial_model_flags_out_of_domain(scientific_client):
    """An assay subsample far above the measured range must raise the flag."""
    body = scientific_client.post("/api/predict/mizuna-microbial-relative-load-v2", json={
        "environment": "ground", "spectrum": "blue", "sanitised": True,
        "freshWeightG": 40.0, "harvestIndex": 1,
    }).json()
    assert body["outOfDistribution"] is True
    assert any("outside observed training range" in w for w in body["warnings"])


def test_science_calibration_exposes_measured_evidence(scientific_client):
    payload = scientific_client.get("/api/science/calibration").json()
    assert payload["status"] == "available"
    assert payload["invariants"]["allPassed"] is True
    assert payload["invariants"]["checksRun"] > 1000
    lettuce = payload["calibration"]["lettuce"]
    # Lettuce is the only crop whose baseline is supported by measured data.
    assert lettuce["evidenceLevel"] == "measured-comparable"
    assert lettuce["baselineWithinMeasuredRange"] is True
    assert lettuce["decision"] == "retained-within-measured-range"
    # Flagged crops must not have been silently changed.
    for crop in ("tomato", "radish"):
        assert payload["calibration"][crop]["decision"] == "flagged"
        assert "NOT applied" in payload["calibration"][crop]["suggestionStatus"]
    assert "PDF" in payload["sourceCaveat"]


def test_science_evidence_separates_measured_from_assumed(scientific_client):
    payload = scientific_client.get("/api/science/evidence").json()
    assert payload["measuredTargets"] and payload["assumedTargets"]
    assert payload["blockedTargets"]
    # Phase 7 split the old single "blocked" list in two. Targets recovered from
    # NASA Technical Memoranda are measured but not trainable; only genuinely
    # absent ones stay blocked. The categories must not overlap, because that is
    # how a measured quantity would get quietly re-labelled as missing (or worse,
    # a missing one presented as measured).
    measured = " ".join(item["target"] for item in payload["measuredNotTrainable"]).lower()
    blocked = " ".join(payload["blockedTargets"]).lower()
    for term in ("transpiration", "co2 assimilation", "water recovery"):
        assert term in measured and term not in blocked
    for term in ("radiation", "gravity", "o2 evolution"):
        assert term in blocked and term not in measured
    assert payload["modelEvidenceStatus"]["mizuna-harvest-v1"] == "baseline-only"


def test_scientific_summary_never_claims_validation(scientific_client):
    payload = scientific_client.get("/api/scientific-summary").json()
    assert payload["nasaEndorsed"] is False
    assert payload["missionCertified"] is False
    assert payload["validatedModels"] == []
    assert payload["platformMaturity"] == "research-and-education"
    assert len(payload["models"]) == 8
    assert payload["calibration"]["invariantsAllPassed"] is True
