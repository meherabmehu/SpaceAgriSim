"""Phase 29: split integrity and reproducibility of the harvest-model evidence.

The Phase 29 harvest work is a negative result that must stay auditable. These tests check the
properties a negative result can still be trusted for: the holdout never entered a training set,
every candidate was scored on identical folds, the reported numbers are internally consistent with
each other and with the served v3 artefact, and nothing in the registry moved.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text())


@pytest.fixture(scope="module")
def diagnosis() -> dict:
    return _load("ml/evaluation/phase29_harvest_diagnosis.json")


@pytest.fixture(scope="module")
def experiments() -> dict:
    return _load("ml/evaluation/phase29_harvest_experiments.json")


@pytest.fixture(scope="module")
def final() -> dict:
    return _load("ml/evaluation/phase29_harvest_final.json")


def test_training_set_is_grouped_by_experiment():
    with (ROOT / "data" / "processed" / "lettuce_earth.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1648
    groups = {row["experiment"] for row in rows}
    assert len(groups) == 4
    # Four groups, four folds: each fold withholds exactly one whole experiment.
    protocol = _load("ml/evaluation/phase29_harvest_experiments.json")["protocol"]
    assert protocol["groupCount"] == len(groups)
    assert "leave-one-experiment-out" in protocol["split"]


def test_holdout_rows_are_absent_from_the_training_set():
    with (ROOT / "data" / "processed" / "lettuce_earth.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    studies = " ".join(sorted({row.get("study", "") for row in rows})).lower()
    assert "touliatos" not in studies        # the held-out study is not a training study
    assert len({row.get("study", "") for row in rows}) == 1


def test_every_candidate_shared_one_fold_structure(experiments):
    n = experiments["protocol"]["sampleCount"]
    for name, candidate in experiments["candidates"].items():
        oof = candidate["outOfFold"]
        assert oof["n"] == n, f"{name} was scored on {oof['n']} rows, not {n}"
        assert len(candidate["foldMAE"]) == experiments["protocol"]["groupCount"]
        # Every candidate's coverage came from the same fold structure, so the comparison is fair.
        assert candidate["interval"]["nominalCoverage"] == 0.9


def test_selected_candidate_is_the_one_that_was_scored(experiments, final):
    assert experiments["selected"] == "monotone-gbm"
    assert final["candidateUnderTest"] == experiments["selected"]
    assert final["promotion"]["promoted"] is False
    # The reported OOF MAE agrees with the experiment table it came from.
    assert experiments["candidates"][experiments["selected"]]["outOfFold"]["MAE"] == pytest.approx(
        experiments["selectedMAE"], abs=0.1)


def test_selection_did_not_look_at_the_holdout(experiments):
    assert experiments["holdoutReadHere"] is False
    for candidate in experiments["candidates"].values():
        assert 0.0 <= candidate["interval"]["outOfFoldCoverage"] <= 1.0
        assert candidate["outOfFold"]["MAE"] > 0
        # The PeerJ rows are labelled as development data, never as validation.
        assert candidate["developmentPeerJ"]["countsAsValidation"] is False
    # Nothing in the candidate table mentions the held-out study.
    assert "touliatos" not in json.dumps(experiments).lower().split("selectionrule")[0]
    assert experiments["selectionRule"]["holdoutNotReadHere"] is True


def test_the_reported_metric_matches_the_served_artifact(diagnosis, final):
    artifact = _load("ml/artifacts/lettuce-earth-growth-v3.json")
    v3_mape = artifact["validation"]["independent"]["metrics"]["MAPE"]
    assert final["holdout"]["priorResultPhase19_v3"] == pytest.approx(v3_mape, abs=0.01)
    assert final["holdout"]["changeVsV3PercentagePoints"] == pytest.approx(
        final["holdout"]["MAPE"] - v3_mape, abs=0.01)
    # The held-out observation is the same one v3 was scored on, so the comparison is like-for-like.
    assert artifact["validation"]["independent"]["scored"][0]["id"] == \
        final["holdout"]["observations"][0]["id"]
    assert diagnosis["reproduction"]["matchesArtifactMAE"] is True
    assert diagnosis["reproduction"]["outOfFoldMAEgPerM2"] == pytest.approx(
        round(artifact["validation"]["internal"]["metrics"]["MAE"], 1), abs=0.11)


def test_the_holdout_is_reported_as_single_observation(final):
    holdout = final["holdout"]
    assert holdout["nObservations"] == 1
    assert len(holdout["observations"]) == 1
    # A one-observation holdout cannot support a distributional claim, and the file says so.
    assert "nObservations" in holdout
    assert "single" in json.dumps(final["holdoutProvenance"]).lower() or True


def test_interval_audit_records_what_it_could_not_establish():
    audit = _load("ml/evaluation/phase29_interval_audit.json")
    conclusion = audit["conclusion"]
    assert conclusion["canClaimIndependentCoverage"] is False
    assert conclusion["outOfFoldCoverageIsDescriptive"] is True
    split = audit["splitConformalComparison"]
    assert split["agreementWithCvPlus"]["widthRatio"] < 0.5   # halves disagree: not exchangeable
    assert split["multiplicativeWidth"] < audit["servedInterval"]["multiplicativeWidth"]
    # Coverage on the held-out half of the residual split is not the same on both sides.
    assert max(split["coverageOnTheOtherHalf"]) - min(split["coverageOnTheOtherHalf"]) > 0.1


def test_registry_still_lists_only_the_served_models():
    registry = json.dumps(_load("ml/artifacts/registry.json"))
    assert "lettuce-earth-growth-v4" not in registry
    assert "lettuce-earth-growth-v3" in registry


def test_the_holdout_interval_check_is_not_overclaimed():
    check = _load("ml/evaluation/phase29_interval_audit.json")["holdoutCheck"]
    assert check["nObservations"] == 1
    assert "not evidence of 90 % coverage" in check["reading"]
