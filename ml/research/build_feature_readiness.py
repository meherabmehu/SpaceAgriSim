"""Build the Phase 26 feature readiness audit and the feature-to-dataset coverage matrix.

    python3 ml/research/build_feature_readiness.py [--check]

Twelve named capabilities are audited against the evidence that exists in this repository, on a
five-tier readiness scale. The tiers are defined by what a feature can *claim*, not by how much
code it has:

    production-ready  an independent evaluation exists, the artefacts are committed, and the
                      product's stated limits match what the evaluation found
    research-ready    measured data and a committed evaluation exist; the level the product claims
                      is not identifiable from that data
    experimental      implemented and internally evaluated; no independent validation exists
    data-blocked      no dataset in this repository - or obtainable under an open licence - can
                      move the feature; the block is the data's absence, not the code
    unsupported       the product must not make the claim at all

The audit refuses to write itself if a feature claims a tier its own evidence does not reach:
a production-ready or research-ready feature must name evaluation artefacts that exist on disk,
and a data-blocked feature may not name an acquired dataset. Those two rules are the whole point
of the file - without them the audit is a list of opinions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TARGET_JSON = ROOT / "data" / "research" / "phase26" / "feature_readiness.json"
TARGET_MD = ROOT / "docs" / "PHASE26_FEATURE_COVERAGE_MATRIX.md"
GENERATED_ON = "2026-11-10"

TIERS = {
    "production-ready": "independent evaluation exists and the stated limits match what it found",
    "research-ready": "measured data and a committed evaluation exist; the claimed level is not "
                      "identifiable from them",
    "experimental": "implemented and internally evaluated; no independent validation exists",
    "data-blocked": "no obtainable dataset can move this feature; the block is the data's absence",
    "unsupported": "the product must not make the claim at all",
    "removed": "the capability is not in the product: no control, page, endpoint, catalogue entry "
               "or documentation claim survives, and a test proves it is absent",
}

# Each feature: what it claims, which tier it reaches, and the artefacts that justify the tier.
# `evidence` entries are paths that must exist; `datasets` are catalogue ids that must exist.
FEATURES: list[dict[str, Any]] = [
    {
        "id": "measured-eta",
        "order": 1,
        "claim": "Predicted crop water use in litres per plant per day",
        "previousTier": "data-blocked",
        "tier": "research-ready",
        "tierChanged": True,
        "evidence": [
            "ml/evaluation/phase26_measured_et_validation.json",
            "data/processed/phase26/schroder2021_lettuce_et.csv",
            "backend/app/simulation/water.py",
        ],
        "datasets": ["zenodo-schroder-2021-lettuce-pot"],
        "measuredOn": "380 pot-days from 35 published pots, 7 treatments, 11 weighings",
        "whatItSupports": [
            "the seasonal shape of lettuce water demand (Spearman 0.7909 across 11 days)",
            "a per-plant, per-day water-use benchmark that any future change must be compared with",
        ],
        "whatItDoesNotSupport": [
            "a level correction: pot-surface and canopy-area denominators reverse the sign of the "
            "discrepancy, and neither is published",
            "a crop coefficient: no per-day trial weather exists",
            "transpiration alone: the measurement includes substrate evaporation",
        ],
        "whatWouldMoveIt": "per-day weather and pot geometry for a gravimetric or lysimeter trial, "
                           "so that measured ET can be divided by a reference ET0 for the same days",
        "blockingEvidence": "none obtainable under an open licence in this phase",
    },
    {
        "id": "independent-et0",
        "order": 2,
        "claim": "The claim that the ET0 target is itself correct",
        "previousTier": "research-ready",
        "tier": "research-ready",
        "tierChanged": False,
        "evidence": [
            "ml/evaluation/et0_dataset_quality.json",
            "docs/ERA5_LAND_INDEPENDENT_VALIDATION.md",
                    ],
        "datasets": ["nasa-power-daily", "era5-land", "era5-hourly-0p25", "noaa-isd-lite"],
        "measuredOn": "four independent reanalysis and station sources over matched days",
        "whatItSupports": [
            "that the FAO-56 computation is implemented correctly and is stable across inputs",
            "that the emulator reproduces the computation, not that the computation is truth",
        ],
        "whatItDoesNotSupport": [
            "a claim that reanalysis ET0 equals on-site measurement",
            "spatial validity below the reanalysis grid cell",
        ],
        "whatWouldMoveIt": "a flux-tower or lysimeter site inside a controlled environment, which "
                           "is the same object measured-eta needs",
        "blockingEvidence": "no controlled-environment ET0 measurement exists openly",
    },
    {
        "id": "yield-labels",
        "order": 3,
        "claim": "Predicted harvest mass per plant",
        "previousTier": "research-ready",
        "tier": "removed",
        "tierChanged": True,
        "phase30": (
            "The served forecast was withdrawn. A leave-one-study-out evaluation over 40 published "
            "lettuce studies (53 treatment means) returned 310.17 % MAPE against the unchanged 30 % "
            "criterion with the mean baseline selected out of fold; the Phase 28 holdout had already "
            "returned 41.59 %. POST /api/workflows/harvest-prediction/run now answers 410 and the "
            "catalogue entry is 'unavailable'."
        ),
        "evidence": [
            "ml/evaluation/phase30_harvest_crossstudy.json",
            "data/processed/phase30/lettuce_multistudy.csv",
            "backend/tests/test_phase30_removed_capabilities.py",
        ],
        "datasets": ["zenodo-kilowatts-lettuce-lue"],
        "measuredOn": "53 published treatment means from 40 studies, used as an evaluation set",
        "whatItSupports": [
            "a measured-versus-model parity record that shows the model overpredicting",
        ],
        "whatItDoesNotSupport": [
            "any harvest forecast, for any crop",
        ],
        "whatWouldMoveIt": "nothing, in this phase: the capability is removed rather than blocked",
        "blockingEvidence": "the independent error is more than ten times the criterion",
    },
    {
        "id": "led-spectrum-response",
        "order": 4,
        "claim": "Response to specific LED spectra and photoperiods",
        "previousTier": "experimental",
        "tier": "experimental",
        "tierChanged": False,
        "evidence": [
            "data/processed/phase26/greenlight2024_lettuce_harvest.csv",
            "data/processed/phase26/greenlight2024_lettuce_fluorescence.csv",
            "backend/app/science_classification.py",
        ],
        "datasets": ["zenodo-greenlight-2024-lettuce"],
        "measuredOn": "252 plants across four fixed spectra at constant 200 umol/m2/s and 16 h",
        "whatItSupports": [
            "that spectral composition can be held as a categorical factor with 48-80 plants per arm",
        ],
        "whatItDoesNotSupport": [
            "an intensity response: PPFD was constant by design",
            "a photoperiod response: photoperiod was constant by design",
            "any quantitative yield model: no model consumes this table yet",
        ],
        "whatWouldMoveIt": "a trial varying PPFD and photoperiod independently, or a model that "
                           "consumes the existing table with leave-one-spectrum-out evaluation",
        "blockingEvidence": "the photoperiod half of the claim has no dataset at all",
    },
    {
        "id": "fractional-gravity",
        "order": 5,
        "claim": "Effect of Mars or lunar gravity on crop growth",
        "previousTier": "data-blocked",
        "tier": "removed",
        "tierChanged": True,
        "phase30": (
            "The growth penalty, input field, presets, impact step and UI control were removed. No "
            "open dataset measures crop yield or biomass across fractional gravity; the ISS "
            "graded-gravity experiments measure gene expression and morphology, and a clinostat is "
            "not partial gravity. Keeping the coefficient would have kept an invented number."
        ),
        "evidence": ["backend/tests/test_phase30_removed_capabilities.py",
                     "docs/PHASE30_REMOVED_CAPABILITIES.md"],
        "datasets": [],
        "measuredOn": "nothing: no fractional-gravity plant yield dataset exists",
        "whatItSupports": [
            "nothing - the simulator has no gravity term",
        ],
        "whatItDoesNotSupport": [
            "any gravity-related yield statement",
        ],
        "whatWouldMoveIt": "a replicated fractional-gravity yield experiment; none exists openly",
        "blockingEvidence": "no open dataset, and none was recoverable in the Phase 30 search",
    },
    {
        "id": "substrate-water",
        "order": 6,
        "claim": "Root-zone water status in a hydroponic or substrate system",
        "previousTier": "data-blocked",
        "tier": "data-blocked",
        "tierChanged": False,
        "evidence": ["backend/app/simulation/water.py"],
        "datasets": [],
        "measuredOn": "nothing: no root-zone water-potential series exists in-repo. The Schroeder "
                      "trial's water-holding-capacity sheet is a static substrate property, not a "
                      "root-zone time series.",
        "whatItSupports": [
            "a single well-mixed root-zone water store with a recovery efficiency assumption",
        ],
        "whatItDoesNotSupport": [
            "substrate matric potential, oxygen status, or root-zone gradients",
        ],
        "whatWouldMoveIt": "a substrate water-potential series logged alongside a growth trial",
        "blockingEvidence": "the acquisition that came closest (water holding capacity) measures "
                            "capacity, not status",
    },
    {
        "id": "sub-daily-weather",
        "order": 7,
        "claim": "Heat-stress and VPD excursion claims",
        "previousTier": "research-ready",
        "tier": "research-ready",
        "tierChanged": False,
        "evidence": [
            "ml/evaluation/phase11_dataset_discovery.json",
            "docs/DATASET_GAP_MATRIX.md",
        ],
        "datasets": ["era5-hourly-0p25", "noaa-isd-lite"],
        "measuredOn": "hourly reanalysis and station records at grid and station resolution",
        "whatItSupports": [
            "hourly VPD and temperature trajectories for siting and for ET0 input",
        ],
        "whatItDoesNotSupport": [
            "canopy-level excursions inside a controlled environment",
            "any statement about a facility's internal climate",
        ],
        "whatWouldMoveIt": "in-facility climate logging at sub-hourly resolution",
        "blockingEvidence": "no open controlled-environment climate series with the required "
                            "resolution was found",
    },
    {
        "id": "cultivar-metadata",
        "order": 8,
        "claim": "Cultivar-specific growth parameters",
        "previousTier": "experimental",
        "tier": "experimental",
        "tierChanged": False,
        "evidence": ["backend/app/simulation/crops.py", "docs/MODEL_LIMITATIONS.md"],
        "datasets": [],
        "measuredOn": "three crop profiles (lettuce, tomato, radish) with no cultivar field",
        "whatItSupports": [
            "a species-level parameter set explicitly documented as not cultivar-resolved",
        ],
        "whatItDoesNotSupport": [
            "any cultivar-specific prediction, and no dataset in-repo carries a cultivar label "
            "usable as a model input",
        ],
        "whatWouldMoveIt": "two or more cultivars of one species grown under identical conditions",
        "blockingEvidence": "the lettuce experiments in-repo each use a single unnamed cultivar",
    },
    {
        "id": "imagery",
        "order": 9,
        "claim": "Plant health or growth stage from imagery",
        "previousTier": "data-blocked",
        "tier": "data-blocked",
        "tierChanged": False,
        "evidence": ["docs/DATASET_GAP_MATRIX.md"],
        "datasets": [],
        "measuredOn": "nothing: the tomato trial ships an RGB leaf-area series, which is a "
                      "measurement derived from imagery rather than the imagery itself",
        "whatItSupports": ["nothing: the product does not claim an imagery model"],
        "whatItDoesNotSupport": ["any computer-vision claim, health classification, or growth-stage "
                                 "detection"],
        "whatWouldMoveIt": "paired imagery and destructive harvest from the same plants",
        "blockingEvidence": "the class E/F imagery datasets in the catalogue cannot be used under "
                            "their licences or do not match the task",
    },
    {
        "id": "mission-energy",
        "order": 10,
        "claim": "Energy and mass cost of a described mission",
        "previousTier": "experimental",
        "tier": "experimental",
        "tierChanged": False,
        "evidence": ["backend/app/simulation/engine.py", "backend/app/science_classification.py"],
        "datasets": [],
        "measuredOn": "nothing: energy per LED-hour and per litre is a deterministic calculation "
                      "over stated assumptions, not a measurement",
        "whatItSupports": [
            "a reproducible accounting of lighting and pumping energy under stated assumptions",
        ],
        "whatItDoesNotSupport": [
            "a validated mission energy budget, and any comparison against a real facility",
        ],
        "whatWouldMoveIt": "metered energy data from an operating controlled-environment facility",
        "blockingEvidence": "no metered facility energy dataset is openly available",
    },
    {
        "id": "nutrient-balance",
        "order": 11,
        "claim": "Nutrient solution management",
        "previousTier": "data-blocked",
        "tier": "experimental",
        "tierChanged": True,
        "evidence": [
            "data/raw/phase26/zenodo-halbert-2020-tomato-hydroponic/"
            "Data_Tomato_hydroponic_experiment_Halbert-Howard_et_al_2020.xlsx",
            "scripts/datasets/registry.py",
        ],
        "datasets": ["zenodo-halbert-2020-tomato-hydroponic"],
        "measuredOn": "row-level shoot and fruit nutrient uptake with solution concentrations and a "
                      "recycled-solution fraction; not yet preprocessed",
        "whatItSupports": [
            "that a nutrient-uptake prior is constructible from a licensed, acquired source",
        ],
        "whatItDoesNotSupport": [
            "any per-plant nutrient claim: replication is at row level",
            "a closed nutrient balance: the sheet reports uptake, not depletion and replenishment",
        ],
        "whatWouldMoveIt": "preprocessing the acquired workbook into a tidy table and evaluating a "
                           "nutrient prior against it with row-level folds",
        "blockingEvidence": "row-level replication caps the inference, and the product makes no "
                            "nutrient claim today",
    },
    {
        "id": "long-run-climate",
        "order": 12,
        "claim": "Siting for a future climate rather than the observed recent past",
        "previousTier": "data-blocked",
        "tier": "data-blocked",
        "tierChanged": False,
        "evidence": ["docs/DATASET_GAP_MATRIX.md"],
        "datasets": [],
        "measuredOn": "nothing acquired: the CMIP6 downscaled product is catalogued at class D and "
                      "was not downloaded",
        "whatItSupports": ["nothing: no siting-for-future-climate claim is made"],
        "whatItDoesNotSupport": ["any projection-based recommendation"],
        "whatWouldMoveIt": "acquiring the downscaled projections and defining a projection-based "
                           "ET0 target with an explicit scenario",
        "blockingEvidence": "the product's ET0 target is the observed recent past by construction",
    },
]

TIER_ORDER = ["production-ready", "research-ready", "experimental", "data-blocked",
              "unsupported", "removed"]


def _catalogue_ids() -> set[str]:
    payload = json.loads((ROOT / "data" / "research" / "dataset_catalog.json").read_text())
    return {dataset["id"] for dataset in payload["datasets"]}


# ---------------------------------------------------------------------------------------------
# Phase 32 dispositions.
#
# Phase 26 asked what each feature may claim and Phase 27 asked whether a user can walk through
# it. Phase 32 closed the list: a feature is either complete at the level it claims, or it is
# removed from the product. Nothing is left in a resting "blocked" state, because a blocked row
# reads as a roadmap and the platform does not intend to build these.
#
# The tier and the reason live here rather than in the JSON so that regenerating this file cannot
# silently restore a withdrawn claim.
# ---------------------------------------------------------------------------------------------
PHASE32 = {
    "yield-labels": ("removed", (
        "The served harvest forecast was withdrawn in Phase 31 after the lettuce v3 model missed "
        "its pre-registered 30 % MAPE criterion at 41.6 % and the mizuna model held a negative "
        "held-out R2 (-0.333). backend/tests/test_phase32_no_forecast.py proves no route, "
        "workflow or assistant passage offers a harvest forecast; only the archival parity record "
        "remains.")),
    "nutrient-balance": ("removed", (
        "Searched for a hydroponic nutrient series with a per-plant response: the acquired archive "
        "records solution composition per treatment, not a response the platform could predict. No "
        "control, page, endpoint or claim exists.")),
    "cultivar-metadata": ("removed", (
        "No experiment in the repository carries a cultivar label usable as a model input and no "
        "cultivar selector or parameter exists. A cultivar effect cannot be learned from one "
        "cultivar per study, so the feature is withdrawn instead of being left as a promise.")),
    "mission-energy": ("removed", (
        "No mission energy or mass budget dataset exists in the repository and the platform "
        "publishes no such figure. Phase 32 proves by test that no response carries one.")),
    "fractional-gravity": ("removed", (
        "No recovered study measures production as a function of gravity: ground chambers and "
        "orbital runs compare a microgravity arm with a 1 g control, not a graded response. The "
        "search record stays in docs/PHASE30_REMOVED_CAPABILITIES.md and no input, card or route "
        "accepts a gravity value.")),
    "substrate-water": ("removed", (
        "No root-zone water-potential series exists in the repository or in the searched sources "
        "(OSDR, Zenodo, Dryad, PANGAEA, Mendeley). The simulator's single well-mixed store is a "
        "documented assumption inside the water-demand calculation, not a root-zone status "
        "feature, and no control claims one.")),
    "imagery": ("removed", (
        "No paired imagery and harvest labels exist for a plant-health model, and the catalogue's "
        "imagery datasets are licence classes E/F, which cannot back a served model. No upload, "
        "camera view or plant-health card exists.")),
    "long-run-climate": ("removed", (
        "The CMIP6 downscaled product is catalogued at licence class D and could not be acquired; "
        "no projection data is in the repository and no climate-siting control or report exists.")),
    "led-spectrum-response": ("research-ready", (
        "Completed as a measured group comparison only: four spectral regimes in lettuce and the "
        "controlled-environment wheat runs, served through the light-stress and "
        "controlled-environment workflows with between-plant spread and a confounded-regime flag. "
        "No fitted response surface is served; the one that was fitted failed its sealed holdout "
        "(297.46 % MAPE) and was deleted.")),
}

SEARCHED = ("NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley Data, Dataverse, "
            "USDA Ag Data Commons, OpenAIRE and journal supplements")

for _feature in FEATURES:
    if _feature["id"] not in PHASE32:
        continue
    _tier, _reason = PHASE32[_feature["id"]]
    _feature["previousTier"] = _feature["tier"]
    _feature["tier"] = _tier
    _feature["tierChanged"] = _feature["previousTier"] != _tier
    _feature["phase32"] = {"tier": _tier, "reason": _reason, "searched": SEARCHED}
    if _tier == "removed":
        _feature["whatItSupports"] = [
            item for item in _feature["whatItSupports"]
            if any(word in item.lower() for word in ("record", "parity", "nothing"))
        ]
        _feature["whatWouldMoveIt"] = "nothing: the capability is removed rather than blocked"



def validate(features: list[dict[str, Any]]) -> list[str]:
    """Refuse to write an audit whose tiers outrun its evidence."""
    problems: list[str] = []
    catalogue = _catalogue_ids()
    acquired = json.loads(
        (ROOT / "data" / "research" / "dataset_catalog.json").read_text())["datasets"]
    acquired_ids = {d["id"] for d in acquired if d.get("imported")}

    for feature in features:
        if feature["tier"] not in TIERS:
            problems.append(f"{feature['id']}: unknown tier {feature['tier']}")
        if feature["tier"] in ("production-ready", "research-ready", "experimental"):
            if not feature["evidence"]:
                problems.append(f"{feature['id']}: {feature['tier']} with no evidence")
        for path in feature["evidence"]:
            if not (ROOT / path).exists():
                problems.append(f"{feature['id']}: evidence path missing: {path}")
        for dataset_id in feature["datasets"]:
            if dataset_id not in catalogue:
                problems.append(f"{feature['id']}: dataset not in catalogue: {dataset_id}")
        named = set(feature["datasets"])
        if feature["tier"] == "data-blocked":
            if named & acquired_ids:
                problems.append(
                    f"{feature['id']}: claims data-blocked but names an acquired dataset "
                    f"({sorted(named & acquired_ids)})")
            if not feature["blockingEvidence"]:
                problems.append(f"{feature['id']}: data-blocked without stating the block")
        if feature["tier"] == "production-ready" and not feature["datasets"]:
            problems.append(f"{feature['id']}: production-ready with no dataset behind it")
        if feature["tierChanged"] and feature["previousTier"] == feature["tier"]:
            problems.append(f"{feature['id']}: marked changed but the tier did not move")
    return problems


def render(payload: dict[str, Any]) -> str:
    features = payload["features"]
    counts = payload["counts"]["byTier"]
    lines = [
        "# Phase 26 — Feature Readiness and Coverage Matrix",
        "",
        f"Generated from `data/research/phase26/feature_readiness.json` on "
        f"{payload['generatedOn']} by `ml/research/build_feature_readiness.py`. "
        "Edit the JSON, not this file.",
        "",
        "Twelve named capabilities, audited against the evidence that exists in this repository. "
        "A tier describes what a feature may **claim**, not how much code it has, and the builder "
        "refuses to write an audit whose tiers outrun their evidence.",
        "",
        "## Tiers",
        "",
        "| Tier | Meaning |",
        "| --- | --- |",
    ]
    for tier in TIER_ORDER:
        lines.append(f"| `{tier}` | {TIERS[tier]} |")

    lines += [
        "",
        f"**{len(features)} features: "
        + ", ".join(f"{tier}: {counts.get(tier, 0)}" for tier in TIER_ORDER)
        + f". {payload['movedCount']} of {len(features)} moved in Phase 26.**",
        "",
        "## Readiness",
        "",
        "| # | Feature | Tier | Previous | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for feature in sorted(features, key=lambda f: f["order"]):
        marker = " **(moved)**" if feature["tierChanged"] else ""
        lines.append(
            f"| {feature['order']} | {feature['claim']} | `{feature['tier']}`{marker} | "
            f"`{feature['previousTier']}` | {len(feature['evidence'])} artefacts, "
            f"{len(feature['datasets'])} datasets |")

    lines += [
        "",
        "## Coverage: which dataset backs which feature",
        "",
        "| Feature | Datasets | Measured on |",
        "| --- | --- | --- |",
    ]
    for feature in sorted(features, key=lambda f: f["order"]):
        datasets = ", ".join(f"`{d}`" for d in feature["datasets"]) or "—"
        lines.append(f"| {feature['claim']} | {datasets} | {feature['measuredOn']} |")

    for feature in sorted(features, key=lambda f: f["order"]):
        lines += [
            "",
            f"### {feature['order']}. {feature['claim']}",
            "",
            f"**Tier: `{feature['tier']}`**"
            + (f" (was `{feature['previousTier']}` before Phase 26)" if feature["tierChanged"]
               else f" (unchanged in Phase 26)"),
            "",
            f"Measured on: {feature['measuredOn']}",
            "",
            "Supports:",
        ]
        lines += [f"- {item}" for item in feature["whatItSupports"]]
        lines += ["", "Does not support:"]
        lines += [f"- {item}" for item in feature["whatItDoesNotSupport"]]
        lines += ["", f"What would move it: {feature['whatWouldMoveIt']}"]
        if feature.get("blockingEvidence"):
            lines += ["", f"Blocking evidence: {feature['blockingEvidence']}"]
        if feature["evidence"]:
            lines += ["", "Evidence artefacts: " + ", ".join(f"`{p}`" for p in feature["evidence"])]

    lines += [
        "",
        "## What this table is not",
        "",
        "No feature reached `production-ready` in this phase and none was promoted on the strength "
        "of a new download. The two tiers that moved each gained a specific, cited artefact: "
        "`measured-eta` gained the first measured crop water use in the repository, and "
        "`nutrient-balance` gained a licensed nutrient-uptake workbook. Both movements are "
        "modest by design - in both cases the acquisition made the feature *legitimately "
        "discussable*, not *solved*.",
        "",
        f"{counts.get('data-blocked', 0)} features remain `data-blocked`. That count fell by one "
        "in this phase, and only because a licensed nutrient-uptake workbook was actually "
        "downloaded and verified. The remaining blocks do not shrink, because the datasets that "
        "would clear them do not exist under an open licence and a catalogue entry cannot be "
        "invented.",
        "",
    ]
    return "\n".join(lines)


def build() -> dict[str, Any]:
    problems = validate(FEATURES)
    if problems:
        raise SystemExit("audit refused:\n  " + "\n  ".join(problems))
    counts: dict[str, int] = {}
    for feature in FEATURES:
        counts[feature["tier"]] = counts.get(feature["tier"], 0) + 1
    return {
        "phase": 26,
        "generatedBy": "ml/research/build_feature_readiness.py",
        "generatedOn": GENERATED_ON,
        "phase32Note": ("Phase 32 closed this list. Every feature is either complete at the level "
                        "it claims or removed from the product; 'data-blocked' is no longer a "
                        "resting state."),
        "tierDefinitions": TIERS,
        "tierOrder": TIER_ORDER,
        "counts": {
            "features": len(FEATURES),
            "byTier": counts,
            "moved": sum(1 for f in FEATURES if f["tierChanged"]),
        },
        "movedCount": sum(1 for f in FEATURES if f["tierChanged"]),
        "features": FEATURES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = build()
    if args.check:
        if not TARGET_JSON.is_file() or not TARGET_MD.is_file():
            print("MISSING readiness files; run without --check")
            return 1
        committed = json.loads(TARGET_JSON.read_text(encoding="utf-8"))
        if committed["features"] != payload["features"]:
            print("STALE JSON: the builder's feature list differs from the committed one")
            return 1
        if TARGET_MD.read_text(encoding="utf-8") != render(committed):
            print("STALE markdown: re-render from the JSON")
            return 1
        print(f"readiness up to date ({len(FEATURES)} features)")
        return 0

    TARGET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TARGET_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    TARGET_MD.write_text(render(payload), encoding="utf-8")
    print(f"wrote {TARGET_MD.relative_to(ROOT)}: {len(FEATURES)} features, "
          + ", ".join(f"{tier}:{count}" for tier, count in sorted(payload['counts']['byTier'].items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
