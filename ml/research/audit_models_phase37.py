"""Phase 37 audit of all seven served models against the evidence acquired this phase.

The obligation here is not to find a reason to promote a model. It is to state, for each
served model, what evidence exists, whether that evidence is independent, and whether the
new datasets can test it at all. A model that cannot be tested is reported as untested -
never as validated, and never as failed for want of data it was never meant to see.

What is checked, per model:
  card        - every field the platform's own audit treats as the model card is present
  domain      - a numeric domain is declared for every feature the caller must supply
  training    - seed, sample count, group count, training script and a training-data hash
  metrics     - held-out metrics exist alongside the baseline they must beat
  uncertainty - an interval definition is present
  artifact    - the file on disk still hashes to the value in the registry
  leakage     - the split unit is recorded as groups rather than rows
  newEvidence - whether either Phase 37 dataset falls inside the declared domain

Usage: python3 ml/research/audit_models_phase37.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
REGISTRY = ROOT / "ml" / "artifacts" / "registry.json"
EVIDENCE = ROOT / "ml" / "evaluation" / "phase37_model_evidence.json"

# Card obligations, each with the field names that can satisfy it. The two model families do not
# carry the same schema: a regressor records a training script and a data hash, while a
# transcriptomic classifier records an evaluator, a source checksum and a probability calibration
# instead of a prediction interval. Checking one literal key across both would report seven
# "incomplete" cards that are in fact complete under their own contract - a false alarm is as
# misleading as a missed one.
CARD_OBLIGATIONS = {
    "identity": ["id", "name"],
    "task": ["task"],
    "organism": ["crop", "organism"],
    "provenance": ["sourceStudy", "sourceUrl", "sourceCitation"],
    "licence": ["sourceLicense", "license"],
    "method": ["method"],
    "features": ["features"],
    "outcome": ["target", "classLabels"],
    "units": ["unit", "expressionUnits"],
    "metrics": ["metrics"],
    "baseline": ["baselineMetrics", "beatsBaseline", "metrics.baselineMacroF1"],
    "uncertainty": ["interval", "probabilityCalibration"],
    "domain": ["domain"],
    "validation": ["validation", "supplementaryEvaluation", "permutationTest", "transfer"],
    "limitations": ["limitations"],
    "trainingCode": ["trainingScript", "evaluator", "environment"],
    "trainingDataHash": ["trainingDataSha256", "sourceChecksum"],
    "seed": ["seed"],
    "samples": ["samples"],
    "groups": ["groups"],
}

# Where each artifact can be regenerated from. The artifact JSON of four of these seven models does
# not embed a pointer to the code that produced it, so the path is resolved here by the script that
# actually names the model id. Recording it makes the gap actionable without editing a published
# artifact and invalidating its checksum.
REPRODUCTION = {
    "lettuce-earth-growth-v1": "ml/training/train_lettuce.py",
    "lettuce-earth-growth-v2": "ml/training/train_lettuce_v2.py",
    "lettuce-earth-growth-v3": "ml/training/train_lettuce_v3.py",
    "mizuna-microbial-relative-load-v2": "ml/training/train_microbial_v2.py",
    "radiation-exposure-osd46-v1": "ml/training/train_radiation_osd46.py",
    "radiation-quality-osd46-v1": "ml/training/train_radiation_osd46.py",
    "tomato-flight-response-v1": "ml/training/train_models.py",
}

# Features each model asks a caller for. Used to test whether a new dataset could address it.
CALLER_FEATURES = {
    "lettuce-earth-growth-v1": ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"],
    "lettuce-earth-growth-v2": ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"],
    "lettuce-earth-growth-v3": ["daysAfterTransplant", "airTemperature", "rootTemperature",
                                "dailyLightIntegral"],
}

# What the two datasets acquired this phase actually measure, as evidenced by the analysis files.
PHASE37_DATASETS = {
    "zenodo-green-light-lettuce": {
        "doi": "10.5281/zenodo.20394352",
        "measures": {
            "daysAfterTransplant": [28, 35],
            "airTemperature": None,
            "rootTemperature": None,
            "ppfd": None,
            "dailyLightIntegral": None,
        },
        "note": ("Photoperiod 16 h and a targeted 200 umol m-2 s-1 are stated by the authors, but no "
                 "measured PPFD column is deposited and no temperature is measured at all. The "
                 "destructive harvest is a single endpoint at 35 days, outside the declared "
                 "2-29 day domain."),
    },
    "zenodo-nutrient-dosing": {
        "doi": "10.5281/zenodo.17794636",
        "measures": {
            "daysAfterTransplant": None,
            "airTemperature": None,
            "rootTemperature": None,
            "ppfd": None,
            "dailyLightIntegral": None,
        },
        "note": ("Ion concentrations, electrical conductivity and one destructive harvest. No "
                 "temperature, no light and no time series of mass, so every growth feature is "
                 "absent."),
    },
}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def domain_of(artifact: dict) -> dict:
    dom = artifact.get("domain") or {}
    return {k: v for k, v in dom.items() if isinstance(v, dict)}


def domain_test(model_id: str, artifact: dict) -> dict:
    """Can either new dataset supply this model's required features?"""
    features = artifact.get("features") or []
    if model_id.startswith(("radiation-", "tomato-")):
        return {
            "testable": False,
            "reason": ("Transcriptomic model. It consumes a normalised expression vector, not "
                       "environmental measurements, and neither dataset deposits expression. "
                       "Untested rather than failed."),
        }
    if model_id.startswith("mizuna-"):
        return {
            "testable": False,
            "reason": ("It predicts from flight microclimate and microbiome covariates recorded in "
                       "VEG-04. Neither dataset is a VEG-04 experiment, so no independent "
                       "prediction is possible. Untested rather than failed."),
        }
    needed = CALLER_FEATURES.get(model_id, [])
    if not needed:
        return {"testable": False, "reason": "No caller-feature list recorded for this model."}
    dom = domain_of(artifact)
    per_dataset = {}
    for name, meta in PHASE37_DATASETS.items():
        have, missing, out_of_range = [], [], []
        for f in needed:
            vals = meta["measures"].get(f)
            if not vals:
                missing.append(f)
                continue
            rng = dom.get(f) or {}
            lo, hi = rng.get("min"), rng.get("max")
            if lo is None or hi is None:
                have.append(f)
            elif all(lo <= v <= hi for v in vals):
                have.append(f)
            else:
                out_of_range.append({"feature": f, "values": vals, "domain": [lo, hi]})
        per_dataset[name] = {"supplied": have, "absent": missing, "outOfDomain": out_of_range}
    testable = any(not d["absent"] and not d["outOfDomain"] for d in per_dataset.values())
    return {
        "testable": testable,
        "requiredFeatures": needed,
        "datasets": per_dataset,
        "reason": ("At least one dataset supplies every required feature inside the declared "
                   "domain." if testable else
                   "Neither dataset supplies every required feature inside the declared domain, "
                   "so no prediction can be scored without violating the model's own contract."),
    }


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    previous = {}
    prev_path = ROOT / "ml" / "evaluation" / "phase36_model_reevaluation.json"
    if prev_path.exists():
        previous = json.loads(prev_path.read_text()).get("models") or {}

    # The served set is read from the application rather than hard-coded here, so a model that is
    # withdrawn tomorrow cannot keep appearing as served in this report.
    from app import research  # noqa: E402  (path set above)
    served_ids = {m["id"] for m in research.model_registry()["models"]}
    retired_ids = set(research.RETIRED_MODEL_IDS)

    models = {}
    for entry in registry["models"]:
        mid = entry["id"]
        if mid not in served_ids:
            continue
        path = ROOT / entry["artifact"]
        artifact = json.loads(path.read_text())
        on_disk = sha256(path)

        # Dotted paths are followed, so "metrics.baselineMacroF1" is a real look-up rather than a
        # label that happens to be listed.
        def present(path: str) -> bool:
            node = artifact
            for part in path.split("."):
                if not isinstance(node, dict):
                    return False
                node = node.get(part)
            return node not in (None, "", [], {})

        satisfied, missing_card = {}, []
        for obligation, alternatives in CARD_OBLIGATIONS.items():
            hit = next((a for a in alternatives if present(a)), None)
            if hit:
                satisfied[obligation] = hit
            else:
                missing_card.append(obligation)
        feats = artifact.get("features") or []
        dom = domain_of(artifact)
        # A transcriptomic model declares its domain as an expression range rather than per-gene
        # bounds; that is still a domain, so it counts.
        domain_complete = bool(dom) and (all(f in dom for f in feats) or "expressionRange" in dom)

        interval = artifact.get("interval") or {}
        has_interval = bool(interval.get("kind") or interval.get("method")
                            or interval.get("outOfFoldCoverage") or interval.get("coverage"))
        # A classifier states its uncertainty as a calibrated probability, not as a prediction
        # interval. Both count as an uncertainty statement; neither is invented for a model that
        # lacks one.
        calib = artifact.get("probabilityCalibration") or {}
        has_uncertainty = has_interval or bool(calib)
        uncertainty_kind = ("prediction-interval" if has_interval
                            else "probability-calibration" if calib else None)

        leakage = artifact.get("validation") or {}
        groups = artifact.get("groups")
        group_note = json.dumps(leakage)

        prev = previous.get(mid, {})
        models[mid] = {
            "artifactSha256": on_disk,
            "registrySha256Matches": on_disk == entry.get("sha256"),
            "artifactUnchangedFromPhase36": (
                prev.get("artifactSha256") in (None, on_disk)),
            "cardMissingObligations": missing_card,
            "cardSatisfiedBy": satisfied,
            "cardComplete": not missing_card,
            "domainDeclared": domain_complete,
            "domainFeatureCount": len(dom),
            "featureCount": len(feats),
            "hasInterval": has_interval,
            "hasUncertainty": has_uncertainty,
            "uncertaintyKind": uncertainty_kind,
            "calibrationRecorded": bool(calib),
            "intervalMethod": interval.get("kind") or interval.get("method"),
            "intervalCoverage": (interval.get("outOfFoldCoverage")
                                 if interval.get("outOfFoldCoverage") is not None
                                 else interval.get("coverage")),
            "intervalCoverageIsIndependent": bool(interval.get("crossCampaign")),
            "samples": artifact.get("samples"),
            "groups": groups,
            "splitIsGrouped": ("group" in group_note.lower() or "campaign" in group_note.lower()
                               or bool(groups)),
            "metrics": artifact.get("metrics"),
            "baselineMetrics": (artifact.get("baselineMetrics")
                                or (artifact.get("metrics") or {}).get("baselineMacroF1")
                                or artifact.get("beatsBaseline")),
            "status": artifact.get("status"),
            "evidenceVerdictInArtifact": artifact.get("evidenceVerdict"),
            "verdictBefore": prev.get("verdictAfter") or artifact.get("evidenceVerdict"),
            "decisionGradeBefore": bool(prev.get("decisionGradeAfter")),
            "newEvidenceTest": domain_test(mid, artifact),
            "retrained": False,
            "thresholdsChanged": False,
            "reproductionScript": REPRODUCTION.get(mid),
            "reproductionScriptExists": bool(REPRODUCTION.get(mid)
                                            and (ROOT / REPRODUCTION[mid]).is_file()),
            "embedsTrainingScript": "trainingScript" in artifact,
            "embedsTrainingDataHash": bool(artifact.get("trainingDataSha256")
                                           or artifact.get("sourceChecksum")),
        }

    # The five-way classification the completion brief asks for, read off the artifact's own
    # recorded verdict rather than assigned by this script. A model can only move if the new
    # evidence was able to test it, which for every model here it was not, so the verdicts are
    # carried forward unchanged and the reason is written down instead of assumed.
    TAXONOMY = {
        "passes-independent-check": "PASS decision-grade",
        "fails-independent-check": "FAILS-INDEPENDENT-CHECK",
        "no-independent-check": "NO-INDEPENDENT-CHECK",
        "domain-refused": "DOMAIN-REFUSED",
        "insufficient-evidence": "INSUFFICIENT-EVIDENCE",
    }
    for mid, rec in models.items():
        verdict = rec["verdictBefore"]
        if isinstance(verdict, dict):
            verdict = verdict.get("verdict")
        rec["verdictAfter"] = verdict
        rec["decisionGradeAfter"] = rec["decisionGradeBefore"]
        rec["promoted"] = False
        rec["classification"] = TAXONOMY.get(str(verdict), "INSUFFICIENT-EVIDENCE")
        if not rec["newEvidenceTest"]["testable"]:
            rec["newEvidenceOutcome"] = "NOT-TESTED"
            rec["why"] = rec["newEvidenceTest"]["reason"]
        else:
            rec["newEvidenceOutcome"] = "PENDING-SCORE"
            rec["why"] = "New evidence falls inside the domain and must be scored."

    counts = {
        "served": len(models),
        "retainedNotServed": len(retired_ids),
        "scored": sum(1 for r in models.values() if r["newEvidenceOutcome"] == "PENDING-SCORE"),
        "classification": {k: sum(1 for r in models.values() if r["classification"] == k)
                           for k in sorted(set(TAXONOMY.values()))},
        "notTestedByNewEvidence": sum(1 for r in models.values()
                                      if r["newEvidenceOutcome"] == "NOT-TESTED"),
        "decisionGradeBefore": sum(1 for r in models.values() if r["decisionGradeBefore"]),
        "decisionGradeAfter": sum(1 for r in models.values() if r["decisionGradeAfter"]),
        "artifactHashesVerified": sum(1 for r in models.values()
                                      if r["registrySha256Matches"] and r["artifactUnchangedFromPhase36"]),
        "cardsComplete": sum(1 for r in models.values() if r["cardComplete"]),
        "domainsDeclared": sum(1 for r in models.values() if r["domainDeclared"]),
        "withInterval": sum(1 for r in models.values() if r["hasInterval"]),
        "withUncertainty": sum(1 for r in models.values() if r["hasUncertainty"]),
        "groupedSplits": sum(1 for r in models.values() if r["splitIsGrouped"]),
        "withBaseline": sum(1 for r in models.values() if r["baselineMetrics"]),
        "reproductionScriptResolvable": sum(1 for r in models.values()
                                            if r["reproductionScriptExists"]),
        "embedTrainingDataHash": sum(1 for r in models.values()
                                     if r["embedsTrainingDataHash"]),
    }

    payload = {
        "schema": "spaceagrisim.phase37.model_evidence/1",
        "generatedAt": "2026-11-12",
        "generatedBy": "ml/research/audit_models_phase37.py",
        "policy": {
            "noDomainExpansion": True,
            "noThresholdMoves": True,
            "noRetraining": True,
            "noRelabelling": True,
            "note": ("Artifacts were not retrained, thresholds were not moved, and no verdict was "
                     "changed. Models are audited against the evidence rather than the evidence "
                     "being shaped around the models."),
        },
        "newEvidence": {k: {"doi": v["doi"], "note": v["note"]}
                        for k, v in PHASE37_DATASETS.items()},
        "models": models,
        "counts": counts,
    }
    EVIDENCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"models audited      {counts['served']} (served set from app.research)")
    print("classification                       "
          + "  ".join(f"{k}={v}" for k, v in counts["classification"].items() if v))
    print(f"scored on new evidence               {counts['scored']} "
          f"(not tested: {counts['notTestedByNewEvidence']})")
    print(f"artifact hashes verified             {counts['artifactHashesVerified']}/{counts['served']}")
    print(f"complete cards / domains / uncertainty / grouped splits / baselines  "
          f"{counts['cardsComplete']} / {counts['domainsDeclared']} / {counts['withUncertainty']} / "
          f"{counts['groupedSplits']} / {counts['withBaseline']}")
    print(f"reproduction script resolvable / embeds training-data hash             "
          f"{counts['reproductionScriptResolvable']} / {counts['embedTrainingDataHash']}")
    print(f"decision grade before -> after       {counts['decisionGradeBefore']} -> "
          f"{counts['decisionGradeAfter']}")
    print(f"report -> {EVIDENCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
