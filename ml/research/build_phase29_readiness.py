#!/usr/bin/env python3
"""Build the Phase 29 workflow coverage matrix and readiness table.

    python3 ml/research/build_phase29_readiness.py [--check]

Phase 27 answered *which layers of a feature exist*. Phase 26 answered *what a claim may say*. This
phase adds a third question, because the product now has three workflows rather than a pile of
features: **can a user walk a scientific question from a source to a rendered result, and where
exactly does that walk stop?**

The document this writes is the successor to `PHASE27_FEATURE_COVERAGE_MATRIX.md`. It does not
overwrite it: the Phase 27 file is the record of what was true then, and rewriting it would erase
the evidence that the picture changed.

Two rules the builder enforces:

* every path named as evidence must exist, so a layer cannot be claimed on aspiration;
* a workflow is `complete` only when all ten layers are present and at least one test file exercises
  the path. A workflow with a UI and no tests, or tests and no UI, is `partial` and is labelled so.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TARGET_JSON = ROOT / "data" / "research" / "phase29" / "workflow_readiness.json"
TARGET_MD = ROOT / "docs" / "PHASE29_WORKFLOW_COVERAGE_MATRIX.md"
GENERATED_ON = "2026-11-10"

LAYERS = [
    ("data", "the dataset, artefact or documented assumption the calculation reads"),
    ("method", "the model or closed-form calculation itself"),
    ("service", "the backend module that assembles the result"),
    ("endpoint", "the HTTP route a client calls"),
    ("inputCheck", "request validation that rejects impossible inputs"),
    ("outputCheck", "validation that the result is coherent, or a stated absence"),
    ("uncertainty", "a quantified spread, or an explicit statement that none exists"),
    ("provenance", "the sources and their limits travel with the answer"),
    ("frontend", "a screen a user can reach and read"),
    ("tests", "automated tests covering the path"),
]

WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "water-demand",
        "order": 1,
        "title": "Water demand and irrigation scheduling",
        "answers": "How much water does this canopy want today, and what happens if it is irrigated "
                   "on this schedule?",
        "status": "complete",
        "evidenceClass": "reference-calculation",
        "phase29Change": ("an FAO-56 soil water balance added to the existing demand calculation: "
                          "depletion, stress coefficient, deep percolation, stress days and an "
                          "irrigation volume, all optional and all labelled as a reference "
                          "calculation"),
        "readinessTier": "research-ready",
        "whatItDoesNotDo": [
            "convert a transpiration deficit into a yield loss: that needs a crop yield-response "
            "factor this repository does not hold",
            "extrapolate the measured lettuce bench to tomato or radish: the study measured lettuce",
            "forecast weather: the schedule repeats the supplied single day across the cycle",
        ],
        "layers": {
            "data": ["data/processed/phase26/schroder2021_lettuce_et.csv",
                     "ml/evaluation/phase26_measured_et_validation.json"],
            "method": ["backend/app/simulation/et0_fao56.py",
                       "backend/app/simulation/water.py",
                       "backend/app/simulation/irrigation.py"],
            "service": ["backend/app/workflows/water_demand.py"],
            "endpoint": ["backend/app/routes/workflows.py"],
            "inputCheck": ["backend/app/routes/workflows.py"],
            "outputCheck": ["backend/app/workflows/water_demand.py"],
            "uncertainty": ["backend/app/simulation/irrigation.py",
                            "backend/app/workflows/water_demand.py"],
            "provenance": ["backend/app/workflows/water_demand.py"],
            "frontend": ["frontend/src/pages/modules/GuidedWorkflows.jsx"],
            "tests": ["backend/tests/test_phase29_workflows.py",
                      "backend/tests/test_phase28_workflows.py"],
        },
    },
    {
        "id": "harvest-prediction",
        "order": 2,
        "title": "Crop growth and harvest prediction",
        "answers": "What fresh mass per square metre does the served model predict from this DLI and "
                   "environment, and how much should that number be trusted?",
        "status": "complete",
        "evidenceClass": "trained-model",
        "phase29Change": ("the served model was re-examined rather than replaced: the pipeline was "
                          "audited, six candidates were scored on identical grouped folds, and the "
                          "winner was taken to the holdout once. It failed the unchanged 30 % "
                          "criterion at 39.28 % MAPE, so v3 stays in service and no v4 artefact "
                          "exists."),
        "readinessTier": "experimental",
        "whatItDoesNotDo": [
            "forecast: the independent holdout failed and the response says so above the number",
            "generalise outside the four training experiments: per-experiment bias runs from "
            "-635 to +505 g/m2",
            "guarantee interval coverage on a new site: the pooled out-of-fold 0.899 is descriptive, "
            "and coverage by experiment falls to 0.696 in EXP3",
        ],
        "layers": {
            "data": ["data/processed/lettuce_earth.csv"],
            "method": ["ml/artifacts/lettuce-earth-growth-v3.json",
                       "backend/app/workflows/harvest.py"],
            "service": ["backend/app/workflows/harvest.py"],
            "endpoint": ["backend/app/routes/workflows.py"],
            "inputCheck": ["backend/app/workflows/harvest.py"],
            "outputCheck": ["backend/app/workflows/harvest.py"],
            "uncertainty": ["ml/evaluation/phase29_interval_audit.json"],
            "provenance": ["ml/evaluation/phase29_harvest_final.json",
                           "ml/artifacts/registry.json"],
            "frontend": ["frontend/src/pages/modules/GuidedWorkflows.jsx"],
            "tests": ["backend/tests/test_phase29_model_evidence.py",
                      "backend/tests/test_phase28_workflows.py"],
        },
    },
    {
        "id": "light-stress",
        "order": 3,
        "title": "Light quality and environmental stress",
        "answers": "Under this spectral regime, what did the plants actually weigh and how did their "
                   "photosystems behave?",
        "status": "complete",
        "evidenceClass": "measured-observation",
        "phase29Change": "new workflow: a measured comparison over four spectral regimes",
        "readinessTier": "research-ready",
        "whatItDoesNotDo": [
            "predict anything: there is no model on this path, by design",
            "respond to PPFD, photoperiod, CO2, temperature or humidity: the experiment held them "
            "constant, so no control exists to move",
            "separate spectrum from density in t3: that regime changes both",
            "compute a composite stress score: the indices are reported side by side",
        ],
        "layers": {
            "data": ["data/processed/phase29/light_stress_harvest.csv",
                     "data/processed/phase29/light_stress_photosynthesis.csv",
                     "data/processed/phase29/light_stress_pigments.csv",
                     "data/processed/phase29/light_spectrum_treatments.csv",
                     "data/processed/phase29/light_stress_quality.json"],
            "method": ["backend/app/workflows/light_stress.py"],
            "service": ["backend/app/workflows/light_stress.py"],
            "endpoint": ["backend/app/routes/workflows.py"],
            "inputCheck": ["backend/app/routes/workflows.py"],
            "outputCheck": ["backend/app/workflows/light_stress.py"],
            "uncertainty": ["backend/app/workflows/light_stress.py"],
            "provenance": ["data/metadata/phase26_acquisition_manifest.json",
                           "data/processed/phase29/light_stress_quality.json"],
            "frontend": ["frontend/src/pages/modules/GuidedWorkflows.jsx"],
            "tests": ["backend/tests/test_phase29_workflows.py",
                      "backend/tests/test_phase29_datasets.py"],
        },
    },
]

FEATURES: list[dict[str, Any]] = [
    {"id": "measured-eta", "claim": "Predicted crop water use in litres per plant per day",
     "tier": "research-ready", "phase29": "unchanged; an irrigation schedule now sits on top of the "
     "demand calculation, and the bench is still one lettuce study"},
    {"id": "independent-et0", "claim": "The ET0 target is itself correct",
     "tier": "research-ready", "phase29": "unchanged; no new independent ET0 source was acquired"},
    {"id": "yield-labels", "claim": "Predicted harvest mass per plant",
     "tier": "research-ready",
     "phase29": "the generalisation attempt failed: holdout MAPE 39.28 % against a 30 % criterion, "
                "so the tier did not move and the failure is recorded"},
    {"id": "led-spectrum-response", "claim": "Response to specific LED spectra and photoperiods",
     "tier": "research-ready",
     "phase29": "moved from experimental to research-ready for the comparison only: a measured "
                "four-regime workflow now exists with intervals, tests and verified provenance. The "
                "response surface is still absent, and photoperiod still has no data."},
    {"id": "fractional-gravity", "claim": "Effect of Mars or lunar gravity on crop growth",
     "tier": "data-blocked", "phase29": "unchanged; no fractional-gravity dataset exists"},
    {"id": "substrate-water", "claim": "Root-zone water status in a hydroponic system",
     "tier": "data-blocked", "phase29": "unchanged; the irrigation balance models the root zone as a "
     "bucket, which is not a substrate measurement"},
    {"id": "sub-daily-weather", "claim": "Heat-stress and VPD excursion claims",
     "tier": "research-ready", "phase29": "unchanged"},
    {"id": "cultivar-metadata", "claim": "Cultivar-specific growth parameters",
     "tier": "experimental", "phase29": "unchanged; the new workflow is single-cultivar (Red Batavia)"},
    {"id": "imagery", "claim": "Plant health or growth stage from imagery",
     "tier": "data-blocked", "phase29": "unchanged"},
    {"id": "mission-energy", "claim": "Energy and mass cost of a described mission",
     "tier": "experimental", "phase29": "unchanged"},
    {"id": "nutrient-balance", "claim": "Nutrient solution management",
     "tier": "experimental", "phase29": "unchanged"},
    {"id": "long-run-climate", "claim": "Siting for a future climate",
     "tier": "data-blocked", "phase29": "unchanged"},
]

BLOCKED: list[dict[str, str]] = [
    {"id": "environmental-stress-response-surface",
     "capability": "A continuous response surface in spectral composition, PPFD, photoperiod, CO2, "
                   "temperature or humidity",
     "blockedBy": "no open dataset varies any of these over a yield response in lettuce; the search "
                  "that established this is data/research/phase29/environmental_stress_search.json",
     "consequence": "the workflow offers four named measured regimes and marks every other "
                    "environmental factor as unsupported, in the response as well as in the UI"},
    {"id": "fractional-gravity",
     "capability": "Growth or yield under lunar or Martian gravity",
     "blockedBy": "no fractional-gravity crop dataset exists in any open repository",
     "consequence": "the simulator refuses the claim and the factor remains data-blocked"},
    {"id": "yield-from-water-deficit",
     "capability": "Converting an irrigation deficit into a yield loss",
     "blockedBy": "no crop yield-response factor (Ky) exists in this repository",
     "consequence": "the irrigation schedule reports stress days and a relative transpiration "
                    "deficit, and explicitly declines the conversion"},
]


def verify(workflows: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for workflow in workflows:
        for layer, paths in workflow["layers"].items():
            for path in paths:
                if not (ROOT / path).exists():
                    missing.append(f"{workflow['id']}/{layer}: {path}")
    return missing


def summarise(workflow: dict[str, Any]) -> dict[str, Any]:
    present = {layer: ("present" if workflow["layers"].get(layer) else "absent") for layer, _ in LAYERS}
    complete = all(state == "present" for state in present.values())
    return {
        "layersPresent": sum(1 for state in present.values() if state == "present"),
        "layersTotal": len(LAYERS),
        "allLayersPresent": complete,
        "deliveredStatus": workflow["status"] if complete else "partial",
    }


def render(payload: dict[str, Any]) -> str:
    rows = payload["workflows"]
    out: list[str] = []
    out.append("# Phase 29 Workflow Coverage Matrix\n")
    out.append(f"Generated from `data/research/phase29/workflow_readiness.json` on "
               f"{payload['generatedOn']} by `ml/research/build_phase29_readiness.py`. Edit the "
               f"builder, not this file.\n")
    out.append(
        "This is the third question the project asks about its own features. Phase 26 asked *what "
        "may a claim say*, Phase 27 asked *which layers of a feature exist*, and this asks *can a "
        "user actually walk the question from a source to a rendered result, and where does the "
        "walk stop*. It supersedes `PHASE27_FEATURE_COVERAGE_MATRIX.md` without overwriting it: that "
        "file is the record of what was true then.\n"
    )
    out.append(
        "A workflow is **complete** only when all ten layers are present and a test file exercises "
        "the path. API-only and UI-only work is `partial` and is labelled so, because a route with "
        "no screen and a screen with no route are both unfinished products.\n"
    )

    complete = [row for row in rows if row["summary"]["deliveredStatus"] == "complete"]
    out.append("## Summary\n")
    out.append(f"**{len(complete)} of {len(rows)} workflows complete.** "
               f"Evidence classes: "
               + ", ".join(f"`{row['id']}` {row['evidenceClass']}" for row in rows) + ".\n")
    out.append("| # | Workflow | Answers | Evidence class | Layers | Status | Readiness |")
    out.append("|---|---|---|---|---|---|---|")
    for row in rows:
        out.append(
            f"| {row['order']} | **{row['title']}** `{row['id']}` | {row['answers']} | "
            f"`{row['evidenceClass']}` | {row['summary']['layersPresent']}/10 | "
            f"**{row['summary']['deliveredStatus']}** | `{row['readinessTier']}` |"
        )
    out.append("")

    out.append("## What each workflow does not do\n")
    out.append("The negative statements are part of the contract: a workflow that lists what it "
               "cannot do is auditable, one that only lists what it can do is not.\n")
    for row in rows:
        out.append(f"### {row['title']}\n")
        out.append(f"- **Changed in Phase 29:** {row['phase29Change']}")
        for limit in row["whatItDoesNotDo"]:
            out.append(f"- **Does not:** {limit}")
        out.append("")

    out.append("## Layer matrix\n")
    out.append("| Layer | " + " | ".join(f"`{row['id']}`" for row in rows) + " |")
    out.append("|---|" + "---|" * len(rows))
    for layer, meaning in LAYERS:
        cells = []
        for row in rows:
            paths = row["layers"].get(layer) or []
            cells.append("present" if paths else "**absent**")
        out.append(f"| `{layer}` — {meaning} | " + " | ".join(cells) + " |")
    out.append("")

    out.append("## Feature readiness\n")
    out.append("Tiers are the Phase 26 vocabulary, unchanged: `production-ready` needs an "
               "independent evaluation whose result matches the stated limits, `research-ready` "
               "needs measured data and a committed evaluation even when the level is not "
               "identifiable, `experimental` means internally evaluated only, `data-blocked` means "
               "no obtainable dataset can move it, and `unsupported` means the product must not make "
               "the claim at all.\n")
    out.append("| Feature | Claim | Tier | Phase 29 movement |")
    out.append("|---|---|---|---|")
    for feature in payload["features"]:
        out.append(f"| `{feature['id']}` | {feature['claim']} | `{feature['tier']}` | "
                   f"{feature['phase29']} |")
    out.append("")

    out.append("## Still blocked\n")
    out.append("These are not to-do items. Each is blocked by the absence of data, and the product "
               "states the consequence rather than approximating around it.\n")
    out.append("| Capability | Blocked by | What the user sees instead |")
    out.append("|---|---|---|")
    for item in payload["blocked"]:
        out.append(f"| **{item['capability']}** `{item['id']}` | {item['blockedBy']} | "
                   f"{item['consequence']} |")
    out.append("")

    out.append("## What was deliberately not built\n")
    out.append(
        "- **A response surface for environmental stress.** Four regimes with unequal replicate "
        "counts, of which two hold a fixed spectrum and one changes density as well, cannot support "
        "a continuous surface. A surface fitted through them would be a curve drawn through four "
        "points with a confound among them, and it would be presented as a prediction.\n"
        "- **A separate stress score.** Collapsing Fv'/Fm', PhiNO, NPQt and yield into one number "
        "requires weights nobody measured. The workflow reports the indices separately.\n"
        "- **A yield-loss conversion for irrigation deficits.** The FAO-56 water balance yields a "
        "relative transpiration deficit. Turning that into lost biomass needs a crop-specific "
        "yield-response factor, and inventing one would be the exact failure mode this project "
        "exists to avoid.\n"
        "- **A replacement harvest model.** The candidate improved cross-validated MAE by 4.6 % and "
        "still missed the holdout criterion by 9.3 points. Shipping it would have moved the "
        "headline number without moving the science.\n"
    )
    return "\n".join(out) + "\n"


def build() -> dict[str, Any]:
    missing = verify(WORKFLOWS)
    if missing:
        raise SystemExit("evidence paths missing:\n  " + "\n  ".join(missing))
    workflows = [{**row, "summary": summarise(row)} for row in WORKFLOWS]
    return {
        "phase": 29,
        "generatedBy": "ml/research/build_phase29_readiness.py",
        "generatedOn": GENERATED_ON,
        "supersedes": "data/research/phase27/feature_implementation_coverage.json",
        "layerDefinitions": {layer: meaning for layer, meaning in LAYERS},
        "counts": {
            "workflows": len(workflows),
            "complete": sum(1 for row in workflows if row["summary"]["deliveredStatus"] == "complete"),
            "measuredObservation": sum(1 for row in workflows
                                       if row["evidenceClass"] == "measured-observation"),
            "blockedCapabilities": len(BLOCKED),
        },
        "workflows": workflows,
        "features": FEATURES,
        "blocked": BLOCKED,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build()
    if args.check:
        if not TARGET_JSON.is_file() or not TARGET_MD.is_file():
            raise SystemExit("phase29 readiness artefacts are missing; run without --check")
        committed = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
        if committed != payload:
            raise SystemExit("workflow_readiness.json is stale")
        if TARGET_MD.read_text(encoding="utf-8") != render(committed):
            raise SystemExit("PHASE29_WORKFLOW_COVERAGE_MATRIX.md is stale")
        print(f"phase29 readiness up to date ({payload['counts']['complete']} workflows complete)")
        return 0
    TARGET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TARGET_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    TARGET_MD.write_text(render(payload), encoding="utf-8")
    print(f"wrote {TARGET_JSON.relative_to(ROOT)} and {TARGET_MD.relative_to(ROOT)}: "
          f"{payload['counts']['complete']} complete, {payload['counts']['blockedCapabilities']} blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
