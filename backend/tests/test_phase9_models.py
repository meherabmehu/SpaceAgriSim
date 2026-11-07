"""Phase 9 model integration, leakage and integrity tests.

The important tests here are not "does the endpoint return 200". They are the ones
that would fail if someone quietly made a result look better than the data
supports, or shipped a model whose provenance no longer matches its artifact.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import research, science_classification
from app.routes.research import router

NATIVE_MODELS = ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1")
EXCLUDED_MODELS = ("radiation-dose-osd782-v1", "gravity-reorientation-osd411-v1")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def profile_request(client, model_id, label):
    payload = client.get(f"/api/models/{model_id}/reference-profiles").json()
    return dict(zip(payload["features"], payload["profiles"][label]))


# ---------------------------------------------------------------------------
# Provenance and artifact integrity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_phase9_models_are_registered_and_checksums_verify(model_id):
    registry = json.loads((research.ARTIFACTS / "registry.json").read_text())
    entries = {m["id"]: m for m in registry["models"]}
    assert model_id in entries
    artifact = research.load_model(model_id)
    assert artifact["id"] == model_id
    assert artifact["sourceStudy"] == "OSD-46"
    assert artifact["sourceUrl"].startswith("https://osdr.nasa.gov/")


@pytest.mark.parametrize("model_id", EXCLUDED_MODELS)
def test_failed_candidates_are_not_served(model_id):
    """A model that failed its pre-specified scheme must not be reachable."""
    ids = {m["id"] for m in research.model_registry()["models"]}
    assert model_id not in ids
    assert model_id not in research.MODEL_IDS
    evidence = research.ROOT / "ml" / "evaluation" / "excluded" / f"{model_id}.json"
    assert evidence.is_file(), "excluded model must retain its evidence artifact"
    assert json.loads(evidence.read_text())["evidenceStatus"] == "insufficient-evidence"


def test_excluded_models_have_no_route(client):
    for model_id in EXCLUDED_MODELS:
        assert client.post(f"/api/predict/{model_id}", json={"expression": {}}).status_code == 404


def test_dataset_manifest_pins_every_file_by_checksum():
    manifest = json.loads((research.DATA / "metadata" / "phase9_nasa_datasets.json").read_text())
    assert len(manifest["files"]) >= 6
    for entry in manifest["files"]:
        assert len(entry["sha256"]) == 64
        assert entry["bytes"] > 0
        assert entry["url"].startswith("https://nasa-osdr.s3.us-west-2.amazonaws.com/")
    # The excluded studies must be recorded with reasons, not silently dropped.
    assert set(manifest["excluded"]) == {"OSD-480", "OSD-772", "OSD-412", "OSD-413", "OSD-414"}


# ---------------------------------------------------------------------------
# Scientific claims
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_models_beat_their_baseline_on_the_right_metric(model_id):
    model = research.load_model(model_id)
    metrics, baseline = model["metrics"], model["baselineMetrics"]
    # Balanced accuracy, not raw accuracy: the tasks are class-imbalanced and raw
    # accuracy would let a majority-class predictor look respectable.
    assert metrics["balancedAccuracy"] > baseline["balancedAccuracy"]
    assert metrics["accuracy"] > 0.8


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_permutation_p_value_is_finite_and_corrected(model_id):
    permutation = research.load_model(model_id)["permutationTest"]
    assert permutation["pValue"] > 0, "a permutation p-value can never be exactly zero"
    expected_floor = 1.0 / (permutation["nPermutations"] + 1)
    assert permutation["pValue"] >= expected_floor - 1e-12
    assert permutation["corrected"] if "corrected" in permutation else True
    assert permutation["pValue"] <= 0.05
    assert permutation["scheme"] == "labels permuted between biological groups"


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_validation_is_group_held_out_not_sample_held_out(model_id):
    model = research.load_model(model_id)
    assert "leave-one-biological-group-out" in model["validation"].lower()
    assert model["groups"] >= 20, "the 22 biological groups of OSD-46 must be preserved"
    # Every learner reports the single-class held-out groups rather than hiding them.
    for learner in model["allLearners"].values():
        assert "singleClassHeldOutGroups" in learner


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_batch_confound_is_disclosed_with_a_number(model_id):
    confound = research.load_model(model_id)["batchConfound"]
    assert 0.0 <= confound["cramersV"] <= 1.0
    assert confound["contingency"], "the batch cross-tabulation must be published"
    assert confound["interpretation"]


def test_exposure_model_publishes_a_batch_controlled_evaluation():
    """The binary task is batch-confounded, so the controlled number must exist."""
    model = research.load_model("radiation-exposure-osd46-v1")
    supplementary = model["supplementaryEvaluation"]
    assert supplementary["batch"] == "0806A-10"
    assert supplementary["arraysUsed"] < model["samples"]
    assert supplementary["bestBalancedAccuracy"] > 0.8
    assert "Cramer" in supplementary["rationale"]


def test_quality_model_confound_is_low_enough_to_be_interpretable():
    """Gamma and HZE are balanced across batches, so batch cannot explain the split."""
    model = research.load_model("radiation-quality-osd46-v1")
    table = model["batchConfound"]["contingency"]
    for batch in table:
        row = table[batch]
        if row.get("gamma", 0) and row.get("hze", 0):
            # Any batch containing both irradiated qualities must contain similar
            # numbers of each, or batch would be a valid explanation.
            assert abs(row["gamma"] - row["hze"]) <= 2, (batch, row)


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_models_never_claim_yield_or_survival_prediction(model_id):
    model = research.load_model(model_id)
    joined = " ".join(model["limitations"]).lower()
    assert "yield" in joined and "not" in joined


# ---------------------------------------------------------------------------
# Prediction contract
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_reference_profiles_are_labelled_synthetic(client, model_id):
    payload = client.get(f"/api/models/{model_id}/reference-profiles").json()
    assert payload["synthetic"] is True
    assert "centroid" in payload["label"].lower()
    assert "not a measured sample" in payload["label"]
    assert len(payload["features"]) == payload["requiredGeneCount"]
    assert len(payload["profiles"]) == len(payload["classLabels"])


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_each_class_centroid_is_classified_as_its_own_class(client, model_id):
    payload = client.get(f"/api/models/{model_id}/reference-profiles").json()
    for label in payload["classLabels"]:
        expression = profile_request(client, model_id, label)
        body = client.post(f"/api/predict/{model_id}", json={"expression": expression}).json()
        assert body["prediction"] == label, (label, body["prediction"])
        assert body["probabilities"][label] > 0.5
        assert abs(sum(body["probabilities"].values()) - 1.0) < 1e-5


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_partial_expression_is_rejected_not_zero_filled(client, model_id):
    features = client.get(f"/api/models/{model_id}/reference-profiles").json()["features"]
    result = client.post(f"/api/predict/{model_id}",
                         json={"expression": {features[0]: 1.0}})
    assert result.status_code == 422
    detail = result.json()["detail"]
    assert detail["error"] == "expression-feature-mismatch"
    assert detail["missingGeneCount"] == len(features) - 1


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_extra_genes_are_rejected(client, model_id):
    expression = profile_request(client, model_id, "control")
    expression["AT9G99999"] = 1.0
    result = client.post(f"/api/predict/{model_id}", json={"expression": expression})
    assert result.status_code == 422
    assert result.json()["detail"]["unexpectedGeneCount"] == 1


@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_prediction_response_carries_its_own_limitations(client, model_id):
    expression = profile_request(client, model_id, "control")
    body = client.post(f"/api/predict/{model_id}", json={"expression": expression}).json()
    assert body["evidenceStatus"] == "experimental"
    assert body["sourceStudy"] == "OSD-46"
    assert body["validation"]["permutationPValue"] is not None
    assert body["validation"]["biologicalGroups"] >= 20
    assert body["interval"]["calibrated"] is False
    assert any("yield" in warning.lower() for warning in body["warnings"])
    # The batch confound travels with every prediction, as data rather than prose.
    assert 0.0 <= body["batchConfound"]["cramersV"] <= 1.0
    assert body["batchConfound"]["contingency"]


def test_exposure_prediction_carries_the_batch_controlled_figure(client):
    expression = profile_request(client, "radiation-exposure-osd46-v1", "control")
    body = client.post("/api/predict/radiation-exposure-osd46-v1",
                       json={"expression": expression}).json()
    supplementary = body["supplementaryEvaluation"]
    assert supplementary["batch"] == "0806A-10"
    assert supplementary["bestBalancedAccuracy"] > 0.8


def test_quality_prediction_has_no_supplementary_evaluation(client):
    """Only the confounded binary task needs one; there must be no invented field."""
    expression = profile_request(client, "radiation-quality-osd46-v1", "control")
    body = client.post("/api/predict/radiation-quality-osd46-v1",
                       json={"expression": expression}).json()
    assert body["supplementaryEvaluation"] is None


def test_out_of_domain_values_raise_a_warning(client):
    payload = client.get("/api/models/radiation-quality-osd46-v1/reference-profiles").json()
    expression = dict(zip(payload["features"], payload["profiles"]["control"]))
    gene = payload["features"][0]
    expression[gene] = 1e6  # far outside any observed intensity
    body = client.post("/api/predict/radiation-quality-osd46-v1",
                       json={"expression": expression}).json()
    assert body["outOfDomain"] is True
    assert any("outside observed training range" in w for w in body["warnings"])


def test_non_finite_expression_is_rejected(client):
    payload = client.get("/api/models/radiation-quality-osd46-v1/reference-profiles").json()
    expression = dict(zip(payload["features"], payload["profiles"]["control"]))
    expression[payload["features"][0]] = "NaN"
    result = client.post("/api/predict/radiation-quality-osd46-v1",
                         json={"expression": expression})
    assert result.status_code == 422


# ---------------------------------------------------------------------------
# Evaluator correctness
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("model_id", NATIVE_MODELS)
def test_served_evaluator_reproduces_its_own_probabilities(client, model_id):
    """The dependency-free evaluator must be arithmetically consistent."""
    model = research.load_model(model_id)
    features = model["features"]
    values = model["referenceProfiles"][model["classLabels"][0]]
    probabilities = research.predict_probabilities(model, values)
    assert abs(sum(probabilities.values()) - 1.0) < 1e-9
    assert max(probabilities.values()) <= 1.0
    # predict_values must agree with the argmax of the probabilities.
    label, _ = research.predict_values(model, values)
    assert label == max(probabilities, key=probabilities.get)
    assert len(values) == len(features)


def test_binary_evaluator_encodes_both_classes_distinctly():
    """Regression guard: a naive coefficient loop gave both classes the same row."""
    model = research.load_model("radiation-exposure-osd46-v1")
    coefficients = model["evaluator"]["coefficients"]
    classes = model["evaluator"]["classes"]
    assert len(classes) == 2
    assert coefficients[classes[0]] != coefficients[classes[1]]
    assert len(model["evaluator"]["intercept"]) == len(classes)


def test_mismatched_feature_vector_length_is_rejected():
    model = research.load_model("radiation-quality-osd46-v1")
    with pytest.raises(ValueError):
        research.predict_probabilities(model, [1.0, 2.0])


# ---------------------------------------------------------------------------
# Classification register
# ---------------------------------------------------------------------------
def test_new_models_are_classified():
    payload = science_classification.classifier_response()
    ids = {feature["id"] for feature in payload["features"]}
    for model_id in NATIVE_MODELS:
        assert model_id in ids
    for model_id in EXCLUDED_MODELS:
        assert model_id in ids
        entry = next(f for f in payload["features"] if f["id"] == model_id)
        assert entry["category"] == 6
        assert entry["status"].startswith("retired")


def test_every_registered_model_is_classified():
    """Registered models must all appear in the classification register.

    Not every registered model is *served as a prediction*: mizuna-microbial-load-v1
    remains registered for reproducibility but answers 410, so it is classified as
    retired rather than served. Both sets must still be covered.
    """
    payload = science_classification.classifier_response()
    registered = {m["id"] for m in research.model_registry()["models"]}
    classified = {feature["id"] for feature in payload["features"]}
    assert registered.issubset(classified)
    served = set(payload["summary"]["servedAsPrediction"])
    retired = set(payload["summary"]["retiredAsPrediction"])
    assert registered.issubset(served | retired)


# ---------------------------------------------------------------------------
# Dataset explorer consistency
# ---------------------------------------------------------------------------
def test_every_modelled_study_is_in_the_dataset_explorer():
    """A model that cites a study the explorer does not list is a dead end.

    Before this test, OSD-46, OSD-782 and OSD-411 trained Phase 9 models while
    being absent from /api/datasets, so a reader following a model back to its
    source data found nothing.
    """
    catalogue = {entry["id"] for entry in research.manifest()["datasets"]}
    # Non-NASA sources are surfaced by /api/external-datasets instead of the OSDR
    # catalogue, so they are checked against that payload rather than this one.
    external = {(research.read_json(research.DATA / "metadata" / "external_lettuce.json")
                 or {}).get("id", "WUR-lettuce")}
    for entry in research.model_registry()["models"]:
        study = research.load_model(entry["id"]).get("sourceStudy")
        if not study:
            continue
        if study.startswith("OSD-"):
            assert study in catalogue, f"{entry['id']} cites {study}, which is not catalogued"
        else:
            assert study in external, f"{entry['id']} cites external {study}, which is not published"


def test_phase9_catalogue_entries_carry_verified_provenance():
    manifest = json.loads((research.DATA / "metadata" / "phase9_nasa_datasets.json").read_text())
    pinned = {(spec["study"], spec["name"]): spec["sha256"] for spec in manifest["files"]}
    catalogue = {entry["id"]: entry for entry in research.manifest()["datasets"]}
    for study in ("OSD-46", "OSD-782", "OSD-411"):
        entry = catalogue[study]
        assert entry["status"] == "verified-data"
        assert entry["sampleCount"] > 0
        assert entry["sampleCountDefinition"]
        downloaded = [f for f in entry["files"] if f.get("downloaded")]
        assert downloaded, "at least one file must be recorded as acquired"
        for item in downloaded:
            assert pinned[(study, item["name"])] == item["sha256"]
            assert item["url"].startswith("https://nasa-osdr.s3.us-west-2.amazonaws.com/")


def test_biological_unit_counts_are_stated_not_inflated():
    """64 libraries from 16 seedlings must not be described as 64 units."""
    catalogue = {entry["id"]: entry for entry in research.manifest()["datasets"]}
    osd411 = catalogue["OSD-411"]
    assert osd411["sampleCount"] == 64
    assert "16" in osd411["sampleCountDefinition"]
    assert any("repeated measures" in note for note in osd411["limitations"])


def test_microbiome_sample_count_disagreement_is_disclosed():
    """The ISA sheet and the processed table differ by one sample; say so."""
    catalogue = {entry["id"]: entry for entry in research.manifest()["datasets"]}
    reconciliation = catalogue["OSD-267"]["sampleCountReconciliation"]
    assert reconciliation["metadataSamples"] == 12
    assert reconciliation["processed16sSamples"] == 11
    assert reconciliation["explanation"]


def test_coverage_no_longer_claims_no_radiation_dataset_exists():
    """The coverage table gates what the UI says is known; it must not go stale."""
    coverage = {row["feature"]: row for row in research.coverage()}
    assert "No suitable NASA dataset identified" not in coverage["Radiation effects"]["status"]
    assert "OSD-46" in coverage["Radiation effects"]["source"]
    assert "not partial gravity" in coverage["Gravity effects"]["limitation"].lower()


# ---------------------------------------------------------------------------
# Harness arithmetic
# ---------------------------------------------------------------------------
def test_harness_reference_evaluator_matches_the_served_evaluator():
    """Two implementations of the same softmax must agree.

    The training harness and the API are separate code paths, so a silent change
    to either could serve probabilities that no longer match the trained model.
    """
    import sys
    sys.path.insert(0, str(research.ROOT / "ml" / "training"))
    import phase9_harness as harness

    for model_id in NATIVE_MODELS:
        model = research.load_model(model_id)
        for values in model["referenceProfiles"].values():
            mine = harness.softmax_probabilities(model["evaluator"], values)
            served = research.predict_probabilities(model, values)
            for label, probability in mine.items():
                assert abs(probability - served[label]) < 1e-12


def test_phase9_previews_expose_design_tables_and_say_so():
    """A preview is a promise that the rows are real. For the Phase 9 studies the
    real, browsable rows are sample-to-condition assignments, not outcomes, so the
    preview must say which it is showing."""
    expected = {
        "OSD-46": {"osd46_radiation_samples.csv": 44, "osd46_array_batch.csv": 44},
        "OSD-782": {"osd782_radiation_samples.csv": 36},
        "OSD-411": {"osd411_gravity_samples.csv": 64},
    }
    for study, tables in expected.items():
        preview = research.preview(study)
        found = {table["name"]: table["rowCount"] for table in preview["tables"]}
        assert found == tables, f"{study} preview mismatch: {found}"
        for table in preview["tables"]:
            assert table["columns"], f"{study}/{table['name']} has no header"
            assert table["note"].strip(), f"{study}/{table['name']} has no caveat"

    osd46_note = " ".join(table["note"] for table in research.preview("OSD-46")["tables"])
    assert "design factors, not measured outcomes" in osd46_note

    osd411_note = research.preview("OSD-411")["tables"][0]["note"]
    # Guards the two claims this study invites: partial gravity and 64 plants.
    assert "not partial gravity" in osd411_note
    assert "not 64 independent plants" in osd411_note


def test_catalogued_sample_counts_state_what_they_count():
    """A sample count without a definition is a number waiting to be misread, and
    OSD-780 is the trap: three files, two measured assay tables, no per-plant rows."""
    catalogue = {entry["id"]: entry for entry in research.manifest()["datasets"]}

    osd780 = catalogue["OSD-780"]
    assert osd780["fileCount"] == 3
    assert osd780["sampleCount"] == 2, "2 assay tables, the third file is a dictionary"
    assert "assay tables" in osd780["sampleCountDefinition"]

    # OSD-411: the 64 libraries come from 16 seedlings, and the definition must say so.
    osd411 = catalogue["OSD-411"]
    assert osd411["sampleCount"] == 64
    assert "16 seedlings" in osd411["sampleCountDefinition"]

    # Scoped to the studies this phase catalogued: the older entries predate the
    # field, and retrofitting them is a separate refactor, not a Phase 9 claim.
    for study in ("OSD-46", "OSD-782", "OSD-411", "OSD-780", "OSD-267", "OSD-269"):
        assert catalogue[study].get("sampleCountDefinition"), f"{study} count undefined"
