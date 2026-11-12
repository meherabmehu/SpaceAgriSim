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
    defaults = dict(crop="lettuce", radiation=0.3, water_availability=100,
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


def test_service_falls_back_to_the_published_equation_when_radiation_is_missing():
    """Phase 31: no learned fallback. Missing inputs select Hargreaves, and the gap is named."""
    result = et0.estimate(tmax_c=30.0, tmin_c=18.0, day_of_year=200, latitude=23.8,
                          elevation_m=10.0, tdew_c=12.0)
    assert result["methods"]["penmanMonteith"] is None
    assert result["primaryMethod"] == "hargreaves"
    assert result["methods"]["hargreaves"]["et0MmPerDay"] > 0
    assert result["methodSelection"]["usedFallback"] is True
    assert set(result["methodSelection"]["missingInputs"]) == {"solarRadiationMJm2", "windSpeedMs"}
    # The removed surrogate must not come back as a third key.
    assert "emulator" not in result["methods"]


def test_no_learned_et0_estimate_is_returned_on_any_input_path():
    """A regression surrogate trained on a derived target is not served, with or without inputs."""
    for kwargs in ({"tmax_c": 25.0, "tmin_c": 15.0, "day_of_year": 200, "latitude": 40.0,
                    "elevation_m": 100.0, "tdew_c": 10.0},
                   {"tmax_c": 25.0, "tmin_c": 15.0, "day_of_year": 200, "latitude": -78.0,
                    "elevation_m": 3000.0, "tdew_c": 10.0, "solar_radiation_mj": 20.0,
                    "wind_speed_ms": 2.0}):
        result = et0.estimate(**kwargs)
        assert "emulator" not in result["methods"]
        assert not hasattr(et0, "load_artifact")
        assert not hasattr(et0, "artifact_status")


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


# ------------------------------------------------------------------ withdrawn surrogate record
def test_the_withdrawn_emulator_card_is_retained_as_a_negative_result():
    """Its artifact stays so the withdrawal can be re-checked; it must stay undeployed.

    A retained card is only safe if it says, in its own record, that it failed. These assertions
    read the artifact rather than a document, so the evidence and the file cannot drift.
    """
    card = _card()
    assert card["status"] == "trained-exploratory"
    assert card["deployed"] is False
    gates = {gate["criterion"]: gate for gate in card["validation"]["acceptanceGate"]}
    assert gates["crossSiteGeneralisation"]["passed"] is False
    assert gates["crossSiteGeneralisation"]["observed"] < 0
    won, total = card["validation"]["losoSitesBeatingHargreaves"].split("/")
    assert int(won) < int(total)
    assert card["improvementOverHargreaves"]["crossSitePct"] < 0
    blob = " ".join(card["limitations"]).lower()
    assert "not measured" in blob or "computed, not measured" in blob


def test_the_withdrawal_reason_is_recorded_next_to_the_served_set():
    assert "et0-emulator-v1" in research.RETIRED_MODEL_IDS
    assert "et0-emulator-v1" not in research.MODEL_IDS
    reason = research.RETIRED_MODEL_IDS["et0-emulator-v1"].lower()
    assert "hargreaves" in reason and "derived" in reason


def test_runtime_pins_match_the_environment_that_wrote_the_artifacts():
    """A scikit-learn pickle only loads where the module layout it recorded still exists.

    The served models are still serialised trees, so the runtime pins are still compared with the
    artifacts' own recorded environment - the check outlived the emulator it was written for.
    """
    registry = json.loads((ROOT / "ml" / "artifacts" / "registry.json").read_text())
    # The registry records the library the artifacts were trained with under its import name.
    trained = {"scikit-learn": registry["environment"]["sklearn"],
               "numpy": registry["environment"]["numpy"]}
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    pins = {}
    for line in requirements.splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            pins[name.strip().lower()] = version.strip()
    for package in ("scikit-learn", "numpy"):
        assert pins.get(package) == trained[package], package


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
    assert body["kind"] == "calculation"
    assert body["allExamplesWithinTolerance"] is True
    assert len(body["publishedExamples"]) == 3
    assert all(row["withinTolerance"] for row in body["publishedExamples"])
    # The card must not claim a measured-ET0 validation it does not have.
    assert body["measuredEt0Validation"]["available"] is False
    assert body["removedSurrogate"]["modelId"] == "et0-emulator-v1"
    assert body["provenance"]["standard"].startswith("FAO-56")


def test_the_withdrawn_emulator_is_absent_from_the_registry_and_the_catalogue(client):
    """Phase 31: absent, not present-and-flagged. A retired card is still a card."""
    registry = client.get("/api/models").json()
    assert "et0-emulator-v1" not in {m["id"] for m in registry["models"]}
    calculations = {row["id"]: row for row in registry["calculations"]}
    assert calculations["reference-et0"]["kind"] == "calculation"

    rows = client.get("/api/workflow/models").json()["models"]
    assert "et0-emulator-v1" not in {r["modelId"] for r in rows}
    assert "weather" not in client.get("/api/workflow/models").json()["families"]


def test_the_withdrawn_emulator_cannot_be_run_through_the_workflow(client):
    response = client.post("/api/workflow/run",
                           json={"modelId": "et0-emulator-v1", "inputs": {}})
    assert response.status_code in {404, 409, 422}
    assert response.status_code != 200


def test_simulate_accepts_the_optional_flux_fields_and_reports_the_basis(client):
    body = client.post("/api/simulate", json={
        "crop": "lettuce", "radiation": 0.3, "waterAvailability": 100,
        "lightHours": 16, "co2Level": 1000, "simulationDays": 30, "growingArea": 10,
        "et0MmPerDay": 4.0}).json()
    assert body["demandBasis"]["basis"] == "et0-reference"
    assert body["demandBasis"]["cropCoefficient"] == 1.0
    assert body["waterUsed"] == pytest.approx(623.04, abs=0.01)
    assert any("reference ET0" in warning for warning in body["warnings"])


def test_simulate_default_response_unchanged_and_says_so(client):
    body = client.post("/api/simulate", json={
        "crop": "lettuce", "radiation": 0.3, "waterAvailability": 100,
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


def test_reference_et0_is_classified_as_a_mechanistic_calculation():
    feature = science_classification.feature_by_id("reference-et0")
    assert feature is not None
    assert feature.category == 4
    assert feature.status.startswith("served")
    blob = " ".join([feature.evidence, *feature.notes]).lower()
    assert "no measured" in blob or "not a measurement" in blob or "not validated" in blob
    assert "microgravity" in blob
    # The removed surrogate must not be a served surface in its own right.
    assert science_classification.feature_by_id("et0-emulator-v1") is None


# --------------------------------------------------------------------------- catalogue + audit
def test_catalogue_counts_match_the_documented_class_counts():
    """34 since Phase 36 acquired four more measured datasets and imported a fifth.

    Each of the five was downloaded, hashed against the publisher's own checksum and preprocessed
    before it entered the catalogue; none was added to raise a count. The class assignments are
    deliberately mixed - A for the ones that drive a committed artefact, B for the ones usable but
    unconsumed, C for the twenty-plant open-field tomato trial, D for the tree gas-exchange series -
    because a class is an answer about usability, not a trophy. Phase 29 promoted the green-light
    trial to A once a workflow served it. Phase 30 added the controlled-environment wheat series
    and the lettuce light-use-efficiency compilation, both class A: the first is served as a
    measured comparison, the second was used to evaluate - and fail - the harvest model.

    Phase 36 added four class-A entries - POWER hourly, the Agroscope weighable lysimeter, the
    TERENO eddy-covariance record and IoT4Lettuce - and promoted NEX-GDDP-CMIP6 from D to A once
    it was actually imported for the six sites. Every one of the four was acquired with a
    publisher checksum verified or a member-level SHA-256 recorded, and each drives a committed
    artefact under data/research/phase36/. The count is still asserted exactly, because the point
    of this test is that the number in the catalogue is not allowed to drift away from the
    number of entries that can be justified one by one.
    """
    payload = json.loads((ROOT / "data" / "research" / "dataset_catalog.json").read_text())
    assert len(payload["datasets"]) == 34
    counts = {}
    for dataset in payload["datasets"]:
        counts[dataset["usabilityClass"]] = counts.get(dataset["usabilityClass"], 0) + 1
    # Phase 36 added four class-A acquisitions and moved NEX-GDDP-CMIP6 from D to A; no other
    # class moved, so the shape of the catalogue is unchanged at B, C, E and F.
    assert counts == {"A": 10, "B": 6, "C": 9, "D": 3, "E": 5, "F": 1}


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


def test_model_audit_passes_after_the_phase31_withdrawals():
    result = subprocess.run([sys.executable, "scripts/audit_models.py"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:]


def test_registry_verifier_passes_after_the_phase31_withdrawals():
    # `--check` verifies without rewriting `docs/phase7/registry_verification.json`. Running the
    # verifier bare regenerated the report with a new `generatedAt` timestamp, so a passing test
    # suite left a dirty working tree whose only diff was that timestamp - a change that has twice
    # been mistaken for a real one. The exit code and the checks are identical either way.
    result = subprocess.run([sys.executable, "scripts/verify_model_registry.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:]


def test_registry_verification_gate_does_not_touch_the_committed_report():
    """The gate must be read-only: a test run may not rewrite the artefact it verifies."""
    report = ROOT / "docs" / "phase7" / "registry_verification.json"
    before = report.read_bytes()
    result = subprocess.run([sys.executable, "scripts/verify_model_registry.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:]
    assert report.read_bytes() == before, (
        "scripts/verify_model_registry.py rewrote docs/phase7/registry_verification.json; "
        "use --check so the gate leaves the tree untouched"
    )
    assert "verified without writing" in result.stdout
