"""Phase 26: the dataset registry, the acquisition manifest and the processed tables.

These tests exist to stop the specific failure this phase already had once: a download that
produced a few hundred bytes of JSON was recorded as an acquired dataset, and a preprocessing
offset error turned one rate column into another. Both are now checkable in milliseconds.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.datasets import registry  # noqa: E402

PROCESSED = REPO_ROOT / "data" / "processed" / "phase26"
MANIFEST = REPO_ROOT / "data" / "metadata" / "phase26_acquisition_manifest.json"
VALIDATION = REPO_ROOT / "ml" / "evaluation" / "phase26_measured_et_validation.json"


# ---------------------------------------------------------------------------------------
# registry vocabulary
# ---------------------------------------------------------------------------------------
def test_every_candidate_uses_a_known_usability_class():
    allowed = set(registry.USABILITY_CLASSES)
    for candidate in registry.CANDIDATES:
        assert candidate["usabilityClass"] in allowed, candidate["id"]
        assert candidate["classReason"].strip(), candidate["id"]


def test_every_candidate_uses_a_known_evidence_category_and_environment():
    for candidate in registry.CANDIDATES:
        assert candidate["evidenceCategory"] in registry.EVIDENCE_CATEGORIES, candidate["id"]
        assert candidate["environment"] in registry.ENVIRONMENTS, candidate["id"]


def test_candidate_ids_are_unique():
    ids = [candidate["id"] for candidate in registry.CANDIDATES]
    assert len(ids) == len(set(ids))


def test_acquired_candidates_declare_a_doi_and_a_licence_with_evidence():
    for candidate in registry.acquired():
        assert candidate["doi"], candidate["id"]
        assert candidate["license"], candidate["id"]
        assert candidate["licenseEvidence"].strip(), candidate["id"]


def test_not_acquired_candidates_state_why():
    for candidate in registry.CANDIDATES:
        if candidate["acquisition"]["status"] == "acquired":
            continue
        assert candidate["acquisition"].get("reason"), candidate["id"]
        assert candidate["inspection"]["status"] != "inspected", (
            f"{candidate['id']} claims an inspection with no file")


def test_summary_counts_cannot_exceed_the_candidate_list():
    summary = registry.summary()
    assert summary["candidates"] == len(registry.CANDIDATES)
    assert 0 <= summary["acquired"] <= summary["candidates"]
    assert 0 <= summary["inspected"] <= summary["acquired"]
    assert 0 <= summary["processed"] <= summary["inspected"]
    assert sum(summary["byClass"].values()) == summary["candidates"]


def test_by_id_raises_on_an_unknown_id():
    with pytest.raises(KeyError):
        registry.by_id("no-such-dataset")


# ---------------------------------------------------------------------------------------
# the manifest describes bytes that are really on disk
# ---------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.skip("acquisition manifest not present")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_verified_count_matches_the_records(manifest):
    counted = sum(record["verifiedDownloadCount"] for record in manifest["datasets"].values())
    assert manifest["verifiedDownloadCount"] == counted


def test_each_verified_file_exists_and_hashes_to_the_recorded_value(manifest):
    for dataset_id, record in manifest["datasets"].items():
        for entry in record["files"]:
            if entry["action"] not in ("written", "unchanged"):
                continue
            path = REPO_ROOT / entry["path"]
            assert path.is_file(), f"{dataset_id}: {entry['path']} missing"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == entry["sha256"], f"{dataset_id}: bytes changed since acquisition"
            if entry.get("declaredSize") is not None:
                assert path.stat().st_size == entry["declaredSize"]


def test_no_verified_file_is_a_metadata_stub(manifest):
    """The bug this guards: 600-900 byte JSON responses recorded as data files."""
    for dataset_id, record in manifest["datasets"].items():
        for entry in record["files"]:
            if entry["action"] not in ("written", "unchanged"):
                continue
            path = REPO_ROOT / entry["path"]
            assert path.stat().st_size > 50_000, f"{dataset_id}: {entry['path']} is too small"
            if path.suffix == ".xlsx":
                assert path.read_bytes()[:4] == b"PK\x03\x04", dataset_id


def test_verification_rejects_a_wrong_size(tmp_path):
    from scripts.datasets.acquire import verify_payload
    target = tmp_path / "toy.csv"
    target.write_bytes(b"a,b\n1,2\n")
    result = verify_payload(target, expected_size=999, expected_checksum=None, extension=".csv")
    assert result["verified"] is False
    assert any("size" in problem for problem in result["problems"])


def test_verification_rejects_json_masquerading_as_csv(tmp_path):
    from scripts.datasets.acquire import verify_payload
    target = tmp_path / "toy.csv"
    target.write_bytes(b'{"created": "2021-10-05", "links": {}}')
    result = verify_payload(target, expected_size=None, expected_checksum=None,
                            extension=".csv")
    assert result["verified"] is False


# ---------------------------------------------------------------------------------------
# processed tables
# ---------------------------------------------------------------------------------------
def _read(name: str) -> pd.DataFrame:
    path = PROCESSED / f"{name}.csv"
    if not path.is_file():
        pytest.skip(f"{name} not generated")
    return pd.read_csv(path)


def test_processed_tables_have_matching_quality_files():
    for path in PROCESSED.glob("*.csv"):
        quality = path.with_name(path.stem + "_quality.json")
        assert quality.is_file(), f"{path.name} has no quality file"
        record = json.loads(quality.read_text(encoding="utf-8"))
        assert record["table"] == path.name
        assert record["rows"] == len(pd.read_csv(path))


def test_et_table_is_monotonic_within_a_pot():
    et = _read("schroder2021_lettuce_et")
    for pot, group in et.groupby("potId"):
        days = group.sort_values("date")["dayNumber"].tolist()
        assert days == sorted(days), f"{pot} has out-of-order measurement dates"


def test_et_rate_column_is_per_day_and_not_per_hour():
    """Regression guard: the workbook's ET/d and ET/h columns are the other way round."""
    et = _read("schroder2021_lettuce_et")
    paired = et.dropna(subset=["etRateMlPerDayFromSource", "etRateMlPerDayRecomputed"])
    assert len(paired) > 100
    ratio = (paired["etRateMlPerDayFromSource"] / paired["etRateMlPerDayRecomputed"]).median()
    assert 0.9 < ratio < 1.1, f"source rate is not a per-day rate (median ratio {ratio:.3f})"


def test_et_per_day_is_the_interval_total_divided_by_elapsed_days():
    et = _read("schroder2021_lettuce_et").dropna(subset=["elapsedDaysSincePrevious"])
    recomputed = et["etTotalMl"] / et["elapsedDaysSincePrevious"]
    assert (recomputed - et["etRateMlPerDayRecomputed"]).abs().max() < 1e-6


def test_et_rows_above_the_irrigation_ceiling_are_flagged_not_deleted():
    et = _read("schroder2021_lettuce_et")
    assert "flagAboveIrrigationCeiling" in et.columns
    assert et["flagAboveIrrigationCeiling"].sum() >= 1
    assert et["etRateMlPerDayRecomputed"].max() > 350


def test_biomass_organs_are_shoot_or_root():
    biomass = _read("schroder2021_lettuce_biomass")
    assert set(biomass["organ"].unique()) <= {"shoot", "root"}


def test_greenlight_harvest_keeps_every_published_plant():
    harvest = _read("greenlight2024_lettuce_harvest")
    assert len(harvest) == 252
    assert harvest["treatment"].nunique() == 4
    assert harvest["freshWeightG"].isna().sum() == 0


def test_greenlight_fluorescence_is_not_labelled_as_a_photosynthesis_rate():
    quality = json.loads(
        (PROCESSED / "greenlight2024_lettuce_fluorescence_quality.json").read_text())
    assert "notAPhotosyntheticRate" in quality
    assert "photosynthesis" in quality["notAPhotosyntheticRate"].lower()


def test_tomato_growth_table_is_per_plant_and_weekly():
    growth = _read("ledphotoperiod2025_tomato_growth")
    assert growth["plantId"].nunique() == 20
    assert growth["week"].nunique() >= 5


def test_open_field_tomato_is_not_described_as_controlled_environment():
    quality = json.loads(
        (PROCESSED / "ledphotoperiod2025_tomato_growth_quality.json").read_text())
    assert quality["study"]["environment"] == "open field"
    assert "not controlled" in quality["note"]


# ---------------------------------------------------------------------------------------
# the ET validation artefact
# ---------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def validation() -> dict:
    if not VALIDATION.is_file():
        pytest.skip("ET validation artefact not present")
    return json.loads(VALIDATION.read_text(encoding="utf-8"))


def test_validation_reports_uncalibrated_and_calibrated_numbers_side_by_side(validation):
    assert validation["scalePerPot"]["pooled"]["ratioPredictedToMeasured"] < 1
    assert validation["scalePerPot"]["fittedSingleScale"] > 1


def test_validation_fitted_scale_has_a_leave_one_treatment_out_estimate(validation):
    folds = validation["scalePerPot"]["leaveOneTreatmentOut"]
    assert len(folds) == len(validation["measuredSide"]["treatments"])
    for fold in folds.values():
        assert fold["fittedScaleOnOtherTreatments"] > 0


def test_validation_states_the_area_denominator_sensitivity(validation):
    sensitivity = validation["denominatorSensitivity"]["denominators"]
    on_pot = sensitivity["potSurfaceAssumption"]["profileIsHigher"]
    on_canopy = sensitivity["canopyLeafArea"]["profileIsHigher"]
    assert on_pot != on_canopy, "the sensitivity block no longer shows the sign reversal"


def test_validation_does_not_close_the_gap(validation):
    assert validation["canItCloseTheGap"]["conclusion"] == "not closed"
    assert validation["canItCloseTheGap"]["why"]


def test_validation_does_not_claim_to_have_changed_the_simulator(validation):
    assert validation["simulatedSide"]["constantsChanged"] == []
    assert any("untouched" in item for item in validation["notClaimed"])


def test_validation_never_calls_a_pot_measurement_microgravity(validation):
    text = json.dumps(validation).lower()
    assert "no microgravity" in text
    assert "microgravity" not in validation["measuredSide"]["measurementBasis"].lower()
