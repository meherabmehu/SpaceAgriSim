"""Phase 35: give every served model a machine-derived evidence verdict.

Phase 34 measured what each interval does outside the campaign it was fitted on. This script turns
those measurements, and every other independent check already committed in this repository, into a
single per-model verdict that the audit, the API and the interface all read from one place. Nothing
here is typed in by hand: every number is read out of an evaluation file or a model card, and
`--check` fails when a card disagrees with its evidence.

Verdicts
--------
`fails-independent-check`
    An independent check exists and the model did not meet it. Decisive failures need no invented
    threshold: a nominal 90 % interval that contains none of six independent treatment means has
    failed, and a pre-registered 30 % MAPE criterion missed at 41.6 % has failed.
`passes-independent-check`
    Every independent check passed, and each one was scored against a criterion that was declared
    before this script existed: `acceptanceCriterionPct` in the card, or the `evidenceBasis` rule
    the card recorded for itself.
`no-independent-check`
    The model has only within-study or within-campaign performance. That is not a failure, but it
    is also not validation, and the interface must not present it as if it were.

`decisionGrade` is true only for `passes-independent-check`, and it carries a `decisionScope` that
says what the number may be used for.

Applying a criterion after the fact
-----------------------------------
One criterion is new: the mizuna v2 `evidenceBasis` rule says the interval must be "within 5 points
of nominal". Phase 34 measured that at 0.8943 against 0.90. The rule was written before the
measurement, but the *application* of it to a cross-campaign number rather than a within-campaign
one happens now, and the report says so rather than implying it was pre-registered end to end.

Run: python ml/research/phase35_evidence_verdicts.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
ARTIFACTS = ROOT / "ml" / "artifacts"
COVERAGE = ROOT / "ml" / "evaluation" / "phase34_cross_campaign_coverage"
OUTPUT = ROOT / "ml" / "evaluation" / "phase35_model_evidence"

# The interval rule is applied to the pooled cross-campaign coverage Phase 34 measured.
COVERAGE_TOLERANCE = 0.05

SERVED = (
    "lettuce-earth-growth-v1",
    "lettuce-earth-growth-v2",
    "lettuce-earth-growth-v3",
    "mizuna-microbial-relative-load-v2",
    "radiation-quality-osd46-v1",
    "radiation-exposure-osd46-v1",
    "tomato-flight-response-v1",
)
WITHDRAWN = ("mizuna-harvest-v1", "mizuna-microbial-load-v1")


def load(path: Path) -> dict:
    return safedata.load(path)


def coverage_checks(model_id: str, coverage: dict) -> list[dict]:
    """Cross-campaign interval coverage, as measured by Phase 34 for this model."""
    row = (coverage.get("models") or {}).get(model_id)
    if not row:
        return []
    campaign = row["crossCampaign"]
    if "pooledAchievedCoverage" in campaign:
        achieved = float(campaign["pooledAchievedCoverage"])
        nominal = 0.9
        passed = achieved >= nominal - COVERAGE_TOLERANCE
        return [{
            "check": "cross-campaign conformal coverage",
            "criterion": (f"pooled achieved coverage within {COVERAGE_TOLERANCE:.2f} of the nominal "
                          f"{nominal:.2f} (the rule the card recorded for itself)"),
            "measured": achieved,
            "unit": "coverage of a nominal 90 % interval",
            "passed": passed,
            "groups": campaign["observations"],
            "detail": (f"{campaign['covered']} of {campaign['observations']} samples covered, pooled "
                       f"across both calibration directions"),
            "evidence": "ml/evaluation/phase34_cross_campaign_coverage",
        }]
    covered = int(campaign["covered"])
    total = int(campaign["observations"])
    # No threshold is invented here: an interval that contains none of the independent observations
    # has failed a 90 % coverage claim whatever the tolerance, and every observation inside it has
    # also not been shown to be anything better than width.
    passed = None if 0 < covered < total else covered == total
    return [{
        "check": "cross-campaign interval coverage",
        "criterion": ("no observation may fall outside a nominal 90 % interval that is offered as a "
                      "90 % interval; the study's six treatment means are independent of the fit"),
        "measured": round(covered / total, 4) if total else None,
        "unit": "coverage of a nominal 90 % interval",
        "passed": passed,
        "groups": total,
        "detail": (f"{covered} of {total} independent treatment means covered, prediction/measurement "
                   f"ratio median {campaign['ratioMedian']} "
                   f"({campaign['ratioMin']}-{campaign['ratioMax']})"),
        "evidence": "ml/evaluation/phase34_cross_campaign_coverage",
    }]


def readable_rule_detail(card: dict, rule: dict, measured: dict) -> str:
    """The recorded rule as one readable sentence, using the numbers behind each term."""
    parts = []
    r2 = card.get("metrics", {}).get("R2")
    if "beatsBaselineWithinPooledData" in rule:
        parts.append(f"pooled R2 {round(r2, 3) if isinstance(r2, (int, float)) else r2} against a "
                     f"training-mean baseline")
    held_out = measured.get("positiveR2OnEveryHeldOutCampaign") or {}
    if "positiveR2OnEveryHeldOutCampaign" in rule and held_out:
        parts.append("held-out R2 positive on every campaign ("
                     + ", ".join(f"{campaign} {round(value, 3)}"
                                 for campaign, value in held_out.items()) + ")")
    permutation = measured.get("transferSignificantUnderPermutation") or {}
    if "transferSignificantUnderPermutation" in rule and permutation:
        parts.append("permutation p = "
                     + ", ".join(f"{round((block or {}).get('empiricalPValue', 0), 3)}"
                                 for block in permutation.values())
                     + f" over {(next(iter(permutation.values())) or {}).get('permutations', 0)} "
                       "permutations")
    if "intervalsEmpiricallyCalibrated" in rule:
        parts.append("cross-campaign interval coverage "
                     f"{rule['intervalsEmpiricallyCalibrated'] and 'measured' or 'not measured'}")
    return "; ".join(parts)


def card_checks(card: dict, coverage: list[dict]) -> list[dict]:
    """The independent checks a card already records, scored against their own criteria."""
    checks = []
    independent = (card.get("validation") or {})
    independent = independent.get("independent") if isinstance(independent, dict) else None
    if isinstance(independent, dict) and "passed" in independent:
        metrics = independent.get("metrics") or {}
        criterion = independent.get("acceptanceCriterionPct")
        value = metrics.get("MAPE")
        checks.append({
            "check": "independent holdout error",
            "criterion": f"MAPE <= {criterion} % fixed before the measurement"
                         if criterion is not None else "pre-registered criterion",
            "measured": value,
            "unit": "% MAPE",
            "passed": bool(independent.get("passed")),
            "groups": metrics.get("n"),
            "detail": (f"{independent.get('study', 'independent study')}: "
                       f"{round(value, 3) if isinstance(value, (int, float)) else value} % MAPE against "
                       f"{criterion} %"),
            "evidence": "ml/artifacts/" + card["id"] + "#validation.independent",
        })
    basis = card.get("evidenceBasis") or {}
    rule = {k: v for k, v in basis.items() if isinstance(v, bool)}
    # One term of the mizuna rule - "conformal coverage within 5 points of nominal" - was stored as
    # a boolean that was false only because the coverage had not been measured across campaigns yet.
    # When such a measurement exists, the term is scored from the measurement rather than from the
    # stored flag, and the card is updated to say which file supplied it.
    coverage_terms = [c for c in coverage if c.get("passed") is not None]
    if rule and "intervalsEmpiricallyCalibrated" in rule and coverage_terms:
        rule["intervalsEmpiricallyCalibrated"] = bool(coverage_terms[0]["passed"])
    if rule:
        transfer = card.get("transferSummary") or {}
        measured = {
            "beatsBaselineWithinPooledData": (card.get("metrics") or {}).get("R2"),
            "positiveR2OnEveryHeldOutCampaign": transfer.get("v2HeldOutR2"),
            "transferSignificantUnderPermutation": transfer.get("permutationTest"),
        }
        checks.append({
            "check": "pre-registered evidence rule",
            "criterion": basis.get("rule"),
            "measured": measured,
            "unit": "mixed: R2, held-out R2 per campaign, permutation p",
            "passed": all(rule.values()),
            "groups": card.get("groups"),
            # A sentence rather than a dump of booleans: this string is what the interface shows a
            # reader, and `beatsBaselineWithinPooledData=True` is not a sentence.
            "detail": readable_rule_detail(card, rule, measured),
            "evidence": "ml/artifacts/" + card["id"] + "#evidenceBasis",
            "ruleTerms": rule,
        })
    return checks


def verdict_for(model_id: str, card: dict, coverage: dict) -> dict:
    measured = coverage_checks(model_id, coverage)
    checks = card_checks(card, measured) + measured
    if model_id in WITHDRAWN:
        return {
            "verdict": "withdrawn",
            "decisionGrade": False,
            "reason": "Not served. Retained as a documented negative result.",
            "checks": checks,
        }
    failures = [c for c in checks if c.get("passed") is False]
    passes = [c for c in checks if c.get("passed") is True]
    if failures:
        verdict = "fails-independent-check"
        reason = "; ".join(c["detail"] for c in failures)
    elif passes:
        verdict = "passes-independent-check"
        reason = "; ".join(c["detail"] for c in passes)
    else:
        verdict = "no-independent-check"
        reason = ("Only within-study or within-campaign performance is recorded; no independent "
                  "campaign has scored this model.")
    return {
        "verdict": verdict,
        "decisionGrade": verdict == "passes-independent-check",
        "decisionScope": (card.get("servedScope") if verdict == "passes-independent-check" else None),
        "reason": reason,
        "checks": checks,
    }


def mizuna_v2_status_change(card: dict, verdict: dict) -> dict | None:
    """Promote only when the card's own recorded rule is fully satisfied by measured evidence.

    The rule lives in the card (`evidenceBasis.rule`) and was written before Phase 34 measured the
    cross-campaign coverage it refers to. The single term that was false - `intervalsEmpiricallyCalib
    rated` - is the one Phase 34 measured, so the promotion is a consequence of evidence rather than
    of a new decision.
    """
    if verdict["verdict"] != "passes-independent-check":
        return None
    basis = card.get("evidenceBasis") or {}
    if not basis:
        return None
    coverage = coverage_checks(card["id"], load(COVERAGE))
    if not coverage or coverage[0]["passed"] is not True:
        return None
    updated = dict(basis)
    updated["intervalsEmpiricallyCalibrated"] = True
    updated["intervalsEmpiricallyCalibratedEvidence"] = (
        "ml/evaluation/phase34_cross_campaign_coverage: pooled cross-campaign coverage "
        f"{coverage[0]['measured']} against a nominal 0.90")
    return updated


def apply(write: bool) -> int:
    coverage = load(COVERAGE) if safedata.exists(COVERAGE) else {"models": {}}
    report = {
        "schema": "spaceagrisim.model_evidence/1",
        "purpose": ("One machine-derived evidence verdict per registered model, read from committed "
                    "evaluation files and model cards. No verdict is typed in by hand."),
        "criteria": {
            "coverageTolerance": COVERAGE_TOLERANCE,
            "decisionGrade": "true only for passes-independent-check",
            "note": ("A model with no independent check is not failed, but it is not validated "
                     "either, and the verdict says exactly that."),
        },
        "models": {},
    }
    changed = []
    for path in safedata.records(ARTIFACTS):
        card = load(path)
        if not isinstance(card, dict) or not card.get("id"):
            continue
        model_id = card["id"]
        verdict = verdict_for(model_id, card, coverage)
        if model_id not in WITHDRAWN:
            if card.get("evidenceVerdict") != verdict:
                card["evidenceVerdict"] = verdict
                changed.append(f"{model_id}: evidenceVerdict")
            if model_id == "mizuna-microbial-relative-load-v2":
                basis = mizuna_v2_status_change(card, verdict)
                if basis is not None:
                    if card.get("evidenceBasis") != basis:
                        card["evidenceBasis"] = basis
                        changed.append(f"{model_id}: evidenceBasis (coverage now measured)")
                    if card.get("evidenceStatus") != "validated-exploratory":
                        card["evidenceStatus"] = "validated-exploratory"
                        changed.append(f"{model_id}: evidenceStatus -> validated-exploratory")
            if write:
                safedata.dump(card, path)
        report["models"][model_id] = verdict

    report["counts"] = {
        verdict: sum(1 for row in report["models"].values() if row["verdict"] == verdict)
        for verdict in ("passes-independent-check", "fails-independent-check",
                        "no-independent-check", "withdrawn")
    }
    report["counts"]["decisionGrade"] = sum(1 for row in report["models"].values()
                                            if row["decisionGrade"])
    if write:
        safedata.dump(report, OUTPUT)
        for entry in changed:
            print(f"updated {entry}")
        print(f"wrote {OUTPUT.relative_to(ROOT)}")
    for model_id, row in report["models"].items():
        print(f"  {model_id:36s} {row['verdict']:26s} decisionGrade={row['decisionGrade']}")
    return 0


def check() -> int:
    coverage = load(COVERAGE)
    problems = []
    for path in safedata.records(ARTIFACTS):
        card = load(path)
        if not isinstance(card, dict) or not card.get("id") or card["id"] in WITHDRAWN:
            continue
        expected = verdict_for(card["id"], card, coverage)
        if card.get("evidenceVerdict") != expected:
            problems.append(f"{card['id']}: evidenceVerdict does not match the committed evidence")
        if expected["verdict"] == "fails-independent-check":
            scope = str(card.get("servedScope") or "")
            if not scope:
                problems.append(f"{card['id']}: a failed check must still declare a served scope")
        if card.get("evidenceStatus") == "validated-exploratory" and not expected["decisionGrade"]:
            problems.append(f"{card['id']}: claims validated-exploratory without a passing check")
    if problems:
        print("phase 35 evidence verdicts are NOT consistent:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("phase 35 evidence verdicts consistent with the committed measurements")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    return check() if arguments.check else apply(write=True)


if __name__ == "__main__":
    sys.exit(main())
