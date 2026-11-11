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

# ---------------------------------------------------------------------------------------------
# The twelve features, scored against the code that exists now.
#
# Phase 27 wrote this table as an audit of gaps. Phase 32 closes it: a feature is either complete
# at the level it claims, served as a measured comparison only, or removed from the product. Every
# `evidence` path below is checked by `validate()`, so a layer cannot be marked `present` because
# somebody remembered building it.
# ---------------------------------------------------------------------------------------------

def _layer(state: str, note: str, *evidence: str) -> dict:
    return {"state": state, "note": note, "evidence": list(evidence)}


def _retired(note: str, *evidence: str) -> dict:
    return _layer("retired", note, *evidence)


def _na(note: str = "") -> dict:
    return {"state": "not-applicable", "note": note, "evidence": []}


PHASE32_TESTS = "backend/tests/test_phase32_removed_features.py"


def _removed_feature(order: int, feature_id: str, claim: str, why: str,
                     provenance: str, tests: list[str],
                     extra: dict | None = None) -> dict:
    """A feature that is not in the product, described as absent in every layer.

    `provenance` and `tests` are the two layers that legitimately survive a removal: the record
    of why it went, and the test that proves it stayed gone. Everything else is `retired`, and an
    input/output/uncertainty layer is `not-applicable` because there is no result to check.
    """
    layers = {
        "data": _retired("no obtainable dataset supports this claim", provenance),
        "method": _retired("no implementation is served"),
        "service": _retired("no module assembles a result"),
        "endpoint": _retired("no route accepts it"),
        "inputCheck": _na("no request schema accepts these inputs"),
        "outputCheck": _na("no result is produced"),
        "uncertainty": _na("no result is produced"),
        "provenance": _layer("present", why, provenance),
        "frontend": _retired("no control, page or panel presents it"),
        "tests": _layer("present", "the removal is asserted, not assumed", *tests),
    }
    if extra:
        layers.update(extra)
    return {"id": feature_id, "order": order, "claim": claim,
            "readinessTier": "removed", "phase27Status": "removed",
            "phase32Disposition": "removed", "removal": why, "layers": layers}


FEATURES: list[dict[str, Any]] = [
    {
        "id": "measured-eta",
        "order": 1,
        "claim": "Measured crop water use, compared against the platform's demand",
        "readinessTier": "research-ready",
        "phase27Status": "completed",
        "phase32Disposition": "complete",
        "layers": {
            "data": _layer("present",
                           "345 usable pot-days reduced to 11 treatment-mean dates, hash-verified",
                           "data/processed/phase26/schroder2021_lettuce_et.csv",
                           "data/metadata/phase26_acquisition_manifest.json"),
            "method": _layer("present", "the shipped crop-relative demand path, called unmodified",
                             "backend/app/simulation/water.py"),
            "service": _layer("present",
                              "assembles the benchmark, the comparison, the uncertainty and the limits",
                              "backend/app/water_evidence.py"),
            "endpoint": _layer("present",
                               "GET /api/water-use-evidence and POST /api/water-use-evidence/compare",
                               "backend/app/routes/research.py"),
            "inputCheck": _layer("present",
                                 "extra fields forbidden, area and light scale bounded, unknown crop 422",
                                 "backend/app/routes/research.py",
                                 "backend/tests/test_phase27_water_evidence.py"),
            "outputCheck": _layer("present",
                                  "the service must reproduce the independent pandas artefact's "
                                  "Spearman and pair count; every curve point must be positive and "
                                  "inside [0,1]; the surface refuses a level claim",
                                  "backend/tests/test_phase27_water_evidence.py",
                                  "backend/tests/test_phase32_output_checks.py"),
            "uncertainty": _layer("present",
                                  "between-pot spread, measured; the three denominators shown side "
                                  "by side and an explicit statement that no confidence interval exists",
                                  "ml/evaluation/phase26_measured_et_validation.json"),
            "provenance": _layer("present",
                                 "DOI, licence, processed path and per-file SHA-256, hashVerified computed",
                                 "data/research/dataset_catalog.json"),
            "frontend": _layer("present",
                               "inside the existing simulation lab; verdict, curve, spread, denominators",
                               "frontend/src/pages/modules/WaterEvidencePanel.jsx",
                               "frontend/e2e/water-evidence.spec.js"),
            "tests": _layer("present", "backend suite and four browser tests across three viewports",
                            "backend/tests/test_phase27_water_evidence.py",
                            "frontend/e2e/water-evidence.spec.js"),
        },
    },
    {
        "id": "independent-et0",
        "order": 2,
        "claim": "The ET0 target is itself correct",
        "readinessTier": "research-ready",
        "phase27Status": "completed",
        "phase32Disposition": "complete",
        "layers": {
            "data": _layer("present",
                           "FAO-56 published worked examples, transcribed with their source pages",
                           "backend/tests/test_phase23_reference_et0.py"),
            "method": _layer("present",
                             "FAO-56 Penman-Monteith with Hargreaves-Samani as the declared fallback; "
                             "the fitted emulator was withdrawn in Phase 31",
                             "backend/app/et0.py", "backend/app/simulation/et0_fao56.py"),
            "service": _layer("present", "one module selects the method and reports why",
                              "backend/app/et0.py"),
            "endpoint": _layer("present",
                               "GET /api/reference-et0/estimate, GET /api/reference-et0/model, and "
                               "the Phase 32 validators GET/POST /api/reference-et0/validate",
                               "backend/app/routes/research.py"),
            "inputCheck": _layer("present", "physical bounds on every weather input; 422 when vapour "
                                            "pressure is undefined; extra fields rejected",
                                 "backend/app/routes/research.py",
                                 "backend/tests/test_phase32_output_checks.py"),
            "outputCheck": _layer("present",
                                  "Phase 32: the result carries a plausibility verdict - 0 <= ET0 <= "
                                  "30 mm/day and tmax >= tmin - returned rather than clamped",
                                  "backend/app/et0.py",
                                  "backend/tests/test_phase32_output_checks.py"),
            "uncertainty": _layer("present",
                                  "the response states that no measured-ET0 benchmark is bundled, that "
                                  "no interval is computed, and that the weather inputs are the caller's",
                                  "backend/app/et0.py"),
            "provenance": _layer("present",
                                 "method selection, missing inputs, weather provenance and the "
                                 "computed-not-measured class travel with the number",
                                 "backend/app/routes/research.py"),
            "frontend": _layer("present",
                               "the water-demand workflow shows daily ET0, its primary method and "
                               "per-scenario deltas",
                               "frontend/src/pages/modules/GuidedWorkflows.jsx",
                               "frontend/e2e/guided-workflows.spec.js"),
            "tests": _layer("present", "worked examples, fallback behaviour and the output gate",
                            "backend/tests/test_phase23_reference_et0.py",
                            "backend/tests/test_phase25_et0_validation.py",
                            "backend/tests/test_phase32_output_checks.py"),
        },
    },
    _removed_feature(
        3, "yield-labels", "Predicted harvest mass per plant",
        "Withdrawn in Phase 31. Lettuce v3 returned 41.6 % on its independent holdout against a "
        "pre-registered 30 % criterion, and mizuna-harvest-v1 held a held-out R2 of -0.333. The "
        "cards stay, with their failed evaluations, as non-serving records.",
        "docs/PHASE31_REMOVED_MODELS.md",
        ["backend/tests/test_phase32_no_forecast.py",
         "backend/tests/test_phase30_removed_capabilities.py"],
        {"provenance": _layer("present",
                              "the removal register, the failed evaluations and the retired card all "
                              "stay committed; every model passage the assistant can quote carries "
                              "its served scope",
                              "docs/PHASE31_REMOVED_MODELS.md",
                              "ml/evaluation/phase30_harvest_crossstudy.json"),
         "tests": _layer("present",
                         "no route, OpenAPI operation, catalogue row, request schema, assistant "
                         "passage or workflow offers a harvest forecast",
                         "backend/tests/test_phase32_no_forecast.py")}),
    {
        "id": "led-spectrum-response",
        "order": 4,
        "claim": "Response to specific LED spectra and photoperiods",
        "readinessTier": "research-ready",
        "phase27Status": "completed",
        "phase32Disposition": "comparison-only",
        "layers": {
            "data": _layer("present",
                           "two measured datasets: four spectral regimes in lettuce, and the "
                           "controlled-environment wheat runs varying PPFD, photoperiod, CO2 and temperature",
                           "data/processed/phase29/light_stress_harvest.csv",
                           "data/processed/phase30/cea_wheat_experiments.csv"),
            "method": _layer("present",
                             "a measured group comparison. The fitted response surface failed its "
                             "sealed holdout (297.46 % MAPE) and was deleted in Phase 30 rather than "
                             "served behind a caveat",
                             "backend/app/workflows/light_stress.py",
                             "backend/app/workflows/cea_evidence.py"),
            "service": _layer("present",
                              "both workflows assemble measured group summaries with their design "
                              "caveats; a regime that changes spectrum and density at once is flagged",
                              "backend/app/workflows/light_stress.py",
                              "backend/app/workflows/cea_evidence.py"),
            "endpoint": _layer("present",
                               "GET/POST /api/workflows/light-stress/{capability,run} and the "
                               "/controlled-environment equivalents",
                               "backend/app/routes/workflows.py"),
            "inputCheck": _layer("present",
                                 "regime is a Literal of the measured regimes; traits and "
                                 "daysAfterSowing are bounded; extra fields forbidden",
                                 "backend/app/routes/workflows.py"),
            "outputCheck": _layer("present",
                                  "every reported group must exist in the measured table, and a "
                                  "group with a confounded design carries the flag",
                                  "backend/app/workflows/light_stress.py"),
            "uncertainty": _layer("present",
                                  "between-plant spread per regime, from the measured replicates; "
                                  "no interval is extrapolated beyond the measured groups",
                                  "backend/app/workflows/light_stress.py"),
            "provenance": _layer("present",
                                 "each regime names its source study, licence and design caveat",
                                 "data/processed/phase29/light_stress_quality.json"),
            "frontend": _layer("present",
                               "the guided workflows render the measured groups and their spread",
                               "frontend/src/pages/modules/GuidedWorkflows.jsx",
                               "frontend/e2e/guided-workflows.spec.js"),
            "tests": _layer("present", "the workflows are tested against the measured table",
                            "backend/tests/test_phase29_workflows.py",
                            "backend/tests/test_phase30_datasets.py"),
        },
    },
    _removed_feature(
        5, "nutrient-balance", "Nutrient solution management",
        "No hydroponic nutrient series with a per-plant response is obtainable: the acquired "
        "archives record solution composition per treatment, not a response the platform could "
        "model. No control, page, endpoint or claim exists.",
        "docs/PHASE27_FEATURE_AUDIT.md",
        [PHASE32_TESTS, "backend/tests/test_phase30_removed_capabilities.py"]),
    {
        "id": "sub-daily-weather",
        "order": 6,
        "claim": "Heat-stress and VPD excursion claims",
        "readinessTier": "research-ready",
        "phase27Status": "completed",
        "phase32Disposition": "complete",
        "layers": {
            "data": _layer("present",
                           "the scenario's own temperature, humidity and light, which are the "
                           "caller's assumptions and are labelled as such",
                           "backend/app/simulation/serializers.py"),
            "method": _layer("present",
                             "Tetens saturation vapour pressure; the light integral is PPFD x hours",
                             "backend/app/simulation/factors.py",
                             "backend/app/simulation/serializers.py"),
            "service": _layer("present", "assembled in the simulation response",
                              "backend/app/simulation/serializers.py"),
            "endpoint": _layer("present", "POST /api/simulate",
                               "backend/app/routes/simulation.py"),
            "inputCheck": _layer("present", "temperature, humidity and light bounds are enforced",
                                 "backend/app/models/simulation.py"),
            "outputCheck": _layer("present",
                                  "Phase 32: VPD and the light integral each carry a method, an "
                                  "assumptions flag and a statement that no error is propagated",
                                  "backend/app/simulation/serializers.py",
                                  "backend/tests/test_phase32_output_checks.py"),
            "uncertainty": _layer("present",
                                  "explicit: `propagatedError: null` plus a sentence saying the value "
                                  "describes a scenario, not a place or a day",
                                  "backend/app/simulation/serializers.py"),
            "provenance": _layer("present",
                                 "the VPD method and the assumption flag travel with the number",
                                 "backend/app/simulation/serializers.py"),
            "frontend": _layer("present",
                               "the environment panel and the digital-twin state read these values",
                               "frontend/src/components/DigitalTwin3D.jsx"),
            "tests": _layer("present",
                            "the output-check suite asserts the statements and the units map",
                            "backend/tests/test_phase32_output_checks.py"),
        },
    },
    _removed_feature(
        7, "cultivar-metadata", "Cultivar-specific growth parameters",
        "No experiment in the repository carries a cultivar label usable as a model input and no "
        "cultivar selector or parameter exists. A cultivar effect cannot be learned from one "
        "cultivar per study.",
        "docs/PHASE26_FEATURE_COVERAGE_MATRIX.md",
        [PHASE32_TESTS]),
    _removed_feature(
        8, "mission-energy", "Energy and mass cost of a described mission",
        "No mission energy or mass budget dataset exists in the repository and the platform "
        "publishes no such figure; Phase 32 proves by test that no response carries one.",
        "docs/PHASE26_FEATURE_COVERAGE_MATRIX.md",
        [PHASE32_TESTS]),
    _removed_feature(
        9, "fractional-gravity", "Effect of Mars or lunar gravity on crop growth",
        "Withdrawn in Phase 30: no recovered study measures production as a function of gravity - "
        "ground chambers and orbital runs compare a microgravity arm against a 1 g control, not a "
        "graded response. No input, card or route accepts a gravity value.",
        "docs/PHASE30_REMOVED_CAPABILITIES.md",
        ["backend/tests/test_phase30_removed_capabilities.py", PHASE32_TESTS]),
    _removed_feature(
        10, "substrate-water", "Root-zone water status",
        "No root-zone water-potential time series exists in the repository or in the searched "
        "sources. The simulator's single well-mixed store is a documented assumption inside the "
        "water-demand calculation, not a root-zone status feature.",
        "docs/PHASE27_FEATURE_AUDIT.md",
        [PHASE32_TESTS]),
    _removed_feature(
        11, "imagery", "Plant health or growth stage from imagery",
        "No paired imagery and harvest labels exist for a plant-health model, and the catalogue's "
        "imagery datasets are licence classes E/F, which cannot back a served model. No upload, "
        "camera view or plant-health card exists.",
        "data/research/dataset_catalog.json",
        [PHASE32_TESTS]),
    _removed_feature(
        12, "long-run-climate", "Siting for a future climate",
        "The CMIP6 downscaled product is catalogued at licence class D and could not be acquired; "
        "no projection data is in the repository and no climate-siting control or report exists.",
        "data/research/dataset_catalog.json",
        [PHASE32_TESTS]),
]

# Cross-cutting findings, each with what Phase 32 did about it. A finding is only listed as open
# when it is still observable in the running product; anything the platform now does is recorded
# as resolved with the artefact that does it, so this list cannot slowly become a wish list.
CROSS_CUTTING_GAPS: list[dict[str, Any]] = [
    {
        "id": "water-paths-unarbitrated",
        "finding": ("Two water demand paths ship - crop-relative and ET0-reference. The response "
                    "names which one ran, and the measured comparison states that it cannot decide "
                    "between them because the trial publishes no pot geometry or spacing."),
        "evidence": ["backend/app/water_evidence.py",
                     "backend/app/simulation/serializers.py"],
        "severity": "documented-limitation",
        "disposition": ("Not actionable with obtainable evidence. An arbiter needs per-day weather "
                        "for the trial plus its pot area; neither is published, so choosing one "
                        "would decide the answer before the comparison was made."),
    },
    {
        "id": "no-measured-et0-benchmark",
        "finding": ("The reference-ET0 calculation is validated against the FAO-56 worked examples, "
                    "not against a measured ET0 station record: none is bundled."),
        "evidence": ["backend/app/et0.py",
                     "backend/tests/test_phase23_reference_et0.py"],
        "severity": "documented-limitation",
        "disposition": ("Stated in the response and on the model card. Acquisition of an "
                        "independent station network failed reproducibly from this environment "
                        "(USDA Ag Data Commons DNS, figshare search API, Dryad 401), so the claim "
                        "is scoped down rather than faked."),
    },
    {
        "id": "comparison-excludes-measurement",
        "finding": ("The scenario comparison compares parameter sets; it deliberately does not mix "
                    "a measured benchmark into a scenario ranking."),
        "evidence": ["backend/app/routes/workspace.py",
                     "frontend/src/pages/modules/WaterEvidencePanel.jsx"],
        "severity": "resolved",
        "disposition": ("By design, and the measured-versus-modelled comparison now has its own "
                        "panel with its own provenance, so a user does not have to infer it from a "
                        "scenario table."),
    },
    {
        "id": "et0-parameter-not-in-frontend",
        "finding": ("POST /api/simulate accepts et0MmPerDay and cropCoefficient; no frontend "
                    "control sets either field."),
        "evidence": ["frontend/src/pages/modules/GuidedWorkflows.jsx",
                     "backend/app/routes/workflows.py"],
        "severity": "resolved",
        "disposition": ("Resolved: the water-demand workflow exposes the ET0-reference path with "
                        "the daily ET0, its primary method and per-scenario deltas. The simulator "
                        "route keeps the fields for API callers; the served UI path is the "
                        "workflow."),
    },
    {
        "id": "units-not-machine-readable",
        "finding": "Units live in field names and prose only.",
        "evidence": ["backend/app/models/simulation.py",
                     "backend/app/simulation/serializers.py"],
        "severity": "resolved",
        "disposition": ("Resolved in Phase 32: /api/simulate returns a `units` map for every "
                        "headline scalar, additively, so existing clients are unaffected."),
    },
    {
        "id": "no-out-of-distribution-warning",
        "finding": "Predictions are returned without an out-of-domain flag.",
        "evidence": ["backend/app/routes/research.py"],
        "severity": "resolved",
        "disposition": ("Resolved: every prediction response carries `outOfDistribution` (or "
                        "`outOfDomain`) with the violated bounds and the warnings that explain them."),
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
    dispositions: dict[str, int] = {}
    for feature in FEATURES:
        key = feature["phase32Disposition"]
        dispositions[key] = dispositions.get(key, 0) + 1
    return {"byLayer": counts, "completeWorkflows": complete, "byDisposition": dispositions,
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
        "Phase 32 status: the list is closed. Every feature is either complete at the level it "
        "claims or removed from the product, so this document records what ships rather than a "
        "plan for what might.",
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
        "The ✅ marks a feature at the top of its readiness ladder. The layer codes are truncated "
        "to four characters; the per-feature sections below carry the Phase 32 disposition and the "
        "evidence for each layer.",
        "",
        "## Per-feature detail",
    ]
    for feature in sorted(features, key=lambda item: item["order"]):
        lines += ["", f"### {feature['order']}. {feature['claim']}", "",
                  f"Readiness tier: `{feature['readinessTier']}` · Phase 27: "
                  f"{feature['phase27Status']} · Phase 32: `{feature['phase32Disposition']}`", "",
                  "| Layer | State | Note |", "| --- | --- | --- |"]
        for layer, _ in LAYERS:
            entry = feature["layers"][layer]
            lines.append(f"| `{layer}` | `{entry['state']}` | {entry.get('note', '')} |")

    lines += ["", "## Cross-cutting gaps found by the audit", "",
              "These are not attributable to a single feature. Each names its evidence, its "
              "severity, why it matters and how hard it is to build.", "",
              "| Gap | Severity | Finding | Phase 32 disposition |",
              "| --- | --- | --- | --- |"]
    for gap in payload["crossCuttingGaps"]:
        lines.append(f"| `{gap['id']}` | {gap['severity']} | {gap['finding']} | "
                     f"{gap['disposition']} |")

    lines += [
        "",
        "## What the pattern says",
        "",
        "The audit's most useful finding was that the layers which were systematically weakest "
        "were `uncertainty` and `outputCheck` - the two that stand between a number and a "
        "defensible number.",
        "",
        "Phase 32 closed that story rather than restating it. The output checks now exist where "
        "the arithmetic could go physically wrong (reference ET0 returns its own plausibility "
        "verdict instead of a bare number), the uncertainty statement is attached to the value it "
        "qualifies (VPD, classification scores), and the features that could not be completed "
        "were removed from every layer rather than left as `data-blocked` rows a reader could "
        "mistake for a roadmap.",
        "",
        "Final dispositions: "
        + ", ".join(f"**{count} {name}**"
                    for name, count in sorted(summary["byDisposition"].items()))
        + f" across {summary['features']} features. No feature is left in a resting blocked "
        "state: either the claim is served with its limits, or the capability is gone.",
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
