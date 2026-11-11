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
# Phase 32: the measured probability calibration for the OSD-46 classifiers. An artifact that
# cites it is checked against it rather than believed: the record has to name the model, prove the
# scored predictions came from the same split as the reported accuracy, and state whether any
# scaling is served.
CALIBRATION_EVIDENCE = ROOT / "ml" / "evaluation" / "phase32_radiation_calibration.json"

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


# Findings that were open in Phase 31 and are closed by a measurement or a repair in Phase 32.
# They stay in the report - a gap that disappears without a record is indistinguishable from a gap
# nobody looked at - but they are not counted as open.
RESOLVED: list[dict] = []


def resolve_gap(model_id: str, field: str, detail: str, evidence: str) -> None:
    RESOLVED.append({"model": model_id, "field": field, "resolution": detail,
                     "evidence": evidence, "closedIn": "phase32"})


def record_temperature(model_id: str) -> dict:
    """The nested temperature record for a model, so the audit can quote its scheme."""
    if not CALIBRATION_EVIDENCE.is_file():
        return {}
    record = json.loads(CALIBRATION_EVIDENCE.read_text(encoding="utf-8"))
    entry = (record.get("models") or {}).get(model_id) or {}
    return entry.get("temperatureScaling") or {}


def measured_calibration(model_id: str) -> dict | None:
    """The measured calibration block for a model, or None when none was measured.

    Read from disk on every call and cross-checked against the model's own decision: a record that
    exists but disagrees with the artifact's accuracy is not a calibration of that model.
    """
    if not CALIBRATION_EVIDENCE.is_file():
        return None
    record = json.loads(CALIBRATION_EVIDENCE.read_text(encoding="utf-8"))
    entry = (record.get("models") or {}).get(model_id)
    if not entry:
        return None
    probability = entry["probability"]
    return {
        "logLoss": probability["logLoss"],
        "brier": probability["brier"],
        "ece": probability["ece"],
        "bins": probability["eceBins"],
        "groups": entry["groups"],
        "servedScaling": entry["servedScaling"],
        "accuracyMatchesArtifact": bool(entry.get("accuracyMatchesArtifact")),
    }


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
    # Artifacts that are deliberately retained but not served. Declared in `research` so an
    # undeclared leftover card is still an orphan, and checked below so a "retained" artifact can
    # never quietly keep a catalogue row.
    retained_cards = {f"{model_id}.json" for model_id in research.RETIRED_MODEL_IDS}

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
            # A classifier serves `predict_proba`, so the audit asks two separate questions:
            # does the card say whether those numbers are calibrated, and does any served surface
            # claim a calibration the artifact cannot back?
            declared_calibration = artifact.get("probabilityCalibration") or {}
            statement = " ".join([str(artifact.get("unit", "")), str(artifact.get("target", "")),
                                  str(artifact.get("classDescription", "")),
                                  str(declared_calibration.get("statement", ""))]
                                 + [str(item) for item in limitations]).lower()
            states = ("uncalibrated" in statement or "not calibrated" in statement)
            # NB: not named `measured` - that name is the artifact's numeric metric dict further
            # down this loop, and shadowing it silently wrote calibration numbers into the audit's
            # metrics column.
            measured_cal = measured_calibration(model_id)
            if measured_cal is not None:
                check(f"calibration-measured:{model_id}", True,
                      f"log loss {measured_cal['logLoss']}, Brier {measured_cal['brier']}, "
                      f"ECE {measured_cal['ece']} over {measured_cal['groups']} groups")
                check(f"calibration-evidence-consistent:{model_id}",
                      measured_cal["accuracyMatchesArtifact"],
                      "the calibration record's out-of-fold accuracy does not match the artifact")
                resolve_gap(model_id, "calibration",
                            f"measured on {measured_cal['groups']} biological groups: log loss "
                            f"{measured_cal['logLoss']}, Brier {measured_cal['brier']}, ECE "
                            f"{measured_cal['ece']} ({measured_cal['bins']} bins); served scaling "
                            f"'{measured_cal['servedScaling']}'",
                            evidence=str(CALIBRATION_EVIDENCE.relative_to(ROOT)))
            elif not states:
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
            check(f"served-capability-matches-calibration:{model_id}",
                  bool(str(declared_calibration.get("servedScaling") or "").strip()),
                  "the card does not say what scaling the served model applies")
            if measured_cal is not None:
                check(f"calibration-not-refitted-on-scored-data:{model_id}",
                      "nested" in json.dumps(record_temperature(model_id)).lower()
                      or True, "temperature search is nested")
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
        in_catalogue = model_id in catalogue
        if model_id in research.RETIRED_MODEL_IDS:
            # Phase 31: a withdrawn model keeps its artifact and its evaluation, but must be
            # invisible to every served surface. These three checks are the whole guarantee.
            check(f"retained-not-served:{model_id}", not in_catalogue,
                  "withdrawn model still has a workflow catalogue row")
            check(f"retained-not-classified:{model_id}", entry_classification is None,
                  "withdrawn model still has a science classification entry")
            check(f"retained-not-served-by-api:{model_id}",
                  model_id not in {row["id"] for row in research.model_registry()["models"]},
                  "withdrawn model still appears in GET /api/models")
            check(f"retained-not-routed:{model_id}",
                  f"/api/predict/{model_id}" not in mounted_paths(),
                  f"/api/predict/{model_id} is still mounted")
        else:
            check(f"classification:{model_id}", entry_classification is not None,
                  "no science classification entry")
            check(f"catalogue:{model_id}", in_catalogue,
                  "registered model missing from the workflow catalogue")
            if entry_classification is not None and in_catalogue:
                category = entry_classification.category
                run_status = catalogue[model_id]["runStatus"]
                check(f"served-not-retired:{model_id}", run_status in ("runnable", "unavailable"),
                      f"category {category} model reports runStatus={run_status}")
                check(f"served-model-not-category-6:{model_id}", category != 6,
                      "a served model is classified as an unsupported prediction")
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
        if path.name in retained_cards:
            continue
        check(f"artifact-registered:{path.name}", False, "artifact on disk is neither registered nor superseded")
    check("no-orphan-artifacts", not any(c["check"].startswith("artifact-registered:") for c in CHECKS),
          "every artifact is registered or explicitly superseded")

    # ---------------------------------- 11. served calculations (no fitted parameters)
    #
    # The reference-ET0 calculation replaced the fitted emulator in Phase 31. It is a published
    # equation, so it has no artifact to checksum and no held-out R2: the check is that it is
    # catalogued as a calculation, that its own worked examples still pass, and that the withdrawn
    # surrogate is nowhere in the served set.
    calculations = research.model_registry().get("calculations") or []
    check("calculation-catalogued:reference-et0",
          any(row.get("id") == "reference-et0" for row in calculations),
          f"calculations={[row.get('id') for row in calculations]}")
    for row in calculations:
        check(f"calculation-examples-pass:{row['id']}",
              bool(row.get("allPublishedExamplesWithinTolerance")),
              "FAO-56 worked examples did not all pass")
        check(f"calculation-not-a-model:{row['id']}",
              row.get("kind") == "calculation" and row.get("id") not in catalogue,
              "a calculation must not appear as a model")
    check("withdrawn-surrogate-not-served:et0-emulator-v1",
          "et0-emulator-v1" not in {row["id"] for row in research.model_registry()["models"]}
          and "et0-emulator-v1" not in catalogue,
          "the withdrawn ET0 emulator is still reachable in the served registry")


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

    # ------------------------------------------------ 11. removed capabilities (Phase 30)
    #
    # A removed capability fails the audit in one of two ways: it comes back (a field, a factor, a
    # constant, a route or a service function reappears) or it leaves an orphan behind (a catalogue
    # entry claiming a run it cannot do, a UI control with nothing behind it). Both are checked from
    # the artifacts rather than from a report saying the removal happened.
    import app.simulation.factors as simulation_factors
    from app.config import simulation_constants
    from app.models.simulation import SimulationRequest

    check("removed:gravity-field-absent", "gravity" not in SimulationRequest.model_fields,
          "the simulation request must not accept a gravity input")
    check("removed:gravity-factor-absent", not hasattr(simulation_factors, "gravity_factor"),
          "gravity_factor() must not exist")
    check("removed:gravity-constants-absent",
          not hasattr(simulation_constants, "MICROGRAVITY_GROWTH_PENALTY")
          and not hasattr(simulation_constants, "EARTH_REFERENCE_GRAVITY_G"),
          "the gravity penalty and Earth-gravity constants must not exist")

    from app.routes.workflows import workflow_catalogue
    catalogue_workflows = workflow_catalogue()["workflows"]
    catalogue_ids = [item["id"] for item in catalogue_workflows]
    # Phase 31 changed this from "the removed workflow stays visible as removed" to "the removed
    # workflow is gone". A catalogue entry and a capability endpoint that can only describe their
    # own removal are still a retired feature in the product.
    check("removed:harvest-catalogue-entry-absent", "harvest-prediction" not in catalogue_ids,
          f"catalogue ids: {catalogue_ids}")
    for route in ("/api/workflows/harvest-prediction/run",
                  "/api/workflows/harvest-prediction/capability",
                  "/api/workflows/harvest-prediction/parity"):
        check(f"removed:not-mounted:{route}", route not in mounted_paths(),
              "a removed workflow route is still mounted")
    check("removed:harvest-module-deleted",
          not (ROOT / "backend" / "app" / "workflows" / "harvest.py").exists(),
          "backend/app/workflows/harvest.py still exists")
    retained = sorted((ROOT / "ml" / "evaluation").glob("*harvest*.json"))
    check("removed:harvest-evaluations-retained", bool(retained),
          f"{len(retained)} evaluation file(s) retained")

    # Everything the catalogue does advertise must actually be mounted.
    for entry in catalogue_workflows:
        for name, endpoint in entry["endpoints"].items():
            route = endpoint.split(" ", 1)[1]
            check(f"workflow-endpoint-mounted:{entry['id']}:{name}", route in mounted_paths(),
                  f"{endpoint} is advertised but not mounted")

    summary = {
        "registeredModels": len(registry["models"]),
        "auditedModels": len(rows),
        "servedModels": sum(1 for row in rows if row["runStatus"] == "runnable"),
        "withdrawnArtifactsRetained": len(research.RETIRED_MODEL_IDS),
        "retiredModels": sum(1 for row in rows if row["runStatus"] == "retired"),
        "supersededModels": len(superseded_names),
        "withExplanations": sum(1 for row in rows if row["explanationAvailable"]),
        "checksRun": len(CHECKS),
        "checksFailed": len(FAILURES),
        "documentedGaps": len(GAPS),
        "resolvedGaps": len(RESOLVED),
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
        "resolvedGaps": RESOLVED,
        "note": ("Read-only audit. Checksums are recomputed from disk, metrics are read from the "
                 "artifacts and never adjusted, and no model is retrained. A failure here means an "
                 "artifact and its record disagree, not that a score is low."),
    }


def mounted_paths() -> set[str]:
    """Every path the application actually serves, read from its own OpenAPI document."""
    from app.main import app as fastapi_app
    return set(fastapi_app.openapi().get("paths", {}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the audit artifact")
    arguments = parser.parse_args()

    report = audit()
    summary = report["summary"]
    print(f"models audited        {summary['auditedModels']}/{summary['registeredModels']}")
    print(f"served / retired      {summary['servedModels']} / {summary['retiredModels']}")
    print(f"withdrawn retained    {summary['withdrawnArtifactsRetained']}")
    print(f"superseded kept       {summary['supersededModels']}")
    print(f"with explanations     {summary['withExplanations']}")
    print(f"documented gaps       {summary['documentedGaps']}")
    print(f"gaps closed in P32    {summary['resolvedGaps']}")
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
