"""Phase 25: the controlled-environment water-use ingestion pipeline.

These tests exercise the validator against labelled synthetic fixtures. **No measurement exists**
in this repository and none is implied by a passing test: what is asserted is that a defective
export is rejected for the right reason, and that the two deliberate refusals (a crop coefficient
without an in-situ ET0, a failed water balance) cannot be softened.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from scripts.experiment import make_synthetic_fixture as fixture_builder
from scripts.experiment import validate_water_use as validator

SCHEMA = validator.load_schema()
FIXTURES = Path(validator.__file__).resolve().parent / "fixtures"
CLEAN = FIXTURES / "SYNTHETIC_FIXTURE_not_a_measurement.csv"


def _report(path: Path) -> dict:
    return validator.validate(path, schema_path=validator.SCHEMA_PATH)


def _status(report: dict, check: str) -> str:
    for entry in report["checks"]:
        if entry["check"] == check:
            return entry["status"]
    raise KeyError(check)


# ---------------------------------------------------------------------------------------
# The schema is a contract, not documentation
# ---------------------------------------------------------------------------------------


def test_schema_declares_the_expected_number_of_columns():
    assert len(SCHEMA["requiredColumns"]) == 23
    assert len(SCHEMA["optionalColumns"]) == 18
    assert len(SCHEMA["derivedColumns"]) == 2


def test_schema_carries_seven_cross_field_rules():
    assert len(SCHEMA["crossFieldChecks"]) == 7
    ids = {rule["id"] for rule in SCHEMA["crossFieldChecks"]}
    assert "kc_requires_in_situ_et0" in ids
    assert "temperature_order" in ids


def test_schema_states_that_no_trial_has_been_performed():
    assert "NO TRIAL HAS BEEN PERFORMED" in SCHEMA["status"]


def test_balance_tolerance_is_ten_percent_and_is_not_a_suggestion():
    assert SCHEMA["qualityRules"]["balanceClosureTolerancePct"] == 10.0
    assert "never averaged in" in SCHEMA["qualityRules"]["balanceClosureDefinition"]


def test_analysis_plan_forbids_retuning_thresholds():
    plan = SCHEMA["analysisPlan"]
    assert "no threshold may be retuned" in plan["thresholds"].lower()
    assert plan["dataExclusion"].startswith("rejected rows are reported")


def test_every_column_declares_a_unit_and_a_type():
    for entry in SCHEMA["requiredColumns"] + SCHEMA["optionalColumns"]:
        assert entry["unit"], entry["name"]
        assert entry["type"] in ("string", "number", "integer", "date")


def test_the_validator_exposes_exactly_eighteen_checks():
    assert len(validator.CHECKS) == 18
    assert set(validator.CHECKS) == {c["check"] for c in _report(CLEAN)["checks"]}


# ---------------------------------------------------------------------------------------
# The clean fixture passes, and the fixtures say what they are
# ---------------------------------------------------------------------------------------


def test_clean_fixture_passes_every_check():
    report = _report(CLEAN)
    assert report["verdict"] == "PASS", report["failedChecks"]
    assert report["rowCount"] == 252


def test_every_fixture_row_is_labelled_as_not_a_measurement():
    with CLEAN.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            assert row["notes"].startswith("SYNTHETIC FIXTURE")


def test_fixture_filenames_admit_that_they_are_fixtures():
    for path in FIXTURES.glob("*.csv"):
        assert "SYNTHETIC_FIXTURE_not_a_measurement" in path.name


# ---------------------------------------------------------------------------------------
# Each defect is caught by the check that is supposed to catch it
# ---------------------------------------------------------------------------------------


DEFECT_CASES = [
    ("unit_mismatch", "unit_matches_schema"),
    ("missing_required", "required_values"),
    ("balance_broken", "water_balance_closure"),
    ("duplicate_row", "row_grain_unique"),
    ("bad_temperature_order", "cross_field_consistency"),
    ("kc_without_in_situ", "kc_requires_in_situ_et0"),
    ("out_of_range", "value_ranges"),
    ("qc_without_note", "cross_field_consistency"),
    ("date_gap", "daily_continuity"),
    ("thin_replication", "replication_and_duration"),
]


@pytest.mark.parametrize("defect,expected_check", DEFECT_CASES)
def test_defect_is_reported_by_the_expected_check(defect, expected_check):
    path = FIXTURES / f"SYNTHETIC_FIXTURE_not_a_measurement__defect_{defect}.csv"
    report = _report(path)
    status = _status(report, expected_check)
    assert status in ("fail", "warn"), f"{defect} left {expected_check} at {status}"


@pytest.mark.parametrize("defect,expected_check", DEFECT_CASES)
def test_a_failed_defect_trial_cannot_be_reported_as_passing(defect, expected_check):
    path = FIXTURES / f"SYNTHETIC_FIXTURE_not_a_measurement__defect_{defect}.csv"
    report = _report(path)
    if _status(report, expected_check) == "fail":
        assert report["verdict"] == "FAIL"
        assert expected_check in report["failedChecks"]


def test_thin_replication_warns_but_does_not_fail_the_trial():
    """Two plants is thin, not invalid; the distinction is the point of a warning."""
    path = FIXTURES / "SYNTHETIC_FIXTURE_not_a_measurement__defect_thin_replication.csv"
    report = _report(path)
    assert _status(report, "replication_and_duration") == "warn"
    assert report["verdict"] == "PASS_WITH_WARNINGS"


def test_a_missing_units_file_is_a_failure_not_a_warning(tmp_path):
    """Without units, 'L' and 'mL' are the same number and differ by a factor of 1000."""
    copied = tmp_path / CLEAN.name
    copied.write_bytes(CLEAN.read_bytes())
    report = validator.validate(copied, schema_path=validator.SCHEMA_PATH)
    assert _status(report, "units_file_present") == "fail"
    assert report["verdict"] == "FAIL"


def test_units_in_the_same_quantity_but_a_different_scale_are_rejected(tmp_path):
    copied = tmp_path / CLEAN.name
    copied.write_bytes(CLEAN.read_bytes())
    units = json.loads((FIXTURES / "SYNTHETIC_FIXTURE_not_a_measurement.units.json").read_text())
    units["units"]["water_input_ml"] = "L"
    (tmp_path / f"{CLEAN.stem}.units.json").write_text(json.dumps(units))
    report = validator.validate(copied, schema_path=validator.SCHEMA_PATH)
    assert _status(report, "unit_matches_schema") == "fail"


def test_balance_failure_rejects_the_day_rather_than_averaging_it(tmp_path):
    """The rejected days are listed by line number so a report can state how many were lost."""
    path = FIXTURES / "SYNTHETIC_FIXTURE_not_a_measurement__defect_balance_broken.csv"
    report = _report(path)
    closure = next(c for c in report["checks"] if c["check"] == "water_balance_closure")
    assert closure["status"] == "fail"
    assert closure["detailCount"] > 0
    assert all("closurePct" in detail for detail in closure["details"])


def test_kc_rule_names_the_offending_rows(tmp_path):
    path = FIXTURES / "SYNTHETIC_FIXTURE_not_a_measurement__defect_kc_without_in_situ.csv"
    report = _report(path)
    kc = next(c for c in report["checks"] if c["check"] == "kc_requires_in_situ_et0")
    assert kc["status"] == "fail"
    assert kc["details"][0]["et0_source"] == "reanalysis"


# ---------------------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------------------


def test_template_has_a_header_and_no_rows(tmp_path):
    target = tmp_path / "template.csv"
    units_path = validator.emit_template(target)
    lines = target.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    declared = json.loads(units_path.read_text(encoding="utf-8"))["units"]
    assert len(declared) == 41  # 23 required + 18 optional
    assert all(value for value in declared.values())


def test_template_validates_as_empty_not_as_measured(tmp_path):
    """An empty export is not a passing trial; it is a file with no rows."""
    target = tmp_path / "template.csv"
    validator.emit_template(target)
    report = validator.validate(target, schema_path=validator.SCHEMA_PATH)
    assert report["rowCount"] == 0


# ---------------------------------------------------------------------------------------
# The generator is reproducible and covers every defect deliberately
# ---------------------------------------------------------------------------------------


def test_generator_covers_each_defect_once():
    assert set(fixture_builder.DEFECTS) == {
        "clean", "unit_mismatch", "missing_required", "balance_broken", "duplicate_row",
        "bad_temperature_order", "kc_without_in_situ", "out_of_range", "qc_without_note",
        "date_gap", "thin_replication",
    }


def test_generator_is_deterministic():
    first = fixture_builder._rows()
    second = fixture_builder._rows()
    assert first == second
    assert len({row["plant_id"] for row in first}) == 6


def test_report_carries_the_honesty_note():
    report = _report(CLEAN)
    assert "cannot establish that a measurement was made" in report["note"]
