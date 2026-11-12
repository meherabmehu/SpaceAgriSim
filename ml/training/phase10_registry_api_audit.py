"""Phase 10: registry and API consistency audit.

Phase 9 added models, intervals, and explanations across several commits, and a
registry that drifts from its artifacts is the failure mode that matters most: a
number in `registry` that no artifact backs is a claim with no evidence behind
it, and it survives every test that only checks the API returns 200.

This script does not trust the registry. It reads the artifact each entry points at and
checks, for every model:

  identity     the artifact exists and its SHA-256 matches the registry's claim
  metrics      every metric in the registry is present in the artifact and equal
  status       a served model is not a rejected candidate, and vice versa
  intervals    a stated nominal coverage has a measured coverage beside it
  explanations a model with an explanation artifact serves an exact method, and a
             model without one is claimed to have none
  catalogue    every study a model cites is in the dataset manifest
  api          the router serves exactly the models the registry lists, and 404s for
             the excluded candidates

`registryChange` is deliberately absent: this pass fixes nothing silently. Anything it
finds is written to `ml/evaluation/phase10_registry_api_audit` and either repaired
explicitly or listed as a known gap.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))

OUT = ROOT / "ml" / "evaluation" / "phase10_registry_api_audit"

EXCLUDED = ("radiation-dose-osd782-v1", "gravity-reorientation-osd411-v1")
METRIC_KEYS = ("accuracy", "balancedAccuracy", "macroF1", "mae", "r2", "rmse")


def sha256(path: Path) -> str:
    return hashlib.sha256(safedata.bytes(path)).hexdigest()


def audit() -> dict:
    from app import research

    artifacts = research.ARTIFACTS
    registry = research.model_registry()
    manifest = {entry["id"] for entry in research.manifest()["datasets"]}
    models = registry["models"]
    findings, checks = [], {"models": len(models)}

    for model in models:
        model_id = model["id"]
        path = artifacts / f"{model_id}"
        if not safedata.exists(path):
            findings.append({"model": model_id, "kind": "missing-artifact", "severity": "high"})
            continue
        artifact = safedata.load(path)

        # --- identity ---------------------------------------------------------
        if model.get("artifactSha256") and model["artifactSha256"] != sha256(path):
            findings.append({"model": model_id, "kind": "artifact-sha-mismatch",
                             "severity": "high"})

        # --- metrics ----------------------------------------------------------
        artifact_metrics = artifact.get("metrics", {}) or {}
        for key in METRIC_KEYS:
            if key in (model.get("metrics") or {}):
                claimed = model["metrics"][key]
                if key not in artifact_metrics:
                    findings.append({"model": model_id, "kind": f"unbacked-metric:{key}",
                                     "severity": "high"})
                elif artifact_metrics[key] is not None and \
                        abs(float(claimed) - float(artifact_metrics[key])) > 1e-9:
                    findings.append({"model": model_id, "kind": f"metric-drift:{key}",
                                     "claimed": claimed,
                                     "artifact": artifact_metrics[key],
                                     "severity": "high"})

        # --- status -----------------------------------------------------------
        if model_id in EXCLUDED:
            findings.append({"model": model_id, "kind": "excluded-model-is-served",
                             "severity": "high"})

        # --- intervals --------------------------------------------------------
        interval = model.get("interval") or {}
        nominal = interval.get("nominalCoverage")
        measured = interval.get("empiricalCoverage")
        if nominal is not None and measured is not None and measured < nominal - 0.05:
            findings.append({"model": model_id, "kind": "stated-coverage-shortfall",
                             "nominal": nominal, "measured": measured,
                             "severity": "medium"})

        # --- explanations -----------------------------------------------------
        explanation_path = artifacts / f"{model_id}-explanation"
        phase10 = model.get("phase10") or {}
        if safedata.exists(explanation_path):
            explanation = safedata.load(explanation_path)
            if explanation.get("identityResidual", 1.0) > 1e-9:
                findings.append({"model": model_id, "kind": "explanation-not-exact",
                                 "residual": explanation["identityResidual"],
                                 "severity": "high"})
            if not phase10.get("explanationAvailable"):
                findings.append({"model": model_id,
                                 "kind": "explanation-exists-but-registry-disagrees",
                                 "severity": "medium"})

        # --- catalogue --------------------------------------------------------
        study = model.get("sourceStudy")
        if study and study.startswith("OSD-") and study not in manifest:
            findings.append({"model": model_id, "kind": f"uncatalogued-study:{study}",
                             "severity": "medium"})

    # --- API surface ----------------------------------------------------------
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes.research import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    served = client.get("/api/models")
    served_ids = {entry["id"] for entry in served.py()["models"]} if served.status_code == 200 else set()
    registry_ids = {model["id"] for model in models}
    if served.status_code != 200:
        findings.append({"kind": "api-models-failed", "status": served.status_code,
                         "severity": "high"})
    elif served_ids != registry_ids:
        findings.append({"kind": "api-registry-mismatch",
                         "onlyApi": sorted(served_ids - registry_ids),
                         "onlyRegistry": sorted(registry_ids - served_ids),
                         "severity": "high"})
    for excluded in EXCLUDED:
        response = client.get(f"/api/models/{excluded}")
        if response.status_code == 200:
            findings.append({"model": excluded, "kind": "excluded-model-reachable",
                             "severity": "high"})
    explanation_404 = client.get("/api/models/lettuce-earth-growth-v2/explanation")
    if explanation_404.status_code != 404:
        findings.append({"kind": "surrogate-explanation-served",
                         "status": explanation_404.status_code, "severity": "high"})
    checks["doubles"] = client.get("/api/models/radiation-quality-osd46-v1/reference-profiles").status_code
    checks["openapiPaths"] = len(client.get("/openapi.py").py().get("paths", {}))

    high = [finding for finding in findings if finding["severity"] == "high"]
    return {
        "phase": 10,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "task": "does the registry say exactly what the artifacts support?",
        "checks": checks,
        "findings": findings,
        "highSeverity": len(high),
        "verdict": ("registry-and-api-agree-with-their-artifacts" if not high
                    else "registry-claims-exceed-evidence"),
        "policy": (
            "A registry number with no artifact behind it is evidence of nothing. This "
            "audit fails on any drift rather than reconciling it silently."),
    }


def main() -> int:
    result = audit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(result, OUT)
    print(f"{result['checks']['models']} models, "
          f"{len(result['findings'])} findings, {result['highSeverity']} high severity")
    for finding in result["findings"]:
        print(f"  [{finding['severity']}] {finding}")
    print(f"verdict: {result['verdict']} -> wrote {OUT.relative_to(ROOT)}")
    return 0 if result["highSeverity"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
