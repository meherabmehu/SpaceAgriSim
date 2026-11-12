"""Phase 7 calibration guarantees.

These tests exist to make three promises mechanically true rather than merely
documented:

  1. no simulator output changed in Phase 7;
  2. the mass-balance invariant still holds across the scenario grid;
  3. Phase 6's declined calibration suggestions were not quietly applied later.

If a future phase legitimately changes a baseline, it must update
docs/phase7/scientific_calibration deliberately - which is exactly the
point: the change becomes a reviewed act with a diff, not a side effect.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.config import simulation_constants as constants  # noqa: E402
from app.simulation import engine  # noqa: E402

EVIDENCE_PATH = ROOT / "docs" / "phase7" / "scientific_calibration"


@pytest.fixture(scope="module")
def evidence():
    if not safedata.exists(EVIDENCE_PATH):
        pytest.skip("Phase 7 calibration evidence not generated")
    return safedata.load(EVIDENCE_PATH)


@pytest.fixture(scope="module")
def calibrate():
    import importlib
    module = importlib.import_module("calibrate_phase7")
    return module


def test_output_fingerprint_is_unchanged(evidence, calibrate):
    fingerprints = [calibrate.fingerprint(engine.run_simulation(p))
                    for p in calibrate.scenario_grid()]
    combined = __import__("hashlib").sha256("".join(fingerprints).encode()).hexdigest()
    assert combined == evidence["outputFingerprint"]["sha256"], (
        "A simulator output value, unit or field changed. If this was intentional, "
        "regenerate docs/phase7/scientific_calibration and justify the diff."
    )


def test_mass_balance_invariant_holds(calibrate):
    result = calibrate.mass_balance_checks()
    assert result["allPassed"], result["failures"]
    assert result["checksRun"] >= 54


def test_no_calibration_was_applied(evidence):
    # Phase 7 applied zero changes. This is a statement about the evidence, not a
    # limitation of the code, so it is asserted rather than assumed.
    assert evidence["appliedChanges"] == []


def test_phase6_suggestions_were_not_applied(evidence):
    declared = evidence["declinedChanges"][0]["detail"]["crops"]
    for crop, expected in (("tomato", 3.5), ("radish", 1.2)):
        assert declared[crop]["applied"] is False
        assert declared[crop]["appliedValueInSimulator"] == expected
        # The live constant must still match, not just the recorded snapshot.
        assert constants.CROP_BASELINES[crop]["harvest_biomass_g"] == expected * 1000
        assert declared[crop]["phase6SuggestedKgPerM2"] != expected


def test_constants_snapshot_matches_live_constants(evidence):
    snapshot = evidence["constantsSnapshot"]
    assert snapshot["WATER_RECOVERY_EFFICIENCY"] == constants.WATER_RECOVERY_EFFICIENCY
    assert snapshot["CARBON_FRACTION_OF_DRY_MASS"] == constants.CARBON_FRACTION_OF_DRY_MASS
    assert snapshot["LOGISTIC_STEEPNESS"] == constants.LOGISTIC_STEEPNESS
    for crop, value in snapshot["cropHarvestBiomassG"].items():
        assert constants.CROP_BASELINES[crop]["harvest_biomass_g"] == value


def test_calibration_checks_carry_their_evidence_class(evidence):
    # A check with no evidence class is a claim with no provenance.
    for check in evidence["checks"]:
        assert check["evidenceClass"]
        assert check["decision"]
        assert check["reason"]
        assert "verdict" in check


def test_water_recovery_assumption_is_not_raised_to_a_leaking_measurement(evidence):
    """The measurement is a lower bound, so 'calibrating up' toward it is a trap.

    WATER_RECOVERY_EFFICIENCY must stay at or below the measured 0.924 - the
    assumption should be conservative, and the chamber that produced 0.924 was
    leaking 20-40 % of its volume per day.
    """
    check = next(c for c in evidence["checks"]
                 if c["parameter"] == "WATER_RECOVERY_EFFICIENCY")
    assert constants.WATER_RECOVERY_EFFICIENCY <= check["measured"] + 1e-9
