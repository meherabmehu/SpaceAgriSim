import safedata
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
    # The explorer must show exactly the studies the application's catalogue declares — no
    # more, no fewer. Asserting a literal count only restates the number in a second place
    # and breaks on every legitimate acquisition; asserting agreement catches the failure
    # that matters, a study that exists in one view of the catalogue and not the other.
    declared = research.manifest()["datasets"]
    assert len(studies) == len(declared)
    assert {row["id"] for row in studies} == {row["id"] for row in declared}
    # Phase 14 acquired five studies by pinned ISA metadata: crop safety on mizuna
    # (OSD-386), long-duration mizuna transcriptome (OSD-59), substrate substitution
    # (OSD-670), hydroponic chemistry (OSD-723) and simulated lunar soil (OSD-856).
    phase14 = [row for row in studies if row["id"] in
               {"OSD-59", "OSD-386", "OSD-670", "OSD-723", "OSD-856"}]
    assert len(phase14) == 5
    assert all(row["status"] == "verified-metadata" for row in phase14)
    mizuna = next(d for d in studies if d["id"] == "OSD-655")
    assert mizuna["organisms"] == ["Brassica rapa"]
    assert mizuna["sampleCount"] == 37
    assert mizuna["downloadedFileCount"] > 0
    assert "files" not in mizuna
    # Phase 14 added the substrate/regolith and edible-microbiology coverage rows, both
    # of which state what the acquired data cannot establish.
    assert len(response.json()["coverage"]) == 20
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
    # Phase 31: the served set is exactly the artifacts that met their evidence bar. The two
    # candidates that failed their pre-specified evaluation (OSD-782 dose, OSD-411 gravity) are
    # absent because they were never registered, and the three withdrawn artifacts (mizuna harvest
    # mass, absolute microbial load, ET0 emulator) are absent because they were removed from every
    # served surface - their files and evaluations remain on disk as documented negative results.
    assert len(models) == len(research.CATALOGUE_MODEL_IDS) == len(research.MODEL_IDS)
    assert {m["id"] for m in models} == {
        "tomato-flight-response-v1",
        "lettuce-earth-growth-v1", "lettuce-earth-growth-v2", "lettuce-earth-growth-v3",
        "mizuna-microbial-relative-load-v2",
        "radiation-quality-osd46-v1", "radiation-exposure-osd46-v1",
    }
    for removed in ("radiation-dose-osd782-v1", "gravity-reorientation-osd411-v1",
                    *research.RETIRED_MODEL_IDS):
        assert removed not in {m["id"] for m in models}
    assert all(m["artifactExists"] for m in models)
    for model in models:
        assert model["status"] == "trained-exploratory"
        assert model["metrics"]
        assert model["limitations"]
        assert model["artifactSha256"] and len(model["artifactSha256"]) == 64
        assert model["domain"]
        # Every served model states provenance structurally, and the counts are derived from it.
        assert model["provenance"]["category"] in {"nasa-measured", "external-measured"}
        assert model["provenance"]["study"] and model["provenance"]["repository"]

    counts = scientific_client.get("/api/models").json()["counts"]
    assert counts["models"] == len(models)
    assert counts["nasaMeasured"] == sum(
        1 for m in models if m["provenance"]["category"] == "nasa-measured")
    assert counts["externalMeasured"] == sum(
        1 for m in models if m["provenance"]["category"] == "external-measured")
    assert counts["nasaMeasured"] + counts["externalMeasured"] == counts["models"]
    assert "retiredRegistered" not in counts or counts.get("retiredRegistered", 0) == 0

    v2 = next(m for m in models if m["id"] == "mizuna-microbial-relative-load-v2")
    assert v2["supersedes"] == "mizuna-microbial-load-v1 (kept, not overwritten)"
    # The re-scoped estimand is what makes held-out-study transfer positive; the artifact must
    # carry both the old and the new held-out numbers.
    assert v2["estimandChange"]["v1HeldOutR2"]["VEG04B"] < 0
    assert all(v > 0 for v in v2["transferSummary"]["v2HeldOutR2"].values())
    # Absolute-scale predictions must not be offered without a campaign reference.
    assert v2["absoluteScaleProtocol"]["required"]
    # Phase 35: this line used to assert the literal "experimental". The card's own recorded rule
    # (`evidenceBasis.rule`) required four things for validated-exploratory status, and exactly one
    # of them - conformal coverage within 5 points of nominal - was unmeasured. Phase 34 measured it
    # across campaigns at 0.8943 against a nominal 0.90, so the rule is now satisfied and the status
    # follows from it. The assertion is on the derivation rather than on the old literal: the status
    # and the verdict must agree, and a passing verdict must carry the measurement that earned it.
    assert v2["evidenceStatus"] == "validated-exploratory"
    verdict = v2["evidenceVerdict"]
    assert verdict["verdict"] == "passes-independent-check"
    assert verdict["decisionGrade"] is True
    coverage_check = next(c for c in verdict["checks"] if c["check"].startswith("cross-campaign"))
    assert coverage_check["passed"] is True
    assert coverage_check["measured"] >= 0.9 - 0.05
    assert v2["interval"]["empiricallyCalibrated"] is True
    assert v2["interval"]["empiricalCoverage"] >= v2["interval"]["nominalCoverage"] - 0.02
    assert v2["uncertainty"]["exchangeabilityUnit"].startswith("biological group")
    assert v2["uncertainty"]["caveat"].strip()


def test_withdrawn_models_are_gone_from_every_served_surface(scientific_client):
    """Phase 31: removal means absent, not "present with a warning attached"."""
    registry = scientific_client.get("/api/models").json()
    served = {m["id"] for m in registry["models"]}
    from app import workflow
    catalogue = {row["modelId"] for row in workflow.model_catalogue()["models"]}
    for model_id in research.RETIRED_MODEL_IDS:
        assert model_id not in served
        assert model_id not in catalogue
        # No prediction route survives, and the request schema went with it.
        assert scientific_client.post(f"/api/predict/{model_id}", json={}).status_code == 404
        assert f"/api/predict/{model_id}" not in {
            path for path in scientific_client.get("/openapi.json").json()["paths"]}


def test_withdrawn_artifacts_are_still_on_disk_and_still_checksummed():
    """A withdrawal must not become a deletion: the negative result has to stay reproducible."""
    import hashlib

    registry = safedata.load(research.ROOT / "ml" / "artifacts" / "registry")
    by_id = {row["id"]: row for row in registry["models"]}
    for model_id in research.RETIRED_MODEL_IDS:
        path = research.ROOT / "ml" / "artifacts" / f"{model_id}"
        assert safedata.exists(path), model_id
        # Two of the three are registered artifacts with a recorded digest; the ET0 emulator
        # shipped a card only (its bundle is a joblib), so it has no registry row to compare with.
        if model_id in by_id:
            assert hashlib.sha256(safedata.bytes(path)).hexdigest() == by_id[model_id]["sha256"], model_id
        else:
            assert model_id == "et0-emulator-v1"
            assert safedata.exists(research.ROOT / "ml" / "artifacts" / f"{model_id}.joblib")
        assert research.RETIRED_MODEL_IDS[model_id].strip()


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
    model_id = "lettuce-earth-growth-v2"
    original = research.ARTIFACTS
    (tmp_path / "registry.py").write_bytes(safedata.bytes(original / "registry"))
    (tmp_path / f"{model_id}.py").write_text('DATA = {"tampered": True}\n')
    research.load_model.cache_clear()
    monkeypatch.setattr(research, "ARTIFACTS", tmp_path)
    with pytest.raises(ValueError, match="SHA256"):
        research.load_model(model_id)
    research.load_model.cache_clear()


def test_all_outer_validation_splits_keep_groups_disjoint():
    for filename, train_key, test_key in [("mizuna_splits", "trainGroups", "testGroups"), ("tomato_splits", "trainPlants", "testPlants")]:
        splits = safedata.load(research.ROOT / "ml" / "evaluation" / filename)
        assert len(splits) == 4
        assert all(not set(f[train_key]) & set(f[test_key]) for f in splits)


def test_tracked_physiological_source_files_have_valid_hashes():
    checks = research.read_json(research.DATA / "metadata" / "download_checksums")
    assert len(checks) == 28
    for item in checks:
        if item["studyId"] != "OSD-767":
            assert hashlib.sha256(safedata.bytes(research.ROOT / item["path"])).hexdigest() == item["sha256"]


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
    splits=safedata.load(research.ROOT/'ml/evaluation/lettuce_splits')
    assert len(splits)==4 and all(not set(s['trainExperiments'])&set(s['testExperiments']) for s in splits)


# ---------------------------------------------------------------------------
# Phase 6: NASA OSD-780 microbial load model and evidence surface
# ---------------------------------------------------------------------------
def test_absolute_microbial_load_model_is_not_served_at_all(scientific_client):
    """Phase 31 removed the surface; the evidence that it failed has to survive the removal.

    Phase 8 answered 410 with the leave-one-campaign-out numbers. A 410 is still a public promise
    that the surface exists and is worth asking about, and the dashboard still counted it, so
    Phase 31 deleted the route instead. What is asserted here is that the withdrawal is total on
    the served side and that the failure record is still on disk and still readable.
    """
    base = {
        "experiment": "VEG04B", "environment": "flight", "spectrum": "red",
        "sanitised": True, "freshWeightG": 5.4, "harvestIndex": 1,
    }
    assert scientific_client.post(
        "/api/predict/mizuna-microbial-load-v1", json=base).status_code == 404
    schema = scientific_client.get("/openapi.json").json()
    assert "/api/predict/mizuna-microbial-load-v1" not in schema["paths"]
    models = {m["id"]: m for m in scientific_client.get("/api/models").json()["models"]}
    assert "mizuna-microbial-load-v1" not in models

    # The artifact that produced the negative result is retained and unchanged.
    artifact = safedata.load(research.ROOT / "ml" / "artifacts" /
                           "mizuna-microbial-load-v1")
    for held_out in ("VEG04A", "VEG04B"):
        assert artifact["leaveOneExperimentOut"][held_out]["R2"] < 0
    assert artifact["evidenceBasis"]["transfersToHeldOutExperiment"] is False
    assert any("not harvest biomass" in note.lower() for note in artifact["limitations"])


def test_the_relative_model_still_carries_the_reason_its_predecessor_was_withdrawn():
    """The successor must say what it replaced and why, or the removal looks unexplained."""
    reason = research.RETIRED_MODEL_IDS["mizuna-microbial-load-v1"]
    assert "VEG-04A" in reason or "VEG04A" in reason
    assert "-0.55" in reason and "-0.58" in reason
    artifact = safedata.load(research.ROOT / "ml" / "artifacts" /
                           "mizuna-microbial-relative-load-v2")
    assert artifact["supersedes"].startswith("mizuna-microbial-load-v1")


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
    # Phase 31: a withdrawn model is not a status row either. The evidence surface reports only
    # what is served, and the withdrawal reasons live in research.RETIRED_MODEL_IDS + docs.
    for withdrawn in research.RETIRED_MODEL_IDS:
        assert withdrawn not in payload["modelEvidenceStatus"]


def test_scientific_summary_never_claims_validation(scientific_client):
    payload = scientific_client.get("/api/scientific-summary").json()
    assert payload["nasaEndorsed"] is False
    assert payload["missionCertified"] is False
    assert payload["validatedModels"] == []
    assert payload["platformMaturity"] == "research-and-education"
    assert len(payload["models"]) == len(research.CATALOGUE_MODEL_IDS)
    assert payload["calibration"]["invariantsAllPassed"] is True


def test_every_served_model_states_a_recorded_source_and_the_counts_add_up():
    """Dashboard category counts must be reproducible from the rows they summarise.

    Phase 31 removed the free-text `sourceType` scrape: two served models had no `sourceType` in
    their artifact and were displayed as "source not recorded" while the counts still claimed
    every model was attributed. Each row now carries the recorded provenance label, and the
    counts are recomputed here from the rows rather than trusted.
    """
    registry = research.model_registry()
    rows = registry["models"]
    nasa = external = 0
    for row in rows:
        assert row["sourceType"], row["id"]
        assert row["provenance"]["category"] in {"nasa-measured", "external-measured"}
        assert row["provenance"]["repository"]
        assert row["sourceType"] == row["provenance"]["label"]
        if row["provenance"]["category"] == "nasa-measured":
            nasa += 1
        else:
            external += 1
    counts = registry["counts"]
    assert counts["models"] == len(rows) == nasa + external
    assert counts["nasaMeasured"] == nasa
    assert counts["externalMeasured"] == external
    assert "not recorded" not in json.dumps(rows).lower().replace("not recorded for this model", "")


def test_withdrawn_models_are_not_in_the_served_catalogue():
    """A withdrawn model is absent, not retired-in-place: no row, no route, no label."""
    for model_id in ("mizuna-microbial-load-v1", "mizuna-harvest-v1"):
        assert model_id not in research.CATALOGUE_MODEL_IDS
        assert model_id not in research.PROVENANCE
        with pytest.raises((KeyError, FileNotFoundError, ValueError)):
            research.load_model(model_id)
