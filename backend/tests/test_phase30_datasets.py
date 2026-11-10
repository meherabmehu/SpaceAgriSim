"""Phase 30: the two acquired datasets, and the two evaluations built on them.

Everything here is checked against the committed files rather than against a report about them:
the raw workbook is hashed, the processed tables are rebuilt in a temporary directory and compared
line for line, and each evaluation artifact is checked for the properties that make a held-out
number a held-out number - disjoint identifiers, a criterion that was not moved, and a served flag
that matches the verdict.

Nothing in this file re-scores a model on data the model was selected on, and nothing asserts a
performance number except the ones recorded in the artifacts themselves.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "phase30"
PROCESSED = ROOT / "data" / "processed" / "phase30"
MANIFEST = ROOT / "data" / "metadata" / "phase30_acquisition_manifest.json"

WHEAT_XLSX = RAW / "wheat_yields.xlsx"
LETTUCE_XLSX = RAW / "lue_dataset.xlsx"

WHEAT_SHA256 = "385d4680067832026296ec6bec1ce8757fa4bc42bd42d6f37b62899b52dc33c5"
LETTUCE_SHA256 = "feb96c6c79c3997fde182dedbd252a76aa41ddd6d980db34c8ce2beaf434cedd"

HARVEST_EVAL = ROOT / "ml" / "evaluation" / "phase30_harvest_crossstudy.json"
CEA_EVAL = ROOT / "ml" / "evaluation" / "phase30_cea_wheat_response.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------- raw acquisition


@pytest.mark.parametrize("path,expected", [(WHEAT_XLSX, WHEAT_SHA256),
                                            (LETTUCE_XLSX, LETTUCE_SHA256)])
def test_the_raw_files_are_the_bytes_that_were_recorded(path, expected):
    """Raw data is immutable: the hash is the acquisition, and a re-download must match it."""
    assert path.is_file(), f"{path.name} is missing from the workspace"
    assert _sha256(path) == expected


def test_the_manifest_records_hash_doi_licence_and_access_date():
    manifest = _json(MANIFEST)
    datasets = manifest["datasets"]
    assert len(datasets) == 2

    wheat = datasets["cea-wheat-apogee"]
    assert wheat["doi"] == "10.5281/zenodo.17764612"
    assert wheat["license"] == "CC BY 4.0"
    assert wheat["rawSha256"] == WHEAT_SHA256
    assert wheat["doi"].startswith("10.5281/zenodo.")
    assert wheat["independenceUnit"].startswith("experiment")
    assert wheat["environmentRanges"] and wheat["yieldRange"]

    lettuce = datasets["lettuce-multistudy-lue"]
    assert lettuce["doi"] == "10.5281/zenodo.14640245"
    assert lettuce["license"] == "CC BY 4.0"
    assert lettuce["rawSha256"] == LETTUCE_SHA256
    assert lettuce["independenceUnit"].startswith("study")


def test_every_rejected_candidate_is_recorded_with_a_reason():
    """A rejected source must stay rejected in writing, or the search gets re-run next phase."""
    rejected = _json(MANIFEST)["rejected"]
    assert len(rejected) >= 10
    for item in rejected:
        assert item["doi"] and item["reason"].strip()
    ids = [item["doi"] for item in rejected]
    assert len(ids) == len(set(ids))


def test_no_unit_mixing_is_recorded_as_a_transformation():
    transformations = _json(MANIFEST)["transformations"]
    assert transformations
    joined = " ".join(transformations).lower()
    # The two things that must never happen silently are stated as refusals.
    assert "no imputation" in joined
    assert "no unit conversion" in joined
    assert "refuses to average" in joined


# ------------------------------------------------------------- processed tables


def test_the_processed_tables_have_the_recorded_shape():
    subplots = _rows(PROCESSED / "cea_wheat_subplots.csv")
    experiments = _rows(PROCESSED / "cea_wheat_experiments.csv")
    assert len(subplots) == 719
    assert len(experiments) == 39
    # Every sub-plot belongs to exactly one experiment row.
    assert {row["experimentId"] for row in subplots} == {
        row["experimentId"] for row in _rows(PROCESSED / "cea_wheat_experiments.csv")}
    # Two experiment rows carry no harvest-mean (one has no yield rows at all); the platform
    # reports coverage rather than imputing them, so 37 is the honest count.
    assert sum(1 for row in experiments if row["grainYieldKgPerM2Mean"]) == 37

    lettuce = _rows(PROCESSED / "lettuce_multistudy.csv")
    assert len(lettuce) == 53
    assert len({row["studyKey"] for row in lettuce}) == 40


def test_subplot_aggregation_reproduces_the_experiment_means():
    """The published mean must equal the mean of the sub-plots it came from, at stored precision."""
    subplots = _rows(PROCESSED / "cea_wheat_subplots.csv")
    experiments = {row["experimentId"]: row for row in
                   _rows(PROCESSED / "cea_wheat_experiments.csv")}
    grouped: dict[str, list[float]] = {}
    for row in subplots:
        if not row["grainYieldKgPerM2"]:
            continue  # a sub-plot with no harvested yield is blank, never zero-filled
        grouped.setdefault(row["experimentId"], []).append(float(row["grainYieldKgPerM2"]))
    for experiment_id, values in grouped.items():
        mean = sum(values) / len(values)
        recorded = float(experiments[experiment_id]["grainYieldKgPerM2Mean"])
        # Stored to six decimals, so compare at that precision rather than at full float precision.
        assert mean == pytest.approx(recorded, rel=1e-6, abs=1e-6), experiment_id


def test_the_builder_reproduces_the_committed_tables():
    """`--check` rebuilds from the raw workbook in memory and compares against the committed CSVs."""
    result = subprocess.run([sys.executable, "ml/research/build_phase30_datasets.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "match the committed manifest" in result.stdout


def test_the_quality_record_carries_units_ranges_and_coverage():
    quality = _json(PROCESSED / "quality.json")
    wheat = quality["datasets"]["cea-wheat-apogee"]
    assert wheat["unitMap"]["grainYieldKgPerM2"]["unit"] == "kg/m2"
    assert wheat["unitMap"]["photoperiodHours"]["unit"] == "h/day"
    assert wheat["environmentRanges"]["meanPpfdUmolPerM2S"]["min"] < 300
    assert wheat["environmentRanges"]["meanPpfdUmolPerM2S"]["max"] > 1000
    lettuce = quality["datasets"]["lettuce-multistudy-lue"]
    assert lettuce["unitMap"]["shootDryMassG"]["unit"] == "g"
    assert lettuce["unitMap"]["co2Ppm"]["unit"] == "ppm"


# ------------------------------------------------------------------- evaluations


def test_the_holdout_sets_are_disjoint_from_the_development_sets():
    """The property that makes a holdout a holdout, checked on the identifiers themselves."""
    harvest = _json(HARVEST_EVAL)
    holdout_studies = set(harvest["protocol"]["holdoutStudies"])
    holdout_records = {row["studyKey"] for row in harvest["holdout"]["records"]}
    assert holdout_records == holdout_studies
    assert harvest["protocol"]["holdoutUsedForSelection"] is False
    all_studies = {row["studyKey"] for row in _rows(PROCESSED / "lettuce_multistudy.csv")}
    assert holdout_studies < all_studies
    assert len(all_studies - holdout_studies) == 32  # the leave-one-study-out development pool

    cea = _json(CEA_EVAL)
    dev = set(cea["protocol"]["developmentExperiments"])
    hold = set(cea["protocol"]["holdoutExperiments"])
    assert hold and dev
    assert not (hold & dev)
    assert {row["experimentId"] for row in cea["holdout"]["perExperiment"]} == hold
    assert len(dev) + len(hold) == 36


@pytest.mark.parametrize("path", [HARVEST_EVAL, CEA_EVAL])
def test_neither_evaluation_moved_the_criterion(path):
    artifact = _json(path)
    assert artifact["protocol"]["acceptanceCriterionPct"] == 30.0
    assert artifact["protocol"]["criterionSource"].startswith("unchanged")
    assert artifact["holdout"]["passed"] is False
    assert artifact["holdout"]["metrics"]["MAPE"] > 30.0
    # The out-of-fold number must not be dressed up as the holdout number.
    assert artifact["holdout"]["metrics"]["n"] < artifact["selectedOutOfFold"]["n"]
    assert artifact["protocol"]["selectionRuleWrittenBeforeScoring"] is True
    assert artifact["protocol"]["noRandomSplit"]


@pytest.mark.parametrize("path", [HARVEST_EVAL, CEA_EVAL])
def test_neither_evaluation_is_served(path):
    artifact = _json(path)
    assert artifact.get("promoted") is False or artifact.get("served") is False
    assert artifact["priorHoldoutInspection"] is not None


def test_the_harvest_evaluation_selected_the_mean_baseline_honestly():
    """The simplicity rule picked the baseline; that is a finding, not a bug to tune away."""
    artifact = _json(HARVEST_EVAL)
    assert artifact["selected"] == "baseline-mean"
    assert artifact["candidates"]["baseline-mean"]["MAEgPerPlant"] == pytest.approx(
        artifact["selectedOutOfFold"]["MAEgPerPlant"])


def test_the_cea_evaluation_records_why_it_is_not_served():
    """A failed surface must carry the reason on the artifact, not only in a document."""
    artifact = _json(CEA_EVAL)
    assert artifact["served"] is False
    assert "will not be re-split" in artifact["holdoutSpent"]
    assert "order of magnitude" in artifact["servedReason"]
    assert artifact["domain"]["noExtrapolationRule"]
    assert artifact["dataset"]["doi"] == "10.5281/zenodo.17764612"


def test_the_cea_artifact_is_wired_to_a_served_surface_and_the_harvest_one_is_recorded():
    """An evaluation nobody can reach is a file, not evidence; one that advertised a removed
    workflow was worse, which is why Phase 31 split these two cases.
    """
    harvest = _json(HARVEST_EVAL)
    cea = _json(CEA_EVAL)
    capability = subprocess.run(
        [sys.executable, "-c",
         "import json,sys; sys.path.insert(0,'backend');"
         "from app.workflows import cea_evidence;"
         "print(json.dumps(cea_evidence.capability()))"],
        cwd=ROOT, capture_output=True, text=True)
    assert capability.returncode == 0, capability.stderr
    payload = json.loads(capability.stdout)
    assert payload["predictiveModel"]["evidenceFile"] == \
        "ml/evaluation/phase30_cea_wheat_response.json"
    assert cea["served"] is False
    # The harvest evaluation is retained and still says it failed; it is reachable through the
    # repository and docs/PHASE31_REMOVED_MODELS.md rather than through an API route.
    assert harvest["promoted"] is False
    assert HARVEST_EVAL.is_file()
    assert "harvest" in (ROOT / "docs" / "PHASE31_REMOVED_MODELS.md").read_text().lower()
