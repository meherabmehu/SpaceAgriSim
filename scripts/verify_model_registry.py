#!/usr/bin/env python3
"""Verify the model registry, artifact checksums and training environment.

Part E requires integration through a registry with checksums. This script makes
the registry self-checking so a corrupted, hand-edited or stale artifact cannot
serve silently:

  * every registered artifact exists and matches its recorded SHA-256;
  * every artifact on disk is either registered or explicitly marked superseded;
  * the loading path the API actually uses accepts each artifact;
  * the recorded training environment matches ml/requirements-training.txt;
  * no artifact claims a stronger evidence status than its own metrics support.

Exit code is non-zero on any failure.

Run: python scripts/verify_model_registry.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ARTIFACTS = ROOT / "ml" / "artifacts"
REGISTRY = ARTIFACTS / "registry.json"
PINS = ROOT / "ml" / "requirements-training.txt"
OUT = ROOT / "docs" / "phase7" / "registry_verification.json"

FAILURES: list[str] = []
CHECKS: list[dict] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    if not passed:
        FAILURES.append(f"{name}: {detail}")


def pinned_versions() -> dict[str, str]:
    pins = {}
    for line in PINS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip()] = version.strip()
    return pins


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    models = registry["models"]

    # 1. Every registered artifact exists and matches its checksum.
    digests = {}
    for item in models:
        path = ROOT / item["artifact"]
        if not path.is_file():
            check(f"artifact exists: {item['id']}", False, str(path))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests[item["id"]] = digest
        check(f"checksum matches: {item['id']}", digest == item["sha256"],
              f"{digest[:12]} vs recorded {item['sha256'][:12]}")

    # 2. No orphan artifacts: everything on disk is accounted for.
    #
    # Explanation files live beside their models (ml/artifacts/<id>-explanation.json)
    # rather than inside them, so a model checksum keeps meaning "the trained model".
    # They are not models and must be excluded here, or every explained model looks
    # like an orphan.
    registered_ids = {item["id"] for item in models}
    on_disk = {p.stem for p in ARTIFACTS.glob("*.json")} - {"registry", "tomato_example"}
    on_disk = {stem for stem in on_disk if not stem.endswith("-explanation")}
    # Phase 31: three artifacts are retained as documented negative results but are not served.
    # They leave the orphan set only because `research.RETIRED_MODEL_IDS` declares them, and that
    # declaration is checked here so a "retained" artifact can never keep a served route.
    from app import research

    on_disk -= set(research.RETIRED_MODEL_IDS)
    for model_id in sorted(research.RETIRED_MODEL_IDS):
        check(f"withdrawn model is not served: {model_id}",
              model_id not in research.MODEL_IDS,
              "a withdrawn artifact is still in the served model set")
    orphans = sorted(on_disk - registered_ids)
    check("no unregistered model artifacts", not orphans, f"orphans={orphans}")

    # 3. Supersession is explicit in both directions where it applies.
    superseded = {item["id"]: item["supersedes"] for item in models if item.get("supersedes")}
    for old_id, note in superseded.items():
        target = note.split(" ")[0]
        check(f"superseded model still registered: {target}", target in registered_ids,
              f"{old_id} supersedes {target}")
        successor = next((i["id"] for i in models if i.get("supersedes", "").startswith(target)), None)
        check(f"supersession is one-directional: {target}",
              successor == old_id,
              f"registered successor of {target} is {successor}")

    # 4. The API loading path accepts every *served* artifact.
    #
    # Withdrawn artifacts are deliberately unreachable through `load_model`: a retained artifact
    # that the API could still load is one refactor away from being served again.
    for model_id in sorted(registered_ids - set(research.RETIRED_MODEL_IDS)):
        try:
            model = research.load_model(model_id)
            check(f"api can load: {model_id}", True, model.get("evidenceStatus", "?"))
        except Exception as exc:  # noqa: BLE001 - any load failure is the finding
            check(f"api can load: {model_id}", False, f"{type(exc).__name__}: {exc}")

    # 5. Recorded environment matches the pins.
    pins = pinned_versions()
    recorded = registry.get("environment", {})
    for library, pin in pins.items():
        if library == "python":
            continue
        if library not in recorded:
            continue
        check(f"pinned version recorded: {library}", recorded[library] == pin,
              f"registry={recorded[library]} pins={pin}")
    check("training pins file lists the core stack",
          {"numpy", "pandas", "scikit-learn"} <= set(pins), f"pins={sorted(pins)}")

    # 6. No artifact claims more than its own evidence supports.
    for item in models:
        path = ARTIFACTS / f"{item['id']}.json"
        if not path.is_file():
            continue
        card = json.loads(path.read_text())
        status = card.get("evidenceStatus")
        basis = card.get("evidenceBasis") or {}
        if status == "validated" or status == "validated-exploratory":
            met = [k for k, v in basis.items() if isinstance(v, bool)]
            check(f"promotion basis complete: {item['id']}", met and all(
                basis[k] for k in met), json.dumps(basis)[:160])
        metric_values = {k: v for k, v in (card.get("metrics") or {}).items()
                         if isinstance(v, (int, float))}
        check(f"artifact reports metrics: {item['id']}", bool(metric_values),
              f"{len(metric_values)} numeric metrics" if metric_values else "none")
        limitations = card.get("limitations") or []
        check(f"artifact reports limitations: {item['id']}", bool(limitations),
              f"{len(limitations)} statements" if limitations else "none listed")
        # A model with a negative held-out R2 must not be labelled validated.
        transfer = card.get("transfer") or card.get("leaveOneExperimentOut") or {}
        negatives = [campaign for campaign, block in transfer.items()
                     if isinstance(block, dict) and block.get("R2", 0) < 0]
        if status and status.startswith("validated"):
            check(f"validated model has no negative held-out result: {item['id']}",
                  not negatives, f"negative in {negatives}")

    # 7. Independent-validation claims are consistent between registry and artifact.
    #
    # Phase 19 gave models an explicit `independentValidation` block: a study, a metric, a value, a
    # criterion fixed before the measurement, and whether it passed. Two things can go wrong and
    # both are silent: the block can drift from the artifact it describes, or a failed evaluation
    # can quietly become a pass. Both are checked against the artifact rather than against
    # themselves.
    for item in models:
        declared = item.get("independentValidation")
        if not declared:
            continue
        path = ARTIFACTS / f"{item['id']}.json"
        if not path.is_file():
            check(f"independent validation has an artifact: {item['id']}", False, str(path))
            continue
        card = json.loads(path.read_text())
        recorded = ((card.get("validation") or {}).get("independent") or {})
        if not recorded:
            check(f"independent validation is recorded in the artifact: {item['id']}", False,
                  "registry claims a holdout the artifact does not report")
            continue
        artifact_mape = (recorded.get("metrics") or {}).get(declared.get("metric", "MAPE"))
        check(f"independent metric matches artifact: {item['id']}",
              artifact_mape is not None and abs(float(artifact_mape) - float(declared["value"])) < 0.05,
              f"registry={declared['value']} artifact={artifact_mape}")
        check(f"independent pass flag matches artifact: {item['id']}",
              bool(recorded.get("passed")) is bool(declared["passed"]),
              f"registry={declared['passed']} artifact={recorded.get('passed')}")
        # The criterion is a pre-declared threshold, so a pass must actually clear it.
        check(f"independent pass is consistent with its own criterion: {item['id']}",
              bool(declared["passed"]) == (float(declared["value"]) <= float(declared["criterionPct"])),
              f"value={declared['value']} criterion={declared['criterionPct']} passed={declared['passed']}")
        # A failed independent check forbids any validated-style status, in the artifact or the registry.
        if not declared["passed"]:
            for label, status in (("artifact", card.get("status") or card.get("evidenceStatus")),
                                  ("registry", item.get("status"))):
                check(f"failed independent check forbids a validated status ({label}): {item['id']}",
                      not str(status or "").startswith(("validated", "calibrated", "externally")),
                      f"status={status}")
            check(f"artifact records the failure verdict: {item['id']}",
                  bool(recorded.get("verdict")),
                  str(recorded.get("verdict") or "no verdict text recorded")[:100])

    # 8. Served calculations are published physics, not fitted models.
    #
    # Phase 31 replaced the fitted ET0 emulator with the FAO-56 equation it approximated, so
    # there is no extra artifact left to load here. What must hold is that the equation is
    # served, that its own published worked examples still pass, and that the withdrawn
    # artifacts are reachable through neither the registry nor the model catalogue.
    from app import workflow

    catalogue_rows = {row["modelId"] for row in workflow.model_catalogue()["models"]}
    for model_id in sorted(research.RETIRED_MODEL_IDS):
        check(f"withdrawn model is not in the served catalogue: {model_id}",
              model_id not in catalogue_rows, "withdrawn model still has a catalogue row")
        check(f"withdrawn model is not in GET /api/models: {model_id}",
              model_id not in {row["id"] for row in research.model_registry()["models"]},
              "withdrawn model still appears in the served registry")
    calculations = research.model_registry().get("calculations") or []
    check("reference ET0 is catalogued as a calculation",
          any(row.get("id") == "reference-et0" for row in calculations),
          str([row.get("id") for row in calculations]))
    for row in calculations:
        check(f"published examples pass: {row['id']}",
              bool(row.get("allPublishedExamplesWithinTolerance")),
              "FAO-56 worked examples did not all pass")
        check(f"no measured-ET0 claim: {row['id']}",
              (row.get("measuredEt0Validation") or {}).get("available") is False,
              "a measured ET0 benchmark is claimed but none is bundled")

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "phase": 7,
        "registrySchemaVersion": registry.get("schemaVersion"),
        "modelCount": len(models),
        "modelIds": sorted(registered_ids),
        "artifactDigests": digests,
        "environment": recorded,
        "pinnedEnvironment": pins,
        "checks": CHECKS,
        "passed": not FAILURES,
        "failures": FAILURES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")

    for entry in CHECKS:
        print(f"  [{'PASS' if entry['passed'] else 'FAIL'}] {entry['check']}"
              f"{(': ' + entry['detail']) if entry['detail'] else ''}")
    print(f"\n{len(CHECKS) - len(FAILURES)}/{len(CHECKS)} checks passed")
    print(f"written: {OUT.relative_to(ROOT)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
