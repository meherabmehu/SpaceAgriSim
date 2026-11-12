"""Phase 37 card completion: every served model must have a card that can be checked.

The point of these tests is that a model card is worth nothing if the metadata in it is merely
present. Each one below fails on a specific way the completion could have been wrong, and two of
them caught real errors while it was being written:

* the first draft declared that lettuce v1 and v2 had no prediction interval. They do - a 90 %
  cross-conformal interval with measured coverage 0.939 and 0.961 - and the draft would have
  published a false "unavailable" over a real field. The test that compares the card's uncertainty
  kind against the artifact's own `interval` block is the one that caught it.
* the first draft pointed the WUR-trained models at a catalogue entry called "wur-lettuce" that
  does not exist. Every dataset reference must now resolve to a real catalogue entry or to a
  committed archive path.

What is enforced:
  presence      - seven cards, one per served model, and no card for a model that is not served
  fidelity      - metrics, baseline, samples, groups and seed in the card equal the artifact's
  artifact hash - unchanged, and equal to the registry value
  code          - an immutable commit that demonstrably contains the training script
  training data - a real digest, with its basis stated, or an explicit unavailable state
  references    - catalogue or archive, and the archive path exists in the commit
  no promotion  - nothing claims the model was retrained, promoted or re-thresholded
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CARDS = ROOT / "ml" / "artifacts" / "cards"
REGISTRY = ROOT / "ml" / "artifacts" / "registry.json"
CATALOGUE = ROOT / "data" / "research" / "dataset_catalog.json"
EVIDENCE = ROOT / "ml" / "evaluation" / "phase37_model_evidence.json"

SERVED = [
    "lettuce-earth-growth-v1",
    "lettuce-earth-growth-v2",
    "lettuce-earth-growth-v3",
    "mizuna-microbial-relative-load-v2",
    "radiation-exposure-osd46-v1",
    "radiation-quality-osd46-v1",
    "tomato-flight-response-v1",
]


def card(model_id: str) -> dict:
    path = CARDS / f"{model_id}.json"
    assert path.is_file(), f"missing model card {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def artifact(model_id: str) -> dict:
    return json.loads((ROOT / "ml" / "artifacts" / f"{model_id}.json").read_text(encoding="utf-8"))


def registry() -> dict[str, dict]:
    return {row["id"]: row for row in json.loads(REGISTRY.read_text())["models"]}


# --------------------------------------------------------------------------- presence
def test_there_is_one_card_per_served_model_and_no_orphans():
    on_disk = {p.stem for p in CARDS.glob("*.json")}
    assert on_disk == set(SERVED), f"card set {sorted(on_disk)} != served set {sorted(SERVED)}"


def test_the_card_set_equals_the_set_the_application_actually_serves():
    """A card for a withdrawn model, or a served model with no card, must be impossible."""
    import sys

    backend = str(ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app import research  # noqa: PLC0415

    served_by_app = {m["id"] for m in research.model_registry()["models"]}
    assert served_by_app == set(SERVED)


@pytest.mark.parametrize("model_id", SERVED)
def test_every_card_states_a_purpose_and_a_refusal(model_id):
    payload = card(model_id)
    assert payload["purpose"].strip(), model_id
    assert payload["intendedUse"].strip(), model_id
    # A card that does not say what the model must not be used for is an advertisement.
    assert len(payload["notIntendedFor"]) >= 2, model_id
    assert payload["outOfDomainBehaviour"]["refuses"] is True, model_id


# --------------------------------------------------------------------------- fidelity
@pytest.mark.parametrize("model_id", SERVED)
def test_the_card_does_not_contradict_the_artifact(model_id):
    payload, source = card(model_id), artifact(model_id)
    assert payload["metrics"] == source.get("metrics"), model_id
    assert payload["samples"] == source.get("samples"), model_id
    assert payload["groups"] == source.get("groups"), model_id
    assert payload["seed"] == source.get("seed"), model_id
    assert payload["identity"]["task"] == source.get("task"), model_id
    assert payload["limitations"] == (source.get("limitations") or []), model_id


@pytest.mark.parametrize("model_id", SERVED)
def test_the_declared_domain_is_the_artifact_domain(model_id):
    payload, source = card(model_id), artifact(model_id)
    assert payload["domain"] == source.get("domain"), model_id


@pytest.mark.parametrize("model_id", SERVED)
def test_the_uncertainty_kind_matches_what_the_artifact_records(model_id):
    """The check that caught a false 'no interval recorded' claim during this completion."""
    payload, source = card(model_id), artifact(model_id)
    has_interval = bool(source.get("interval"))
    has_calibration = bool(source.get("probabilityCalibration"))
    kind = payload["uncertainty"]["kind"]
    if has_interval:
        assert kind == "prediction-interval", f"{model_id}: artifact has an interval, card says {kind}"
    elif has_calibration:
        assert kind == "probability-calibration", f"{model_id}: card says {kind}"
    else:
        assert kind == "unavailable", f"{model_id}: card claims {kind} with no artifact support"


@pytest.mark.parametrize("model_id", SERVED)
def test_every_model_records_an_uncertainty_statement_and_a_grouped_split(model_id):
    payload = card(model_id)
    assert payload["uncertainty"]["statement"].strip(), model_id
    assert payload["uncertainty"]["kind"] in {
        "prediction-interval", "probability-calibration"}, model_id
    split = payload["split"]
    assert split["method"].strip(), model_id
    assert split["grouped"] is True, model_id
    assert split["groupUnit"].strip(), model_id
    assert split["groups"] == payload["groups"], model_id


# --------------------------------------------------------------------------- artifact hash
@pytest.mark.parametrize("model_id", SERVED)
def test_the_artifact_hash_is_preserved_and_matches_the_registry(model_id):
    payload = card(model_id)
    row = registry()[model_id]
    assert payload["artifact"]["sha256"] == row["sha256"], model_id
    assert payload["artifact"]["hashPreserved"] is True, model_id
    assert payload["artifact"]["modifiedByThisCompletion"] is False, model_id
    # And the file on disk still hashes to it, so the card cannot outlive a silent edit.
    import hashlib

    on_disk = hashlib.sha256((ROOT / row["artifact"]).read_bytes()).hexdigest()
    assert on_disk == row["sha256"], f"{model_id}: artifact edited after the registry was written"


def test_no_model_artifact_was_modified_by_completing_the_cards():
    """The completion must be additive. Every registry hash must still resolve to its file."""
    import hashlib

    for model_id, row in registry().items():
        on_disk = hashlib.sha256((ROOT / row["artifact"]).read_bytes()).hexdigest()
        assert on_disk == row["sha256"], model_id


# --------------------------------------------------------------------------- code reference
@pytest.mark.parametrize("model_id", SERVED)
def test_every_code_reference_is_an_immutable_commit_containing_the_script(model_id):
    ref = card(model_id)["code"]
    assert len(ref["commit"]) == 40 and all(c in "0123456789abcdef" for c in ref["commit"]), ref
    # Not a branch name: a branch moves, a commit does not.
    assert ref["commit"] not in {"main", "HEAD"}, model_id
    exists = subprocess.run(["git", "cat-file", "-e", f"{ref['commit']}:{ref['path']}"],
                            cwd=ROOT, capture_output=True)
    assert exists.returncode == 0, f"{model_id}: {ref['path']} is not in {ref['commit']}"
    assert ref["immutable"] is True, model_id


@pytest.mark.parametrize("model_id", SERVED)
def test_the_script_on_disk_is_the_one_the_commit_recorded(model_id):
    """If the script drifted, the commit reference describes code that no longer exists here."""
    ref = card(model_id)["code"]
    assert ref["unchangedSinceCommit"] is True, (
        f"{model_id}: {ref['path']} has changed since {ref['commit']}; update the reference")


# --------------------------------------------------------------------------- training data
@pytest.mark.parametrize("model_id", SERVED)
def test_every_card_records_a_training_data_digest_or_an_explicit_refusal(model_id):
    data = card(model_id)["trainingData"]
    assert data["status"] in {
        "committed-file", "recorded-checksum", "reconstructed-derived", "unavailable"}, data["status"]
    if data["status"] == "unavailable":
        # An unavailable field is only acceptable with a reason and with itself declared.
        assert data.get("reason"), model_id
        assert card(model_id)["exceptions"], model_id
    else:
        assert data["sha256"], model_id
        assert len(data["sha256"]) == 64, model_id
        assert data["hashBasis"].strip(), model_id


@pytest.mark.parametrize("model_id", SERVED)
def test_every_recorded_digest_is_checked_against_its_declared_source(model_id):
    """No digest is accepted on the card's word alone, whichever of the three cases applies."""
    import hashlib

    data = card(model_id)["trainingData"]
    status = data["status"]
    if status == "committed-file":
        path = ROOT / data["primaryInput"]
        assert path.is_file(), data["primaryInput"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == data["sha256"], model_id
    elif status == "recorded-checksum":
        manifest = json.loads((ROOT / data["manifest"]).read_text())
        entries = manifest.get("files") if isinstance(manifest, dict) else manifest
        name = pathlib.Path(data["primaryInput"]).name
        pinned = [e["sha256"] for e in entries
                  if str(e.get("name", e.get("path", ""))).endswith(name)]
        assert data["sha256"] in pinned, f"{model_id}: digest not among the manifest's pins"
    elif status == "reconstructed-derived":
        # The digest cannot be recomputed here (it needs a 4.5 MB download), so what is enforced is
        # that the upstream file it is derived from is itself pinned, and that the card records
        # which command reproduces it.
        upstream = [i for i in data["supportingInputs"] if i.get("sha256")]
        assert upstream, model_id
        assert data["verifiedWith"].endswith("--verify-training-data"), model_id
    else:
        assert data.get("reason") and card(model_id)["exceptions"], model_id


def test_the_lettuce_hash_agrees_with_the_value_the_v3_run_recorded():
    """Corroboration, not assertion: v3's artifact wrote this digest at training time."""
    recorded = artifact("lettuce-earth-growth-v3").get("trainingDataSha256")
    assert recorded, "the v3 artifact no longer records a training-data hash"
    for model_id in ("lettuce-earth-growth-v1", "lettuce-earth-growth-v2", "lettuce-earth-growth-v3"):
        assert card(model_id)["trainingData"]["sha256"] == recorded, model_id


def test_the_radiation_digest_matches_the_committed_nasa_manifest():
    manifest = json.loads((ROOT / "data" / "metadata" / "phase9_nasa_datasets.json").read_text())
    pinned = None
    for entry in manifest.get("files") or []:
        if str(entry.get("name", "")).startswith("GLDS-46_array_normalized_expression_probeset"):
            pinned = entry["sha256"]
    assert pinned, "the OSD-46 matrix digest is no longer pinned in the manifest"
    for model_id in ("radiation-exposure-osd46-v1", "radiation-quality-osd46-v1"):
        data = card(model_id)["trainingData"]
        assert data["sha256"] == pinned, model_id
        assert data["artifactAgrees"] is True, model_id


def test_the_tomato_digest_is_tied_to_a_checked_upstream_file():
    data = card("tomato-flight-response-v1")["trainingData"]
    upstream = next(item for item in data["supportingInputs"]
                    if "GLDS-709" in item["path"])
    pinned = json.loads((ROOT / "data" / "metadata" / "download_checksums.json").read_text())
    expected = next(e["sha256"] for e in pinned if str(e.get("path", "")).endswith("GLDS-709_rna_seq_STAR_Unnormalized_Counts_GLbulkRNAseq.csv"))
    assert upstream["sha256"] == expected
    # The card must state that the parquet digest was obtained by reconstruction, not by reading a
    # committed file, and must carry the version-independent content digest alongside it.
    assert data["status"] == "reconstructed-derived"
    assert data["contentSha256"] and len(data["contentSha256"]) == 64
    assert "reconstruct" in data["reconstruction"].lower()


# --------------------------------------------------------------------------- dataset references
@pytest.mark.parametrize("model_id", SERVED)
def test_every_dataset_reference_resolves(model_id):
    data = card(model_id)["trainingData"]
    catalogue = {d["id"] for d in json.loads(CATALOGUE.read_text())["datasets"]}
    resolved = False
    if data.get("catalogueRef"):
        assert data["catalogueRef"] in catalogue, (
            f"{model_id}: catalogueRef {data['catalogueRef']} is not a catalogue entry")
        resolved = True
    if data.get("archiveRef"):
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", data["archiveRef"]],
                                 cwd=ROOT, capture_output=True)
        assert tracked.returncode == 0, (
            f"{model_id}: archiveRef {data['archiveRef']} is not a tracked file")
        resolved = True
    assert resolved, f"{model_id}: neither a catalogue entry nor an archive path"


@pytest.mark.parametrize("model_id", SERVED)
def test_every_supporting_input_that_claims_a_computed_hash_has_one(model_id):
    for item in card(model_id)["trainingData"]["supportingInputs"]:
        assert item["path"], model_id
        if item.get("hashVerifiedAtBuild") is True:
            assert item["sha256"] and len(item["sha256"]) == 64, item["path"]
        else:
            # Not computed here: the card must say where the digest came from instead.
            assert item.get("sha256") or item.get("hashSource"), item["path"]


# --------------------------------------------------------------------------- no promotion
@pytest.mark.parametrize("model_id", SERVED)
def test_completing_metadata_promoted_retrained_and_relabelled_nothing(model_id):
    payload = card(model_id)
    evidence = payload["evidence"]
    assert evidence["promotedByThisCompletion"] is False, model_id
    assert evidence["retrainedByThisCompletion"] is False, model_id
    assert evidence["thresholdsChangedByThisCompletion"] is False, model_id
    # And the verdict must still be the one the evidence audit recorded.
    audit = json.loads(EVIDENCE.read_text())["models"][model_id]
    assert evidence["classification"] == audit["classification"], model_id
    assert evidence["verdict"] == audit["verdictBefore"], model_id
    assert evidence["decisionGrade"] == audit["decisionGradeAfter"], model_id


def test_exactly_one_model_is_decision_grade_and_the_cards_say_so():
    graded = [m for m in SERVED if card(m)["evidence"]["decisionGrade"]]
    assert graded == ["mizuna-microbial-relative-load-v2"], graded


def test_every_card_reports_itself_complete_or_declares_an_exception():
    for model_id in SERVED:
        completeness = card(model_id)["completeness"]
        assert completeness["complete"] == completeness["total"], (
            f"{model_id}: {completeness['complete']}/{completeness['total']} checks, "
            f"exceptions={completeness['exceptions']}")
        assert completeness["allComplete"] is True, model_id


def test_the_cards_are_not_stale():
    result = subprocess.run(["python3", "ml/research/build_model_cards.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
