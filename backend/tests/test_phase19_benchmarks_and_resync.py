"""Phase 19: benchmark panel and OSDR provenance re-sync.

Both surfaces exist to keep measured numbers visible next to modelled ones. The failure mode they
must not have is inventing agreement:

* the benchmark panel must reproduce the pinned artifact exactly, including the gaps;
* the CO2 factor it shows must be the one the engine applies, not a constant typed into a table;
* the re-sync endpoint must never imply a live query, and must report a missing snapshot as
  missing rather than as "all clear".
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import benchmarks, research
from app.config import simulation_constants as constants
from app.main import app
from app.simulation.factors import co2_factor


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def test_benchmarks_endpoint_reports_the_pinned_bpc_numbers(client):
    body = client.get("/api/benchmarks").json()["benchmarks"]
    artifact = json.loads((research.DATA / "derived" / "bpc_benchmark.json").read_text())
    assert body["bpc"]["measured"] == artifact["measured"]
    assert body["bpc"]["ratios"] == artifact["ratios"]
    # the published anchor and the lettuce comparison must survive the round trip unchanged
    assert body["leafyAnchor"]["g_per_m2_day_from_tray"] == pytest.approx(59.5)
    assert body["freshProductivity"]["lettuce"]["fresh_g_per_m2_day"] == pytest.approx(57.1)
    assert body["freshProductivity"]["lettuce"]["ratio_to_nasa_leafy_anchor"] == pytest.approx(0.96)


def test_benchmark_panel_does_not_hide_the_gap(client):
    """The modelled CO2 flux is far below the measured one; that must be visible, not smoothed."""
    body = client.get("/api/benchmarks").json()["benchmarks"]
    ratio = body["bpc"]["ratios"]["lettuce"]["co2_mean"]["model_over_measured"]
    assert ratio < 0.5, "a near-parity number here would mean the artifact was edited"
    assert body["bpc"]["caveats"], "the caveats travel with the numbers"


def test_co2_points_are_evaluated_by_the_model(client):
    points = client.get("/api/benchmarks").json()["benchmarks"]["co2"]["points"]
    by_ppm = {point["ppm"]: point["factor"] for point in points}
    for ppm, factor in by_ppm.items():
        assert factor == pytest.approx(co2_factor(ppm), abs=5e-3)
    assert by_ppm[constants.EARTH_AMBIENT_CO2_PPM] == pytest.approx(1.0, abs=5e-3)
    # still rising above the measured optimum - the documented limitation, not a fitted bend
    assert by_ppm[3000.0] > by_ppm[1000.0]


def test_benchmark_payload_states_what_it_is_not(client):
    body = client.get("/api/benchmarks").json()
    assert body["disclaimer"].lower().startswith("exploratory")
    joined = " ".join(body["reading"]).lower()
    assert "not" in joined
    assert body["benchmarks"]["co2"]["evidenceStatus"].startswith("the curve is a model assumption")


def test_missing_artifact_is_reported_not_faked(monkeypatch, tmp_path):
    monkeypatch.setattr(benchmarks, "BPC_BENCHMARK", tmp_path / "absent.json")
    benchmarks._artifact.cache_clear()
    try:
        body = benchmarks.payload()["benchmarks"]
        assert body["availability"]["available"] is False
        assert body["bpc"] is None
        assert "benchmark_bpc_vs_simulation" in body["availability"]["howToRebuild"]
    finally:
        benchmarks._artifact.cache_clear()


# ---------------------------------------------------------------------------
# Live provenance re-sync
# ---------------------------------------------------------------------------

def test_live_status_endpoint_reports_age_and_scope(client):
    body = client.get("/api/datasets/live-status").json()
    assert body["available"] is True
    assert body["studiesChecked"] >= 1
    assert body["ageDays"] >= 0
    assert "not a live query" in body["scopeNote"]
    # every study carries a verdict rather than a bare "ok"
    for study in body["studies"]:
        assert study["verdict"] in {
            "unchanged", "newer-version-available", "bytes-changed", "missing-files",
            "version-only", "not-checkable"}


def test_live_status_reports_a_newer_published_version(client):
    """OSD-120 was pinned at v14 and the repository now publishes later versions."""
    body = client.get("/api/datasets/live-status").json()
    entries = {study["id"]: study for study in body["studies"]}
    osd120 = entries.get("OSD-120")
    assert osd120 is not None
    assert osd120["pinnedVersion"] == 14
    assert osd120["latestVersion"] > osd120["pinnedVersion"]
    assert osd120["verdict"] == "newer-version-available"


def test_live_status_never_claims_more_than_it_checked(client):
    body = client.get("/api/datasets/live-status").json()
    for study in body["studies"]:
        assert study["filesChecked"] <= study["filesTotal"]
        if study["verdict"] == "not-checkable":
            assert all(not item.get("checked") for item in study["files"])


def test_missing_snapshot_yields_an_honest_answer(monkeypatch, tmp_path):
    monkeypatch.setattr(research, "DATA", tmp_path)
    body = research.osdr_live_status()
    assert body["available"] is False
    assert "No provenance re-sync" in body["reason"]
    assert "scripts/resync_osdr.py" in body["howToRefresh"]


# ---------------------------------------------------------------------------
# External validation status
# ---------------------------------------------------------------------------

def test_external_validation_records_every_candidate_with_a_verdict(client):
    body = client.get("/api/external-validation").json()
    assert body["available"] is True
    conclusion = body["conclusion"]
    # the check has since been run and failed; the record keeps both facts
    assert conclusion["externalValidationAvailable"] is True
    assert conclusion["externalValidationPassed"] is False
    assert "does not mean the model's internal cross-validation was wrong" in conclusion["whatThisDoesNotMean"]
    verdicts = {candidate["id"]: candidate["verdict"] for candidate in body["candidates"]}
    assert verdicts["peerj-17085"] == "used-external-check-failed"
    assert verdicts["touliatos-2016"] == "out-of-domain"


def test_training_source_is_excluded_from_validation(client):
    body = client.get("/api/external-validation").json()
    assert body["trainingSource"]["id"] == "WUR-lettuce"
    assert "cannot also be the external validation" in body["trainingSource"]["reason"]
    assert "WUR-lettuce" not in {candidate["id"] for candidate in body["candidates"]}


def test_no_candidate_invents_a_measurement(client):
    """A candidate that was scored must name the transcription it was scored from."""
    body = client.get("/api/external-validation").json()
    used = [c for c in body["candidates"] if c["verdict"] == "used-external-check-failed"]
    assert used, "the used candidate must still be listed, not quietly removed"
    assert used[0]["transcription"]["observations"] == 6
    assert len(used[0]["transcription"]["sourceSha256"]) == 64
    assert used[0]["blocking"] == ""


def test_out_of_domain_refusal_comes_from_the_served_model(client):
    body = client.get("/api/external-validation").json()
    check = body["domainCheck"]
    assert check["available"] is True
    assert check["flaggedOutOfDistribution"] is True
    assert {item["feature"] for item in check["violations"]} >= {"airTemperature"}

    # the flag shown here must be the same one the prediction route gives a real caller
    response = client.post("/api/predict/lettuce-earth-growth-v2", json=check["point"])
    assert response.status_code == 200
    served = response.json()
    assert served["outOfDistribution"] is True
    assert any("temperature" in w.lower() or "domain" in w.lower() for w in served["warnings"])


# ---------------------------------------------------------------------------
# External check: transcription provenance and the honesty of the verdict
# ---------------------------------------------------------------------------

def test_transcription_matches_the_published_table_verbatim():
    """Six observations, each traceable to a numbered row of the study's Table 1."""
    import json
    from app.research import DATA

    study = json.loads((DATA / "literature" / "external_lettuce_peerj17085.json").read_text())
    assert study["source"]["doi"] == "10.7717/peerj.17085"
    assert study["source"]["license"] == "CC BY 4.0"
    assert len(study["source"]["retrievedSha256"]) == 64
    assert study["source"]["retrievedAt"]
    assert len(study["observations"]) == 6
    # the values are the publication's: fresh yield per plant at 28 DAT, per level and cultivar
    expected = {
        "baby-cos-upper": (697, 84.5), "baby-cos-middle": (391, 123.8),
        "baby-cos-lower": (322, 92.9), "green-oak-upper": (697, 97.3),
        "green-oak-middle": (391, 190.7), "green-oak-lower": (322, 203.7),
    }
    for observation in study["observations"]:
        ppfd, fresh = expected[observation["id"]]
        assert observation["ppfdUmol"] == ppfd
        assert observation["freshWeightGPerPlant"] == fresh
        assert observation["daysAfterTransplant"] == 28
        assert observation["sourceTable"] == "Table 1"
    # the reported study average must not have been used in place of the per-level rows
    averages = {observation["freshWeightGPerPlant"] for observation in study["observations"]}
    assert 100.4 not in averages and 163.9 not in averages


def test_missing_root_temperature_is_declared_not_invented():
    import json
    from app.research import DATA

    study = json.loads((DATA / "literature" / "external_lettuce_peerj17085.json").read_text())
    assumption = study["acceptedAssumptions"][0]
    assert assumption["input"] == "rootTemperature"
    assert "not root-zone or growing-media temperature" in assumption["why"]
    assert assumption["sensitivityChecked"] is True
    assert "rootTemperature" not in study["studyConditions"]


def test_external_check_reports_a_failure_rather_than_a_score(client):
    check = client.get("/api/external-validation").json()["externalCheck"]
    assert check["available"] is True
    metrics = check["metrics"]
    assert metrics["observations"] == 6
    # every observation is overpredicted: the model fails, and the payload says so
    rows = check["rows"]
    assert all(row["ratio"] > 1.0 for row in rows)
    assert metrics["medianRatio"] > 2.0
    assert check["verdict"]["passed"] is False
    assert "overpredicts" in check["verdict"]["headline"]
    assert "must not be used to forecast harvest weight" in check["verdict"]["consequence"]


def test_external_check_predictions_are_computed_not_stored(client):
    """The rows must come from the served artifact, so a retrained model changes them."""
    from app import external_validation

    first = client.get("/api/external-validation").json()["externalCheck"]["rows"]
    external_validation._external.cache_clear()
    second = client.get("/api/external-validation").json()["externalCheck"]["rows"]
    assert first == second
    # a stored result would not move when the model changes; this one must
    from app import research

    original = research.predict_values
    try:
        research.predict_values = lambda model, values: (100.0, [])
        external_validation._predict.cache_clear() if hasattr(external_validation._predict, "cache_clear") else None
        moved = external_validation._external_check()["rows"]
    finally:
        research.predict_values = original
    assert moved[0]["predictedG"] == 100.0
    assert moved != first


def test_root_temperature_assumption_cannot_explain_the_gap(client):
    check = client.get("/api/external-validation").json()["externalCheck"]
    probes = check["rootTemperatureSensitivity"]
    assert {probe["rootTemperatureC"] for probe in probes} >= {20.0, 27.5, 32.0}
    # even at the probe most favourable to the model, it still overpredicts
    assert all(probe["medianRatio"] > 1.0 for probe in probes)
    assert "not explained by the root-temperature assumption" in check["verdict"]["statement"]


def test_structural_findings_name_what_the_model_cannot_represent(client):
    check = client.get("/api/external-validation").json()["externalCheck"]
    findings = " ".join(item["finding"] for item in check["structuralFindings"])
    assert "no cultivar input" in findings
    assert "not monotonic" in findings
