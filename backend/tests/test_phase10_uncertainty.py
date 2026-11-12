"""Phase 10: the stated interval must be the interval that was measured.

Phase 9 shipped intervals that said so in their own text — `empiricallyCalibrated:
false`, coverage 0.811 and 0.849 against a nominal 0.90. That honesty was right and
the defect was real. Phase 10 recalibrated them, and these tests exist so the fix
cannot quietly rot back into a disclaimed number.
"""
from __future__ import annotations
import sys

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.research import router

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
EVALUATION = ROOT / "ml" / "evaluation"

@pytest.fixture
def scientific_client():
    """The research router alone: these tests are about model payloads, not auth."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


# Phase 31 removed mizuna-microbial-load-v1 from the served set, so it no longer has an interval
# to check here; its calibrated interval is still recorded in its retained artifact, and the
# withdrawal reason is asserted in test_research.py.
SERVED_INTERVAL_MODELS = (
    "lettuce-earth-growth-v1",
    "lettuce-earth-growth-v2",
    "mizuna-microbial-relative-load-v2",
)


@pytest.mark.parametrize("model_id", SERVED_INTERVAL_MODELS)
def test_every_served_interval_reports_its_measured_coverage(scientific_client, model_id):
    """No served model may state a nominal coverage without the achieved one."""
    models = {m["id"]: m for m in scientific_client.get("/api/models").json()["models"]}
    interval = models[model_id]["interval"]

    assert interval["empiricallyCalibrated"] is True
    assert interval["nominalCoverage"] == 0.9
    assert interval["empiricalCoverage"] >= interval["nominalCoverage"] - 0.02, (
        f"{model_id} states a 90% interval but achieved {interval['empiricalCoverage']}")
    assert interval["radius"] > 0
    assert interval["caveat"].strip(), "a calibrated interval still needs its caveat"


def test_recalibration_did_not_promote_any_model():
    """Fixing an interval is not a validation. Statuses must be unchanged.

    A model whose interval now covers still has whatever limitation made it
    experimental; conflating the two would be the exact overclaim this project is
    built to avoid.
    """
    # Status lives in the artifact, not the registry entry.
    registry = safedata.load(ROOT / "ml" / "artifacts" / "registry")
    statuses = {m["id"]: safedata.load(ROOT / m["artifact"]).get("status")
                for m in registry["models"]}
    # A withdrawn artifact keeps its exploratory status: removal is not a promotion either.
    assert statuses["mizuna-microbial-load-v1"] == "trained-exploratory"
    assert statuses["mizuna-microbial-relative-load-v2"] == "trained-exploratory"
    assert statuses["lettuce-earth-growth-v1"] == "trained-exploratory"
    assert statuses["lettuce-earth-growth-v2"] == "trained-exploratory"
    # The two rejected candidates must still be absent, not quietly restored.
    assert "radiation-dose-osd782-v1" not in statuses
    assert "gravity-reorientation-osd411-v1" not in statuses


def test_uncertainty_study_is_reproducible():
    """The coverage figures must be deterministic.

    They were not. `RandomForestRegressor(n_jobs=-1)` on the same seed and data
    returned coverage 0.878 on one run and 0.886 on the next, because parallel tree
    building sums split gains in a different order and one near-tie flips. A number
    that moves between identical runs cannot be the basis of a scientific claim, so
    the study pins n_jobs=1 and this test re-runs a slice of it to prove the output
    is stable.
    """
    import sys

    sys.path.insert(0, str(ROOT / "ml" / "training"))
    sys.path.insert(0, str(ROOT / "scripts"))
    from conformal import evaluate  # noqa: PLC0415
    from phase10_conformal_study import microbial_fit, microbial_relative  # noqa: PLC0415

    x, y, groups, strata, _ = microbial_relative()
    first = evaluate(microbial_fit, x, y, groups, alpha=0.10, outer_folds=3,
                     inner_folds=3, strata=strata, seed=42)
    second = evaluate(microbial_fit, x, y, groups, alpha=0.10, outer_folds=3,
                      inner_folds=3, strata=strata, seed=42)
    assert first["summary"] == second["summary"]


def test_scientific_claims_about_coverage_match_the_evidence_file():
    """The artifact's numbers must be the ones the study measured, not retyped."""
    study = safedata.load(EVALUATION / "phase10_conformal")
    decision = safedata.load(EVALUATION / "phase10_uncertainty_decision")

    for model_id, choice in decision["decisions"].items():
        adopted = choice["adopted"]
        measured = study["models"][model_id]["summary"][adopted]["empiricalCoverage"]
        assert choice["achievedCoverage"] == pytest.approx(measured, abs=1e-4), (
            f"{model_id}: decision says {choice['achievedCoverage']}, study measured {measured}")

    for model_id, comparison in decision["measured"].items():
        for method, values in comparison.items():
            measured = study["models"][model_id]["summary"][method]["empiricalCoverage"]
            assert values["coverage"] == pytest.approx(measured, abs=1e-4)


def test_intervals_are_calibrated_on_groups_not_rows():
    """The unit matters. Rows are tissues inside a pillow; a prediction is about a pillow."""
    decision = safedata.load(EVALUATION / "phase10_uncertainty_decision")
    for model_id in ("mizuna-microbial-load-v1", "mizuna-microbial-relative-load-v2"):
        assert decision["decisions"][model_id]["adopted"] == "group_level"

    registry = safedata.load(ROOT / "ml" / "artifacts" / "registry")
    for model in registry["models"]:
        if model["id"] in ("mizuna-microbial-load-v1", "mizuna-microbial-relative-load-v2"):
            artifact = safedata.load(ROOT / model["artifact"])
            assert "group" in artifact["uncertainty"]["exchangeabilityUnit"]
            # The row-level radius must still be visible, so the cost of the group
            # interval is auditable rather than hidden.
            assert artifact["uncertainty"]["rowLevelRadiusForComparison"] > 0
