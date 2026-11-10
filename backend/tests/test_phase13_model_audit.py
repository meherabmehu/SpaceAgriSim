"""Phase 13: the model audit must pass, and must stay read-only.

`scripts/audit_models.py` recomputes checksums, re-reads every artifact and asserts the invariants
around supersession, retirement and dataset independence. These tests run that audit in-process
so a future change to an artifact or a classification breaks the build rather than the audit.

The last test is the important one: it proves the audit did not rewrite a single byte. An audit
that can edit the thing it audits reports whatever it just wrote.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "ml" / "artifacts"


def _load_audit():
    spec = importlib.util.spec_from_file_location("audit_models", ROOT / "scripts" / "audit_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit_module():
    return _load_audit()


@pytest.fixture(scope="module")
def report(audit_module):
    return audit_module.audit()


def test_audit_reports_no_failures(report):
    assert report["failures"] == []


def test_every_registered_artifact_is_audited(report):
    registry = json.loads((ARTIFACTS / "registry.json").read_text(encoding="utf-8"))
    assert report["summary"]["registeredModels"] == len(registry["models"])
    assert report["summary"]["auditedModels"] == len(registry["models"])
    assert {row["id"] for row in report["models"]} == {entry["id"] for entry in registry["models"]}


def test_checksums_are_recomputed_from_disk(report):
    registry = {entry["id"]: entry for entry in
                json.loads((ARTIFACTS / "registry.json").read_text(encoding="utf-8"))["models"]}
    for row in report["models"]:
        digest = hashlib.sha256((ROOT / registry[row["id"]]["artifact"]).read_bytes()).hexdigest()
        assert row["sha256"] == digest == registry[row["id"]]["sha256"]


def test_api_metrics_match_the_artifacts_exactly(report):
    """No silent metric change: what the API serves is what the artifact records."""
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app import research

    served = {model["id"]: model for model in research.model_registry()["models"]}
    for row in report["models"]:
        if row["id"] in research.RETIRED_MODEL_IDS:
            # Withdrawn artifacts are still audited and still checksummed, but they publish no
            # metrics through the API - which is the point of withdrawing them.
            assert row["id"] not in served
            continue
        numeric = {name: value for name, value in served[row["id"]]["metrics"].items()
                   if isinstance(value, (int, float))}
        assert numeric == row["metrics"], row["id"]


def test_superseded_predecessors_are_kept_not_overwritten(report):
    superseded = [row for row in report["models"] if row["supersedes"]]
    # Two pre-existing pairs: lettuce v2 -> v1 and mizuna v2 -> v1. v3 supersedes nothing - it
    # serves alongside lettuce v2, whose failed external check is the evidence that justified it.
    assert len(superseded) == 2
    assert all(row["id"] != "lettuce-earth-growth-v3" for row in superseded)
    for row in superseded:
        # The recorded string is "mizuna-microbial-load-v1 (kept, not overwritten)": the id is the
        # first token, and the parenthetical is the statement of what happened to the old file.
        predecessor = row["supersedes"].split()[0]
        assert (ARTIFACTS / f"{predecessor}.json").is_file()


def test_no_served_model_is_retired_and_every_withdrawal_is_recorded(report):
    """Phase 31: the retired state no longer exists in the served set - removal replaced it."""
    assert [row["id"] for row in report["models"] if row["runStatus"] == "retired"] == []
    for row in report["models"]:
        if row["classification"]:
            assert row["classification"]["category"] != 6, row["id"]
            assert row["runStatus"] != "retired", row["id"]

    from app import research
    # The two withdrawn models that were registered artifacts are audited (checksummed, provenance
    # checked) and appear with no catalogue status. The ET0 emulator only ever shipped a card, so
    # it is covered by the named checks rather than by a model row.
    withdrawn = {row["id"] for row in report["models"] if row["id"] in research.RETIRED_MODEL_IDS}
    assert withdrawn == {"mizuna-harvest-v1", "mizuna-microbial-load-v1"}
    checks = {entry["check"]: entry["passed"] for entry in report["checks"]}
    assert checks["withdrawn-surrogate-not-served:et0-emulator-v1"] is True
    assert checks["retained-not-served-by-api:mizuna-harvest-v1"] is True
    assert checks["retained-not-served-by-api:mizuna-microbial-load-v1"] is True
    assert checks["retained-not-routed:mizuna-harvest-v1"] is True
    assert checks["retained-not-routed:mizuna-microbial-load-v1"] is True
    for row in report["models"]:
        if row["id"] in research.RETIRED_MODEL_IDS:
            # Retained, checksummed, and invisible to every served surface.
            assert row["runStatus"] is None and row["classification"] is None, row["id"]
            assert row["checksumMatches"] is True, row["id"]
            assert research.RETIRED_MODEL_IDS[row["id"]].strip()


def test_no_classifier_is_presented_as_calibrated(report):
    for row in report["models"]:
        calibration = row.get("calibration") or {}
        assert calibration.get("calibrated") is not True, row["id"]


def test_calibration_gaps_are_reported_rather_than_hidden(report):
    high = [gap for gap in report["gaps"] if gap["severity"] == "high"]
    assert {gap["model"] for gap in high} == {"radiation-quality-osd46-v1", "radiation-exposure-osd46-v1"}
    assert all(gap["field"] == "calibration" for gap in high)


def test_dataset_safeguards_survive_the_audit(report):
    names = {check["check"] for check in report["checks"]}
    assert "duplicate-safeguard-wording" in names
    assert "safeguard-present:phase11-duplicate-osd320" in names
    assert all(check["passed"] for check in report["checks"]
               if check["check"].startswith(("safeguard-present", "osd320-not-independence")))


def test_osd320_is_never_cited_as_independent_evidence():
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app import evidence

    passage = next(p for p in evidence.corpus()["passages"]
                   if p.id == "finding::phase11-duplicate-osd320")
    text = (passage.text + " " + " ".join(passage.limitations)).lower()
    assert "never be used as independent validation" in text
    # And the shared-array fact is stated numerically, not asserted vaguely.
    assert "1.000000" in text and "22,810" in text


def test_the_audit_does_not_modify_any_artifact(audit_module):
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(ARTIFACTS.glob("*.json"))}
    audit_module.audit()
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(ARTIFACTS.glob("*.json"))}
    assert before == after
