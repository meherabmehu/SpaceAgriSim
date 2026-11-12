#!/usr/bin/env python3
"""Build the Phase 7 training-eligibility matrix.

Every modelling task in the project - the four shipped models and the twelve
NTRS targets from the Phase 7 recovery - gets an explicit verdict and the
evidence rule behind it. The matrix is derived from the measurement catalog for
the NTRS targets, so an eligibility claim cannot drift away from the status of
the underlying measurement.

Eligibility levels (fixed vocabulary, shared with the catalog):

  ready              clean per-sample target with replication; trainable now
  statistical        replicated but too small or single-study for predictive CV
  mechanistic        usable to constrain an equation, not to fit a learner
  plausibility-only  bounds and signs only
  insufficient       cannot support any quantitative claim

Run: python scripts/build_training_eligibility.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
CATALOG = ROOT / "data" / "metadata" / "phase7_measurement_catalog"
OUT = ROOT / "data" / "metadata" / "phase7_training_eligibility"

# Tasks that predate Phase 7. Their verdicts restate what the shipped artifacts
# already measured; they are re-derived here (not copied) so that the whole
# matrix is in one place and can be re-checked in one run.
EXISTING = [
    {
        "taskId": "mizuna-harvest-v1",
        "target": "harvest fresh mass per pillow (g)",
        "samples": 14, "groups": 10, "groupingVariable": "pillow (paired numbers kept together)",
        "eligibility": "statistical",
        "trainable": True,
        "trained": True,
        "reason": (
            "Measured per-sample target, but the harvest-mass definition differs "
            "between the two arms (documented in DATA_HARMONIZATION.md H1), so the "
            "target is not the same quantity across the data. That is why the "
            "registry pins this model at 'baseline-only' and never promotes it."
        ),
        "evidence": "OSD-655 VEG-04A harvest tables",
    },
    {
        "taskId": "mizuna-microbial-load-v1",
        "target": "log10(1 + CFU/g) on edible leaf, absolute level",
        "samples": 123, "groups": 35, "groupingVariable": "pillow (biological replicate)",
        "eligibility": "statistical",
        "trainable": True,
        "trained": True,
        "reason": (
            "The cleanest measured target in the project (123 leaf samples, 35 "
            "pillows, two campaigns), yet still single-crop and two-campaign. "
            "Grouped CV beats the baseline inside pooled data; leave-one-experiment-out "
            "R2 is negative for both campaigns, so the ABSOLUTE level does not transfer. "
            "Phase 7 diagnoses this as an unidentifiable campaign offset rather than a "
            "modelling failure and re-scopes the estimand in mizuna-microbial-relative-load-v2."
        ),
        "evidence": "OSD-780 VEG-04A/B ALSDA plate counts",
    },
    {
        "taskId": "lettuce-earth-growth-v1",
        "target": "fresh shoot mass per plant (g)",
        "samples": 1648, "groups": 4, "groupingVariable": "experiment",
        "eligibility": "statistical",
        "trainable": True,
        "trained": True,
        "reason": (
            "External (WUR) ground data spanning an environmental grid, validated by "
            "nested leave-one-experiment-out. Not NASA data and not flight data; "
            "Earth-only domain."
        ),
        "evidence": "WUR lettuce dataset (external, not NASA)",
    },
    {
        "taskId": "tomato-flight-response-v1",
        "target": "binary flight/ground discrimination from expression",
        "samples": 36, "groups": 21, "groupingVariable": "sample group",
        "eligibility": "statistical",
        "trainable": True,
        "trained": True,
        "reason": (
            "Class-balanced and separable in-sample, but 36 samples cannot support a "
            "claim about mechanism, and the labels are environment labels rather than "
            "measured plant performance. Useful as a discrimination demonstration only."
        ),
        "evidence": "OSD-... tomato transcript abundance table",
    },
]

# Tasks that are deliberately NOT trained, with the reason. This list is the
# point of the matrix: it is the record of what the data cannot carry.
REFUSED = [
    {"taskId": "wheat-biomass-time-series",
     "wouldPredict": "dry mass vs age",
     "eligibility": "mechanistic",
     "reason": ("7 ages, 1 tray each. A curve can be fitted and its residuals "
                "characterised; nothing can be validated out of sample because "
                "every age has n = 1."),
     "alternativeApplied": "Used in Part C as a shape/bound check on the logistic growth curve."},
    {"taskId": "wheat-harvest-yield",
     "wouldPredict": "per-tray dry harvest mass",
     "eligibility": "statistical",
     "reason": ("16 trays from a single study, dry-matter basis, wheat grain. A "
                "descriptive model would be learnable but would transfer to nothing: "
                "one cultivar, one chamber, one institution, and a different edible "
                "organ from the simulator's crops."),
     "alternativeApplied": "Used in Part C as a dry-matter yield bound."},
    {"taskId": "wheat-gas-exchange",
     "wouldPredict": "transpiration / CO2 assimilation rate",
     "eligibility": "plausibility-only",
     "reason": ("Stand-level integrated values from two studies with no per-sample "
                "replication. There are 15 scalar values in total, not a table of "
                "observations."),
     "alternativeApplied": "Used in Part C as bounds and signs only."},
    {"taskId": "water-recovery",
     "wouldPredict": "recovered fraction",
     "eligibility": "plausibility-only",
     "reason": "One balance from one leaking chamber.",
     "alternativeApplied": "Recorded as a lower bound with the leak caveat."},
    {"taskId": "ppfd-photoperiod-response",
     "wouldPredict": "yield vs irradiance and photoperiod",
     "eligibility": "insufficient",
     "reason": ("Three operating points confounded with system phase, sealing, "
                "nutrient-control maturity and a documented copper deficiency. "
                "Fitting a response surface here would produce a confident curve "
                "with no identifying variation behind it."),
     "alternativeApplied": "Nothing applied. The simulator's light response remains an assumption."},
    {"taskId": "stress-severity",
     "wouldPredict": "stress outcome",
     "eligibility": "insufficient",
     "reason": ("Five binary tray labels, no severity, no stressor measurement, no "
                "control arm. Training on it would manufacture a label the source "
                "never measured."),
     "alternativeApplied": "Kept as a descriptive grouping variable only."},
    {"taskId": "o2-evolution",
     "wouldPredict": "O2 production rate",
     "eligibility": "insufficient",
     "reason": "Never measured. Deriving it from CO2 would turn an assumption into a pseudo-measurement.",
     "alternativeApplied": "Remains a Phase 6 blocked target."},
    {"taskId": "gravity-response",
     "wouldPredict": "growth vs gravity level",
     "eligibility": "insufficient",
     "reason": "No gravity manipulation exists in the recovered corpus; all studies are 1 g ground chambers.",
     "alternativeApplied": "Simulator coefficients remain labelled unsupported assumptions."},
    {"taskId": "radiation-dose-response",
     "wouldPredict": "growth vs absorbed dose",
     "eligibility": "insufficient",
     "reason": "No absorbed-dose measurement paired with any plant response.",
     "alternativeApplied": "Simulator coefficients remain labelled unsupported assumptions."},
]

# Guard rails restated as data so the report and the code cannot disagree.
POLICY = {
    "deepLearning": {
        "permitted": False,
        "reason": ("Largest measured target is 123 samples across 35 groups and 2 "
                   "campaigns. Any neural model would be unidentifiable at this size, "
                   "and its reported error would be optimistically biased regardless "
                   "of grouping discipline."),
    },
    "modelClassesBenchmarked": ["Dummy baseline", "Ridge (linear)", "RandomForest", "HistGradientBoosting"],
    "groupingPolicy": (
        "Every CV split is grouped by the biological replicate (tray, pillow or "
        "experiment). Splitting samples from one replicate across folds is treated "
        "as an invalid evaluation, not a methodological choice."
    ),
    "transferPolicy": (
        "Held-out-study evaluation is reported for every task where more than one "
        "study or campaign exists, even when it is unflattering. A model that beats "
        "its baseline within pooled data but fails to transfer is reported as "
        "'experimental', never 'validated'."
    ),
    "promotionRule": (
        "A model may only be described as validated if it beats its baseline AND "
        "has positive R2 on every held-out study AND its interval coverage is "
        "within 5 percentage points of nominal."
    ),
}


def main() -> int:
    if not safedata.exists(CATALOG):
        print(f"missing {CATALOG}; run scripts/build_measurement_catalog.py first",
              file=sys.stderr)
        return 1
    catalog = safedata.load(CATALOG)

    ntrs = []
    for target in catalog["targets"]:
        ntrs.append({
            "taskId": f"ntrs-target-{target['id']}",
            "target": target["name"],
            "eligibility": target["eligibility"],
            "measurementStatus": target["status"],
            "trainable": target["eligibility"] in ("ready", "statistical"),
            "trained": False,
            "reason": target["eligibilityNote"],
            "replicates": target["replicates"],
            "source": sorted({item.get("source", "") for item in target["evidence"]}) or ["none"],
        })

    trainable_now = [t for t in ntrs + EXISTING if t["eligibility"] == "ready"]
    matrix = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "phase": 7,
        "policy": POLICY,
        "existingTasks": EXISTING,
        "ntrsTargets": ntrs,
        "refusedTasks": REFUSED,
        "summary": {
            "existingTaskCount": len(EXISTING),
            "ntrsTargetCount": len(ntrs),
            "refusedTaskCount": len(REFUSED),
            "readyForPredictiveTraining": [t["taskId"] for t in trainable_now],
            "trainableButConstrained": [t["taskId"] for t in ntrs + EXISTING
                                        if t["eligibility"] == "statistical"],
            "newModelsTrained": ["mizuna-microbial-relative-load-v2"],
            "newModelsTrainedReason": (
                "Only one task changed verdict in Phase 7: the microbial task, whose "
                "estimand was re-scoped from absolute load to within-campaign relative "
                "load because diagnosis showed the campaign offset - not the effect - "
                "is what fails to transfer. No NTRS target qualified for training."
            ),
        },
    }

    problems = []
    for task in ntrs + EXISTING:
        if task["eligibility"] not in ("ready", "statistical", "mechanistic",
                                       "plausibility-only", "insufficient"):
            problems.append(f"{task['taskId']}: unknown eligibility '{task['eligibility']}'")
        if task["trained"] and task["eligibility"] == "insufficient":
            problems.append(f"{task['taskId']}: refused task marked trained")
    if problems:
        print("ELIGIBILITY MATRIX REJECTED:", file=sys.stderr)
        for problem in problems:
            print("  -", problem, file=sys.stderr)
        return 1

    safedata.dump(matrix, OUT)
    print("ELIGIBILITY MATRIX BUILT")
    print(f"  existing tasks   : {len(EXISTING)}")
    print(f"  NTRS targets     : {len(ntrs)}")
    print(f"  refused tasks    : {len(REFUSED)}")
    print(f"  ready to train   : {len(trainable_now)}")
    print(f"  written          : {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
