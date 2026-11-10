"""Workflow B — harvest forecasting, retired in Phase 30; what remains is the evidence.

Why there is no forecast here any more
-------------------------------------
Phase 28 shipped this workflow as a forecast: a lettuce yield model wrapped in inputs, comparison and
a conformal interval. It was honest about the model's independent holdout failing — 41.6 % MAPE
against a 30 % criterion fixed in advance — and served the number anyway with the failure printed next
to it.

Phase 30 set out to close exactly that gap: acquire genuinely independent harvest data, harmonise it,
and re-evaluate with study-aware grouping. Two evaluations were completed on new, licensed,
hash-verified data:

1. **Published lettuce studies** (53 treatment means from 40 studies, Zenodo 14640245). Leave-one-
   study-out over the development studies, then a single scoring pass on eight studies sealed by
   SHA-256 of the study key and never used for selection. The selected model — which turned out to be
   the mean baseline, because no candidate beat it out of fold — scored a holdout MAPE above 300 %,
   with R² below zero.
2. **A controlled-environment wheat series** (36 experiments with a logged environment, Zenodo
   17764612). A response surface was attempted and scored once on six sealed experiments; it missed
   the same criterion by an order of magnitude (297 % MAPE).

Neither met the criterion, and the failure is not a tuning problem: published treatment means move by
more than an order of magnitude between studies growing the same species, because study-level choices —
cultivar, substrate, density, harvest definition, dry versus fresh basis — dominate the environmental
signal a model of this kind can see. The corpus cannot support the claim, so Phase 30 applies the
acceptance rule as written and **removes operational forecasting**.

What a user gets instead
------------------------
`capability()` reports that forecasting is unavailable, why, and carries every evaluation behind that
decision. `parity()` returns the measured-versus-exploratory-model comparison the artifact recorded,
labelled as a record rather than a validation. The research artifacts (`ml/artifacts/*`,
`ml/evaluation/phase30_*.json`) stay in the repository as the record of what was tried and scored; no
workflow serves them as forecasts.

The single-model research endpoints `/api/predict/lettuce-earth-growth-v2` and `-v3` remain the
exploratory research surface they always were and now carry an explicit `operationalForecast: false`
flag. No product surface treats their output as a harvest forecast.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import research
from app.workflows import units

MODEL_ID = "lettuce-earth-growth-v3"
RECORD_MODEL_ID = "lettuce-earth-growth-v2"
CROPS = ("lettuce",)

ROOT = Path(__file__).resolve().parents[3]
CROSSSTUDY = ROOT / "ml" / "evaluation" / "phase30_harvest_crossstudy.json"

ACCEPTANCE_CRITERION_PCT = 30.0

EVIDENCE_LAYERS = [
    {"kind": "measured-observation",
     "what": "1 648 destructive harvest weights over four WUR lettuce experiments — training and "
              "leave-one-experiment-out validation",
     "isMeasurement": True,
     "provenance": "WUR-lettuce, CC-BY-4.0, DOI 10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1"},
    {"kind": "measured-observation",
     "what": "six PeerJ 17085 observations (Baby Cos, Green Oak) — development data, not validation",
     "isMeasurement": True,
     "provenance": "PeerJ 12:e17085, CC BY 4.0"},
    {"kind": "measured-observation",
     "what": "one Touliatos et al. 2016 observation — the independent holdout, scored once, failed",
     "isMeasurement": True,
     "provenance": "Food and Energy Security 5(3):184-191, DOI 10.1002/fes3.83"},
    {"kind": "measured-observation",
     "what": "53 published treatment means from 40 lettuce studies, harmonised in Phase 30 and used "
              "for leave-one-study-out and an eight-study sealed holdout",
     "isMeasurement": True,
     "provenance": "Zenodo 14640245, CC BY 4.0, sha256-verified; "
                   "data/processed/phase30/lettuce_multistudy.csv"},
    {"kind": "measured-observation",
     "what": "719 sub-plot harvest weights over 39 controlled-environment wheat experiments (36 with "
              "yield plus environment), used for the Phase 30 wheat response evaluation",
     "isMeasurement": True,
     "provenance": "Zenodo 17764612, CC BY 4.0, sha256-verified; "
                   "data/processed/phase30/cea_wheat_subplots.csv"},
]


@lru_cache(maxsize=2)
def _model(model_id: str) -> dict[str, Any]:
    return research.load_model(model_id)


@lru_cache(maxsize=1)
def _crossstudy() -> dict[str, Any]:
    return json.loads(CROSSSTUDY.read_text(encoding="utf-8"))


def evaluations() -> list[dict[str, Any]]:
    """Every independent evaluation of a lettuce-harvest model here, failures first.

    Numbers are read from the artifacts, never retyped: if an artifact is regenerated the response
    changes with it.
    """
    v3 = _model(MODEL_ID).get("validation") or {}
    v2 = _model(RECORD_MODEL_ID)
    independent = v3.get("independent") or {}
    development_v3 = v3.get("development") or {}
    cross = _crossstudy()
    return [
        {
            "id": "phase30-leave-one-study-out",
            "phase": 30,
            "data": ("53 published treatment means from 40 studies (Zenodo 14640245)"),
            "protocol": ("leave-one-study-out over the development studies, then a single scoring "
                         "pass on eight studies sealed by SHA-256 of the study key"),
            "independent": True,
            "countsAsValidation": True,
            "metrics": cross["holdout"]["metrics"],
            "medianStudyAPE": cross["holdout"].get("medianStudyAPE"),
            "acceptanceCriterionPct": cross["holdout"]["acceptanceCriterionPct"],
            "passed": cross["holdout"]["passed"],
            "selectedModel": cross["selected"],
            "verdict": ("failed by a wide margin. Out of fold, no candidate beat the mean baseline, "
                        "so the selected model is the baseline itself; its sealed holdout error is "
                        f"{cross['holdout']['metrics']['MAPE']:.1f} % MAPE and its interval spans a "
                        f"factor of {cross['interval']['multiplicativeWidth']:.1f}. A point forecast "
                        "that wide is not a forecast."),
            "artifact": "ml/evaluation/phase30_harvest_crossstudy.json",
        },
        {
            "id": "phase28-touliatos-holdout",
            "phase": 28,
            "data": "one independent greenhouse observation (Touliatos et al. 2016)",
            "protocol": "single scoring pass, criterion fixed in advance",
            "independent": True,
            "countsAsValidation": True,
            "metrics": independent.get("metrics"),
            "acceptanceCriterionPct": independent.get("acceptanceCriterionPct"),
            "passed": independent.get("passed"),
            "verdict": independent.get("verdict"),
            "artifact": "ml/artifacts/lettuce-earth-growth-v3.json",
        },
        {
            "id": "phase28-v3-development",
            "phase": 28,
            "data": "six PeerJ 17085 observations, used to choose the daily-light-integral feature",
            "protocol": "development check — informed model selection, so it cannot validate",
            "independent": False,
            "countsAsValidation": False,
            "metrics": development_v3.get("metrics"),
            "acceptanceCriterionPct": None,
            "passed": None,
            "verdict": ("recorded for completeness only. These observations chose the feature set, so "
                        "scoring them again is not validation."),
            "artifact": "ml/artifacts/lettuce-earth-growth-v3.json",
        },
        {
            "id": "phase27-v2-internal",
            "phase": 27,
            "data": "the same four WUR experiments, leave-one-experiment-out — the retired model",
            "protocol": "internal cross-validation on the training experiments, not an external check",
            "independent": False,
            "countsAsValidation": False,
            "metrics": v2.get("metrics"),
            "acceptanceCriterionPct": None,
            "passed": None,
            "verdict": ("the failure that motivated v3: mass per plant from PPFD alone, "
                        "overpredicting the six PeerJ observations by a median of 3.2x, because "
                        "photoperiod and density were missing from its inputs."),
            "artifact": "ml/artifacts/lettuce-earth-growth-v2.json",
        },
    ]


def capability() -> dict[str, Any]:
    """The honest state of workflow B: no forecast, with the evidence for that decision."""
    return {
        "workflow": "harvest-prediction",
        "title": "Crop growth and harvest prediction (lettuce)",
        "status": "unavailable",
        "capabilityAvailable": False,
        "operationalForecast": False,
        "isSimulation": False,
        "removedInPhase": 30,
        "crop": "lettuce",
        "reason": ("No harvest model in this repository met the 30 % independent-error criterion. "
                   "The Phase 30 evaluation on studies the model had never seen missed it by more "
                   "than a factor of ten, and the controlled-environment wheat response surface "
                   "missed it by an order of magnitude. Phase 30 removed the forecast rather than "
                   "keep presenting a failed model as a product."),
        "acceptanceCriterionPct": ACCEPTANCE_CRITERION_PCT,
        "evaluations": evaluations(),
        "removed": [
            "POST /api/workflows/harvest-prediction/run — the forecast endpoint",
            "the harvest forecast inputs and scenario comparison in the guided workflow interface",
            "the claim that a lettuce harvest can be predicted for a stated environment",
        ],
        "whatRemains": [
            {"what": "measured-versus-model record for the external studies",
             "endpoint": "GET /api/workflows/harvest-prediction/parity"},
            {"what": "the exploratory artifact and its failed holdout, as a research record",
             "endpoint": "POST /api/predict/lettuce-earth-growth-v3 (operationalForecast: false)"},
            {"what": "measured controlled-environment and light-quality evidence for other crops",
             "endpoint": "GET /api/workflows/light-stress/capability"},
        ],
        "evidenceLayers": EVIDENCE_LAYERS,
        "note": ("A user who needs a yield number for a specified environment must measure it. This "
                 "platform will not produce one, and the evaluations above are why."),
        "units": units.block(measuredG="g/plant", predictedG="g/plant", ratio="dimensionless"),
    }


def parity() -> dict[str, Any]:
    """Measured vs the exploratory model, from the two external studies the artifact records.

    Served straight from the artifact rather than recomputed: recomputing would make every page load a
    second model-selection opportunity, and the numbers a reader sees must be the numbers the artifact
    was accepted or rejected on. This is a record of a comparison, not a validation.
    """
    model = _model(MODEL_ID)
    validation = model.get("validation") or {}
    development = validation.get("development") or {}
    independent = validation.get("independent") or {}
    points = []
    for row in development.get("scored") or []:
        points.append({
            "id": row["id"], "set": "development", "countsAsValidation": False,
            "measuredG": row["measuredG"], "predictedG": row["predictedG"],
            "ratio": row["ratio"], "ppfdUmol": row.get("ppfdUmol"),
        })
    for row in independent.get("scored") or []:
        points.append({
            "id": row["id"], "set": "independent", "countsAsValidation": True,
            "measuredG": row["measuredG"], "predictedG": row["predictedG"],
            "ratio": row["ratio"], "ppfdUmol": row.get("ppfdUmol"),
            "domainViolations": row.get("domainViolations"),
        })
    cross = _crossstudy()
    return {
        "workflow": "harvest-prediction",
        "operationalForecast": False,
        "modelId": MODEL_ID,
        "points": points,
        "developmentMetrics": development.get("metrics"),
        "independentMetrics": independent.get("metrics"),
        "acceptanceCriterionPct": independent.get("acceptanceCriterionPct"),
        "passed": independent.get("passed"),
        "crossStudy": {
            "studies": cross["holdout"]["studies"],
            "metrics": cross["holdout"]["metrics"],
            "acceptanceCriterionPct": cross["holdout"]["acceptanceCriterionPct"],
            "passed": cross["holdout"]["passed"],
        },
        "units": units.block(measuredG="g/plant", predictedG="g/plant", ratio="dimensionless"),
        "caveat": ("Seven points in total from the artifact, two cultivars, two facilities, plus the "
                   "Phase 30 cross-study result on eight further studies. This is the whole external "
                   "evidence base for the model, and it is not enough to call a model validated. The "
                   "ratios are all above 1: the model overpredicts in both studies."),
    }
