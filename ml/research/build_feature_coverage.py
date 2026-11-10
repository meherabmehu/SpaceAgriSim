"""Build the feature implementation coverage matrix: which of the ten workflow layers exist.

    python3 ml/research/build_feature_coverage.py [--check]

The Phase 26 readiness audit answered *what a feature may claim*. This answers a different and
more practical question: **is there a complete workflow a user can actually walk through**, layer by
layer, from a scientific source to a rendered result.

Ten layers, in the order a request travels:

    data          a dataset, artefact or documented assumption the calculation reads
    method        the model or closed-form calculation itself
    service       the backend module that assembles the result
    endpoint      the HTTP route a client calls
    inputCheck    request validation that rejects impossible inputs
    outputCheck   validation that the result is physically coherent
    uncertainty   a quantified spread, or an explicit statement that none exists
    provenance    the sources and their limits travel with the answer
    frontend      a screen a user can reach and read
    tests         automated tests covering the path

A layer is `present` only when an artefact for it exists in the repository and is named here. The
builder verifies every named path, so the matrix cannot drift into aspiration.

The distinction that matters most in the output is between `absent` and `not-applicable`. A
missing layer is a gap; a layer that does not apply (no uncertainty layer for a deterministic unit
conversion) is not.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TARGET_JSON = ROOT / "data" / "research" / "phase27" / "feature_implementation_coverage.json"
TARGET_MD = ROOT / "docs" / "PHASE27_FEATURE_COVERAGE_MATRIX.md"
GENERATED_ON = "2026-11-10"

LAYERS = [
    ("data", "A dataset, artefact or documented assumption the calculation reads"),
    ("method", "The model or closed-form calculation"),
    ("service", "The backend module that assembles the result"),
    ("endpoint", "The HTTP route a client calls"),
    ("inputCheck", "Request validation that rejects impossible inputs"),
    ("outputCheck", "Validation that the result is physically coherent"),
    ("uncertainty", "A quantified spread, or an explicit statement that none exists"),
    ("provenance", "Sources and their limits travel with the answer"),
    ("frontend", "A screen a user can reach and read"),
    ("tests", "Automated tests covering the path"),
]

STATES = {
    "present": "implemented and verified in this repository",
    "partial": "implemented for some inputs or some of the layer's meaning",
    "absent": "missing, and usable if built",
    "not-applicable": "the layer does not apply to this kind of feature",
    "retired": "removed in Phase 30 - the capability is gone and a test proves it is gone",
}

# Every feature from the Phase 26 readiness audit, with the workflow layers as they actually stand.
FEATURES: list[dict[str, Any]] = [
    {
        "id": "measured-eta",
        "order": 1,
        "claim": "Measured crop water use, compared against the platform's demand",
        "readinessTier": "research-ready",
        "phase27Status": "completed",
        "layers": {
            "data": {"state": "present", "evidence": [
                "data/processed/phase26/schroder2021_lettuce_et.csv",
                "data/metadata/phase26_acquisition_manifest.json"],
                "note": "345 usable pot-days reduced to 11 treatment-mean dates, hash-verified"},
            "method": {"state": "present", "evidence": [
                "backend/app/simulation/water.py"],
                "note": "the shipped crop-relative demand path, called unmodified"},
            "service": {"state": "present", "evidence": [
                "backend/app/water_evidence.py"],
                "note": "assembles the benchmark, the comparison, the uncertainty and the limits"},
            "endpoint": {"state": "present", "evidence": [
                "backend/app/routes/research.py"],
                "note": "GET /api/water-use-evidence and POST /api/water-use-evidence/compare"},
            "inputCheck": {"state": "present", "evidence": [
                "backend/app/routes/research.py",
                "backend/tests/test_phase27_water_evidence.py"],
                "note": "extra fields forbidden, area and light scale bounded, unknown crop 422"},
            "outputCheck": {"state": "present", "evidence": [
                "backend/tests/test_phase27_water_evidence.py"],
                "note": ("the service must reproduce the independent pandas artefact's Spearman "
                         "and pair count; every curve point must be positive and inside [0,1]")},
            "uncertainty": {"state": "present", "evidence": [
                "ml/evaluation/phase26_measured_et_validation.json"],
                "note": ("between-pot spread, measured; plus the three denominators shown "
                         "side by side and the explicit statement that no confidence interval "
                         "exists")},
            "provenance": {"state": "present", "evidence": [
                "data/research/dataset_catalog.json"],
                "note": "DOI, licence, processed path and per-file SHA-256, with hashVerified computed"},
            "frontend": {"state": "present", "evidence": [
                "frontend/src/pages/modules/WaterEvidencePanel.jsx",
                "frontend/e2e/water-evidence.spec.js"],
                "note": "inside the existing simulation lab; verdict, curve, spread, denominators"},
            "tests": {"state": "present", "evidence": [
                "backend/tests/test_phase27_water_evidence.py",
                "frontend/e2e/water-evidence.spec.js"],
                "note": "24 backend tests and 4 browser tests across three viewports"},
        },
    },
    {
        "id": "independent-et0",
        "order": 2,
        "claim": "The ET0 target is itself correct",
        "readinessTier": "research-ready",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "present", "evidence": [
                "data/raw/nasa_power/power_tucson_us.json",
                "data/metadata/power_acquisition_manifest.json"],
                     "note": "POWER plus three cross-check sources"},
            "method": {"state": "present", "evidence": ["backend/app/simulation/et0_fao56.py"]},
            "service": {"state": "present", "evidence": ["backend/app/et0.py"]},
            "endpoint": {"state": "present", "evidence": ["backend/app/routes/research.py"],
                         "note": "GET /api/reference-et0/estimate and /model"},
            "inputCheck": {"state": "present", "evidence": ["backend/app/routes/research.py"]},
            "outputCheck": {"state": "partial", "evidence": ["ml/evaluation/et0_dataset_quality.json"],
                            "note": "input-quality checks exist; no physical-plausibility gate on output"},
            "uncertainty": {"state": "partial", "evidence": ["docs/ERA5_LAND_INDEPENDENT_VALIDATION.md"],
                            "note": "cross-source spread is reported; no confidence interval"},
            "provenance": {"state": "present", "evidence": ["data/research/dataset_catalog.json"]},
            "frontend": {"state": "present", "evidence": ["frontend/src/pages/modules/Methodology.jsx"],
                         "note": "shown as method documentation, not as a per-simulation result"},
            "tests": {"state": "present", "evidence": ["backend/tests/test_phase23_reference_et0.py"]},
        },
    },
    {
        "id": "yield-labels",
        "order": 3,
        "claim": "Predicted harvest mass per plant",
        "readinessTier": "removed",
        "phase27Status": "audited only",
        "phase30Status": "removed",
        "removal": (
            "Operational harvest forecasting was removed in Phase 30. A leave-one-study-out "
            "evaluation over 40 published lettuce studies returned 310.17 % MAPE against the "
            "unchanged 30 % criterion, with the mean baseline selected; the Phase 28 holdout had "
            "already returned 41.59 %. Phase 31 deleted the workflow module, all three endpoints and "
            "the catalogue entry; the measured-versus-model parity record and every failed "
            "evaluation remain committed as data."
        ),
        "layers": {
            "data": {"state": "retired", "evidence": ["data/processed/phase30/lettuce_multistudy.csv"],
                     "note": "the evaluation data is kept; the served model is not"},
            "method": {"state": "retired", "evidence": ["ml/evaluation/phase30_harvest_crossstudy.json"],
                       "note": "the model and its failed evaluation are recorded, not served"},
            "service": {"state": "retired", "evidence": ["docs/PHASE31_REMOVED_MODELS.md"],
                        "note": "the module itself was deleted in Phase 31; the record is kept"},
            "endpoint": {"state": "retired", "evidence": ["backend/app/routes/workflows.py"],
                         "note": "POST .../run answers 410; GET .../capability and .../parity remain"},
            "inputCheck": {"state": "retired", "evidence": []},
            "outputCheck": {"state": "retired", "evidence": []},
            "uncertainty": {"state": "retired", "evidence": [],
                            "note": "the interval used to span a factor of 29; it is no longer served"},
            "provenance": {"state": "present", "evidence": ["docs/PHASE31_REMOVED_MODELS.md"],
                           "note": "the removal reason and every failed evaluation stay readable"},
            "frontend": {"state": "retired", "evidence": ["frontend/src/pages/modules/GuidedWorkflows.jsx"],
                         "note": "the tab is gone; the record lives in docs/PHASE31_REMOVED_MODELS.md"},
            "tests": {"state": "present", "evidence": [
                "backend/tests/test_phase28_workflows.py",
                "backend/tests/test_phase30_removed_capabilities.py"],
                "note": "the tests assert the capability is unavailable, not that a screen exists"},
        },
    },
    {
        "id": "led-spectrum-response",
        "order": 4,
        "claim": "Response to specific LED spectra and photoperiods",
        "readinessTier": "experimental",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "present", "evidence": [
                "data/processed/phase29/light_stress_harvest.csv",
                "data/processed/phase30/cea_wheat_experiments.csv"],
                "note": "two measured datasets: four spectral regimes in lettuce, and 39 "
                        "controlled-environment wheat runs varying PPFD, photoperiod, CO2 and "
                        "temperature"},
            "method": {"state": "partial", "evidence": ["backend/app/workflows/light_stress.py",
                                                        "backend/app/workflows/cea_evidence.py"],
                       "note": "measured group comparison ships; the fitted response surface "
                               "failed its sealed holdout (297.46 % MAPE) and is not served"},
            "service": {"state": "absent", "evidence": []},
            "endpoint": {"state": "absent", "evidence": []},
            "inputCheck": {"state": "present", "evidence": ["backend/app/models/simulation.py"],
                           "note": "lightSpectrum is a Literal of three values"},
            "outputCheck": {"state": "not-applicable", "evidence": []},
            "uncertainty": {"state": "not-applicable", "evidence": []},
            "provenance": {"state": "present", "evidence": ["data/research/dataset_catalog.json"]},
            "frontend": {"state": "partial", "evidence": [
                "frontend/src/pages/modules/Laboratory.jsx"],
                "note": "the selector says it is an annotation and infers no response"},
            "tests": {"state": "present", "evidence": ["backend/tests/test_phase26_datasets.py"],
                      "note": "the dataset is tested; the feature is not implemented"},
        },
    },
    {
        "id": "nutrient-balance",
        "order": 5,
        "claim": "Nutrient solution management",
        "readinessTier": "experimental",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "partial", "evidence": [
                "data/raw/phase26/zenodo-halbert-2020-tomato-hydroponic/"],
                "note": "acquired and verified, not preprocessed into a table"},
            "method": {"state": "absent", "evidence": []},
            "service": {"state": "absent", "evidence": []},
            "endpoint": {"state": "absent", "evidence": []},
            "inputCheck": {"state": "not-applicable", "evidence": []},
            "outputCheck": {"state": "not-applicable", "evidence": []},
            "uncertainty": {"state": "not-applicable", "evidence": []},
            "provenance": {"state": "present", "evidence": ["data/research/dataset_catalog.json"]},
            "frontend": {"state": "absent", "evidence": []},
            "tests": {"state": "present", "evidence": ["backend/tests/test_phase26_datasets.py"],
                      "note": "acquisition is tested; no nutrient feature exists"},
        },
    },
    {
        "id": "sub-daily-weather",
        "order": 6,
        "claim": "Heat-stress and VPD excursion claims",
        "readinessTier": "research-ready",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "present", "evidence": [
                "data/raw/nasa_power/power_tucson_us.json"]},
            "method": {"state": "present", "evidence": ["backend/app/simulation/gas_exchange.py"],
                       "note": "VPD is computed per scenario from temperature and humidity"},
            "service": {"state": "present", "evidence": ["backend/app/simulation/serializers.py"]},
            "endpoint": {"state": "present", "evidence": ["backend/app/routes/simulation.py"],
                         "note": "environment.vaporPressureDeficitKpa on /api/simulate"},
            "inputCheck": {"state": "present", "evidence": ["backend/app/models/simulation.py"]},
            "outputCheck": {"state": "partial", "evidence": ["backend/tests/test_engine.py"]},
            "uncertainty": {"state": "absent", "evidence": [],
                            "note": "the reported VPD is a point value with no stated source error"},
            "provenance": {"state": "partial", "evidence": ["backend/app/simulation/serializers.py"],
                           "note": "method named; the weather source is not attached per value"},
            "frontend": {"state": "present", "evidence": [
                "frontend/src/pages/modules/Laboratory.jsx"]},
            "tests": {"state": "present", "evidence": ["backend/tests/test_engine.py"]},
        },
    },
    {
        "id": "cultivar-metadata",
        "order": 7,
        "claim": "Cultivar-specific growth parameters",
        "readinessTier": "experimental",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "absent", "evidence": [],
                     "note": "no experiment in-repo carries a cultivar label usable as an input"},
            "method": {"state": "partial", "evidence": ["backend/app/simulation/crops.py"],
                       "note": "three species profiles, no cultivar field"},
            "service": {"state": "present", "evidence": ["backend/app/simulation/crops.py"]},
            "endpoint": {"state": "present", "evidence": ["backend/app/routes/simulation.py"],
                         "note": "GET /api/crops lists the profiles"},
            "inputCheck": {"state": "present", "evidence": ["backend/app/models/simulation.py"]},
            "outputCheck": {"state": "not-applicable", "evidence": []},
            "uncertainty": {"state": "absent", "evidence": []},
            "provenance": {"state": "present", "evidence": ["backend/app/routes/simulation.py"],
                           "note": "'Phase 1 simulation assumptions, not measured NASA values'"},
            "frontend": {"state": "present", "evidence": [
                "frontend/src/pages/modules/Laboratory.jsx"]},
            "tests": {"state": "present", "evidence": ["backend/tests/test_crops.py"]},
        },
    },
    {
        "id": "mission-energy",
        "order": 8,
        "claim": "Energy and mass cost of a described mission",
        "readinessTier": "experimental",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "present", "evidence": [
                "backend/app/config/simulation_constants.py"],
                "note": "stated energy assumptions, not measurements"},
            "method": {"state": "present", "evidence": ["backend/app/simulation/engine.py"]},
            "service": {"state": "present", "evidence": ["backend/app/simulation/engine.py"]},
            "endpoint": {"state": "present", "evidence": ["backend/app/routes/simulation.py"]},
            "inputCheck": {"state": "present", "evidence": ["backend/app/models/simulation.py"]},
            "outputCheck": {"state": "partial", "evidence": ["backend/tests/test_engine.py"]},
            "uncertainty": {"state": "absent", "evidence": []},
            "provenance": {"state": "present", "evidence": ["backend/app/simulation/model_description.py"]},
            "frontend": {"state": "present", "evidence": ["frontend/src/pages/modules/Analytics.jsx"]},
            "tests": {"state": "present", "evidence": ["backend/tests/test_engine.py"]},
        },
    },
    {
        "id": "fractional-gravity",
        "order": 9,
        "claim": "Effect of Mars or lunar gravity on crop growth",
        "readinessTier": "removed",
        "phase27Status": "audited only",
        "phase30Status": "removed",
        "removal": (
            "The fractional-gravity response was removed in Phase 30: the growth-penalty "
            "coefficient, the input field, the presets, the impact step and the frontend readout "
            "are gone. No open dataset measures crop yield or biomass across fractional gravity - "
            "the ISS graded-gravity work measures gene expression and morphology, and a clinostat "
            "is not partial gravity - so the placeholder could not be replaced by evidence."
        ),
        "layers": {
            "data": {"state": "retired", "evidence": [],
                     "note": "no fractional-gravity growth dataset exists, and none was recoverable"},
            "method": {"state": "retired", "evidence": ["backend/app/simulation/factors.py"],
                       "note": "gravity_factor() no longer exists; a test asserts its absence"},
            "service": {"state": "retired", "evidence": ["backend/app/simulation/engine.py"],
                        "note": "the engine has no gravity term"},
            "endpoint": {"state": "retired", "evidence": ["backend/app/models/simulation.py"],
                         "note": "/api/simulate rejects a gravity field and names the decision"},
            "inputCheck": {"state": "present", "evidence": ["backend/app/models/simulation.py"],
                           "note": "extra='forbid' plus a model validator turn the field into a 422"},
            "outputCheck": {"state": "not-applicable", "evidence": []},
            "uncertainty": {"state": "not-applicable", "evidence": []},
            "provenance": {"state": "present", "evidence": ["backend/app/simulation/serializers.py"],
                           "note": "the radiation warning states that gravity is not modelled at all"},
            "frontend": {"state": "retired", "evidence": ["frontend/src/pages/MissionPlatform.jsx"],
                         "note": "the gravity control and its presets were removed; the component "
                                 "that carried them was dead code and was deleted in Phase 31"},
            "tests": {"state": "present", "evidence": [
                "backend/tests/test_phase27_engine_integrity.py",
                "backend/tests/test_phase30_removed_capabilities.py"],
                "note": "the tests assert the input is refused and the factor is absent"},
        },
    },
    {
        "id": "substrate-water",
        "order": 10,
        "claim": "Root-zone water status",
        "readinessTier": "data-blocked",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "absent", "evidence": [],
                     "note": "no root-zone water-potential time series exists"},
            "method": {"state": "partial", "evidence": ["backend/app/simulation/water.py"],
                       "note": "a single well-mixed store with a recovery-efficiency assumption"},
            "service": {"state": "present", "evidence": ["backend/app/simulation/water.py"]},
            "endpoint": {"state": "present", "evidence": ["backend/app/routes/simulation.py"]},
            "inputCheck": {"state": "present", "evidence": ["backend/app/models/simulation.py"]},
            "outputCheck": {"state": "partial", "evidence": ["backend/tests/test_water.py"]},
            "uncertainty": {"state": "absent", "evidence": []},
            "provenance": {"state": "present", "evidence": ["backend/app/simulation/serializers.py"]},
            "frontend": {"state": "present", "evidence": ["frontend/src/services/twinState.js"]},
            "tests": {"state": "present", "evidence": ["backend/tests/test_water.py"]},
        },
    },
    {
        "id": "imagery",
        "order": 11,
        "claim": "Plant health or growth stage from imagery",
        "readinessTier": "data-blocked",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "absent", "evidence": [],
                     "note": "no paired imagery and harvest labels; the catalogue's imagery "
                             "datasets are class E/F under their licences"},
            "method": {"state": "absent", "evidence": []},
            "service": {"state": "absent", "evidence": []},
            "endpoint": {"state": "absent", "evidence": []},
            "inputCheck": {"state": "not-applicable", "evidence": []},
            "outputCheck": {"state": "not-applicable", "evidence": []},
            "uncertainty": {"state": "not-applicable", "evidence": []},
            "provenance": {"state": "not-applicable", "evidence": []},
            "frontend": {"state": "absent", "evidence": []},
            "tests": {"state": "not-applicable", "evidence": []},
        },
    },
    {
        "id": "long-run-climate",
        "order": 12,
        "claim": "Siting for a future climate",
        "readinessTier": "data-blocked",
        "phase27Status": "audited only",
        "layers": {
            "data": {"state": "absent", "evidence": [],
                     "note": "the CMIP6 downscaled product is catalogued at class D and not acquired"},
            "method": {"state": "absent", "evidence": []},
            "service": {"state": "absent", "evidence": []},
            "endpoint": {"state": "absent", "evidence": []},
            "inputCheck": {"state": "not-applicable", "evidence": []},
            "outputCheck": {"state": "not-applicable", "evidence": []},
            "uncertainty": {"state": "not-applicable", "evidence": []},
            "provenance": {"state": "not-applicable", "evidence": []},
            "frontend": {"state": "absent", "evidence": []},
            "tests": {"state": "not-applicable", "evidence": []},
        },
    },
]

# Gaps found by the Phase 27 audit that are not attributable to a single feature. Each one is a
# concrete, buildable improvement with the evidence that it is real.
CROSS_CUTTING_GAPS = [
    {
        "id": "et0-parameter-not-in-frontend",
        "finding": ("POST /api/simulate accepts et0MmPerDay and cropCoefficient, and the whole "
                    "reference-ET0 water path is reachable only by hand-crafting an HTTP request. "
                    "No frontend control sets either field."),
        "evidence": ["backend/app/models/simulation.py",
                     "frontend/src/services/defaultConfig.js"],
        "severity": "major",
        "why": "a validated-by-construction capability that no user can reach",
        "feasibility": "high: two optional request fields and one control group",
    },
    {
        "id": "no-per-prediction-interval",
        "finding": ("The harvest models report leave-one-experiment-out error as a single number. "
                    "No individual prediction carries a range, so a user cannot tell whether a "
                    "given scenario is inside or outside the model's envelope."),
        "evidence": ["ml/evaluation/lettuce_splits.json"],
        "severity": "major",
        "why": "the platform's central claim is prediction, and a point estimate hides its own error",
        "feasibility": "medium: quantile regression or a fold-based empirical interval",
    },
    {
        "id": "no-out-of-distribution-warning",
        "finding": ("Model endpoints validate types and ranges but not whether an input lies "
                    "outside the training envelope. A prediction at day 60 with 1000 umol/m2/s "
                    "returns a number with no warning."),
        "evidence": ["backend/app/routes/research.py"],
        "severity": "major",
        "why": "an extrapolated prediction is indistinguishable from an interpolated one to a user",
        "feasibility": "high: the training envelope is in the split artefacts",
    },
    {
        "id": "water-paths-unarbitrated",
        "finding": ("Two water demand paths ship - crop-relative and ET0-reference - and the "
                    "response names which one ran but does not say they cannot both be right."),
        "evidence": ["backend/app/simulation/serializers.py",
                     "ml/evaluation/phase26_measured_et_validation.json"],
        "severity": "major",
        "why": "a ~60 % difference between two live calculations with no arbiter",
        "feasibility": "done for the evidence half in Phase 27; the arbiter needs per-day weather",
    },
    {
        "id": "comparison-is-parameter-only",
        "finding": ("The comparison module compares parameter sets. The measured benchmark cannot "
                    "be included in a comparison because it is not a scenario, and there is no "
                    "export of the comparison with its provenance."),
        "evidence": ["backend/app/routes/workspace.py"],
        "severity": "minor",
        "why": "users comparing scenarios cannot see how any of them relates to measurement",
        "feasibility": "high",
    },
    {
        "id": "units-not-machine-readable",
        "finding": ("Units appear in field names (`waterUsed` is litres, `co2Removed` grams) and in "
                    "descriptions, but no response field carries a unit object, so a client must "
                    "read prose to know what it has."),
        "evidence": ["backend/app/models/simulation.py"],
        "severity": "minor",
        "why": "the stated goal includes consistent units across the platform",
        "feasibility": "medium: an additive `units` map without breaking existing clients",
    },
]


def _catalogue_ok() -> dict[str, Any]:
    return json.loads((ROOT / "data" / "research" / "phase26" / "feature_readiness.json")
                      .read_text(encoding="utf-8")) if (
        ROOT / "data" / "research" / "phase26" / "feature_readiness.json").is_file() else {}


def validate() -> list[str]:
    problems: list[str] = []
    readiness = {feature["id"]: feature["tier"]
                 for feature in _catalogue_ok().get("features", [])}
    for feature in FEATURES:
        if feature["id"] not in readiness:
            problems.append(f"{feature['id']}: not in the Phase 26 readiness audit")
            continue
        if readiness[feature["id"]] != feature["readinessTier"]:
            problems.append(f"{feature['id']}: tier differs from the readiness audit "
                            f"({feature['readinessTier']} vs {readiness[feature['id']]})")
        for layer, _ in LAYERS:
            entry = feature["layers"].get(layer)
            if entry is None:
                problems.append(f"{feature['id']}: layer {layer} missing entirely")
                continue
            if entry["state"] not in STATES:
                problems.append(f"{feature['id']}.{layer}: unknown state {entry['state']}")
            if entry["state"] == "present" and not entry["evidence"]:
                problems.append(f"{feature['id']}.{layer}: present with no evidence path")
            for path in entry["evidence"]:
                if not (ROOT / path).exists():
                    problems.append(f"{feature['id']}.{layer}: missing path {path}")
    return problems


def summarise() -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {layer: {} for layer, _ in LAYERS}
    for feature in FEATURES:
        for layer, _ in LAYERS:
            state = feature["layers"][layer]["state"]
            counts[layer][state] = counts[layer].get(state, 0) + 1
    complete = [feature["id"] for feature in FEATURES
                if all(feature["layers"][layer]["state"] in ("present", "not-applicable")
                       for layer, _ in LAYERS)]
    return {"byLayer": counts, "completeWorkflows": complete,
            "features": len(FEATURES)}


def render(payload: dict[str, Any]) -> str:
    features = payload["features"]
    summary = payload["summary"]
    lines = [
        "# Phase 27 — Feature Implementation Coverage Matrix",
        "",
        f"Generated from `data/research/phase27/feature_implementation_coverage.json` on "
        f"{payload['generatedOn']} by `ml/research/build_feature_coverage.py`. Edit the JSON, not "
        "this file.",
        "",
        "Phase 26 asked what each feature may **claim**. This asks whether a user can actually "
        "**walk through** it: ten layers, from a scientific source to a rendered result. A layer "
        "is `present` only when a named artefact for it exists in the repository and the builder "
        "verified the path.",
        "",
        "| State | Meaning |",
        "| --- | --- |",
    ]
    for state, meaning in STATES.items():
        lines.append(f"| `{state}` | {meaning} |")

    lines += ["", "## Layer coverage", "",
              "| Layer | present | partial | absent | n/a |", "| --- | --- | --- | --- | --- |"]
    for layer, description in LAYERS:
        counts = summary["byLayer"][layer]
        lines.append(f"| `{layer}` — {description} | {counts.get('present', 0)} | "
                     f"{counts.get('partial', 0)} | {counts.get('absent', 0)} | "
                     f"{counts.get('not-applicable', 0)} |")

    lines += ["", "## Per feature", ""]
    header = "| # | Feature | Tier | " + " | ".join(layer for layer, _ in LAYERS) + " |"
    lines.append(header)
    lines.append("| " + " | ".join(["---"] * (len(LAYERS) + 3)) + " |")
    for feature in sorted(features, key=lambda item: item["order"]):
        cells = [feature["layers"][layer]["state"][:4] for layer, _ in LAYERS]
        marker = " ✅" if feature["phase27Status"] == "completed" else ""
        lines.append(f"| {feature['order']} | {feature['claim']}{marker} | "
                     f"`{feature['readinessTier']}` | " + " | ".join(cells) + " |")

    lines += [
        "",
        f"**{len(summary['completeWorkflows'])} of {summary['features']} features have every "
        f"applicable layer implemented:** "
        + ", ".join(f"`{feature}`" for feature in summary["completeWorkflows"]) + ".",
        "",
        "The ✅ marks the one feature Phase 27 completed end to end. The layer codes are truncated "
        "to four characters; read the per-feature sections below for the meaning.",
        "",
        "## Per-feature detail",
    ]
    for feature in sorted(features, key=lambda item: item["order"]):
        lines += ["", f"### {feature['order']}. {feature['claim']}", "",
                  f"Readiness tier: `{feature['readinessTier']}` · Phase 27: {feature['phase27Status']}", "",
                  "| Layer | State | Note |", "| --- | --- | --- |"]
        for layer, _ in LAYERS:
            entry = feature["layers"][layer]
            lines.append(f"| `{layer}` | `{entry['state']}` | {entry.get('note', '')} |")

    lines += ["", "## Cross-cutting gaps found by the audit", "",
              "These are not attributable to a single feature. Each names its evidence, its "
              "severity, why it matters and how hard it is to build.", "",
              "| Gap | Severity | Finding | Why | Feasibility |",
              "| --- | --- | --- | --- | --- |"]
    for gap in payload["crossCuttingGaps"]:
        lines.append(f"| `{gap['id']}` | {gap['severity']} | {gap['finding']} | {gap['why']} | "
                     f"{gap['feasibility']} |")

    lines += [
        "",
        "## What the pattern says",
        "",
        "The audit's most useful finding is not any single `absent` cell. It is that the layers "
        "which are systematically weakest are `uncertainty` and `outputCheck` - the two that stand "
        "between a number and a defensible number. Data, method, service, endpoint and tests are "
        "largely present; what is missing is the layer that says how wrong a result might be and "
        "the layer that refuses to return an incoherent one.",
        "",
        "That is a product problem rather than a data problem, which is why it is ranked above "
        "acquiring more datasets.",
        "",
    ]
    return "\n".join(lines)


def build() -> dict[str, Any]:
    problems = validate()
    if problems:
        raise SystemExit("coverage audit refused:\n  " + "\n  ".join(problems))
    return {
        "phase": 27,
        "generatedBy": "ml/research/build_feature_coverage.py",
        "generatedOn": GENERATED_ON,
        "layerDefinitions": dict(LAYERS),
        "stateDefinitions": STATES,
        "summary": summarise(),
        "features": FEATURES,
        "crossCuttingGaps": CROSS_CUTTING_GAPS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = build()
    if args.check:
        if not TARGET_JSON.is_file() or not TARGET_MD.is_file():
            print("MISSING coverage files; run without --check")
            return 1
        committed = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
        if committed["features"] != payload["features"]:
            print("STALE JSON: the builder's feature list differs from the committed one")
            return 1
        if TARGET_MD.read_text(encoding="utf-8") != render(committed):
            print("STALE markdown: re-render from the JSON")
            return 1
        print(f"coverage up to date ({len(FEATURES)} features)")
        return 0

    TARGET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TARGET_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    TARGET_MD.write_text(render(payload), encoding="utf-8")
    print(f"wrote {TARGET_MD.relative_to(ROOT)}: {len(FEATURES)} features, "
          f"{len(payload['summary']['completeWorkflows'])} complete workflows, "
          f"{len(CROSS_CUTTING_GAPS)} cross-cutting gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
