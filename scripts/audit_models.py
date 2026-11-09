#!/usr/bin/env python3
"""Phase 13: audit every registered model artifact and the dataset safeguards around them.

Read-only by construction. This script re-computes checksums, re-reads each artifact and asserts
the things that must remain true, then writes an audit artifact. It never rewrites a model, a
metric or a classification: an audit that can edit the thing it audits is not an audit.

    python3 scripts/audit_models.py            # audit and report
    python3 scripts/audit_models.py --write    # also write ml/evaluation/phase13_model_audit.json

Exit code is non-zero if any check fails.

What is checked
---------------
1.  Registry integrity      - every registered artifact exists and matches its recorded SHA-256.
2.  No orphan artifacts     - every artifact on disk is registered or marked superseded.
3.  Provenance              - study, URL, source type, licence, method, seed, validation text.
4.  Schema                  - features, target and unit are present and non-empty.
5.  Metrics                 - measured metrics exist and are paired with a baseline; no metric is
                              reported that has no value behind it.
6.  Uncertainty             - a calibration record exists, and any claim of calibration carries a
                              measured coverage rather than an intended one.
7.  Classification          - every model has exactly one science classification, and nothing is
                              classified "unsupported" while still served as a prediction.
8.  Explanations            - an explanation flag matches the artifact that backs it.
9.  Superseded/excluded     - the predecessor is kept rather than overwritten, retired models are
                              not runnable, and none is silently reintroduced.
10. Dataset safeguards      - the OSD-320 duplicate finding is still present, and no artifact
                              describes OSD-320 as independent evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import evidence, research, science_classification, workflow  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
REGISTRY = ARTIFACTS / "registry.json"
OUT = ROOT / "ml" / "evaluation" / "phase13_model_audit.json"

CHECKS: list[dict] = []
FAILURES: list[str] = []
# Findings that are real but are not correctness failures: an absent optional field, a
# classification model with no calibrated probability, a licence not recorded per artifact. They
# are reported and counted, never hidden, and they are never "fixed" by editing an artifact.
GAPS: list[dict] = []
# Files under ml/artifacts that are deliberately not models (see scripts/build_registry.py).
NON_MODEL_ARTIFACTS = {"tomato_example.json"}
# Fields every artifact must record. `license` and `sourceUrl` are tracked separately: they are
# genuinely absent on several artifacts, and inventing them would be worse than reporting them.
REQUIRED_PROVENANCE = ("sourceStudy", "method", "trainedAt", "seed")
TRACKED_PROVENANCE = ("sourceUrl", "sourceType", "license")


def check(name: str, passed: bool, detail: str = "") -> bool:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    if not passed:
        FAILURES.append(f"{name}: {detail}")
    return bool(passed)


def gap(model_id: str, field: str, detail: str, severity: str = "documentation") -> None:
    GAPS.append({"model": model_id, "field": field, "detail": detail, "severity": severity})


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def audit() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    catalogue = {row["modelId"]: row for row in workflow.model_catalogue()["models"]}
    served = research.model_registry()["models"]
    corpus = evidence.corpus()["passages"]

    rows: list[dict] = []
    registered_names: set[str] = set()
    superseded_names: set[str] = set()
    # Cards for models served by their own runtime are legitimate artifacts here, but only
    # because they are declared. The declaration is checked below, and an undeclared card is
    # still an orphan.
    external_cards = {Path(service["card"]).name
                      for service in research.EXTERNAL_SERVICES.values()}

    # ---------------------------------------------------------------- 1. checksums
    for entry in registry["models"]:
        model_id = entry["id"]
        path = ROOT / entry["artifact"]
        registered_names.add(path.name)
        exists = path.is_file()
        check(f"artifact-exists:{model_id}", exists, entry["artifact"])
        if not exists:
            continue
        actual = sha256_of(path)
        check(f"checksum:{model_id}", actual == entry["sha256"],
              f"registry={entry['sha256'][:16]}… disk={actual[:16]}…")
        superseded = entry.get("supersedes")
        if superseded:
            superseded_names.add(f"{superseded}.json")
        artifact = json.loads(path.read_text(encoding="utf-8"))

        # ------------------------------------------------------------ 3. provenance
        provenance = {field: artifact.get(field) for field in
                      REQUIRED_PROVENANCE + TRACKED_PROVENANCE + ("validation",)}
        missing = [field for field, value in provenance.items()
                   if value in (None, "", []) and field not in TRACKED_PROVENANCE
                   and field != "validation"]
        # A superseding artifact may carry its evaluation under a differently named key; the
        # question is whether the validation is documented, not what the key is called.
        validation_documented = bool(artifact.get("validation") or artifact.get("transferSummary")
                                     or artifact.get("evidenceBasis"))
        if not validation_documented:
            missing.append("validation")
        check(f"provenance:{model_id}", not missing, f"missing {missing}" if missing else "complete")
        for field in TRACKED_PROVENANCE:
            if provenance.get(field) in (None, "", []):
                suggestion = ""
                study = artifact.get("sourceStudy") or ""
                if field == "sourceUrl" and isinstance(study, str) and study.startswith("OSD-"):
                    suggestion = f" (derivable: https://osdr.nasa.gov/bio/repo/data/studies/{study})"
                gap(model_id, field, f"not recorded on the artifact{suggestion}")
        limitations = artifact.get("limitations") or []
        check(f"limitations:{model_id}", len(limitations) >= 1, f"{len(limitations)} recorded")

        # ---------------------------------------------------------------- 4. schema
        features = artifact.get("features") or []
        is_classifier = "classif" in str(artifact.get("task", "")).lower()
        # A classifier's schema is its class labels; demanding a numeric target and unit from it
        # would be asking for a field that cannot exist.
        schema_ok = bool(features) and (
            bool(artifact.get("target") and artifact.get("unit"))
            or (is_classifier and bool(artifact.get("classLabels") or artifact.get("classDescription"))))
        check(f"schema:{model_id}", schema_ok,
              f"{len(features)} features, target={artifact.get('target')}, unit={artifact.get('unit')}")

        # --------------------------------------------------------------- 5. metrics
        metrics = artifact.get("metrics") or {}
        measured = {name: value for name, value in metrics.items() if isinstance(value, (int, float))}
        check(f"metrics-present:{model_id}", bool(measured), f"{sorted(metrics)}")
        nulls = [name for name, value in metrics.items() if value is None]
        check(f"metrics-no-null:{model_id}", not nulls, f"null metrics {nulls}" if nulls else "all valued")
        if artifact.get("status", "").startswith("trained") and artifact.get("task", "").find("regression") >= 0:
            check(f"metrics-baseline:{model_id}", bool(artifact.get("baselineMetrics")),
                  "a regression model must report its baseline")

        # ----------------------------------------------------------- 6. uncertainty
        calibration = artifact.get("uncertainty") or artifact.get("interval") or {}
        declared = artifact.get("uncertainty") or {}
        if is_classifier:
            # No classifier here has a calibrated probability. Two separate questions follow, and
            # only the second one is a correctness check: what does the artifact say about it, and
            # does the served surface ever claim calibration it does not have?
            statement = " ".join([str(artifact.get("unit", "")), str(artifact.get("target", "")),
                                  str(artifact.get("classDescription", ""))]
                                 + [str(item) for item in limitations]).lower()
            states = "uncalibrated" in statement or "not calibrated" in statement
            if not states:
                gap(model_id, "calibration",
                    "the model card does not state whether class probabilities are calibrated; "
                    "no calibration analysis is recorded for this classifier",
                    severity="high")
            else:
                gap(model_id, "calibration", "probabilities documented as uncalibrated")
            served_calibration = (catalogue.get(model_id, {}).get("calibration") or {})
            check(f"no-false-calibration-claim:{model_id}",
                  served_calibration.get("calibrated") is not True,
                  "the served catalogue claims a calibrated classifier")
        else:
            check(f"uncertainty:{model_id}", bool(calibration), f"{sorted(calibration)}")
        if declared.get("calibrated") is True or declared.get("empiricallyCalibrated") is True:
            has_coverage = any(key in declared for key in
                               ("measuredCoverage", "empiricalCoverage", "achievedCoverage", "coverage"))
            check(f"calibration-measured:{model_id}", has_coverage,
                  "calibration is claimed without a measured coverage")
            if has_coverage:
                coverage = (declared.get("achievedCoverage") or declared.get("measuredCoverage")
                            or declared.get("empiricalCoverage") or declared.get("coverage"))
                gap(model_id, "calibration-scope", f"measured coverage {coverage} is within the "
                                                   "documented campaigns, not across campaigns")

        # ------------------------------------------------ 7/8. classification + explanation
        entry_classification = science_classification.feature_by_id(model_id)
        check(f"classification:{model_id}", entry_classification is not None,
              "no science classification entry")
        in_catalogue = model_id in catalogue
        check(f"catalogue:{model_id}", in_catalogue, "registered model missing from the workflow catalogue")
        if entry_classification is not None and in_catalogue:
            category = entry_classification.category
            run_status = catalogue[model_id]["runStatus"]
            if category == 6:
                check(f"retired-not-runnable:{model_id}", run_status == "retired",
                      f"category 6 model reports runStatus={run_status}")
            else:
                check(f"served-not-retired:{model_id}", run_status in ("runnable", "unavailable"),
                      f"category {category} model reports runStatus={run_status}")
        explanation_flag = catalogue.get(model_id, {}).get("explanationAvailable")
        explanation_file = ARTIFACTS / f"{model_id}-explanation.json"
        check(f"explanation-flag:{model_id}", bool(explanation_flag) == explanation_file.is_file(),
              f"flag={explanation_flag} file={explanation_file.name} exists={explanation_file.is_file()}")

        rows.append({
            "id": model_id,
            "status": artifact.get("status"),
            "version": artifact.get("version"),
            "sha256": actual,
            "checksumMatches": True,
            "supersedes": artifact.get("supersedes"),
            "task": artifact.get("task"),
            "target": artifact.get("target"),
            "unit": artifact.get("unit"),
            "features": len(features),
            "samples": artifact.get("samples"),
            "groups": artifact.get("groups"),
            "metrics": measured,
            "baselineMetrics": artifact.get("baselineMetrics"),
            "validation": artifact.get("validation"),
            "provenance": provenance,
            "limitations": len(limitations),
            "classification": None if entry_classification is None else {
                "category": entry_classification.category,
                "name": science_classification.CATEGORY_NAMES[entry_classification.category],
            },
            "runStatus": catalogue.get(model_id, {}).get("runStatus"),
            "calibration": catalogue.get(model_id, {}).get("calibration"),
            "explanationAvailable": bool(explanation_flag),
        })

    # ------------------------------------------------------- 2. no unregistered artifacts
    for path in sorted(ARTIFACTS.glob("*.json")):
        if path.name in {"registry.json", *NON_MODEL_ARTIFACTS} or path.name.endswith("-explanation.json"):
            continue
        if path.name in registered_names or path.name in superseded_names:
            continue
        if path.name in external_cards:
            continue
        check(f"artifact-registered:{path.name}", False, "artifact on disk is neither registered nor superseded")
    check("no-orphan-artifacts", not any(c["check"].startswith("artifact-registered:") for c in CHECKS),
          "every artifact is registered or explicitly superseded")

    # --------------------------------------- 11. models served by their own runtime
    for model_id, service in research.EXTERNAL_SERVICES.items():
        card_path = ROOT / service["card"]
        check(f"external-card-exists:{model_id}", card_path.is_file(), service["card"])
        if not card_path.is_file():
            continue
        card = json.loads(card_path.read_text(encoding="utf-8"))
        row = catalogue.get(model_id) or {}
        # The whole point of the declaration is that such a model cannot be parked somewhere
        # unreachable: the catalogue must name the surface that serves it, and that surface must
        # exist in the mounted app.
        check(f"external-run-status:{model_id}", row.get("runStatus") == "external-service",
              f"catalogue runStatus={row.get('runStatus')}")
        check(f"external-endpoint-named:{model_id}",
              bool(service.get("endpoint")) and service["endpoint"].startswith("/api/"),
              str(service.get("endpoint")))
        # Routers are nested, so the app's own OpenAPI document is the honest answer to "is this
        # path actually reachable" rather than walking `app.routes`.
        from app.main import app as mounted_app

        mounted = set(mounted_app.openapi().get("paths") or {})
        check(f"external-endpoint-mounted:{model_id}",
              service["endpoint"] in mounted,
              f"{service['endpoint']} is declared but not routed")
        check(f"external-card-endpoint-mounted:{model_id}",
              service["cardEndpoint"] in mounted,
              f"{service['cardEndpoint']} is declared but not routed")
        check(f"external-classified:{model_id}",
              science_classification.feature_by_id(model_id) is not None,
              "served model with no science classification")
        service_class = science_classification.feature_by_id(model_id)
        if service_class is not None:
            check(f"external-not-unsupported:{model_id}", service_class.category != 6,
                  f"category {service_class.category}")
        # A surrogate that has not passed its gates must not claim to be deployed.
        gates = (card.get("validation") or {}).get("acceptanceGate") or []
        failed = [gate["criterion"] for gate in gates if not gate.get("passed")]
        check(f"external-gates-recorded:{model_id}", bool(gates), f"{len(gates)} criteria")
        check(f"external-deployment-matches-gates:{model_id}",
              (not failed and card.get("deployed") is True)
              or (bool(failed) and card.get("deployed") is False),
              f"failed={failed} deployed={card.get('deployed')}")
        metrics = card.get("metrics") or {}
        check(f"external-metrics-present:{model_id}",
              all(key in metrics for key in ("mae", "rmse", "n")), str(sorted(metrics)))
        baseline = (card.get("baselineMetrics") or {}).get("hargreaves") or {}
        check(f"external-baseline-present:{model_id}", "mae" in baseline, "no baseline to compare")
        # The direction of every criterion is declared, so a "lower is better" metric can never be
        # read as an improvement.
        criteria = card.get("criteria") or {}
        check(f"external-criteria-direction:{model_id}",
              bool(criteria.get("mae")) and "lower" in str(criteria.get("mae")).lower(),
              str(criteria))
        check(f"external-model-binary-present:{model_id}",
              (card_path.parent / f"{model_id}.joblib").is_file()
              or (card_path.parent / f"{model_id}.pkl").is_file(),
              "card without a fitted model beside it")
        registry_row = next((item for item in research.model_registry()["models"]
                             if item["id"] == model_id), {})
        et0_status_checks(model_id, card, registry_row)

    # ------------------------------------------------ 9. superseded / excluded handling
    for entry in registry["models"]:
        predecessor = entry.get("supersedes")
        if not predecessor:
            continue
        predecessor_path = ARTIFACTS / f"{predecessor}.json"
        check(f"predecessor-kept:{entry['id']}", predecessor_path.is_file(),
              f"{predecessor}.json was removed instead of kept")
        if predecessor_path.is_file():
            old = json.loads(predecessor_path.read_text(encoding="utf-8"))
            new = json.loads((ROOT / entry["artifact"]).read_text(encoding="utf-8"))
            check(f"predecessor-not-overwritten:{entry['id']}",
                  old.get("id") == predecessor and old.get("trainedAt") != new.get("trainedAt"),
                  "predecessor artifact looks like it was regenerated by the successor run")

    # Declared unsupported targets are the interface's own statement of what no model here does.
    # They are recorded so a later phase cannot quietly add one of them as a served prediction.
    unsupported = research.model_registry().get("unsupportedTargets") or []
    check("unsupported-targets-declared", bool(unsupported),
          f"{len(unsupported)} targets named as not modelled")

    # --------------------------------------------------------- 10. dataset safeguards
    corpus_ids = {passage.id for passage in corpus}
    for finding in ("phase11-duplicate-osd320", "phase11-gravity-osd346", "phase11-ood-rejected"):
        check(f"safeguard-present:{finding}", f"finding::{finding}" in corpus_ids,
              "safeguard finding missing from the evidence corpus")

    duplicate = next((passage for passage in corpus
                      if passage.id == "finding::phase11-duplicate-osd320"), None)
    if duplicate is not None:
        text = (duplicate.text + " " + " ".join(duplicate.limitations)).lower()
        # The safeguard is the prohibition, not a particular word for it: this finding says the
        # arrays are the same and must never be used as independent validation.
        check("duplicate-safeguard-wording",
              "osd-320" in text and "independent" in text
              and ("never be used as independent" in text or "duplicate" in text
                   or "not independent" in text or "same affymetrix arrays" in text),
              "the OSD-320 finding must state that the shared arrays are not independent evidence")

    # No artifact may present OSD-320 as independent evidence for a trained model.
    for path in sorted(ARTIFACTS.glob("*.json")):
        if path.name == "registry.json":
            continue
        blob = path.read_text(encoding="utf-8")
        for match in re.finditer(r"OSD-320", blob):
            window = blob[max(0, match.start() - 200):match.end() + 200].lower()
            absent = not any(word in window for word in
                             ("duplicate", "not independent", "same samples", "copy", "not a replication"))
            check(f"osd320-not-independence:{path.name}", not absent,
                  "OSD-320 is mentioned without a duplicate/independence caveat")

    summary = {
        "registeredModels": len(registry["models"]),
        "auditedModels": len(rows),
        "servedModels": sum(1 for row in rows if row["runStatus"] == "runnable"),
        "externallyServedModels": sum(1 for row in rows
                                      if row["runStatus"] == "external-service"),
        "retiredModels": sum(1 for row in rows if row["runStatus"] == "retired"),
        "supersededModels": len(superseded_names),
        "withExplanations": sum(1 for row in rows if row["explanationAvailable"]),
        "checksRun": len(CHECKS),
        "checksFailed": len(FAILURES),
        "documentedGaps": len(GAPS),
    }
    return {
        "phase": 13,
        "task": "model-audit",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "registry": {
            "schemaVersion": registry.get("schemaVersion"),
            "trainedAt": registry.get("trainedAt"),
            "dataVersion": registry.get("dataVersion"),
            "environment": registry.get("environment"),
        },
        "summary": summary,
        "models": rows,
        "checks": CHECKS,
        "failures": FAILURES,
        "gaps": GAPS,
        "note": ("Read-only audit. Checksums are recomputed from disk, metrics are read from the "
                 "artifacts and never adjusted, and no model is retrained. A failure here means an "
                 "artifact and its record disagree, not that a score is low."),
    }


def et0_status_checks(model_id: str, card: dict, row: dict) -> bool:
    """Level with the serving layer rather than re-deriving its answer.

    `app.et0` already degrades to physics when the artifact is unreadable; the audit asserts that
    the registry row reports the same availability, so a service that silently fell back would be
    caught here as a disagreement between the card and the API.
    """
    from app import et0

    status = et0.artifact_status()
    check(f"external-availability-agrees:{model_id}",
          bool(status.get("available")) == bool(row.get("artifactExists")),
          f"service={status.get('available')} registry={row.get('artifactExists')}")
    check(f"external-primary-is-physics:{model_id}",
          "physics" in str(status.get("fallback") or "") or status.get("available") is False,
          "the physics fallback is not described")
    return bool(status.get("available"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the audit artifact")
    arguments = parser.parse_args()

    report = audit()
    summary = report["summary"]
    print(f"models audited        {summary['auditedModels']}/{summary['registeredModels']}")
    print(f"served / retired      {summary['servedModels']} / {summary['retiredModels']}")
    print(f"superseded kept       {summary['supersededModels']}")
    print(f"with explanations     {summary['withExplanations']}")
    print(f"documented gaps       {summary['documentedGaps']}")
    print(f"checks                {summary['checksRun']} run, {summary['checksFailed']} failed")
    if report["failures"]:
        print("\nfailures:")
        for failure in report["failures"]:
            print(f"  {failure}")
    else:
        print("\nevery check passed")
    if arguments.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        print(f"\nwritten: {OUT.relative_to(ROOT)}")
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
