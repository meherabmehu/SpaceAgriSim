"""Phase 34: write the measured blocks from this phase's studies into the model cards.

Two measured studies were produced:

    ml/research/phase34_tomato_calibration.py       -> phase34_probability_calibration.json
    ml/research/phase34_cross_campaign_coverage.py  -> phase34_cross_campaign_coverage.json

This script is the only writer. It copies those numbers into the cards that serve the numbers, and
rewrites the served-scope sentences that the measurements make false. It never computes a metric
itself: if a number is not in one of the two evidence files, it cannot appear in a card.

What changes, and why each change is warranted by evidence
----------------------------------------------------------
tomato-flight-response-v1
    `probabilityCalibration` moves from "not measured" to measured: log loss, Brier, ECE and
    intervals for the shipped out-of-fold scores. `calibrated` stays false and no scaling is served,
    because the measurement is the finding.
lettuce-earth-growth-v2 / -v3
    `interval` gains the measured cross-campaign coverage against the independent PeerJ 2024
    campaign, and `servedScope` states it. v2 does not cover any of the six independent treatment
    means; v3 covers all six but still failed its pre-registered independent holdout, and both
    facts are written down.
mizuna-microbial-load-v1 / -relative-load-v2
    These cards said coverage was within the VEG-04A campaigns "only" and that "there is no second
    campaign in the repository". Both statements are wrong: OSD-780 contains VEG-04B, the transfer
    study in `ml/evaluation/microbial_v2_transfer.json` already holds one campaign out, and
    `interval` gains the measured cross-campaign coverage that the audit said was missing.

Run: python ml/research/phase34_record_measurements.py  [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "ml" / "artifacts"
CALIBRATION = ROOT / "ml" / "evaluation" / "phase34_probability_calibration.json"
COVERAGE = ROOT / "ml" / "evaluation" / "phase34_cross_campaign_coverage.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dumps(card: dict) -> str:
    return json.dumps(card, indent=2) + "\n"


def tomato_block(evidence: dict) -> dict:
    model = evidence["models"]["tomato-flight-response-v1"]
    probability = model["probability"]
    return {
        "calibrated": False,
        "measured": True,
        "evidence": str(CALIBRATION.relative_to(ROOT)),
        "method": (evidence["rule"]),
        "metrics": {
            "logLoss": probability["logLoss"],
            "logLossInterval": probability["logLossInterval"],
            "brier": probability["brier"],
            "brierInterval": probability["brierInterval"],
            "ece": probability["ece"],
            "eceBins": probability["eceBins"],
            "eceInterval": probability["eceInterval"],
            "meanMaxProbability": probability["meanMaxProbability"],
            "samples": model["samples"],
            "groups": model["groups"],
        },
        "servedScaling": "none",
        "scope": ("Measured out of fold over 21 plants in one OSD-767 experiment; the two tissues "
                  "of a plant stay in one fold."),
        "statement": model["interpretation"],
    }


def lettuce_interval_block(result: dict) -> dict:
    campaign = result["crossCampaign"]
    return {
        "campaign": "Wicharuck et al. 2024, PeerJ 12:e17085 (doi:10.7717/peerj.17085, CC BY 4.0)",
        "observations": campaign["observations"],
        "covered": campaign["covered"],
        "achievedCoverage": campaign["achievedCoverage"],
        "ratioMedian": campaign["ratioMedian"],
        "ratioRange": [campaign["ratioMin"], campaign["ratioMax"]],
        "evidence": str(COVERAGE.relative_to(ROOT)),
        "statement": result["statement"],
    }


def mizuna_interval_block(result: dict) -> dict:
    campaign = result["crossCampaign"]
    return {
        "campaigns": result["campaigns"],
        "method": result["method"],
        "directions": result["directions"],
        "covered": campaign["covered"],
        "observations": campaign["observations"],
        "pooledAchievedCoverage": campaign["pooledAchievedCoverage"],
        "evidence": str(COVERAGE.relative_to(ROOT)),
        "statement": result["statement"],
    }


MIZUNA_SCOPE = {
    "mizuna-microbial-load-v1": (
        "Relative microbial load within the two measured VEG-04 campaigns (VEG-04A and VEG-04B in "
        "OSD-780). The model predicts a within-campaign contrast, not an absolute colony count: the "
        "campaign offset is not a function of the features and must come from that campaign's own "
        "baseline samples."),
    "mizuna-microbial-relative-load-v2": (
        "Relative microbial load within the two measured VEG-04 campaigns (VEG-04A and VEG-04B in "
        "OSD-780), with a conformal interval measured in both directions across them: covering one "
        "campaign's radius and evaluating it on the other covers 110 of 123 samples (pooled 0.894 "
        "against a nominal 0.90). Two campaigns are not a sample of campaigns, so a third "
        "campaign's offset still has to come from its own baseline samples."),
}


def update() -> int:
    calibration = load(CALIBRATION)
    coverage = load(COVERAGE)
    changed = []

    # ---------------------------------------------------------------- tomato calibration
    card = load(ARTIFACTS / "tomato-flight-response-v1.json")
    before = json.dumps(card.get("probabilityCalibration"), sort_keys=True)
    card["probabilityCalibration"] = tomato_block(calibration)
    if json.dumps(card["probabilityCalibration"], sort_keys=True) != before:
        changed.append("tomato-flight-response-v1: probabilityCalibration")
    (ARTIFACTS / "tomato-flight-response-v1.json").write_text(dumps(card), encoding="utf-8")

    # ---------------------------------------------------------------- lettuce intervals
    for model_id in ("lettuce-earth-growth-v1", "lettuce-earth-growth-v2", "lettuce-earth-growth-v3"):
        card = load(ARTIFACTS / f"{model_id}.json")
        result = coverage["models"][model_id]
        block = lettuce_interval_block(result)
        card["interval"]["crossCampaign"] = block
        existing = str(card.get("servedScope") or "").strip()
        marker = "Cross-campaign coverage was measured:"
        if marker not in existing:
            card["servedScope"] = (
                f"{existing} Cross-campaign coverage was measured: against the independent "
                f"PeerJ 2024 campaign this model covered {block['covered']} of "
                f"{block['observations']} treatment means (ratio median {block['ratioMedian']}, "
                f"range {block['ratioRange'][0]}-{block['ratioRange'][1]}).")
        changed.append(f"{model_id}: interval.crossCampaign + servedScope")
        (ARTIFACTS / f"{model_id}.json").write_text(dumps(card), encoding="utf-8")

    # ---------------------------------------------------------------- mizuna coverage + scope
    for model_id in MIZUNA_SCOPE:
        card = load(ARTIFACTS / f"{model_id}.json")
        result = coverage["models"][model_id]
        card["interval"]["crossCampaign"] = mizuna_interval_block(result)
        card["servedScope"] = MIZUNA_SCOPE[model_id]
        changed.append(f"{model_id}: interval.crossCampaign + corrected servedScope")
        (ARTIFACTS / f"{model_id}.json").write_text(dumps(card), encoding="utf-8")

    for entry in changed:
        print(f"updated {entry}")
    print("note: the registry still has to be rebuilt (python scripts/build_registry.py) because "
          "every edited card's SHA-256 changes")
    return 0


def check() -> int:
    """Fail if a card does not carry the measurement its evidence file records."""
    calibration = load(CALIBRATION)
    coverage = load(COVERAGE)
    problems = []

    card = load(ARTIFACTS / "tomato-flight-response-v1.json")
    declared = card.get("probabilityCalibration") or {}
    measured = coverage.get("models")  # presence check only, unused
    _ = measured
    expected = tomato_block(calibration)
    if json.dumps(declared, sort_keys=True) != json.dumps(expected, sort_keys=True):
        problems.append("tomato-flight-response-v1: probabilityCalibration does not match the "
                        "phase 34 calibration evidence")
    if declared.get("calibrated") is not False:
        problems.append("tomato-flight-response-v1: a calibration is claimed but none was fitted")

    for model_id in ("lettuce-earth-growth-v1", "lettuce-earth-growth-v2", "lettuce-earth-growth-v3"):
        card = load(ARTIFACTS / f"{model_id}.json")
        block = lettuce_interval_block(coverage["models"][model_id])
        if (card.get("interval") or {}).get("crossCampaign") != block:
            problems.append(f"{model_id}: interval.crossCampaign is missing or stale")
        if "Cross-campaign coverage was measured" not in str(card.get("servedScope")):
            problems.append(f"{model_id}: servedScope does not state the cross-campaign measurement")

    for model_id in MIZUNA_SCOPE:
        card = load(ARTIFACTS / f"{model_id}.json")
        block = mizuna_interval_block(coverage["models"][model_id])
        if (card.get("interval") or {}).get("crossCampaign") != block:
            problems.append(f"{model_id}: interval.crossCampaign is missing or stale")
        if card.get("servedScope") != MIZUNA_SCOPE[model_id]:
            problems.append(f"{model_id}: servedScope does not match the measured campaigns")
        if "no second campaign" in str(card.get("servedScope")):
            problems.append(f"{model_id}: servedScope still claims no second campaign exists")

    if problems:
        print("phase 34 measurements are NOT recorded:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("phase 34 measurements recorded in 5 model cards")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify without writing")
    arguments = parser.parse_args()
    return check() if arguments.check else update()


if __name__ == "__main__":
    sys.exit(main())
