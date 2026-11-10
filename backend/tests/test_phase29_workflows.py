"""Phase 29: the environmental-stress workflow, the irrigation balance, and the model evidence files.

Three groups of tests, each checking something a reader of the platform would otherwise have to
take on trust:

1. **The new workflow is a measured comparison and says so.** It reports measured groups with
   replicate spread, refuses an unknown regime, exposes which environmental factors it can and
   cannot move, computes no composite stress score, and returns the same numbers on every call.
2. **The irrigation schedule is a real water balance.** Stress days respond to the irrigation
   interval, the volumes scale with area, deep percolation never goes negative, and the response
   refuses to convert a transpiration deficit into a yield claim.
3. **The Phase 29 model artefacts are the ones being served.** The diagnosis reproduces the served
   model's metrics, the experiments record which candidate won and that the holdout was not read,
   the final evaluation reports a fail rather than a pass, and the 30 % criterion is still 30 %.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.workflows import units

ROOT = Path(__file__).resolve().parents[2]

LIGHT = "/api/workflows/light-stress"
WATER = "/api/workflows/water-demand"

WATER_SCENARIO = {
    "crop": "lettuce", "growingAreaM2": 10.0, "daysAfterTransplant": 10.0,
    "tmaxC": 30.0, "tminC": 20.0, "relativeHumidityPct": 55.0,
    "solarRadiationMJm2": 20.0, "windSpeedMs": 2.0, "dayOfYear": 180,
    "latitude": 23.8, "elevationM": 8.0, "plantsPerM2": 25.0,
}
IRRIGATED = {**WATER_SCENARIO, "totalAvailableWaterMm": 40.0, "initialDepletionMm": 10.0,
             "irrigationAmountMm": 6.0, "irrigationIntervalDays": 2}


# ------------------------------------------------------------------ W3: light-stress


def test_light_stress_is_advertised_as_measured_not_simulated(client):
    catalogue = client.get("/api/workflows").json()
    entry = next(item for item in catalogue["workflows"] if item["id"] == "light-stress")
    assert entry["status"] == "complete"
    assert entry["evidenceClass"] == "measured-observation"
    assert entry["isSimulation"] is False
    assert entry["measuredEvidence"] is True


def test_light_stress_capability_states_the_fixed_conditions(client):
    body = client.get(LIGHT + "/capability").json()
    assert body["crop"]["cultivar"] == "Red Batavia"
    assert len(body["regimes"]) == 4
    assert body["fixedConditions"]["ppfdUmolPerM2S"] == 200.0
    assert body["fixedConditions"]["photoperiodHours"] == 16.0
    assert "no PPFD or photoperiod response" in body["fixedConditions"]["note"]
    # Exactly one supported factor, and it is the one the experiment varied.
    assert body["supportedFactors"] == ["greenLightFractionPct"]
    unsupported = {factor["factor"] for factor in body["unsupportedFactors"]}
    assert {"ppfdUmolPerM2S", "co2Ppm", "airTemperatureC", "photoperiodHours"} <= unsupported


def test_light_stress_run_reports_measured_groups_with_replicate_spread(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "control", "traits": ["freshWeightG"], "daysAfterSowing": 35},
        {"regime": "t2", "traits": ["freshWeightG"], "daysAfterSowing": 35},
    ]}).json()
    assert body["status"] == "complete"
    assert body["evidenceClass"] == "measured-observation"
    assert body["isSimulation"] is False

    control, treatment = body["scenarios"]
    assert control["isMeasurement"] is True
    assert control["isModelPrediction"] is False
    trait = control["traits"][0]
    assert trait["n"] >= 40                      # replicate count is reported, not implied
    assert trait["standardDeviation"] is not None
    assert trait["meanCiLow"] < trait["mean"] < trait["meanCiHigh"]
    assert "bootstrap" in trait["ciKind"]

    # The treatment carries its own comparison against the control.
    versus = treatment["traits"][0]["versusControl"]
    assert versus["applies"] is True
    assert versus["withinExperimentOnly"] is True
    assert versus["nControl"] >= 40 and versus["nTreatment"] >= 40
    assert versus["welch"]["pValue"] is not None


def test_light_stress_control_has_no_self_comparison(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "control", "traits": ["freshWeightG"]}]}).json()
    versus = body["scenarios"][0]["traits"][0]["versusControl"]
    assert versus["applies"] is False


def test_light_stress_reports_stress_indicators_separately_and_computes_no_composite(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "t1", "traits": ["fvPOverFmP", "phiNO", "npqT"], "daysAfterSowing": 35}]}).json()
    traits = {item["trait"] for item in body["scenarios"][0]["traits"]}
    assert traits == {"fvPOverFmP", "phiNO", "npqT"}
    assert body["method"]["compositeScore"] == "none computed, deliberately"
    assert body["method"]["pseudoReplication"].startswith("replicate plants share a chamber")


def test_light_stress_measurement_day_changes_the_numbers(client):
    day28 = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "t2", "traits": ["phiNO"], "daysAfterSowing": 28}]}).json()
    day35 = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "t2", "traits": ["phiNO"], "daysAfterSowing": 35}]}).json()
    a = day28["scenarios"][0]["traits"][0]
    b = day35["scenarios"][0]["traits"][0]
    assert a["daysAfterSowing"] == 28 and b["daysAfterSowing"] == 35
    assert a["mean"] != b["mean"]


def test_light_stress_comparison_states_whether_intervals_are_separated(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "control", "traits": ["phiNO"], "daysAfterSowing": 35},
        {"regime": "t2", "traits": ["phiNO"], "daysAfterSowing": 35},
    ]}).json()
    delta = body["comparison"]["deltas"][0]
    assert delta["trait"] == "phiNO"
    assert delta["unit"] == "fraction"
    assert isinstance(delta["meansAreSeparated"], bool)
    assert "one experiment" in delta["note"]


def test_light_stress_names_the_confounded_regime(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [{"regime": "t3",
                                                            "traits": ["freshWeightG"]}]}).json()
    design = body["scenarios"][0]["design"]
    assert design["confoundsSpectrumWithDensity"] is True
    assert design["relativePlantingDensity"] == 1.25
    assert any("t3 changes two things at once" in line for line in body["limitations"])


def test_light_stress_refuses_an_unknown_regime_and_an_unknown_trait(client):
    assert client.post(LIGHT + "/run", json={"scenarios": [{"regime": "t9"}]}).status_code == 422
    # An unknown trait is dropped rather than invented, and the response stays well-formed.
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "t1", "traits": ["notATrait"]}]}).json()
    assert body["scenarios"][0]["traits"] == []


def test_light_stress_is_deterministic(client):
    request = {"scenarios": [{"regime": "t2", "traits": ["freshWeightG"], "daysAfterSowing": 35}]}
    first = client.post(LIGHT + "/run", json=request).json()
    second = client.post(LIGHT + "/run", json=request).json()
    assert first["scenarios"][0]["traits"] == second["scenarios"][0]["traits"]


def test_light_stress_carries_verified_provenance(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [{"regime": "control"}]}).json()
    provenance = body["provenance"]
    assert provenance["source"]["doi"] == "10.5281/zenodo.20394352"
    assert provenance["source"]["license"] == "CC BY 4.0"
    assert provenance["verifiedAgainstManifest"] is True
    assert len(provenance["rawFileSha256"]) == 64
    assert provenance["recordCounts"]["harvestRows"] > 1000


def test_light_stress_units_are_registered(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "t1", "traits": ["freshWeightG", "fvPOverFmP", "spad"]}]}).json()
    for field, meta in body["units"].items():
        assert meta["registered"] is True, f"{field} carries an unregistered unit"


def test_light_stress_never_claims_a_co2_or_ppfd_response(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [{"regime": "control"}]}).json()
    assert "co2Ppm" in body["unsupportedFactors"]
    assert "ppfdUmolPerM2S" in body["unsupportedFactors"]
    for factor in body["factors"]:
        if not factor["supported"]:
            assert factor["limitation"]


# ------------------------------------------------------- W1: irrigation scheduling


def test_irrigation_schedule_is_absent_without_a_storage_term(client):
    body = client.post(WATER + "/run", json={"scenarios": [WATER_SCENARIO]}).json()
    schedule = body["scenarios"][0]["irrigationSchedule"]
    assert schedule["available"] is False
    assert "totalAvailableWaterMm" in schedule["reason"]
    # The workflow is still complete without it.
    assert body["status"] == "complete"


def test_irrigation_schedule_runs_a_water_balance(client):
    body = client.post(WATER + "/run", json={"scenarios": [IRRIGATED]}).json()
    schedule = body["scenarios"][0]["irrigationSchedule"]
    assert schedule["available"] is True
    assert schedule["isReferenceCalculation"] is True
    assert schedule["isMeasurement"] is False
    totals = schedule["totals"]
    assert totals["daysSimulated"] > 0
    assert totals["cropEtcMm"] > 0
    assert totals["actualEtaMm"] <= totals["cropEtcMm"] + 1e-6
    assert 0 <= totals["relativeTranspirationDeficit"] <= 1
    assert totals["deepPercolationMm"] >= 0
    assert schedule["daily"][0]["depletionEndMm"] >= 0


def test_irrigation_interval_changes_the_stress_burden(client):
    daily = {**IRRIGATED, "irrigationIntervalDays": 1}
    sparse = {**IRRIGATED, "irrigationIntervalDays": 6}
    body = client.post(WATER + "/run", json={"scenarios": [daily, sparse]}).json()
    a = body["scenarios"][0]["irrigationSchedule"]["totals"]
    b = body["scenarios"][1]["irrigationSchedule"]["totals"]
    assert b["stressDays"] >= a["stressDays"]
    assert b["relativeTranspirationDeficit"] >= a["relativeTranspirationDeficit"]


def test_no_irrigation_reports_the_deficit_rather_than_a_failure(client):
    unirrigated = {**IRRIGATED, "irrigationAmountMm": 0.0}
    body = client.post(WATER + "/run", json={"scenarios": [unirrigated]}).json()
    totals = body["scenarios"][0]["irrigationSchedule"]["totals"]
    assert totals["irrigationMm"] == 0
    assert totals["stressDays"] > 0
    assert totals["relativeTranspirationDeficit"] > 0


def test_irrigation_volume_scales_with_area(client):
    small = {**IRRIGATED, "growingAreaM2": 5.0}
    large = {**IRRIGATED, "growingAreaM2": 20.0}
    body = client.post(WATER + "/run", json={"scenarios": [small, large]}).json()
    a = body["scenarios"][0]["irrigationSchedule"]["totals"]
    b = body["scenarios"][1]["irrigationSchedule"]["totals"]
    assert b["irrigationMm"] == pytest.approx(a["irrigationMm"], rel=1e-6)
    assert b["irrigationLitres"] == pytest.approx(4 * a["irrigationLitres"], rel=1e-6)


def test_irrigation_schedule_refuses_a_yield_claim(client):
    body = client.post(WATER + "/run", json={"scenarios": [IRRIGATED]}).json()
    stress = body["scenarios"][0]["irrigationSchedule"]["stress"]
    assert stress["isYieldClaim"] is False
    assert "yield-response factor" in stress["whyNoYieldClaim"]


def test_irrigation_schedule_rejects_impossible_soil_inputs(client):
    impossible = {**IRRIGATED, "initialDepletionMm": 90.0}   # deeper than the root zone holds
    assert client.post(WATER + "/run", json={"scenarios": [impossible]}).status_code == 422
    assert client.post(WATER + "/run", json={"scenarios": [
        {**IRRIGATED, "totalAvailableWaterMm": 0}]}).status_code == 422
    assert client.post(WATER + "/run", json={"scenarios": [
        {**IRRIGATED, "irrigationIntervalDays": 0}]}).status_code == 422


# ------------------------------------------------------- Phase 29 model evidence


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text())


def test_diagnosis_reproduces_the_served_model():
    diagnosis = _load("ml/evaluation/phase29_harvest_diagnosis.json")
    artifact = _load("ml/artifacts/lettuce-earth-growth-v3.json")
    assert diagnosis["reproduction"]["matchesArtifactMAE"] is True
    assert diagnosis["reproduction"]["outOfFoldMAEgPerM2"] == pytest.approx(
        round(artifact["metrics"]["MAE"], 1), abs=0.1)


def test_diagnosis_records_the_domain_mismatch_it_found():
    audit = _load("ml/evaluation/phase29_harvest_diagnosis.json")["declaredDomainAudit"]
    assert audit["dailyLightIntegral"]["declaredMatchesObserved"] is False
    assert audit["dailyLightIntegral"]["observed"][1] > audit["dailyLightIntegral"]["declared"][1]
    assert "hardcoded" in audit["finding"]
    # The other three features do match, so the finding is specific rather than a blanket claim.
    for feature in ("daysAfterTransplant", "airTemperature", "rootTemperature"):
        assert audit[feature]["declaredMatchesObserved"] is True


def test_holdout_was_not_read_during_model_selection():
    experiments = _load("ml/evaluation/phase29_harvest_experiments.json")
    assert experiments["holdoutReadHere"] is False
    assert experiments["selectionRule"]["writtenBeforeScoring"] is True
    assert experiments["selected"] in experiments["candidates"]
    # The selection rule's criterion is the cross-validation MAE, not any external score.
    assert "leave-one-experiment-out" in experiments["selectionRule"]["primary"]


def test_final_evaluation_reports_a_failure_with_the_criterion_unchanged():
    final = _load("ml/evaluation/phase29_harvest_final.json")
    assert final["holdout"]["acceptanceCriterionPct"] == 30.0
    assert final["holdout"]["passed"] is False
    assert final["holdout"]["MAPE"] > 30.0
    assert final["outcome"] == "B-fail"
    assert final["promotion"]["promoted"] is False
    assert final["notChanged"] == ["the 30 % acceptance criterion", "the holdout observations",
                                   "the evaluation metric"]


def test_final_evaluation_disclaims_a_pristine_holdout():
    provenance = _load("ml/evaluation/phase29_harvest_final.json")["holdoutProvenance"]
    assert provenance["usedInFitting"] is False
    assert provenance["usedInModelSelection"] is False
    assert "NOT an untouched final test set" in provenance["pristineClaim"]


def test_interval_audit_exposes_non_uniform_coverage():
    audit = _load("ml/evaluation/phase29_interval_audit.json")
    coverages = [entry["coverage"] for entry in audit["coverageByExperiment"].values()]
    # The pooled number hides at least one group well below nominal coverage.
    assert min(coverages) < 0.8
    assert max(coverages) - min(coverages) > 0.2
    assert audit["conclusion"]["canClaimIndependentCoverage"] is False
    assert audit["conclusion"]["outOfFoldCoverageIsDescriptive"] is True


def test_served_model_was_not_silently_replaced():
    artifact = _load("ml/artifacts/lettuce-earth-growth-v3.json")
    assert artifact["status"] == "trained-exploratory"
    assert artifact["validation"]["independent"]["passed"] is False
    assert not (ROOT / "ml" / "artifacts" / "lettuce-earth-growth-v4.json").exists()


def test_water_and_harvest_contracts_survive_phase29(client):
    """Both Phase 28 workflows must still answer with the same envelope."""
    harvest = client.post("/api/workflows/harvest-prediction/run", json={"scenarios": [
        {"daysAfterTransplant": 21, "airTemperature": 24, "rootTemperature": 24, "ppfd": 400,
         "photoperiodHours": 16, "plantDensityPerM2": 25}]}).json()
    assert harvest["workflowComplete"] is True
    assert harvest["modelValidatedForForecasting"] is False
    assert harvest["scenarios"][0]["recordPrediction"]["modelId"] == "lettuce-earth-growth-v2"

    water = client.post(WATER + "/run", json={"scenarios": [WATER_SCENARIO]}).json()
    assert water["status"] == "complete"
    assert water["scenarios"][0]["demand"]["agreement"]["arbitrated"] is False
    assert water["scenarios"][0]["measuredBench"]["hashVerified"] is True
    for field, meta in water["units"].items():
        assert meta["registered"] is True
        assert meta["dimension"] in units.DIMENSIONS


def test_light_stress_withholds_a_meaningless_percentage(client):
    """NPQt's control mean sits near zero, so a percentage change against it is arithmetic.

    The absolute difference and the effect size still carry the comparison; the percentage is
    withheld and the response says why.
    """
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "control", "traits": ["npqT"], "daysAfterSowing": 35},
        {"regime": "t2", "traits": ["npqT"], "daysAfterSowing": 35},
    ]}).json()
    treatment = next(s for s in body["scenarios"] if s["regime"] == "t2")
    versus = treatment["traits"][0]["versusControl"]
    assert versus["relativeDifferenceMeaningful"] is False
    assert versus["relativeDifference"] is None
    assert "arithmetic rather than a finding" in versus["relativeDifferenceNote"]
    assert versus["difference"] > 1.0          # the real signal survives
    assert versus["hedgesG"] > 1.0
    delta = body["comparison"]["deltas"][0]
    assert delta["relativeDifferenceMeaningful"] is False
    assert delta["relativeDifference"] is None


def test_light_stress_keeps_percentages_where_they_are_meaningful(client):
    body = client.post(LIGHT + "/run", json={"scenarios": [
        {"regime": "control", "traits": ["freshWeightG"], "daysAfterSowing": 35},
        {"regime": "t2", "traits": ["freshWeightG"], "daysAfterSowing": 35},
    ]}).json()
    delta = body["comparison"]["deltas"][0]
    assert delta["relativeDifferenceMeaningful"] is True
    assert delta["relativeDifference"] == pytest.approx(0.1771, abs=1e-4)
