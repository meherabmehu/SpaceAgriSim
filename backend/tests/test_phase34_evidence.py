"""Phase 34: the measured cross-campaign and probability evidence, and what it is allowed to say.

Two files were produced this phase:

    ml/evaluation/phase34_probability_calibration.json    (tomato classifier, out of fold)
    ml/evaluation/phase34_cross_campaign_coverage.json    (5 intervals, independent campaigns)

Every test here reads one of those files and the artifact that serves it. None of them re-fits
anything, and none of them relaxes an earlier assertion: the point of the phase is that a
measurement exists and that the served text does not outrun it. The failures are kept as failures -
lettuce v2 covers 0 of 6 independent treatment means, and v3 covering 6 of 6 does not turn its
failed independent holdout into a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import research  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
CALIBRATION = ROOT / "ml" / "evaluation" / "phase34_probability_calibration.json"
COVERAGE = ROOT / "ml" / "evaluation" / "phase34_cross_campaign_coverage.json"


def card(model_id: str) -> dict:
    return json.loads((ARTIFACTS / f"{model_id}.json").read_text(encoding="utf-8"))


def coverage_record() -> dict:
    return json.loads(COVERAGE.read_text(encoding="utf-8"))


def calibration_record() -> dict:
    return json.loads(CALIBRATION.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the evidence files themselves
def test_the_evidence_files_exist_and_declare_their_schema():
    for path, schema in ((CALIBRATION, "spaceagrisim.probability_calibration/1"),
                         (COVERAGE, "spaceagrisim.cross_campaign_coverage/1")):
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["schema"] == schema, path.name
        assert record["models"], path.name


def test_cross_campaign_coverage_covers_every_model_that_claims_a_measured_interval():
    """A model that reports a measured coverage must have the cross-campaign number too.

    Leaving one out is how a scope gap survives a phase that claims to have measured it.
    """
    measured = coverage_record()["models"]
    for model_id, row in measured.items():
        assert row["withinCampaignCoverage"] is not None, model_id
        campaign = row["crossCampaign"]
        assert campaign["observations"] > 0, model_id
        assert 0 <= campaign["covered"] <= campaign["observations"], model_id
        assert row["statement"].strip(), model_id
    assert "lettuce-earth-growth-v2" in measured and "lettuce-earth-growth-v3" in measured


def test_the_coverage_numbers_are_the_measured_ones():
    """Pinned to the measurement so a later edit cannot quietly change what a card claims."""
    measured = coverage_record()["models"]
    v2 = measured["lettuce-earth-growth-v2"]["crossCampaign"]
    v3 = measured["lettuce-earth-growth-v3"]["crossCampaign"]
    assert (v2["covered"], v2["observations"]) == (0, 6)
    assert 3.0 < v2["ratioMedian"] < 3.5
    assert (v3["covered"], v3["observations"]) == (6, 6)
    mizuna = measured["mizuna-microbial-relative-load-v2"]["crossCampaign"]
    assert mizuna["observations"] == 123
    assert 0.85 <= mizuna["pooledAchievedCoverage"] <= 0.95


# ---------------------------------------------------------------- the served cards
@pytest.mark.parametrize("model_id", ["lettuce-earth-growth-v1", "lettuce-earth-growth-v2",
                                      "lettuce-earth-growth-v3"])
def test_lettuce_cards_carry_their_cross_campaign_measurement(model_id):
    artifact = card(model_id)
    block = (artifact.get("interval") or {}).get("crossCampaign")
    assert block, f"{model_id} has no cross-campaign interval measurement"
    measured = coverage_record()["models"][model_id]["crossCampaign"]
    assert block["covered"] == measured["covered"]
    assert block["observations"] == measured["observations"]
    assert "PeerJ" in block["campaign"] and "CC BY 4.0" in block["campaign"], \
        "the measurement must name the study and its licence, not just a number"
    assert block["evidence"] == "ml/evaluation/phase34_cross_campaign_coverage.json"
    assert "Cross-campaign coverage was measured" in artifact["servedScope"]


@pytest.mark.parametrize("model_id", ["mizuna-microbial-load-v1",
                                      "mizuna-microbial-relative-load-v2"])
def test_mizuna_cards_no_longer_claim_that_no_second_campaign_exists(model_id):
    artifact = card(model_id)
    scope = artifact["servedScope"]
    # The Phase 32 wording said coverage was "within the VEG-04A campaigns only" and that "there is
    # no second campaign in the repository". OSD-780 contains VEG-04A and VEG-04B and the transfer
    # study already held each one out, so both sentences were false.
    assert "no second campaign" not in scope, model_id
    assert "VEG-04A campaigns only" not in scope, model_id
    assert "VEG-04A" in scope and "VEG-04B" in scope, model_id
    block = artifact["interval"]["crossCampaign"]
    assert block["campaigns"] == ["VEG04A", "VEG04B"]
    assert len(block["directions"]) == 2, "both calibration directions must be recorded"
    for label, direction in block["directions"].items():
        calibrated_on, evaluated_on = label.split("/")
        assert calibrated_on.replace("calibratedOn", "") != evaluated_on.replace("evaluatedOn", ""), \
            "calibration and evaluation must not share a campaign"
        assert direction["observations"] > 0
    assert 0.85 <= block["pooledAchievedCoverage"] <= 0.95
    assert block["covered"] < block["observations"], (
        "a 90 % interval on a campaign offset should not cover everything; if it did, the "
        "measurement is worth re-reading before the card says so")


def test_the_tomato_card_reports_a_measurement_without_claiming_a_calibration():
    artifact = card("tomato-flight-response-v1")
    block = artifact["probabilityCalibration"]
    assert block["measured"] is True
    assert block["calibrated"] is False, "no scaling was fitted, so nothing may be claimed"
    assert block["servedScaling"] == "none"
    record = calibration_record()["models"]["tomato-flight-response-v1"]
    assert block["metrics"]["logLoss"] == record["probability"]["logLoss"]
    assert block["metrics"]["brier"] == record["probability"]["brier"]
    assert block["metrics"]["ece"] == record["probability"]["ece"]
    assert block["metrics"]["groups"] == record["groups"] == 21
    assert block["evidence"] == "ml/evaluation/phase34_probability_calibration.json"
    # The prediction is measured out of fold over plants, not over rows.
    assert record["groups"] < record["samples"]
    served = next(model for model in research.model_registry()["models"]
                  if model["id"] == "tomato-flight-response-v1")
    assert (served.get("calibration") or {}).get("calibrated") is not True


def test_no_served_number_outruns_its_evidence_file():
    """Any served claim of measured calibration must point at a file that exists."""
    for model_id in research.MODEL_IDS:
        artifact = card(model_id)
        declared = artifact.get("probabilityCalibration") or {}
        if declared.get("measured"):
            # Phase 32 recorded the OSD-46 calibrations under `scope`+`statement` without a
            # numeric block, so the requirement is the cited evidence file and a statement, not a
            # shape only the newer cards use.
            assert (ROOT / declared["evidence"]).is_file(), model_id
            assert declared.get("statement"), model_id
        block = (artifact.get("interval") or {}).get("crossCampaign")
        if block:
            assert (ROOT / block["evidence"]).is_file(), model_id


# ---------------------------------------------------------------- API surface
def test_the_served_scope_reaches_the_api_and_states_the_campaign(client):
    body = client.post("/api/predict/lettuce-earth-growth-v2", json={
        "daysAfterTransplant": 21, "airTemperature": 23, "rootTemperature": 22, "ppfd": 400,
    })
    assert body.status_code == 200, body.text
    scope = body.json()["scopeStatement"]
    assert "Cross-campaign coverage was measured" in scope
    assert "0 of 6" in scope or "6 of 6" in scope
    # The prediction itself is still an estimate with an interval, never a measurement.
    payload = body.json()
    assert payload["interval"]["low"] <= payload["prediction"] <= payload["interval"]["high"]
    assert payload["operationalForecast"] is False


def test_the_retired_mizuna_load_model_stays_unreachable():
    """Recording a measurement against a withdrawn artifact must not reinstate it."""
    assert "mizuna-microbial-load-v1" not in research.MODEL_IDS
    with pytest.raises(KeyError):
        research.load_model("mizuna-microbial-load-v1")
