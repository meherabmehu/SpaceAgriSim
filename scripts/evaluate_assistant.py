#!/usr/bin/env python3
"""Run the Phase 13 assistant benchmark and write the metrics artifact.

    python3 scripts/evaluate_assistant.py                 # score the current build
    python3 scripts/evaluate_assistant.py --write         # also write ml/evaluation/phase13_assistant_eval.json
    python3 scripts/evaluate_assistant.py --compare 4a09de3  # score the Phase 12 build too
    python3 scripts/evaluate_assistant.py --explain echo --write  # + narration-layer guards

--compare imports the assistant as it exists at a git revision and scores it on the same
benchmark, so an improvement claim is a measured before-and-after rather than an assertion.
Pass the Phase 12 commit explicitly (4a09de3). `HEAD` stops being the baseline the moment this
branch commits anything, which is exactly how a before-and-after quietly becomes a no-op.
"""
from __future__ import annotations

import argparse
import types
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app import assistant, assistant_eval, llm  # noqa: E402

ARTIFACT = ROOT / "ml" / "evaluation" / "phase13_assistant_eval.json"


def score_current() -> dict:
    return assistant_eval.evaluate(assistant.answer)


def _load_module_from_revision(revision: str, module_path: str, module_name: str):
    """Import one module as it existed at a git revision, without touching the work tree."""
    source = subprocess.run(["git", "show", f"{revision}:backend/{module_path}"],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    module = types.ModuleType(module_name)
    module.__dict__["__file__"] = str(BACKEND / module_path)
    # dataclasses resolves the defining module through sys.modules, so an unregistered module
    # fails with a confusing "'NoneType' has no attribute '__dict__'" during class creation.
    sys.modules[module_name] = module
    exec(compile(source, f"{revision}:backend/{module_path}", "exec"), module.__dict__)
    return module


def score_revision(revision: str) -> dict:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    previous = _load_module_from_revision(revision, "app/assistant.py",
                                          f"assistant_at_{revision.replace('-', '_')}")
    return assistant_eval.evaluate(previous.answer)


def score_narration(provider_name: str) -> dict:
    """Run every benchmark item through the optional narration layer.

    This measures the *guards*, not the model. With `echo` - the deterministic local stub - the
    numbers say whether narration can be attached to these 32 answers without introducing an
    untraceable accession, quantity or uncited sentence. They say nothing about the prose quality
    of a real provider, which is why the artifact records `providerIsStub`.
    """
    config = llm.LLMConfig(provider=provider_name)
    items = assistant_eval.load_benchmark()["items"]
    budget = llm.Budget(config.max_calls)
    accepted, rejected, downgraded = 0, [], {}
    for item in items:
        payload = assistant.answer(item["question"]).render()
        result = llm.explain(payload, item["question"], config=config, budget=budget)
        if result["source"] == "llm":
            accepted += 1
        else:
            reason = result["downgradeReason"] or "unknown"
            downgraded[reason] = downgraded.get(reason, 0) + 1
            if reason == "validation-rejected":
                rejected.append({"id": item["id"], "reasons": result["validation"]["reasons"]})
    total = len(items)
    return {
        "provider": provider_name,
        "providerIsStub": provider_name == "echo",
        "items": total,
        "narratedAndValidated": accepted,
        "fellBackToDeterministic": total - accepted,
        "validationRejections": rejected,
        "downgradeReasons": downgraded,
        "citationIntegrityUnchanged": not rejected,
        "note": ("Narration is attached only when it adds no accession, quantity or sentence "
                 "that the citations do not already contain. A rejection here means the guard "
                 "worked, not that the answer was wrong."),
    }


def _report_row(label: str, report: dict) -> str:
    metrics = report["metrics"]
    return (f"  {label:22s} status {metrics['statusAccuracy']:.3f}  "
            f"citationHit {metrics['citationHitRate']:.3f}  "
            f"unsupported {metrics['unsupportedClaimRate']:.3f}  "
            f"refusal {metrics['refusalCorrectness']:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="write the metrics artifact to ml/evaluation/")
    parser.add_argument("--compare", metavar="REV",
                        help="also score the assistant at this git revision")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("--explain", metavar="PROVIDER",
                        help="also score the optional narration layer with this provider "
                             "(disabled|echo|http); no external model is called by default")
    arguments = parser.parse_args()

    current = score_current()
    print(assistant_eval.format_summary(current))

    payload = {"phase": 13, "task": "assistant-evaluation", "current": current}

    if arguments.compare:
        print()
        print(f"  comparison against {arguments.compare}")
        try:
            baseline = score_revision(arguments.compare)
            payload["baseline"] = {"revision": arguments.compare, "report": baseline}
            print(_report_row("current", current))
            print(_report_row(arguments.compare, baseline))
            delta = (current["metrics"]["statusAccuracy"]
                     - baseline["metrics"]["statusAccuracy"])
            print(f"  {'statusAccuracy delta':22s} {delta:+.3f}")
            payload["delta"] = {
                "statusAccuracy": round(delta, 4),
                "unsupportedClaimRate": round(
                    current["metrics"]["unsupportedClaimRate"]
                    - baseline["metrics"]["unsupportedClaimRate"], 4),
            }
        except Exception as error:  # noqa: BLE001 - a missing revision must not fail the run
            print(f"  could not score {arguments.compare}: {error}")

    if arguments.explain:
        print()
        print(f"  narration layer (provider: {arguments.explain})")
        narration = score_narration(arguments.explain)
        payload["narration"] = narration
        print(f"  {'narrated + validated':22s} {narration['narratedAndValidated']}"
              f"/{narration['items']}")
        print(f"  {'fell back':22s} {narration['fellBackToDeterministic']}"
              f"  reasons: {narration['downgradeReasons'] or 'none'}")
        if narration["validationRejections"]:
            for rejection in narration["validationRejections"]:
                print(f"    rejected {rejection['id']}: {rejection['reasons']}")
        if narration["providerIsStub"]:
            print("  note: 'echo' is a deterministic local stub, not a language model.")
            print("        These figures measure the guards, not prose quality.")

    if arguments.write:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
        print(f"\nwritten: {ARTIFACT.relative_to(ROOT)}")

    if arguments.json:
        print(json.dumps(payload, indent=1, sort_keys=True))

    return 0 if not current["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
