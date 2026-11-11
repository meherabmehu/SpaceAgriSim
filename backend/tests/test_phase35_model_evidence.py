"""Phase 35: the evidence verdict that every served model and every prediction carries.

The phase's scientific claim is a single sentence: no served model is presented as validated unless
an independent check was met, and every number says which case it is in. These tests check that the
claim holds at the boundary a user actually meets - the catalogue row and the HTTP response - rather
than only in the artifact.

Nothing here re-fits or re-scores a model. Every number asserted below is read from
`ml/evaluation/phase35_model_evidence.json` or from a card that a script wrote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import research  # noqa: E402

EVIDENCE = ROOT / "ml" / "evaluation" / "phase35_model_evidence.json"
ARTIFACTS = ROOT / "ml" / "artifacts"


def evidence() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def card(model_id: str) -> dict:
    return json.loads((ARTIFACTS / f"{model_id}.json").read_text(encoding="utf-8"))


def test_the_evidence_file_covers_every_registered_model():
    record = evidence()
    assert record["schema"] == "spaceagrisim.model_evidence/1"
    registered = {path.stem for path in ARTIFACTS.glob("*.json")
                  if json.loads(path.read_text(encoding="utf-8")).get("id")}
    assert registered <= set(record["models"]), sorted(registered - set(record["models"]))


def test_every_served_model_carries_a_verdict_with_a_sentence():
    catalogue = research.model_registry()["models"]
    assert len(catalogue) == len(research.MODEL_IDS)
    for row in catalogue:
        verdict = row["evidenceVerdict"]
        assert verdict["verdict"] in {
            "passes-independent-check", "fails-independent-check",
            "no-independent-check", "unrecorded"}, row["id"]
        assert verdict["verdict"] != "unrecorded", (
            f"{row['id']} has no evidence verdict; an absence must never read as a pass")
        assert verdict["summary"].strip(), row["id"]
        if verdict["verdict"] != "passes-independent-check":
            assert verdict["decisionGrade"] is False, row["id"]


def test_the_failed_lettuce_models_say_so_where_a_user_meets_them():
    """v1 and v2 covered none of the six independent treatment means; v3 failed its holdout."""
    expected = {
        "lettuce-earth-growth-v1": "fails-independent-check",
        "lettuce-earth-growth-v2": "fails-independent-check",
        "lettuce-earth-growth-v3": "fails-independent-check",
    }
    catalogue = {row["id"]: row for row in research.model_registry()["models"]}
    for model_id, verdict in expected.items():
        assert catalogue[model_id]["evidenceVerdict"]["verdict"] == verdict, model_id
        assert "0 of 6" in catalogue[model_id]["evidenceVerdict"]["reason"] or \
               "41.5" in catalogue[model_id]["evidenceVerdict"]["reason"], model_id
        scope = catalogue[model_id]["servedScope"]
        assert scope and len(scope) > 40, f"{model_id} must still declare what it serves"


def test_v3_reports_both_its_failure_and_its_coverage():
    """Coverage of six means is not accuracy, and the card must not trade one for the other."""
    verdict = card("lettuce-earth-growth-v3")["evidenceVerdict"]
    checks = {check["check"]: check for check in verdict["checks"]}
    holdout = checks["independent holdout error"]
    assert holdout["passed"] is False
    assert "30" in holdout["criterion"]
    coverage = next(c for name, c in checks.items() if name.startswith("cross-campaign"))
    assert coverage["groups"] == 6
    assert verdict["verdict"] == "fails-independent-check", (
        "a passing coverage count must not outvote a failed pre-registered accuracy criterion")


@pytest.mark.parametrize("model_id", ["radiation-quality-osd46-v1",
                                      "radiation-exposure-osd46-v1",
                                      "tomato-flight-response-v1"])
def test_within_study_models_are_not_called_validated(model_id):
    verdict = card(model_id)["evidenceVerdict"]
    assert verdict["verdict"] == "no-independent-check"
    assert verdict["decisionGrade"] is False
    assert "nowhere else" in verdict["reason"] or "no independent" in verdict["reason"].lower()


def test_the_promoted_model_earned_it_from_its_own_recorded_rule():
    """mizuna v2 is the one model whose status moved, and it moved on measurement."""
    record = card("mizuna-microbial-relative-load-v2")
    assert record["evidenceStatus"] == "validated-exploratory"
    for name, value in record["evidenceBasis"].items():
        if isinstance(value, bool):
            assert value is True, f"promotion term {name} is not satisfied"
    basis = record["evidenceBasis"]
    assert "phase34_cross_campaign_coverage.json" in basis["intervalsEmpiricallyCalibratedEvidence"]
    verdict = record["evidenceVerdict"]
    assert verdict["decisionGrade"] is True
    coverage = next(c for c in verdict["checks"] if c["check"].startswith("cross-campaign"))
    assert coverage["passed"] is True and coverage["groups"] == 123
    # The scope still binds the number to a campaign that supplies its own baseline.
    assert "baseline" in record["servedScope"]


def test_an_unpromoted_model_cannot_claim_a_validated_status():
    for model_id in research.MODEL_IDS:
        record = card(model_id)
        status = str(record.get("evidenceStatus") or "")
        if status.startswith("validated"):
            assert record["evidenceVerdict"]["verdict"] == "passes-independent-check", model_id


def test_every_prediction_route_returns_its_verdict_and_warning(client):
    """The number and its verdict leave the API together, on every prediction route."""
    lettuce = client.post("/api/predict/lettuce-earth-growth-v2", json={
        "daysAfterTransplant": 21, "airTemperature": 23, "rootTemperature": 22, "ppfd": 400})
    assert lettuce.status_code == 200, lettuce.text
    body = lettuce.json()
    assert body["decisionGrade"] is False
    assert body["evidenceVerdict"]["verdict"] == "fails-independent-check"
    assert any(w.startswith("Evidence status:") for w in body["warnings"]), body["warnings"]
    assert body["operationalForecast"] is False

    v3 = client.post("/api/predict/lettuce-earth-growth-v3", json={
        "daysAfterTransplant": 21, "airTemperature": 23, "rootTemperature": 22, "ppfd": 400,
        "photoperiodHours": 16, "plantDensityPerM2": 25})
    assert v3.status_code == 200, v3.text
    assert v3.json()["decisionGrade"] is False
    assert any(w.startswith("Evidence status:") for w in v3.json()["warnings"])

    v1 = client.post("/api/predict/lettuce-earth-growth-v1", json={
        "daysAfterTransplant": 21, "airTemperature": 23, "rootTemperature": 22, "ppfd": 400})
    assert v1.status_code == 200, v1.text
    assert v1.json()["decisionGrade"] is False


def test_no_route_presents_a_failed_model_as_a_forecast(client):
    body = client.post("/api/predict/lettuce-earth-growth-v3", json={
        "daysAfterTransplant": 21, "airTemperature": 23, "rootTemperature": 22, "ppfd": 400,
        "photoperiodHours": 16, "plantDensityPerM2": 25}).json()
    assert body["operationalForecast"] is False
    assert body["harvestForecastClaim"] is None
    joined = " ".join(body["warnings"]).lower()
    assert "forecast" not in joined.replace("forecast claim", "") or "not" in joined
