"""Phase 10: the dose and gravity recovery results, and what they may not be used for.

These tests exist because both findings are the kind that get quoted out of context.
A dose model that scores well on held-out timepoints is not a dose predictor, and a
partial-gravity contrast that separates 0 g from 0.34 g in one mission is not a
predictor of Moon or Mars gravity. The assertions below pin the numbers to their
protocols and the protocols to their limits.
"""

from __future__ import annotations
import sys

import json

from pathlib import Path

from app import research

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
EVALUATION = ROOT / "ml" / "evaluation"


def artifact(name: str) -> dict:
    return safedata.load(EVALUATION / name)


def test_the_dose_labels_were_valid_all_along():
    """Phase 9 called the dose label unusable; the label was fine, the split was not."""
    dose = artifact("phase10_dose_recovery")
    assert dose["labelsAvailable"]["absorbedDoseGy"] is True
    assert dose["labelsAvailable"]["values"] == [0.0, 10.0, 100.0]
    audit = dose["confoundAudit"]
    assert audit["doseBalancedWithinTimepoint"] is True
    assert audit["doseConfoundedWithTimepoint"] is False
    # The real limitation is that each (dose, timepoint) cell is one batch.
    assert audit["cellIsOneSequencingBatch"] is True


def test_the_dose_protocol_decides_the_answer():
    """Two protocols on the same 36 libraries give opposite readings, and both are kept."""
    dose = artifact("phase10_dose_recovery")
    protocols = dose["protocols"]
    cell = protocols["A_cellHeldOut"]["balancedAccuracy"]
    time = protocols["B_timepointHeldOut"]["balancedAccuracy"]
    assert cell < 0.5, "the cell-held-out protocol must stay at or below chance"
    assert time > cell, "holding out whole timepoints must not make the task harder"
    assert protocols["B_timepointHeldOut"]["permutation"]["pCorrected"] < 0.05
    # The permutation p is corrected for finite sampling and therefore never zero.
    assert protocols["B_timepointHeldOut"]["permutation"]["pCorrected"] > 0
    assert protocols["C_timepointHeldOutOrdinal"]["spearman"]["pCorrected"] > 0


def test_a_zero_balanced_accuracy_is_labelled_as_worse_than_chance():
    """A degenerate split must not be reported as 'no better than chance'."""
    dose = artifact("phase10_dose_recovery")
    assert "whyItCannotAnswerTheQuestion" in dose["protocols"]["A_cellHeldOut"]
    assert dose["registryChange"] is None


def test_dose_is_not_served_even_though_the_signal_was_detected():
    """Recovering a signal on 36 libraries does not create a model."""
    dose = artifact("phase10_dose_recovery")
    assert dose["outcome"] != "dose-signal-not-recovered"
    assert dose["registryChange"] is None
    assert "does not create a servable model" in dose["disclosure"]
    served = {entry["id"] for entry in research.model_registry()["models"]}
    assert "radiation-dose-osd782-v1" not in served
    assert "gravity-reorientation-osd411-v1" not in served


def test_the_partial_gravity_study_is_real_and_catalogued():
    """OSD-314's gravity levels come from its own factor table, not from hardware prose."""
    catalogue = {entry["id"]: entry for entry in research.manifest()["datasets"]}
    assert "OSD-314" in catalogue
    entry = catalogue["OSD-314"]
    assert entry["gravityLevelsG"] == [0.0, 0.34, 1.0]
    assert entry["sampleCount"] == 17
    assert entry["status"] == "analysed-not-served"
    assert any("Moon" in limitation for limitation in entry["limitations"])


def test_partial_gravity_is_reported_with_its_confound():
    gravity = artifact("phase10_partial_gravity")
    design = gravity["design"]
    assert design["gravityLevelsG"] == [0.0, 0.34, 1.0]
    # The three-level analysis is flight-confounded and must say so in the artifact.
    assert design["threeLevelAnalysisIsFlightConfounded"] is True
    assert gravity["secondaryThreeLevel"]["whyNotPromoted"] == design["threeLevelStatement"]
    # The within-flight contrast is the primary one, and it is the only clean one.
    assert design["withinFlightContrastIsClean"] is True
    assert gravity["primaryContrast"]["folds"] == 2


def test_the_perfect_separation_is_corroborated_and_batch_limited():
    """1.0 balanced accuracy on 11 libraries needs both a corroboration and a caveat."""
    gravity = artifact("phase10_partial_gravity")
    corroboration = gravity["corroboration"]
    assert corroboration["available"] is True
    counts = corroboration["withinFlightContrasts"]
    assert counts and min(counts.values()) > 1000, (
        "the deposit's own differential expression must show a large uG-versus-0.34g "
        "difference, otherwise a perfect split would indicate a leak")
    assert "no sequencing-run" in gravity["batchCaveat"]
    assert gravity["registryChange"] is None
    assert gravity["notPromotedBecause"]


def test_no_model_claims_partial_gravity_or_dose_anywhere_in_the_registry():
    forbidden = ("moon", "mars", "partial gravity", "absorbed dose", "gy")
    for model in research.model_registry()["models"]:
        text = json.dumps(model).lower()
        for phrase in forbidden:
            assert f"predict {phrase}" not in text, (
                f"{model['id']} must not claim to predict {phrase}")


def test_the_registry_says_only_what_the_artifacts_support():
    """The registry/API audit must be clean, and its own output must prove it ran."""
    audit = artifact("phase10_registry_api_audit")
    assert audit["checks"]["models"] == 8
    assert audit["highSeverity"] == 0, audit["findings"]
    assert audit["findings"] == [], (
        "every registry claim must trace to an artifact; a new finding here means a "
        "number was written that nothing backs")
    assert audit["verdict"] == "registry-and-api-agree-with-their-artifacts"
    # The two capability gaps the audit found are fixed rather than silenced:
    # both radiation models now advertise their exact explanation.
    for model_id in ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1"):
        model = next(entry for entry in research.model_registry()["models"]
                     if entry["id"] == model_id)
        assert model["phase10"]["explanationAvailable"] is True
        assert model["phase10"]["explanationIsSurrogate"] is False


def test_the_osd346_replication_is_catalogued_with_its_limit():
    catalogue = {entry["id"]: entry for entry in research.manifest()["datasets"]}
    assert "OSD-346" in catalogue
    entry = catalogue["OSD-346"]
    assert entry["status"] == "analysed-not-served"
    assert entry["rawCommitted"] is False
    assert entry["gravityLevelsG"] == [0.0, 0.1, 0.25, 0.3, 0.38, 0.5, 0.64, 0.65, 1.0]
    # The genotypes are mutants only, and the entry must say so rather than imply
    # wild-type physiology.
    assert any("mutant" in limitation for limitation in entry["limitations"])


def test_the_partial_gravity_result_did_not_replicate_and_says_so():
    """The headline number must carry its failed replication wherever it travels."""
    replication = artifact("phase10_partial_gravity_replication")
    assert replication["replicated"] is False
    assert replication["gradedGravityDetected"] is True
    # A graded signal exists, but only at higher gravity: this is not a rescue.
    assert replication["P2_gradedRegression"]["monotoneInLevelOrder"] is False
    assert replication["P2_gradedRegression"]["correlation"]["pCorrected"] < 0.05
    p1 = replication["P1_binaryReplication"]
    assert p1["collapsedToSingleClass"] is True
    # A collapsed classifier makes the null a point mass; the artifact must not
    # present that p-value as evidence of absence.
    assert p1["permutation"]["degenerate"] is True
    assert "no information" in p1["permutation"]["degenerateMeaning"]
    assert replication["registryChange"] is None


def test_the_osd314_artifact_points_at_its_own_failed_replication():
    gravity = artifact("phase10_partial_gravity")
    assert "does not reproduce this contrast" in gravity["nextAction"]
    assert "one experiment" in gravity["nextAction"]
