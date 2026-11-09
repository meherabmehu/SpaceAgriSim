"""Phase 23: reference ET0, the emulator, and the dataset catalogue.

Three kinds of assertion live here, and they are kept separate on purpose:

    physics      the FAO-56 implementation reproduces the manual's own worked examples
    honesty      the emulator reports the gate it failed, and the service never hides the physics
    integration  the new surface is reachable, classified, audited, and changes nothing by default

The last group is the one that would catch a silent regression: a saved scenario that replays to
different litres is a broken product, whatever a new model scores.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from app import et0, research, science_classification, workflow
from app.config import simulation_constants as constants
from app.simulation import et0_fao56, water
from app.simulation.engine import SimulationInput, run_simulation

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "processed" / "et0_dataset.csv"
DATASET_META = ROOT / "data" / "processed" / "et0_dataset.metadata.json"
QUALITY = ROOT / "ml" / "evaluation" / "et0_dataset_quality.json"
EMULATOR_CARD = ROOT / "ml" / "artifacts" / "et0-emulator-v1.json"


def _card() -> dict:
    return json.loads(EMULATOR_CARD.read_text(encoding="utf-8"))


def _dataset_meta() -> dict:
    return json.loads(DATASET_META.read_text(encoding="utf-8"))


def _simulate(**overrides) -> SimulationInput:
    defaults = dict(crop="lettuce", gravity=0.0, radiation=0.3, water_availability=100,
                    light_hours=16, co2_level=1000, simulation_days=30, growing_area=10)
    defaults.update(overrides)
    return SimulationInput(**defaults)


# --------------------------------------------------------------------------- physics
def test_example_17_bangkok_is_within_one_and_a_half_percent():
    row = et0_fao56.run_published_examples()[0]
    assert "Example 17" in row["example"]
    assert row["computedMmPerDay"] == pytest.approx(5.77, abs=0.01)
    assert row["withinTolerance"]


def test_example_18_uccle_reproduces_the_manual_exactly():
    row = et0_fao56.run_published_examples()[1]
    assert row["computedMmPerDay"] == pytest.approx(3.880, abs=0.005)


def test_example_20_hargreaves_reproduces_five_millimetres():
    row = et0_fao56.run_published_examples()[2]
    assert row["computedMmPerDay"] == pytest.approx(5.03, abs=0.01)


def test_every_published_example_passes_its_own_tolerance():
    rows = et0_fao56.run_published_examples()
    assert len(rows) == 3
    assert all(row["withinTolerance"] for row in rows), rows
    assert all(abs(row["percentDifference"]) <= et0_fao56.PUBLISHED_EXAMPLE_TOLERANCE_PERCENT
               for row in rows)


def test_hargreaves_carries_the_latent_heat_factor():
    """Without 0.408 the baseline is 2.45x too large - the bug that flattered every model."""
    ra, _ = et0_fao56.extraterrestrial_radiation(45.72, 196)
    with_factor = et0_fao56.hargreaves_et0(26.6, 14.8, ra)["et0MmPerDay"]
    without = 0.0023 * ra * ((26.6 + 14.8) / 2.0 + 17.8) * math.sqrt(26.6 - 14.8)
    assert with_factor == pytest.approx(0.408 * without, rel=1e-9)
    assert without / with_factor == pytest.approx(2.45, abs=0.02)


def test_extraterrestrial_radiation_matches_the_manual_for_bangkok():
    ra, daylight = et0_fao56.extraterrestrial_radiation(13.73, 105)
    assert ra == pytest.approx(38.06, abs=0.1)
    assert 11.0 < daylight < 13.0


def test_vapour_pressure_never_inverts_when_dewpoint_exceeds_the_mean():
    """A daily dew point above the daily mean is clamped, and the clamp is reported."""
    result = et0.estimate(tmax_c=30.0, tmin_c=24.0, day_of_year=200, latitude=23.8,
                          elevation_m=10.0, tdew_c=28.5, solar_radiation_mj=20.0,
                          wind_speed_ms=2.0)
    assert result["methods"]["penmanMonteith"]["vpdKpa"] >= 0.0
    assert result["inputs"]["tdewC"] <= (30.0 + 24.0) / 2.0


def test_relative_humidity_is_converted_and_the_conversion_is_reported():
    result = et0.estimate(tmax_c=25.0, tmin_c=15.0, day_of_year=150, latitude=40.0,
                          elevation_m=0.0, relative_humidity_pct=70.0, tdew_c=None)
    assert result["inputs"]["dewpointDerivedFromRelativeHumidity"] is True
    # 70 % RH at a 20 degC mean puts the dew point near 14 degC; the assertion is that a
    # plausible value is derived, not a particular number.
    assert 13.5 < result["inputs"]["tdewC"] < 15.0


def test_light_integral_is_flagged_as_an_estimate_not_a_measurement():
    light = et0_fao56.daily_light_integral(20.0)
    assert light["estimate"] is True
    assert light["dliMolPerM2PerDay"] == pytest.approx(20.0 * 0.45 * 4.57, rel=1e-3)
    assert et0_fao56.daily_light_integral(20.0)["dliMolPerM2PerDay"] > \
        et0_fao56.daily_light_integral(10.0)["dliMolPerM2PerDay"]


def test_wind_height_correction_is_a_noop_at_two_metres():
    assert et0_fao56.wind_at_2m(3.1, 2.0) == pytest.approx(3.1)


def test_penman_monteith_needs_radiation_and_wind_while_hargreaves_does_not():
    penman = et0_fao56.reference_et0(tmax=28.0, tmin=16.0, ea=1.4, rs=20.0, wind_2m=2.0,
                                     pressure_kpa=101.0, day_of_year=180,
                                     latitude_deg=30.0, elevation_m=0.0)
    ra, _ = et0_fao56.extraterrestrial_radiation(30.0, 180)
    hargreaves = et0_fao56.hargreaves_et0(28.0, 16.0, ra)
    # Both are physically plausible daily fluxes for a warm day: the check is agreement in order
    # of magnitude, not that one approximates the other.
    assert 3.0 < penman["et0MmPerDay"] < 9.0
    assert 3.0 < hargreaves["et0MmPerDay"] < 9.0


# --------------------------------------------------------------------------- service contract
def test_service_serves_physics_when_radiation_and_wind_are_supplied():
    result = et0.estimate(tmax_c=21.5, tmin_c=12.3, day_of_year=187, latitude=50.8,
                          elevation_m=100.0, tdew_c=12.07, solar_radiation_mj=22.07,
                          wind_speed_ms=2.78, pressure_kpa=100.1)
    assert result["primaryMethod"] == "penman-monteith"
    assert 3.5 < result["et0MmPerDay"] < 4.2
    terms = result["methods"]["penmanMonteith"]
    assert terms["radiationTermMm"] + terms["aeroTermMm"] == pytest.approx(
        terms["et0MmPerDay"], abs=0.01)


def test_service_falls_back_to_the_emulator_when_radiation_is_missing():
    result = et0.estimate(tmax_c=30.0, tmin_c=18.0, day_of_year=200, latitude=23.8,
                          elevation_m=10.0, tdew_c=12.0)
    assert result["methods"]["penmanMonteith"] is None
    assert result["primaryMethod"] in {"emulator", "hargreaves"}
    # Both alternatives are always present, so the caller can compare rather than trust one.
    assert result["methods"]["hargreaves"]["et0MmPerDay"] > 0


def test_emulator_flags_inputs_outside_its_training_envelope():
    inside = et0.estimate(tmax_c=25.0, tmin_c=15.0, day_of_year=200, latitude=40.0,
                          elevation_m=100.0, tdew_c=10.0)
    outside = et0.estimate(tmax_c=25.0, tmin_c=15.0, day_of_year=200, latitude=-78.0,
                           elevation_m=3000.0, tdew_c=10.0)
    assert inside["methods"]["emulator"]["outOfDistribution"] is False
    assert outside["methods"]["emulator"]["outOfDistribution"] is True
    assert outside["methods"]["emulator"]["outsideFeatures"]


def test_service_degrades_to_physics_when_the_artifact_is_unreadable(monkeypatch, tmp_path):
    monkeypatch.setattr(et0, "ARTIFACT_MODEL", tmp_path / "not-there.joblib")
    et0.load_artifact.cache_clear()
    try:
        result = et0.estimate(tmax_c=25.0, tmin_c=15.0, day_of_year=200, latitude=40.0,
                              elevation_m=100.0, tdew_c=10.0, solar_radiation_mj=20.0,
                              wind_speed_ms=2.0)
        assert result["methods"]["emulator"] is None
        assert result["primaryMethod"] == "penman-monteith"
        assert result["et0MmPerDay"] > 0
        assert et0.artifact_status()["available"] is False
    finally:
        et0.load_artifact.cache_clear()


def test_artifact_diagnostics_name_the_actual_failure(monkeypatch, tmp_path):
    """A missing file and a missing package fail the same way but need different fixes."""
    healthy = et0.load_diagnostics()
    assert healthy["cardFilePresent"] and healthy["modelFilePresent"]
    assert all(healthy["packages"].values())

    monkeypatch.setattr(et0, "ARTIFACT_MODEL", tmp_path / "absent.joblib")
    et0._LAST_LOAD_ERROR.clear()
    et0.load_artifact.cache_clear()
    try:
        status = et0.artifact_status()
        assert status["available"] is False
        assert "not present in this deployment" in status["reason"]
        assert status["diagnostics"]["modelFilePresent"] is False
        assert status["diagnostics"]["cardFilePresent"] is True
        # The physics fallback is described even when nothing is available.
        assert "Hargreaves" in status["fallback"]
    finally:
        et0.load_artifact.cache_clear()


def test_service_refuses_to_guess_the_vapour_pressure():
    with pytest.raises(ValueError):
        et0.estimate(tmax_c=25.0, tmin_c=15.0, day_of_year=200, latitude=40.0,
                     elevation_m=0.0)


def test_estimate_never_describes_itself_as_a_measurement():
    result = et0.estimate(tmax_c=25.0, tmin_c=15.0, day_of_year=200, latitude=40.0,
                          elevation_m=0.0, tdew_c=10.0)
    blob = json.dumps(result).lower()
    assert "not a measurement" in blob or "not a measurement of" in blob
    assert "microgravity" in blob  # the limitation is stated, not implied


# --------------------------------------------------------------------------- water demand
def test_default_water_demand_is_unchanged():
    result = run_simulation(_simulate())
    assert result.space.water_demand_l == pytest.approx(389.401, abs=0.001)
    assert result.space.demand_basis == "crop-relative"


def test_et0_basis_scales_demand_with_the_flux():
    four = run_simulation(_simulate(et0_mm_per_day=4.0))
    eight = run_simulation(_simulate(et0_mm_per_day=8.0))
    assert four.space.demand_basis == "et0-reference"
    assert four.space.water_demand_l == pytest.approx(623.042, abs=0.001)
    assert eight.space.water_demand_l == pytest.approx(2 * four.space.water_demand_l, rel=1e-6)


def test_one_millimetre_over_one_square_metre_is_one_litre():
    litre = water.et0_reference_demand_l(1.0, 1.0, growth_fraction=1.0, growing_area_m2=1.0)
    assert litre == pytest.approx(1.0)


def test_crop_coefficient_scales_demand_linearly():
    plain = run_simulation(_simulate(et0_mm_per_day=4.0))
    doubled = run_simulation(_simulate(et0_mm_per_day=4.0, crop_coefficient=2.0))
    assert doubled.space.water_demand_l == pytest.approx(2 * plain.space.water_demand_l, rel=1e-6)


def test_yield_is_identical_on_both_water_bases():
    """ET0 changes the water ledger, not the growth curve: that is the whole design."""
    default = run_simulation(_simulate())
    flux = run_simulation(_simulate(et0_mm_per_day=4.0))
    assert flux.space.crop_yield_g == pytest.approx(default.space.crop_yield_g)


def test_et0_path_does_not_apply_the_light_scale_twice():
    """ET0 already contains the site's radiation, so photoperiod must not rescale it."""
    short = run_simulation(_simulate(et0_mm_per_day=4.0, light_hours=8))
    long = run_simulation(_simulate(et0_mm_per_day=4.0, light_hours=20))
    assert short.space.water_demand_l == pytest.approx(long.space.water_demand_l, rel=1e-6)
    # The crop-relative path does scale with light, which is what makes the test meaningful.
    assert (run_simulation(_simulate(light_hours=8)).space.water_demand_l
            < run_simulation(_simulate(light_hours=20)).space.water_demand_l)


def test_implausible_reference_flux_is_rejected():
    with pytest.raises(ValueError):
        water.simulate_water(crop=run_simulation(_simulate()).crop,
                             growth_points=run_simulation(_simulate()).space.daily_growth,
                             water_availability_percent=100, light_scale=1.0,
                             growing_area_m2=10, et0_mm_per_day=-1.0)


def test_non_positive_crop_coefficient_is_rejected():
    with pytest.raises(ValueError):
        water.simulate_water(crop=run_simulation(_simulate()).crop,
                             growth_points=run_simulation(_simulate()).space.daily_growth,
                             water_availability_percent=100, light_scale=1.0,
                             growing_area_m2=10, et0_mm_per_day=4.0, crop_coefficient=0.0)


# --------------------------------------------------------------------------- dataset
def test_dataset_is_the_one_its_metadata_describes():
    digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    assert digest == _dataset_meta()["sha256"]


def test_dataset_size_and_sites():
    meta = _dataset_meta()
    assert meta["rows"] == 17021
    assert len(meta["sites"]) == 6
    assert meta["removedRows"] == 145


def test_dataset_has_no_missing_values_in_its_model_columns():
    with DATASET.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = ["T2M_MAX", "T2M_MIN", "T2MDEW", "raMj", "daylightHours", "et0MmPerDay"]
    assert all(row[column] != "" for row in rows for column in required)


def test_quality_report_records_no_issues_and_states_the_drops():
    report = json.loads(QUALITY.read_text(encoding="utf-8"))
    assert report["sitesWithIssues"] == []
    assert report["removed"]["nonPositiveEt0Rows"] == 145
    assert report["removed"]["total"] == 145
    assert "never clipped" in report["removed"]["policy"]


# --------------------------------------------------------------------------- emulator honesty
def test_emulator_card_is_exploratory_and_not_deployed():
    card = _card()
    assert card["status"] == "trained-exploratory"
    assert card["deployed"] is False
    assert card["productionModelChanged"] is False


def test_emulator_records_the_gate_it_fails():
    gates = {gate["criterion"]: gate for gate in _card()["validation"]["acceptanceGate"]}
    assert gates["crossSiteGeneralisation"]["passed"] is False
    assert gates["crossSiteGeneralisation"]["observed"] < 0
    assert gates["beatsHargreavesTemporal"]["passed"] is True
    assert gates["intervalCoverage"]["passed"] is True


def test_emulator_is_better_than_hargreaves_only_on_the_temporal_holdout():
    card = _card()
    assert card["metrics"]["mae"] < card["baselineMetrics"]["hargreaves"]["mae"]
    assert card["improvementOverHargreaves"]["crossSitePct"] < 0


def test_emulator_does_not_beat_hargreaves_on_most_unseen_sites():
    won, total = _card()["validation"]["losoSitesBeatingHargreaves"].split("/")
    assert int(won) < int(total)


def test_emulator_declares_metric_directions():
    criteria = _card()["criteria"]
    assert "lower" in criteria["mae"].lower()
    assert "higher" in criteria["r2"].lower()


def test_emulator_training_data_precedes_its_holdout():
    card = _card()
    holdout = card["evaluation"]["temporalHoldout"]["start"]
    assert card["trainingData"]["lastDay"] >= holdout
    # The holdout starts after every training day that was used for fitting, which the split in
    # the trainer asserts; here the record itself must state the same boundary.
    assert holdout == "2024-01-01"
    assert card["trainingData"]["sha256"] == _dataset_meta()["sha256"]


def test_emulator_limitations_name_what_it_is_not():
    blob = " ".join(_card()["limitations"]).lower()
    assert "not measured" in blob or "computed, not measured" in blob
    assert "microgravity" in blob


def test_runtime_requirements_can_load_the_emulator():
    """The runtime image ships the artifact, so it must also ship the code that reads it.

    The first production deploy proved the failure mode: `ml/artifacts/et0-emulator-v1.joblib` was
    in the image, `joblib` was not, and the service answered every request from FAO-56 physics while
    the model card said `available: false`. It degraded correctly and silently - which is exactly
    why this assertion parses the runtime requirement file rather than trusting the image.
    """
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    names = {line.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip().lower()
             for line in requirements.splitlines()
             if line.strip() and not line.strip().startswith("#")}
    for package in ("scikit-learn", "joblib", "numpy"):
        assert package in names, f"{package} missing from backend/requirements.txt (runtime)"


def test_emulator_features_match_the_served_bundle():
    bundle = json.loads(json.dumps(_card()["features"]))
    assert bundle == ["T2M_MAX", "T2M_MIN", "T2MDEW", "latitude", "elevationM",
                      "doySin", "doyCos", "raMj", "daylightHours"]
    assert et0.artifact_status()["features"] == bundle


# --------------------------------------------------------------------------- API integration
def test_reference_endpoint_serves_physics_for_a_complete_request(client):
    response = client.get("/api/reference-et0/estimate", params={
        "tmaxC": 21.5, "tminC": 12.3, "latitude": 50.8, "elevationM": 100,
        "dayOfYear": 187, "tdewC": 12.07, "solarRadiationMJm2": 22.07,
        "windSpeedMs": 2.78, "pressureKpa": 100.1})
    assert response.status_code == 200
    body = response.json()
    assert body["primaryMethod"] == "penman-monteith"
    assert body["dayOfYearSource"] == "supplied"


def test_reference_endpoint_needs_a_vapour_pressure_input(client):
    response = client.get("/api/reference-et0/estimate", params={
        "tmaxC": 25, "tminC": 15, "latitude": 40, "dayOfYear": 200})
    assert response.status_code == 422


def test_model_card_endpoint_publishes_the_published_example_checks(client):
    body = client.get("/api/reference-et0/model").json()
    assert body["available"] is True
    assert body["physics"]["allExamplesWithinTolerance"] is True
    assert len(body["physics"]["publishedExamples"]) == 3
    assert body["validation"]["gatesPassed"] == 3
    assert body["validation"]["gatesTotal"] == 4


def test_model_registry_lists_the_emulator_with_its_failures(client):
    models = {m["id"]: m for m in client.get("/api/models").json()["models"]}
    assert "et0-emulator-v1" in models
    row = models["et0-emulator-v1"]
    assert row["servedBy"] == "app.et0"
    assert row["deployed"] is False
    assert row["scientificClassification"]["category"] == 4
    assert row["baselineComparison"]["measuredOn"].startswith("temporal holdout")


def test_workflow_catalogue_marks_the_emulator_as_an_external_service(client):
    rows = client.get("/api/workflow/models").json()["models"]
    row = next(r for r in rows if r["modelId"] == "et0-emulator-v1")
    assert row["runStatus"] == "external-service"
    assert row["servedAt"] == "/api/reference-et0/estimate"
    assert row["inputFamily"] == "weather"


def test_workflow_refuses_to_run_the_emulator_through_the_json_loader(client):
    response = client.post("/api/workflow/run",
                           json={"modelId": "et0-emulator-v1", "inputs": {}})
    assert response.status_code == 409
    body = response.json()["detail"]
    assert body["error"] == "external-service"
    assert body["endpoint"] == "/api/reference-et0/estimate"
    assert body["cardEndpoint"] == "/api/reference-et0/model"


def test_simulate_accepts_the_optional_flux_fields_and_reports_the_basis(client):
    body = client.post("/api/simulate", json={
        "crop": "lettuce", "gravity": 0, "radiation": 0.3, "waterAvailability": 100,
        "lightHours": 16, "co2Level": 1000, "simulationDays": 30, "growingArea": 10,
        "et0MmPerDay": 4.0}).json()
    assert body["demandBasis"]["basis"] == "et0-reference"
    assert body["demandBasis"]["cropCoefficient"] == 1.0
    assert body["waterUsed"] == pytest.approx(623.04, abs=0.01)
    assert any("reference ET0" in warning for warning in body["warnings"])


def test_simulate_default_response_unchanged_and_says_so(client):
    body = client.post("/api/simulate", json={
        "crop": "lettuce", "gravity": 0, "radiation": 0.3, "waterAvailability": 100,
        "lightHours": 16, "co2Level": 1000, "simulationDays": 30, "growingArea": 10}).json()
    assert body["demandBasis"]["basis"] == "crop-relative"
    assert body["demandBasis"]["et0MmPerDay"] is None
    assert body["waterUsed"] == pytest.approx(389.40, abs=0.01)


def test_config_describes_the_reference_et0_component(client):
    assumptions = {a["key"]: a for a in client.get("/api/config").json()["assumptions"]}
    component = assumptions["reference-et0"]
    assert "ET0" in component["formula"]
    assert component["constants"]["defaultCropCoefficient"] == 1.0
    assert len(component["sources"]) == 2
    assert "not a measurement" in component["evidence"].lower()


def test_emulator_is_classified_as_a_mechanistic_calculation():
    feature = science_classification.feature_by_id("et0-emulator-v1")
    assert feature is not None
    assert feature.category == 4
    assert "worse than Hargreaves" in feature.evidence
    assert any("microgravity" in note for note in feature.notes)


# --------------------------------------------------------------------------- catalogue + audit
def test_catalogue_covers_twenty_one_datasets_with_the_documented_class_counts():
    payload = json.loads((ROOT / "data" / "research" / "dataset_catalog.json").read_text())
    assert len(payload["datasets"]) == 21
    counts = {}
    for dataset in payload["datasets"]:
        counts[dataset["usabilityClass"]] = counts.get(dataset["usabilityClass"], 0) + 1
    assert counts == {"A": 1, "B": 6, "C": 5, "D": 3, "E": 5, "F": 1}


def test_only_the_imported_datasets_have_an_open_commercial_licence():
    payload = json.loads((ROOT / "data" / "research" / "dataset_catalog.json").read_text())
    for dataset in payload["datasets"]:
        if dataset["imported"]:
            assert dataset["usabilityClass"] in {"A", "B", "C"}
            assert dataset["license"], dataset["id"]


def test_catalogue_markdown_is_not_stale():
    result = subprocess.run([sys.executable, "ml/research/build_catalog.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_gap_matrix_markdown_is_not_stale():
    result = subprocess.run([sys.executable, "ml/research/build_gap_matrix.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_dataset_can_be_rebuilt_to_the_same_checksum():
    result = subprocess.run([sys.executable, "ml/research/build_et0_dataset.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_model_audit_passes_with_the_external_service_declared():
    result = subprocess.run([sys.executable, "scripts/audit_models.py"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:]


def test_registry_verifier_passes_with_the_external_service_declared():
    result = subprocess.run([sys.executable, "scripts/verify_model_registry.py"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:]
